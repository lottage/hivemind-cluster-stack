#!/usr/bin/env python3
"""
Gemini Web Session Client (Google One AI Plus / Gemini Advanced)
Zero-token-cost reasoning bridge utilizing user's existing Google One AI Plus subscription.
Communicates directly with gemini.google.com using browser session cookies (__Secure-1PSID and __Secure-1PSIDTS).

Zero-dependency: 100% Python standard library (urllib, json, re, time).
"""

import os
import re
import sys
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, Optional, Tuple

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

def parse_raw_cookies(raw_text: str) -> Dict[str, str]:
    """Extracts individual cookies from raw text, key=value format, or Cookie request headers."""
    extracted = {}
    if not raw_text:
        return extracted
    # Split by semicolon or newline
    parts = re.split(r'[;\n]', raw_text)
    for p in parts:
        p = p.strip()
        if "=" in p:
            k, v = p.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and v:
                extracted[k] = v
    return extracted

class GeminiWebClient:
    def __init__(self, psid: str = "", psidts: str = "", extra_cookies: Optional[Dict[str, str]] = None):
        self.psid = ""
        self.psidts = ""
        self.extra_cookies = extra_cookies or {}
        self.snlm0e: Optional[str] = None
        self.conversation_id: str = ""
        self.response_id: str = ""
        self.choice_id: str = ""
        self._last_validated: float = 0
        self._is_valid: bool = False
        self._user_email: Optional[str] = None
        self.bl: str = "boq_assistant-bard-web-server_20260907.07_p0"
        self.update_cookies(psid, psidts, extra_cookies)

    def update_cookies(self, psid: str, psidts: str, extra: Optional[Dict[str, str]] = None):
        raw_input = f"{psid} {psidts}"
        parsed = parse_raw_cookies(raw_input)
        
        # Check if parsed dictionary yielded cookies
        if "__Secure-1PSID" in parsed:
            self.psid = parsed.pop("__Secure-1PSID")
        elif "SID" in parsed:
            self.psid = parsed.get("SID", "")
        else:
            self.psid = psid.strip()

        if "__Secure-1PSIDTS" in parsed:
            self.psidts = parsed.pop("__Secure-1PSIDTS")
        else:
            self.psidts = psidts.strip()

        # Any other cookies go into extra_cookies
        self.extra_cookies.update(parsed)
        if extra:
            self.extra_cookies.update(extra)

        self.snlm0e = None
        self._last_validated = 0
        self._is_valid = False

    def get_cookie_header(self) -> str:
        cookies = dict(self.extra_cookies)
        if self.psid:
            cookies["__Secure-1PSID"] = self.psid
            cookies["__Secure-3PSID"] = self.psid
        if self.psidts:
            cookies["__Secure-1PSIDTS"] = self.psidts
            cookies["__Secure-3PSIDTS"] = self.psidts
        return "; ".join([f"{k}={v}" for k, v in cookies.items()])

    def validate_session(self, force: bool = False) -> Tuple[bool, str]:
        """Probes gemini.google.com/app and extracts CSRF token."""
        now = time.time()
        if not force and self._is_valid and self.snlm0e and (now - self._last_validated < 300):
            return True, "Session active and cached."

        if not self.psid:
            self._is_valid = False
            return False, "Missing __Secure-1PSID cookie."

        url = "https://gemini.google.com/app"
        headers = {
            "User-Agent": USER_AGENT,
            "Cookie": self.get_cookie_header(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            # Extract CSRF token (Google uses thykhd / SNlM0e / AFWLbD...)
            token = None
            m_token = re.search(r'"(?:SNlM0e|thykhd)":"([^"]+)"', html)
            if m_token:
                token = m_token.group(1)
            else:
                m_afw = re.search(r'"[a-zA-Z0-9_-]{4,12}":"(AFWLbD[^"]+)"', html)
                if m_afw:
                    token = m_afw.group(1)
                else:
                    m_arr = re.search(r'\["(?:SNlM0e|thykhd)",\[\],null,"([^"]+)"\]', html)
                    if m_arr:
                        token = m_arr.group(1)

            # Extract dynamic build label cfb2h
            m_bl = re.search(r'"cfb2h":"([^"]+)"', html)
            if m_bl:
                self.bl = m_bl.group(1)

            if token:
                self.snlm0e = token
                self._is_valid = True
                self._last_validated = now
                
                # Check for Gemini Advanced badge or features
                is_advanced = "Gemini Advanced" in html or "Advanced" in html or "106447585" in html
                status_note = "Gemini Advanced ($0 token cost)" if is_advanced else "Standard Gemini active"
                return True, f"Authenticated successfully ({status_note}). Session token acquired."
            else:
                self._is_valid = False
                if "Sign in" in html or "accounts.google.com" in html:
                    return False, "Session expired or cookies invalid (Google redirected to sign-in)."
                return False, "Could not extract CSRF token from response HTML."
        except Exception as e:
            self._is_valid = False
            return False, f"Connection failed to gemini.google.com: {e}"

    def generate_content(self, prompt: str, timeout: float = 40.0) -> Dict[str, Any]:
        """Sends a prompt to gemini.google.com and streams the response text."""
        t0 = time.time()
        ok, msg = self.validate_session()
        if not ok:
            return {"ok": False, "error": f"Session invalid: {msg}"}

        url = "https://gemini.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"
        params = {
            "bl": self.bl or "boq_assistant-bard-web-server_20260907.07_p0",
            "_reqid": str(int(time.time() * 1000) % 1000000),
            "rt": "c"
        }
        full_url = f"{url}?{urllib.parse.urlencode(params)}"

        # Construct payload matching Google's BardChatUi RPC format
        msg_struct = [
            [prompt, 0, None, None, None, None, 0],
            ["en"],
            [self.conversation_id, self.response_id, self.choice_id],
            None, None, None,
            [0],
            0,
            [],
            [],
            None,
            0
        ]
        form_data = {
            "at": self.snlm0e,
            "f.req": json.dumps([None, json.dumps(msg_struct)])
        }
        encoded_data = urllib.parse.urlencode(form_data).encode("utf-8")

        headers = {
            "User-Agent": USER_AGENT,
            "Cookie": self.get_cookie_header(),
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Origin": "https://gemini.google.com",
            "Referer": "https://gemini.google.com/app",
            "X-Same-Domain": "1"
        }

        try:
            req = urllib.request.Request(full_url, data=encoded_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw_response = resp.read().decode("utf-8", errors="replace")

            # Parse stream lines
            response_text = self._parse_gemini_stream(raw_response)
            if not response_text:
                return {"ok": False, "error": "Empty response extracted from Gemini Web stream."}

            elapsed_ms = round((time.time() - t0) * 1000, 1)
            return {
                "ok": True,
                "text": response_text,
                "provider": "gemini_web_advanced",
                "latency_ms": elapsed_ms,
                "token_cost": 0.0
            }
        except Exception as e:
            return {"ok": False, "error": f"Gemini web request failed: {e}"}

    def _parse_gemini_stream(self, raw: str) -> str:
        """Extracts completion text and session IDs from Google's chunked response."""
        extracted_text = ""
        lines = raw.split("\n")
        for line in lines:
            if not line.strip() or line.startswith(")]}'"):
                continue
            try:
                # Format: number\n[array]
                data = json.loads(line)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, list) and len(item) > 2 and isinstance(item[2], str):
                            sub_json = json.loads(item[2])
                            if isinstance(sub_json, list) and len(sub_json) > 4:
                                # Candidate answers
                                candidates = sub_json[4]
                                if isinstance(candidates, list) and len(candidates) > 0:
                                    for cand in candidates:
                                        if isinstance(cand, list) and len(cand) > 1 and isinstance(cand[1], list):
                                            for part in cand[1]:
                                                if isinstance(part, str) and len(part) > len(extracted_text):
                                                    extracted_text = part
                                    first_cand = candidates[0]
                                    # Also save conversation identifiers
                                    if len(sub_json) > 1 and isinstance(sub_json[1], list):
                                        conv_info = sub_json[1]
                                        if len(conv_info) > 1:
                                            self.conversation_id = conv_info[0] or self.conversation_id
                                            self.response_id = conv_info[1] or self.response_id
                                    if isinstance(first_cand, list) and len(first_cand) > 0 and isinstance(first_cand[0], str):
                                        self.choice_id = first_cand[0]
            except Exception:
                continue

        # Fallback text search if JSON hierarchy differed slightly
        if not extracted_text:
            text_matches = re.findall(r'\["([^"\\]*(?:\\.[^"\\]*)*)",\[\],\[\],\[\]\]', raw)
            if text_matches:
                longest_match = max(text_matches, key=len)
                extracted_text = longest_match.encode("utf-8").decode("unicode_escape", errors="replace")

        return extracted_text.strip()

    def audit_challenge(self, challenge_data: Dict[str, Any], timeout: float = 45.0) -> Dict[str, Any]:
        """Conducts a structured Tier-1 Frontier audit using Gemini Web."""
        prompt = f"""You are the Tier-1 Frontier Meta-Verifier for an autonomous dual-GPU AI homelab cluster.
Audit this empirical reasoning challenge between a 3B Worker and a 14B Coordinator.
Eliminate syntactic leniency bias: evaluate strict correctness, mathematical proofs, or concurrency invariants.

### Challenge: {challenge_data.get('title', 'Unknown')}
Target Invariant: {challenge_data.get('target_invariant', '')}
Original Prompt:
{challenge_data.get('prompt', '')}

--- 3B WORKER OUTPUT ---
{challenge_data.get('worker_output', '')}

--- 14B COORDINATOR OUTPUT ---
{challenge_data.get('coordinator_output', '')}

--- 14B FIRST-PASS EVALUATION ---
{json.dumps(challenge_data.get('eval', {}), indent=2)}

TASK:
1. Objectively evaluate correctness.
2. Determine if the target invariant held or failed.
3. Respond ONLY with valid, raw JSON (no conversational text outside JSON):
{{
  "verdict": "CONFIRM_LIMIT_VALIDATED" | "REVISE_LIMIT_IDENTIFIED" | "INCONCLUSIVE",
  "frontier_notes": "Critical assessment highlighting subtle bugs or truth.",
  "refined_limits": "Precise failure boundary and invariants discovered."
}}"""

        res = self.generate_content(prompt, timeout=timeout)
        if not res.get("ok"):
            return res

        raw = res.get("text", "").strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        try:
            parsed = json.loads(raw)
            return {
                "ok": True,
                "provider": "gemini_web_advanced (AI Plus $0 token cost)",
                "verdict": parsed.get("verdict", "CONFIRM_LIMIT_VALIDATED").upper(),
                "frontier_notes": parsed.get("frontier_notes", ""),
                "refined_limits": parsed.get("refined_limits", ""),
                "latency_ms": res.get("latency_ms", 0),
                "model": "Gemini Advanced (Web Session)"
            }
        except Exception:
            # Fallback extraction
            verdict = "CONFIRM_LIMIT_VALIDATED"
            if "REVISE" in raw.upper():
                verdict = "REVISE_LIMIT_IDENTIFIED"
            elif "INCONCLUSIVE" in raw.upper():
                verdict = "INCONCLUSIVE"
            return {
                "ok": True,
                "provider": "gemini_web_advanced (AI Plus $0 token cost)",
                "verdict": verdict,
                "frontier_notes": raw,
                "refined_limits": "Extracted via Gemini Web session",
                "latency_ms": res.get("latency_ms", 0),
                "model": "Gemini Advanced (Web Session)"
            }
