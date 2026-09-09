#!/usr/bin/env python3
"""
Frontier Bridge Server (Node 2: bigserv - LXC 120)
Multi-Tier Resilient Architecture:
1. Primary Provider: Local Antigravity CLI (agy) using Prepaid Account ($0 token cost).
   - If unauthenticated or delayed (e.g. mobile session), instantly bypassed with zero latency.
2. Backup Provider A: OpenRouter API (google/gemini-2.5-flash, claude-3.5-sonnet, deepseek-r1, etc.).
3. Backup Provider B: Direct Google Gemini API (gemini-2.5-flash / gemini-3.8-flash).
4. Backup Provider C: OpenAI API (gpt-4o / o3-mini).
5. Backup Provider D: Local 14B Coordinator (pve VM 102 :8001).

Exposes:
  - GET  /health              -> Live health, provider matrix, and active routing path
  - POST /api/frontier/audit  -> Structured Tier-1 Frontier audit of thinking cycle dossiers
  - POST /api/frontier/chat   -> General frontier reasoning / completion
"""

import os
import sys
import json
import time
import uuid
import logging
import subprocess
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

try:
    from gemini_web_client import GeminiWebClient
except ImportError:
    GeminiWebClient = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [FrontierBridge] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("FrontierBridge")

CONFIG_FILE = os.environ.get("FRONTIER_CONFIG", "/opt/frontier-bridge/config.json")
STONESAGE_CONFIG_FILE = "/opt/stonesage/backend/config.json"

DEFAULT_CONFIG = {
    "host": "0.0.0.0",
    "port": 8085,
    "delay_agy_auth": False,
    "agy_path": "/usr/local/bin/agy",
    "agy_timeout_sec": 25,
    "agy_model": "gemini-3.8-flash",
    "agy_effort": "high",
    "gemini_web_url": "http://127.0.0.1:8087",
    "gemini_web_psid": "",
    "gemini_web_psidts": "",
    "openrouter_api_key": "",
    "openrouter_model": "google/gemini-2.5-flash",
    "gemini_api_key": "",
    "fallback_model": "gemini-2.5-flash",
    "openai_api_key": "",
    "openai_model": "gpt-4o-mini",
    "local_coordinator_url": "http://192.168.1.105:8001/v1/chat/completions"
}

# Cache for agy auth status (check once per 60 seconds)
_agy_auth_cache = {"status": None, "checked_at": 0}

def load_config():
    cfg = DEFAULT_CONFIG.copy()
    
    # 1. Read /opt/frontier-bridge/config.json
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as e:
            logger.warning(f"Error reading {CONFIG_FILE}: {e}")
            
    # 2. Check StoneSage backend config for keys if not already set
    if os.path.exists(STONESAGE_CONFIG_FILE):
        try:
            with open(STONESAGE_CONFIG_FILE, "r", encoding="utf-8") as f:
                ss_cfg = json.load(f)
                ext = ss_cfg.get("external_providers", {})
                if not cfg.get("openrouter_api_key") and ext.get("openrouter", {}).get("api_key"):
                    cfg["openrouter_api_key"] = ext["openrouter"]["api_key"].strip()
                if not cfg.get("gemini_api_key") and ext.get("gemini", {}).get("api_key"):
                    cfg["gemini_api_key"] = ext["gemini"]["api_key"].strip()
                if not cfg.get("openai_api_key") and ext.get("openai", {}).get("api_key"):
                    cfg["openai_api_key"] = ext["openai"]["api_key"].strip()
                # Load Gemini Web AI Plus session
                gw = ss_cfg.get("gemini_web", {})
                if gw.get("psid"):
                    cfg["gemini_web_psid"] = gw["psid"].strip()
                if gw.get("psidts"):
                    cfg["gemini_web_psidts"] = gw["psidts"].strip()
                if gw.get("endpoint"):
                    cfg["gemini_web_url"] = gw["endpoint"].strip()
        except Exception as e:
            logger.warning(f"Error reading {STONESAGE_CONFIG_FILE}: {e}")
            
    # Check for dedicated gemini_session.json
    sess_file = os.path.join(os.path.dirname(CONFIG_FILE), "gemini_session.json")
    if os.path.exists(sess_file):
        try:
            with open(sess_file, "r", encoding="utf-8") as f:
                s_data = json.load(f)
                if s_data.get("psid"):
                    cfg["gemini_web_psid"] = s_data["psid"].strip()
                if s_data.get("psidts"):
                    cfg["gemini_web_psidts"] = s_data["psidts"].strip()
        except Exception as e:
            logger.warning(f"Error reading {sess_file}: {e}")

    # 3. Check Environment Variables
    if not cfg.get("openrouter_api_key") and os.environ.get("OPENROUTER_API_KEY"):
        cfg["openrouter_api_key"] = os.environ["OPENROUTER_API_KEY"].strip()
    if not cfg.get("gemini_api_key") and os.environ.get("GEMINI_API_KEY"):
        cfg["gemini_api_key"] = os.environ["GEMINI_API_KEY"].strip()
    if not cfg.get("openai_api_key") and os.environ.get("OPENAI_API_KEY"):
        cfg["openai_api_key"] = os.environ["OPENAI_API_KEY"].strip()
    if os.environ.get("GEMINI_WEB_PSID"):
        cfg["gemini_web_psid"] = os.environ["GEMINI_WEB_PSID"].strip()
    if os.environ.get("GEMINI_WEB_PSIDTS"):
        cfg["gemini_web_psidts"] = os.environ["GEMINI_WEB_PSIDTS"].strip()

    return cfg

def check_agy_authenticated(agy_path, force=False):
    """Probes if agy has valid credentials (cached 60s to avoid latency)."""
    now = time.time()
    if not force and _agy_auth_cache["status"] is not None and (now - _agy_auth_cache["checked_at"] < 60):
        return _agy_auth_cache["status"]
        
    if not os.path.exists(agy_path):
        _agy_auth_cache["status"] = False
        _agy_auth_cache["checked_at"] = now
        return False
        
    try:
        res = subprocess.run(
            [agy_path, "models"],
            capture_output=True,
            text=True,
            timeout=3
        )
        is_auth = (res.returncode == 0 and "Please sign in" not in res.stderr and "Error" not in res.stderr and "sign in" not in res.stdout)
        _agy_auth_cache["status"] = is_auth
        _agy_auth_cache["checked_at"] = now
        return is_auth
    except Exception:
        _agy_auth_cache["status"] = False
        _agy_auth_cache["checked_at"] = now
        return False

def call_agy_audit(challenge_data: dict, cfg: dict) -> dict:
    """Executes a structured Tier-1 audit via Antigravity CLI (prepaid account)."""
    t0 = time.time()
    prompt = f"""You are the Tier-1 Frontier Companion and Meta-Verifier for an autonomous dual-GPU AI homelab cluster.
Audit this empirical reasoning challenge between a 3B Worker and a 14B Coordinator.

### Challenge: {challenge_data.get('title', 'Unknown')}
Target Invariant: {challenge_data.get('target_invariant', '')}
Original Prompt:
{challenge_data.get('prompt', '')}

--- 3B WORKER OUTPUT ---
{challenge_data.get('worker_output', '')}

--- 14B COORDINATOR OUTPUT ---
{challenge_data.get('coordinator_output', '')}

--- 14B COORDINATOR FIRST-PASS EVALUATION ---
{json.dumps(challenge_data.get('eval', {}), indent=2)}

TASK:
1. Objectively evaluate mathematical, concurrency, or architectural correctness of both models.
2. Check for syntactic leniency bias where the 14B coordinator may have rated buggy code favorably due to formatting.
3. Determine if the target invariant held or failed.
4. Output STRICT JSON only with these keys:
{{
  "verdict": "CONFIRM_LIMIT_VALIDATED" | "REVISE_LIMIT_IDENTIFIED" | "INCONCLUSIVE",
  "frontier_notes": "Detailed critical assessment highlighting truth and subtle failure modes.",
  "refined_limits": "Concise permanent architectural invariant for the master synthesis."
}}"""

    agy_path = cfg.get("agy_path", "/usr/local/bin/agy")
    timeout = int(cfg.get("agy_timeout_sec", 25))
    model = cfg.get("agy_model", "gemini-3.8-flash")
    effort = cfg.get("agy_effort", "high")

    cmd = [
        agy_path,
        "-p", prompt,
        "--model", model,
        "--effort", effort,
        "--output-format", "json",
        "--disable-slash-commands"
    ]

    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout
    )

    elapsed_ms = round((time.time() - t0) * 1000, 1)

    if res.returncode != 0:
        err_msg = res.stderr.strip() or f"agy exited with code {res.returncode}"
        raise RuntimeError(f"agy execution error: {err_msg}")

    stdout = res.stdout.strip()
    raw = stdout
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    parsed = json.loads(raw)
    return {
        "ok": True,
        "provider": "agy_prepaid",
        "verdict": parsed.get("verdict", "CONFIRM_LIMIT_VALIDATED").upper(),
        "frontier_notes": parsed.get("frontier_notes", ""),
        "refined_limits": parsed.get("refined_limits", ""),
        "latency_ms": elapsed_ms,
        "model": model
    }

def call_gemini_web_audit(challenge_data: dict, cfg: dict) -> dict:
    """Zero-token-cost Tier-1 audit via Gemini Web (Google One AI Plus session)."""
    t0 = time.time()
    # 1. Try dedicated microservice on port 8087 if available
    web_url = cfg.get("gemini_web_url", "http://127.0.0.1:8087")
    audit_endpoint = f"{web_url.rstrip('/')}/api/audit"
    try:
        req_data = json.dumps(challenge_data).encode("utf-8")
        req = urllib.request.Request(audit_endpoint, data=req_data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=40.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return data
    except Exception as ex:
        logger.debug(f"Gemini web service on {audit_endpoint} unavailable: {ex}")

    # 2. Direct client fallback using cookies in config
    if GeminiWebClient and (cfg.get("gemini_web_psid") or cfg.get("gemini_web_psidts")):
        client = GeminiWebClient(
            psid=cfg.get("gemini_web_psid", ""),
            psidts=cfg.get("gemini_web_psidts", "")
        )
        res = client.audit_challenge(challenge_data, timeout=40.0)
        if res.get("ok"):
            return res
        raise RuntimeError(res.get("error", "Direct Gemini Web audit failed."))

    raise ValueError("Gemini Web session cookies (__Secure-1PSID) not configured.")

def call_openrouter_audit(challenge_data: dict, cfg: dict) -> dict:
    """OpenRouter API fallback provider."""
    t0 = time.time()
    api_key = cfg.get("openrouter_api_key", "").strip()
    if not api_key:
        raise ValueError("OpenRouter API key is empty.")

    model = cfg.get("openrouter_model", "google/gemini-2.5-flash")
    url = "https://openrouter.ai/api/v1/chat/completions"

    system_instruction = (
        "You are the Tier-1 Frontier Meta-Verifier for an autonomous AI cluster. "
        "Audit model outputs objectively, eliminate syntactic leniency bias, and evaluate strict correctness. "
        "Output STRICT JSON only containing keys: 'verdict', 'frontier_notes', 'refined_limits'. "
        "Valid verdicts: CONFIRM_LIMIT_VALIDATED, REVISE_LIMIT_IDENTIFIED, INCONCLUSIVE."
    )

    user_content = f"""Challenge: {challenge_data.get('title', '')}
Target Invariant: {challenge_data.get('target_invariant', '')}
Original Prompt: {challenge_data.get('prompt', '')}

3B Worker Output:
{challenge_data.get('worker_output', '')}

14B Coordinator Output:
{challenge_data.get('coordinator_output', '')}

14B Evaluation:
{json.dumps(challenge_data.get('eval', {}), indent=2)}"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2
    }

    req_data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "http://192.168.1.167:8080",
        "X-Title": "StoneSage Homelab Frontier Bridge"
    }
    req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

    with urllib.request.urlopen(req, timeout=15.0) as resp:
        resp_data = json.loads(resp.read().decode("utf-8"))

    elapsed_ms = round((time.time() - t0) * 1000, 1)
    raw_content = resp_data["choices"][0]["message"]["content"].strip()
    
    if "```json" in raw_content:
        raw_content = raw_content.split("```json")[1].split("```")[0].strip()
    elif "```" in raw_content:
        raw_content = raw_content.split("```")[1].split("```")[0].strip()
        
    parsed = json.loads(raw_content)

    return {
        "ok": True,
        "provider": f"openrouter ({model})",
        "verdict": parsed.get("verdict", "CONFIRM_LIMIT_VALIDATED").upper(),
        "frontier_notes": parsed.get("frontier_notes", ""),
        "refined_limits": parsed.get("refined_limits", ""),
        "latency_ms": elapsed_ms,
        "model": model
    }

def call_gemini_api_audit(challenge_data: dict, cfg: dict) -> dict:
    """Direct Google Gemini REST API fallback."""
    t0 = time.time()
    api_key = cfg.get("gemini_api_key", "").strip()
    if not api_key:
        raise ValueError("Gemini API key is empty.")

    model = cfg.get("fallback_model", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    system_instruction = (
        "You are the Tier-1 Frontier Meta-Verifier. Audit cluster model outputs objectively. "
        "Eliminate leniency bias and verify strict logical/mathematical invariants. "
        "Respond with STRICT JSON containing 'verdict', 'frontier_notes', and 'refined_limits'."
    )

    user_content = f"""Challenge: {challenge_data.get('title', '')}
Target Invariant: {challenge_data.get('target_invariant', '')}
Original Prompt: {challenge_data.get('prompt', '')}

3B Worker Output:
{challenge_data.get('worker_output', '')}

14B Coordinator Output:
{challenge_data.get('coordinator_output', '')}

14B Evaluation:
{json.dumps(challenge_data.get('eval', {}), indent=2)}"""

    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"parts": [{"text": user_content}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2
        }
    }

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=req_data, headers={"Content-Type": "application/json"}, method="POST")

    with urllib.request.urlopen(req, timeout=12.0) as resp:
        resp_data = json.loads(resp.read().decode("utf-8"))

    elapsed_ms = round((time.time() - t0) * 1000, 1)
    text = resp_data["candidates"][0]["content"]["parts"][0]["text"].strip()
    parsed = json.loads(text)

    return {
        "ok": True,
        "provider": f"gemini_api ({model})",
        "verdict": parsed.get("verdict", "CONFIRM_LIMIT_VALIDATED").upper(),
        "frontier_notes": parsed.get("frontier_notes", ""),
        "refined_limits": parsed.get("refined_limits", ""),
        "latency_ms": elapsed_ms,
        "model": model
    }

def call_local_coordinator_fallback(challenge_data: dict, cfg: dict) -> dict:
    """Local 14B Coordinator emergency fallback when all external APIs are unconfigured."""
    t0 = time.time()
    url = cfg.get("local_coordinator_url", "http://192.168.1.105:8001/v1/chat/completions")
    
    prompt = f"""You are acting as the Meta-Verifier fallback for this cluster challenge.
Challenge: {challenge_data.get('title', '')}
Invariant: {challenge_data.get('target_invariant', '')}
3B Output: {challenge_data.get('worker_output', '')}
14B Output: {challenge_data.get('coordinator_output', '')}

Provide an objective arbitration. Respond ONLY with JSON:
{{
  "verdict": "CONFIRM_LIMIT_VALIDATED" or "REVISE_LIMIT_IDENTIFIED" or "INCONCLUSIVE",
  "frontier_notes": "Objective analysis of observed limitations.",
  "refined_limits": "Refined invariant rule."
}}"""

    payload = {
        "model": "coordinator",
        "messages": [
            {"role": "system", "content": "You are the local arbitration engine. Output strict JSON only."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 800
    }
    
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=req_data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=25.0) as resp:
        resp_data = json.loads(resp.read().decode("utf-8"))
        
    elapsed_ms = round((time.time() - t0) * 1000, 1)
    raw = resp_data["choices"][0]["message"]["content"].strip()
    if "```json" in raw: raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw: raw = raw.split("```")[1].split("```")[0].strip()
    parsed = json.loads(raw)
    
    return {
        "ok": True,
        "provider": "local_14b_fallback",
        "verdict": parsed.get("verdict", "INCONCLUSIVE").upper(),
        "frontier_notes": parsed.get("frontier_notes", ""),
        "refined_limits": parsed.get("refined_limits", ""),
        "latency_ms": elapsed_ms,
        "model": "Qwen2.5-Coder-14B-abliterated"
    }

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class FrontierBridgeHandler(BaseHTTPRequestHandler):
    def send_json(self, data: dict, code: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        cfg = load_config()
        if self.path in ("/health", "/api/frontier/status"):
            is_auth = check_agy_authenticated(cfg.get("agy_path", "/usr/local/bin/agy"))
            delay_auth = cfg.get("delay_agy_auth", False) or not is_auth
            
            # Determine active provider
            active_provider = "local_14b_fallback"
            if is_auth and not cfg.get("delay_agy_auth", False):
                active_provider = "agy_prepaid"
            elif cfg.get("gemini_web_psid"):
                active_provider = "gemini_web_advanced (AI Plus $0 token cost)"
            elif cfg.get("openrouter_api_key"):
                active_provider = f"openrouter ({cfg.get('openrouter_model')})"
            elif cfg.get("gemini_api_key"):
                active_provider = f"gemini_api ({cfg.get('fallback_model')})"
            elif cfg.get("openai_api_key"):
                active_provider = f"openai ({cfg.get('openai_model')})"

            self.send_json({
                "status": "online",
                "service": "frontier-bridge",
                "host": "stonesage",
                "node": "bigserv (192.168.1.167:8085)",
                "active_provider": active_provider,
                "agy": {
                    "installed": os.path.exists(cfg.get("agy_path", "/usr/local/bin/agy")),
                    "authenticated": is_auth,
                    "auth_delayed": delay_auth,
                    "model": cfg.get("agy_model", "gemini-3.8-flash")
                },
                "gemini_web": {
                    "configured": bool(cfg.get("gemini_web_psid")),
                    "endpoint": cfg.get("gemini_web_url", "http://127.0.0.1:8086"),
                    "tier": "Google One AI Plus / Gemini Advanced ($0 token cost)"
                },
                "backups": {
                    "gemini_web_configured": bool(cfg.get("gemini_web_psid")),
                    "openrouter_configured": bool(cfg.get("openrouter_api_key")),
                    "openrouter_model": cfg.get("openrouter_model", "google/gemini-2.5-flash"),
                    "gemini_api_configured": bool(cfg.get("gemini_api_key")),
                    "gemini_model": cfg.get("fallback_model", "gemini-2.5-flash"),
                    "openai_configured": bool(cfg.get("openai_api_key")),
                    "local_14b_available": True
                }
            })
            return
        self.send_json({"error": "Not Found"}, 404)

    def do_POST(self):
        cfg = load_config()
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            body = json.loads(raw_body)
        except Exception as e:
            logger.warning(f"Failed to parse JSON body (len={length}, raw={raw_body[:100]!r}): {e}")
            self.send_json({"ok": False, "error": "Invalid JSON payload"}, 400)
            return

        if self.path in ("/api/frontier/gemini_web/cookies", "/api/gemini_web/configure"):
            psid = body.get("psid", "").strip()
            psidts = body.get("psidts", "").strip()
            extra = body.get("extra_cookies", {})
            if not psid:
                self.send_json({"ok": False, "error": "Missing __Secure-1PSID cookie"}, 400)
                return
            sess_file = os.path.join(os.path.dirname(CONFIG_FILE), "gemini_session.json")
            try:
                with open(sess_file, "w", encoding="utf-8") as f:
                    json.dump({"psid": psid, "psidts": psidts, "extra_cookies": extra, "updated_at": time.time()}, f, indent=2)
                # Re-validate
                if GeminiWebClient:
                    test_client = GeminiWebClient(psid=psid, psidts=psidts, extra_cookies=extra)
                    v_ok, v_msg = test_client.validate_session(force=True)
                    self.send_json({"ok": True, "valid": v_ok, "message": v_msg})
                    return
                self.send_json({"ok": True, "message": "Cookies saved successfully."})
                return
            except Exception as ex:
                self.send_json({"ok": False, "error": str(ex)}, 500)
                return

        if self.path in ("/api/frontier/audit", "/api/frontier/verify"):
            title = body.get('title', 'Unknown challenge')
            pref_provider = body.get('preferred_provider', '').lower()
            logger.info(f"Received audit request for: {title} (preferred: {pref_provider or 'default'})")
            errors = []

            # Check if caller specifically requested Gemini Web (AI Plus)
            if pref_provider in ("gemini_web", "gemini_advanced", "ai_plus"):
                try:
                    res = call_gemini_web_audit(body, cfg)
                    logger.info(f"Audit completed via Preferred (Gemini Web AI Plus) in {res['latency_ms']}ms: {res['verdict']}")
                    self.send_json(res)
                    return
                except Exception as ex:
                    logger.warning(f"Preferred Gemini Web failed: {ex}. Falling back to standard cascade...")
                    errors.append(f"gemini_web_preferred: {ex}")

            # 1. Primary: Antigravity CLI (Prepaid) - ONLY IF AUTHENTICATED AND NOT DELAYED
            is_auth = check_agy_authenticated(cfg.get("agy_path", "/usr/local/bin/agy"))
            if is_auth and not cfg.get("delay_agy_auth", False) and pref_provider != "gemini_web":
                try:
                    res = call_agy_audit(body, cfg)
                    logger.info(f"Audit completed via Primary (agy) in {res['latency_ms']}ms: {res['verdict']}")
                    self.send_json(res)
                    return
                except Exception as e:
                    logger.warning(f"Primary (agy) failed: {e}. Progressing to backups...")
                    errors.append(f"agy: {e}")
            else:
                reason = "auth delayed for mobile" if cfg.get("delay_agy_auth") else "agy not yet authenticated"
                logger.info(f"Skipping agy primary ({reason}). Routing directly to backups...")

            # 2. Backup Tier 1: Gemini Web Session (Google One AI Plus - $0 Token Cost)
            if cfg.get("gemini_web_psid") or cfg.get("gemini_web_url"):
                try:
                    res = call_gemini_web_audit(body, cfg)
                    logger.info(f"Audit completed via Backup Tier 1 (Gemini Web AI Plus) in {res['latency_ms']}ms: {res['verdict']}")
                    self.send_json(res)
                    return
                except Exception as ex:
                    logger.warning(f"Gemini Web session backup failed: {ex}")
                    errors.append(f"gemini_web: {ex}")

            # 3. Backup Tier 2: OpenRouter
            if cfg.get("openrouter_api_key"):
                try:
                    res = call_openrouter_audit(body, cfg)
                    logger.info(f"Audit completed via Backup Tier 2 (OpenRouter) in {res['latency_ms']}ms: {res['verdict']}")
                    self.send_json(res)
                    return
                except Exception as ex:
                    logger.warning(f"OpenRouter backup failed: {ex}")
                    errors.append(f"openrouter: {ex}")

            # 3. Backup B: Direct Google Gemini API
            if cfg.get("gemini_api_key"):
                try:
                    res = call_gemini_api_audit(body, cfg)
                    logger.info(f"Audit completed via Backup B (Gemini API) in {res['latency_ms']}ms: {res['verdict']}")
                    self.send_json(res)
                    return
                except Exception as ex:
                    logger.warning(f"Gemini API backup failed: {ex}")
                    errors.append(f"gemini_api: {ex}")

            # 4. Backup C: Local 14B Coordinator Fallback
            try:
                res = call_local_coordinator_fallback(body, cfg)
                logger.info(f"Audit completed via Backup C (Local 14B) in {res['latency_ms']}ms: {res['verdict']}")
                res["backup_reason"] = "All external frontier keys unconfigured or failed."
                self.send_json(res)
                return
            except Exception as ex:
                logger.error(f"Local 14B fallback failed: {ex}")
                errors.append(f"local_14b: {ex}")

            self.send_json({
                "ok": False,
                "error": f"All frontier providers failed: {'; '.join(errors)}"
            }, 502)
            return

        self.send_json({"error": "Endpoint not supported"}, 404)

def run():
    cfg = load_config()
    host = cfg.get("host", "0.0.0.0")
    port = int(cfg.get("port", 8085))
    server = ThreadedHTTPServer((host, port), FrontierBridgeHandler)
    logger.info(f"Frontier Bridge Server listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopping Frontier Bridge Server...")
    finally:
        server.server_close()

if __name__ == "__main__":
    run()
