#!/usr/bin/env python3
"""
EasyDash Local Server & Antigravity (agy) PowerShell CLI Bridge
+ Open WebUI Homelab Backend Services:
  - Hub Defaults & Provider Settings Persistence (hub_config.json)
  - BIONIC Engine: Privacy RAG (local vector/lexical search) & Airgap/Audit Guardrails
  - LM Studio Proxy & Connectivity Ping (:1234)
  - Web Search (zero-key DuckDuckGo Lite grounding with airgap guardrail)
  - Web Scraper (URL article text extractor with airgap guardrail)
  - Ollama Manager & Proxy (model list, pull with SSE progress, delete, show, chat)
  - Server-Side Chat Persistence (multi-device sync & history storage)
  - PowerShell & Antigravity CLI Execution with live SSE streaming output

Zero-dependency: 100% Python 3 standard library.
"""

import http.server
import subprocess
import json
import os
import sys
import threading
import concurrent.futures
import uuid
import re
import time
import math
import urllib.request
import urllib.parse
import urllib.error
import html as html_lib
import mimetypes

mimetypes.add_type('application/manifest+json', '.webmanifest')
mimetypes.add_type('application/javascript', '.js')

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
CHATS_DIR = os.path.join(DIRECTORY, 'chats')
CONFIG_FILE = os.path.join(DIRECTORY, 'hub_config.json')
AUDIT_LOG_FILE = os.path.join(DIRECTORY, 'bionic_audit.json')

os.makedirs(CHATS_DIR, exist_ok=True)

active_procs = {}
active_procs_lock = threading.Lock()
agy_models_cache = {"timestamp": 0, "models": []}

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ==========================================
# Hub Configuration & Defaults
# ==========================================
DEFAULT_HUB_CONFIG = {
    "defaults": {
        "engine": "agy",
        "modelAgy": "gemini-2.5-pro",
        "modelLmstudio": "",
        "modelOllama": "llama3.2",
        "modelOpenai": "gpt-4o",
        "codeCopyFormat": "clean",
        "autoScroll": "always",
        "telemetryMode": "detailed",
        "soundFeedback": "silent",
        "termFontSize": "13px"
    },
    "lmstudio": {
        "endpoint": "http://localhost:1234/v1",
        "activeModel": "",
        "temp": 0.70,
        "top_p": 0.95,
        "top_k": 40,
        "min_p": 0.05,
        "repeat_penalty": 1.10,
        "freq_penalty": 0.00,
        "pres_penalty": 0.00,
        "seed": -1,
        "num_ctx": 4096,
        "max_tokens": -1,
        "stop": "",
        "template": "auto",
        "overflow": "truncate",
        "json_mode": False,
        "gpu_layers": -1,
        "keep_alive": "15m",
        "api_key": ""
    },
    "mcp": {
        "enabled": True,
        "auto_execute_read": True,
        "require_confirm_write": True,
        "max_turns": 5,
        "rag": {
            "chunk_size": 512,
            "chunk_overlap": 64,
            "top_k": 4,
            "min_score": 0.60,
            "embed_endpoint": "http://localhost:11434/api/embeddings",
            "embed_model": "nomic-embed-text"
        },
        "servers": []
    },
    "bionic": {
        "thinking_mode": "auto",
        "show_duration": True,
        "show_tokens": True,
        "agentic_loop": True
    },
    "agy": {
        "effort": "",
        "mode": "",
        "max_steps": "",
        "cwd": "",
        "continue_session": False,
        "auto_compress": "never",
        "tool_exec": True,
        "tool_file": True,
        "tool_web": True,
        "tool_subagents": True
    },
    "ollama": {
        "endpoint": "http://localhost:11434",
        "num_ctx": 4096,
        "keep_alive": "15m",
        "temp": 0.70,
        "top_p": 0.90,
        "top_k": 40,
        "repeat_penalty": 1.10,
        "repeat_last_n": 64,
        "mirostat": "0",
        "num_gpu": -1,
        "raw_mode": False
    },
    "openai": {
        "endpoint": "https://api.openai.com/v1",
        "api_key": "",
        "org_id": "",
        "custom_headers": "{}"
    },
    "powershell": {
        "timeout": 60,
        "max_buffer": 50000,
        "cwd": ""
    },
    "persona": {
        "active_preset": "sre",
        "system_prompt": "You are an expert Linux, Proxmox VE, Docker and PowerShell homelab administrator. Be concise, precise, and practical."
    },
    "cluster": {
        "coordinator_url": "http://127.0.0.1:8001",
        "worker_url": "http://127.0.0.1:8002",
        "embedder_url": "http://127.0.0.1:8003",
        "mcp_url": "http://127.0.0.1:8765",
        "qdrant_url": "http://127.0.0.1:6333",
        "active_role": "coordinator"
    },
    "ha": {
        "endpoint": "http://127.0.0.1:8123",
        "token": ""
    }
}

def load_hub_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                cfg = dict(DEFAULT_HUB_CONFIG)
                for k, v in saved.items():
                    if isinstance(v, dict) and k in cfg and isinstance(cfg[k], dict):
                        cfg[k] = dict(cfg[k])
                        cfg[k].update(v)
                    else:
                        cfg[k] = v
                return cfg
        except Exception:
            pass
    return dict(DEFAULT_HUB_CONFIG)

def save_hub_config_to_disk(new_cfg):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(new_cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

def record_bionic_audit(event_type, details):
    record = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "type": event_type,
        "details": details
    }
    try:
        existing = []
        if os.path.exists(AUDIT_LOG_FILE):
            with open(AUDIT_LOG_FILE, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        existing.append(record)
        if len(existing) > 200:
            existing = existing[-200:]
        with open(AUDIT_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2)
    except Exception:
        pass

# ==========================================
# Web Search & Scraper Helpers
# ==========================================
def search_web_ddg(query, max_results=8):
    """Zero-key web search using DuckDuckGo Lite HTML parsing."""
    url = "https://lite.duckduckgo.com/lite/"
    data = urllib.parse.urlencode({"q": query}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://lite.duckduckgo.com/"
        }
    )
    results = []
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html_text = resp.read().decode("utf-8", errors="replace")

        link_matches = list(re.finditer(
            r'<a\s+[^>]*class=["\']result-link["\'][^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            html_text, re.DOTALL | re.IGNORECASE
        ))
        if not link_matches:
            link_matches = list(re.finditer(
                r'<a\s+[^>]*rel=["\']nofollow["\'][^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                html_text, re.DOTALL | re.IGNORECASE
            ))

        snippet_matches = list(re.finditer(
            r'<td\s+[^>]*class=["\']result-snippet["\'][^>]*>(.*?)</td>',
            html_text, re.DOTALL | re.IGNORECASE
        ))

        for i, m in enumerate(link_matches[:max_results]):
            raw_url = m.group(1)
            if "uddg=" in raw_url:
                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                clean_url = parsed.get("uddg", [raw_url])[0]
            else:
                clean_url = raw_url

            title = html_lib.unescape(re.sub(r'<[^>]+>', '', m.group(2)).strip())
            snippet = ""
            if i < len(snippet_matches):
                snippet = html_lib.unescape(re.sub(r'<[^>]+>', '', snippet_matches[i].group(1)).strip())

            if clean_url.startswith("http"):
                results.append({
                    "title": title,
                    "url": clean_url,
                    "snippet": snippet
                })
    except Exception as e:
        results.append({
            "title": "Search Error",
            "url": "",
            "snippet": f"Could not retrieve DuckDuckGo search results: {str(e)}"
        })
    return results

def scrape_url_text(url, max_chars=8000):
    """Zero-key readability extraction from URL using standard library."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()
            charset = "utf-8"
            if "charset=" in content_type:
                charset = content_type.split("charset=")[-1].split(";")[0].strip()
            try:
                html_text = raw.decode(charset, errors="replace")
            except Exception:
                html_text = raw.decode("utf-8", errors="replace")

        cleaned = re.sub(r'<(script|style|nav|header|footer|aside|svg|noscript)[^>]*>.*?</\1>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html_text, re.IGNORECASE | re.DOTALL)
        title = html_lib.unescape(title_match.group(1).strip()) if title_match else url

        cleaned = re.sub(r'<(p|div|br|li|h[1-6])[^>]*>', '\n', cleaned, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', cleaned)
        text = html_lib.unescape(text)

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        full_text = "\n\n".join(lines)

        if len(full_text) > max_chars:
            full_text = full_text[:max_chars] + f"\n\n[... Truncated to {max_chars} chars ...]"

        return {"ok": True, "title": title, "url": url, "text": full_text}
    except Exception as e:
        return {"ok": False, "title": "Scrape Error", "url": url, "error": str(e), "text": f"Error scraping {url}: {str(e)}"}

# ==========================================
# BIONIC RAG Engine (Semantic & Lexical Search)
# ==========================================
def chunk_text(text, chunk_size=512, overlap=64):
    """Splits text into chunks of roughly chunk_size words with overlap."""
    words = text.split()
    if not words:
        return []
    chunks = []
    step = max(1, chunk_size - overlap)
    for i in range(0, len(words), step):
        chunk_words = words[i:i + chunk_size]
        chunks.append(" ".join(chunk_words))
        if i + chunk_size >= len(words):
            break
    return chunks

def tokenize_words(text):
    return [w.lower() for w in re.findall(r'[a-zA-Z0-9]{2,}', text)]

def lexical_cosine_similarity(query_tokens, chunk_tokens):
    if not query_tokens or not chunk_tokens:
        return 0.0
    q_freq = {}
    for w in query_tokens:
        q_freq[w] = q_freq.get(w, 0) + 1
    c_freq = {}
    for w in chunk_tokens:
        c_freq[w] = c_freq.get(w, 0) + 1

    dot = 0.0
    for w, count in q_freq.items():
        if w in c_freq:
            dot += count * c_freq[w]

    q_norm = math.sqrt(sum(v*v for v in q_freq.values()))
    c_norm = math.sqrt(sum(v*v for v in c_freq.values()))
    if q_norm == 0 or c_norm == 0:
        return 0.0
    return dot / (q_norm * c_norm)

def fetch_local_embedding(endpoint, model, text):
    """Fetches real embedding from Ollama or LM Studio if available."""
    try:
        norm_endpoint = endpoint.replace("localhost", "127.0.0.1")
        # Check if Ollama endpoint
        if '/api/embeddings' in norm_endpoint or '11434' in norm_endpoint:
            url = norm_endpoint if norm_endpoint.endswith('/api/embeddings') else norm_endpoint.rstrip('/') + '/api/embeddings'
            payload = json.dumps({"model": model, "prompt": text}).encode('utf-8')
        else: # OpenAI / LM Studio /v1/embeddings
            url = norm_endpoint if norm_endpoint.endswith('/embeddings') else norm_endpoint.rstrip('/') + '/v1/embeddings'
            payload = json.dumps({"model": model, "input": text}).encode('utf-8')

        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=0.6) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if "embedding" in data:
                return data["embedding"]
            elif "data" in data and len(data["data"]) and "embedding" in data["data"][0]:
                return data["data"][0]["embedding"]
    except Exception:
        pass
    return None

def vector_cosine_similarity(vec_a, vec_b):
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

# ==========================================
# HTTP Request Handler
# ==========================================
class EasyDashHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == '/manifest.webmanifest':
            self.serve_pwa_file('manifest.webmanifest', 'application/manifest+json; charset=utf-8', {'Cache-Control': 'no-cache'})
            return
        elif path == '/sw.js':
            self.serve_pwa_file('sw.js', 'application/javascript; charset=utf-8', {'Service-Worker-Allowed': '/', 'Cache-Control': 'no-cache'})
            return
        elif path == '/api/health':
            self.send_json({
                'status': 'ok',
                'bridge': True,
                'engine': 'EasyDash-OpenWebUI',
                'features': ['agy', 'ps', 'web_search', 'web_scrape', 'ollama_proxy', 'lmstudio_proxy', 'bionic_rag', 'hub_config', 'chats_sync', 'cluster_hub', 'ha_bridge', 'qdrant_memory'],
                'os': sys.platform,
                'cwd': DIRECTORY,
                'python': sys.version.split()[0]
            })
            return
        elif path in ('/api/config', '/api/config/get'):
            self.send_json(load_hub_config())
            return
        elif path == '/api/cluster/health':
            self.handle_cluster_health()
            return
        elif path.startswith('/api/ha/'):
            self.handle_ha_proxy('GET')
            return
        elif path == '/api/memory/collections':
            self.handle_memory_collections()
            return
        elif path.startswith('/api/memory/points'):
            self.handle_memory_points()
            return
        elif path == '/api/bionic/audit':
            self.handle_get_bionic_audit()
            return
        elif path in ('/api/chats', '/api/chats/list'):
            self.handle_list_chats()
            return
        elif path.startswith('/api/chats/'):
            chat_id = path.split('/api/chats/')[1]
            self.handle_get_chat(chat_id)
            return
        elif path == '/api/ollama/tags':
            qs = urllib.parse.parse_qs(parsed.query)
            host = qs.get('host', ['http://localhost:11434'])[0].rstrip('/')
            self.proxy_ollama_tags(host)
            return
        elif path == '/api/lmstudio/models':
            qs = urllib.parse.parse_qs(parsed.query)
            host = qs.get('host', ['http://localhost:1234'])[0].rstrip('/')
            self.proxy_lmstudio_models(host)
            return
        elif path == '/api/mcp/tools':
            self.handle_mcp_tools()
            return
        elif path == '/api/mcp/servers':
            self.handle_mcp_servers()
            return
        elif path == '/api/lmstudio/ping':
            qs = urllib.parse.parse_qs(parsed.query)
            host = qs.get('host', ['http://localhost:1234'])[0].rstrip('/')
            self.handle_lmstudio_ping(host)
            return
        elif path == '/api/agy/models':
            self.handle_agy_models()
            return

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ('/api/agy', '/api/ps', '/api/exec'):
            self.handle_execution()
            return
        elif path.startswith('/api/ha/'):
            self.handle_ha_proxy('POST')
            return
        elif path == '/api/cluster/chat':
            self.handle_cluster_chat()
            return
        elif path == '/api/memory/search':
            self.handle_memory_search()
            return
        elif path == '/api/memory/store':
            self.handle_memory_store()
            return
        elif path == '/api/cancel':
            self.handle_cancel()
            return
        elif path in ('/api/config', '/api/config/save'):
            self.handle_save_config()
            return
        elif path == '/api/mcp/call':
            self.handle_mcp_call()
            return
        elif path == '/api/mcp/servers/save':
            self.handle_save_mcp_servers()
            return
        elif path == '/api/mcp/servers/test':
            self.handle_test_mcp_server()
            return
        elif path == '/api/rag/query':
            self.handle_rag_query()
            return
        elif path == '/api/bionic/audit/clear':
            self.handle_clear_bionic_audit()
            return
        elif path == '/api/web/search':
            self.handle_web_search()
            return
        elif path == '/api/web/scrape':
            self.handle_web_scrape()
            return
        elif path == '/api/ollama/pull':
            self.handle_ollama_pull()
            return
        elif path == '/api/ollama/delete':
            self.handle_ollama_delete()
            return
        elif path == '/api/ollama/show':
            self.handle_ollama_show()
            return
        elif path == '/api/chats/save':
            self.handle_save_chat()
            return
        elif path == '/api/chats/delete':
            self.handle_delete_chat()
            return
        elif path == '/api/lmstudio/chat':
            self.proxy_lmstudio_chat()
            return

        super().do_POST()

    def read_json_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode('utf-8')
        try:
            return json.loads(raw)
        except Exception:
            return {}

    # ==========================================
    # PWA & Static Asset Handlers
    # ==========================================
    def serve_pwa_file(self, filename, content_type, extra_headers=None):
        target = os.path.join(DIRECTORY, filename)
        if not os.path.exists(target):
            self.send_error(404, f"File {filename} not found")
            return
        try:
            with open(target, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Access-Control-Allow-Origin', '*')
            if extra_headers:
                for k, v in extra_headers.items():
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, str(e))

    # ==========================================
    # PVE Cluster & Home Assistant Handlers
    # ==========================================
    def handle_cluster_health(self):
        cfg = load_hub_config()
        cluster_cfg = cfg.get('cluster', {})
        ha_cfg = cfg.get('ha', {})
        coord_url = cluster_cfg.get('coordinator_url', 'http://127.0.0.1:8001')
        worker_url = cluster_cfg.get('worker_url', 'http://127.0.0.1:8002')
        embed_url = cluster_cfg.get('embedder_url', 'http://127.0.0.1:8003')
        mcp_url = cluster_cfg.get('mcp_url', 'http://127.0.0.1:8765')
        qdrant_url = cluster_cfg.get('qdrant_url', 'http://127.0.0.1:6333')
        ha_url = ha_cfg.get('endpoint', 'http://127.0.0.1:8123')

        def ping_http(url, path='/health', valid_codes=(200,)):
            target = f"{url.rstrip('/')}{path}"
            t0 = time.perf_counter()
            try:
                req = urllib.request.Request(target, headers={"User-Agent": DEFAULT_USER_AGENT})
                with urllib.request.urlopen(req, timeout=2.5) as resp:
                    latency = round((time.perf_counter() - t0) * 1000, 1)
                    return {"status": "online", "latency_ms": latency, "code": resp.status}
            except urllib.error.HTTPError as he:
                latency = round((time.perf_counter() - t0) * 1000, 1)
                if he.code in valid_codes:
                    return {"status": "online", "latency_ms": latency, "code": he.code}
                return {"status": f"http_{he.code}", "latency_ms": latency, "error": he.reason}
            except Exception as ex:
                return {"status": "offline", "error": str(ex)}

        def probe_mcp():
            res = ping_http(mcp_url, "/health")
            if res.get("status") == "offline" or res.get("status", "").startswith("http_404"):
                return ping_http(mcp_url, "/sse")
            return res

        probes = {
            "coordinator": (lambda: {**ping_http(coord_url, "/health"), "role": "14B Qwen Coder (RX 6750 XT)", "url": coord_url}),
            "worker": (lambda: {**ping_http(worker_url, "/health"), "role": "3B Qwen Worker (RX 6600 XT)", "url": worker_url}),
            "embedder": (lambda: {**ping_http(embed_url, "/health"), "role": "BGE-Large Embedder (RX 6600 XT)", "url": embed_url}),
            "mcp_bridge": (lambda: {**probe_mcp(), "role": "FastMCP Universal Bridge", "url": mcp_url}),
            "qdrant": (lambda: {**ping_http(qdrant_url, "/readyz"), "role": "Qdrant Vector DB (LXC 117)", "url": qdrant_url}),
            "home_assistant": (lambda: {**ping_http(ha_url, "/api/", valid_codes=(200, 401)), "role": "Home Assistant OS (VM 103)", "url": ha_url})
        }

        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(probes)) as executor:
            future_to_key = {executor.submit(fn): key for key, fn in probes.items()}
            for future in concurrent.futures.as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    results[key] = future.result()
                except Exception as exc:
                    results[key] = {"status": "offline", "error": str(exc), "url": ""}

        self.send_json({"ok": True, "cluster": results})

    def handle_ha_proxy(self, method='GET'):
        cfg = load_hub_config()
        ha_cfg = cfg.get('ha', {})
        ha_base = ha_cfg.get('endpoint', 'http://127.0.0.1:8123').rstrip('/')
        token = ha_cfg.get('token', '') or os.getenv('HASS_TOKEN', '')

        client_auth = self.headers.get('Authorization', '')
        if client_auth and client_auth.startswith('Bearer '):
            token = client_auth[7:]

        parsed = urllib.parse.urlparse(self.path)
        subpath = parsed.path[len('/api/ha'):]
        if not subpath.startswith('/'):
            subpath = '/' + subpath

        target_url = f"{ha_base}/api{subpath}"
        if parsed.query:
            target_url += f"?{parsed.query}"

        headers = {
            "Content-Type": "application/json",
            "User-Agent": DEFAULT_USER_AGENT
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        body_bytes = None
        if method == 'POST':
            length = int(self.headers.get('Content-Length', 0))
            if length > 0:
                body_bytes = self.rfile.read(length)

        try:
            req = urllib.request.Request(target_url, data=body_bytes, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=12.0) as resp:
                resp_bytes = resp.read()
                self.send_response(resp.status)
                self.send_header('Content-Type', resp.headers.get('Content-Type', 'application/json'))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(resp_bytes)
        except urllib.error.HTTPError as he:
            err_body = he.read()
            self.send_response(he.code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(err_body)
        except Exception as ex:
            self.send_json({'ok': False, 'error': f"Failed to proxy Home Assistant request: {str(ex)}"}, 502)

    def handle_memory_collections(self):
        cfg = load_hub_config()
        qdrant_url = cfg.get('cluster', {}).get('qdrant_url', 'http://127.0.0.1:6333').rstrip('/')
        try:
            req = urllib.request.Request(f"{qdrant_url}/collections", headers={"User-Agent": DEFAULT_USER_AGENT})
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                self.send_json({'ok': True, 'collections': data.get('result', {}).get('collections', [])})
        except Exception as e:
            self.send_json({'ok': False, 'error': str(e)}, 500)

    def handle_memory_points(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        collection = qs.get('collection', ['companion_profile'])[0]
        limit = int(qs.get('limit', [15])[0])
        cfg = load_hub_config()
        qdrant_url = cfg.get('cluster', {}).get('qdrant_url', 'http://127.0.0.1:6333').rstrip('/')

        payload = json.dumps({"limit": limit, "with_payload": True, "with_vector": False}).encode('utf-8')
        try:
            req = urllib.request.Request(f"{qdrant_url}/collections/{collection}/points/scroll", data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                points = data.get('result', {}).get('points', [])
                self.send_json({'ok': True, 'collection': collection, 'points': points})
        except Exception as e:
            self.send_json({'ok': False, 'error': str(e)}, 500)

    def handle_memory_search(self):
        body = self.read_json_body()
        query = body.get('query', '').strip()
        collection = body.get('collection', 'companion_profile').strip()
        limit = int(body.get('limit', 5))

        if not query:
            self.send_json({'ok': False, 'error': 'Query required'}, 400)
            return

        cfg = load_hub_config()
        embed_url = cfg.get('cluster', {}).get('embedder_url', 'http://127.0.0.1:8003').rstrip('/')
        qdrant_url = cfg.get('cluster', {}).get('qdrant_url', 'http://127.0.0.1:6333').rstrip('/')

        try:
            emb_payload = json.dumps({"input": query, "model": "embedder"}).encode('utf-8')
            emb_req = urllib.request.Request(f"{embed_url}/v1/embeddings", data=emb_payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(emb_req, timeout=10.0) as emb_resp:
                emb_data = json.loads(emb_resp.read().decode('utf-8'))
                vec = emb_data['data'][0]['embedding']

            search_payload = json.dumps({"vector": vec, "limit": limit, "with_payload": True}).encode('utf-8')
            search_req = urllib.request.Request(f"{qdrant_url}/collections/{collection}/points/search", data=search_payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(search_req, timeout=10.0) as s_resp:
                results = json.loads(s_resp.read().decode('utf-8')).get('result', [])
                self.send_json({'ok': True, 'collection': collection, 'query': query, 'results': results})
        except Exception as e:
            self.send_json({'ok': False, 'error': str(e)}, 500)

    def handle_memory_store(self):
        body = self.read_json_body()
        content = body.get('content', '').strip()
        collection = body.get('collection', 'companion_profile').strip()
        metadata = body.get('metadata', {})

        if not content:
            self.send_json({'ok': False, 'error': 'Content required'}, 400)
            return

        cfg = load_hub_config()
        embed_url = cfg.get('cluster', {}).get('embedder_url', 'http://127.0.0.1:8003').rstrip('/')
        qdrant_url = cfg.get('cluster', {}).get('qdrant_url', 'http://127.0.0.1:6333').rstrip('/')

        try:
            emb_payload = json.dumps({"input": content, "model": "embedder"}).encode('utf-8')
            emb_req = urllib.request.Request(f"{embed_url}/v1/embeddings", data=emb_payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(emb_req, timeout=10.0) as emb_resp:
                vec = json.loads(emb_resp.read().decode('utf-8'))['data'][0]['embedding']

            point_id = str(uuid.uuid4())
            metadata['timestamp'] = time.strftime("%Y-%m-%d %H:%M:%S")
            store_payload = json.dumps({
                "points": [{"id": point_id, "vector": vec, "payload": {"content": content, "metadata": metadata}}]
            }).encode('utf-8')
            store_req = urllib.request.Request(f"{qdrant_url}/collections/{collection}/points", data=store_payload, headers={"Content-Type": "application/json"}, method="PUT")
            with urllib.request.urlopen(store_req, timeout=10.0) as st_resp:
                self.send_json({'ok': True, 'id': point_id, 'collection': collection, 'message': f"Memory point {point_id} stored in {collection}"})
        except Exception as e:
            self.send_json({'ok': False, 'error': str(e)}, 500)

    def handle_cluster_chat(self):
        body = self.read_json_body()
        target_role = body.get('role', 'coordinator')
        cfg = load_hub_config()
        cluster_cfg = cfg.get('cluster', {})
        if target_role == 'worker':
            base_url = cluster_cfg.get('worker_url', 'http://127.0.0.1:8002').rstrip('/')
            default_model = 'worker'
        else:
            base_url = cluster_cfg.get('coordinator_url', 'http://127.0.0.1:8001').rstrip('/')
            default_model = 'coordinator'

        messages = body.get('messages', [])
        model = body.get('model') or default_model
        stream = body.get('stream', True)
        temperature = float(body.get('temperature', 0.2))
        max_tokens = int(body.get('max_tokens', 2048))

        target_payload = json.dumps({
            "model": model,
            "messages": messages,
            "stream": stream,
            "temperature": temperature,
            "max_tokens": max_tokens
        }).encode('utf-8')

        target_url = f"{base_url}/v1/chat/completions"
        headers_sent = False
        try:
            req = urllib.request.Request(target_url, data=target_payload, headers={"Content-Type": "application/json", "User-Agent": DEFAULT_USER_AGENT}, method="POST")
            with urllib.request.urlopen(req, timeout=180.0) as resp:
                self.send_response(resp.status)
                self.send_header('Content-Type', resp.headers.get('Content-Type', 'text/event-stream' if stream else 'application/json'))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                headers_sent = True

                if stream:
                    for line in resp:
                        if line:
                            self.wfile.write(line)
                            self.wfile.flush()
                else:
                    self.wfile.write(resp.read())
                    self.wfile.flush()
        except Exception as e:
            if not headers_sent:
                self.send_json({'ok': False, 'error': f"Failed to connect to cluster model ({target_role}): {str(e)}"}, 502)
            else:
                err_payload = json.dumps({'error': str(e)})
                try:
                    self.wfile.write(f"data: {err_payload}\n\n".encode('utf-8'))
                    self.wfile.flush()
                except Exception:
                    pass

    # ==========================================
    # Hub Config Endpoints
    # ==========================================
    def handle_save_config(self):
        body = self.read_json_body()
        if not body:
            self.send_json({'ok': False, 'error': 'No config body provided'}, 400)
            return
        cur = load_hub_config()
        for k, v in body.items():
            if isinstance(v, dict) and k in cur and isinstance(cur[k], dict):
                cur[k].update(v)
            else:
                cur[k] = v
        success = save_hub_config_to_disk(cur)
        record_bionic_audit("CONFIG_SAVE", "Saved Hub Defaults & Provider Settings")
        self.send_json({'ok': success, 'config': cur})

    def handle_get_bionic_audit(self):
        cfg = load_hub_config()
        events = []
        if os.path.exists(AUDIT_LOG_FILE):
            try:
                with open(AUDIT_LOG_FILE, 'r', encoding='utf-8') as f:
                    events = json.load(f)
            except Exception:
                pass
        self.send_json({
            'ok': True,
            'strict_airgap': cfg.get('bionic', {}).get('strict_airgap', False),
            'pii_redaction': cfg.get('bionic', {}).get('pii_redaction', False),
            'total_events': len(events),
            'recent_events': events[-25:]
        })

    def handle_clear_bionic_audit(self):
        try:
            if os.path.exists(AUDIT_LOG_FILE):
                os.remove(AUDIT_LOG_FILE)
            self.send_json({'ok': True})
        except Exception as e:
            self.send_json({'ok': False, 'error': str(e)}, 500)

    # ==========================================
    # BIONIC RAG Query Endpoint
    # ==========================================

    # ==========================================
    # Model Context Protocol (MCP) & Tools Suite
    # ==========================================
    def handle_mcp_tools(self):
        cfg = load_hub_config()
        mcp_cfg = cfg.get('mcp', {})
        rag_cfg = mcp_cfg.get('rag', {})

        tools = [
            {
                "name": "homelab_rag",
                "description": "Search local homelab documentation, workspace files, and chat history using semantic vector embeddings and lexical matching.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": { "type": "string", "description": "The search query or concept to look up in local homelab knowledge base" },
                        "top_k": { "type": "integer", "description": "Number of top chunks to return", "default": rag_cfg.get('top_k', 4) },
                        "min_score": { "type": "number", "description": "Minimum similarity score threshold (0.0 to 1.0)", "default": rag_cfg.get('min_score', 0.60) }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "web_search",
                "description": "Perform zero-key real-time web search via DuckDuckGo Lite to fetch up-to-date documentation, release notes, or guides.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": { "type": "string", "description": "The web search query" },
                        "count": { "type": "integer", "description": "Number of search results to return", "default": 5 }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "fetch_webpage",
                "description": "Scrape and extract readable markdown text content from a web URL.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": { "type": "string", "description": "The HTTP or HTTPS URL to scrape" },
                        "max_chars": { "type": "integer", "description": "Maximum characters to extract", "default": 8000 }
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "run_powershell",
                "description": "Execute a shell command on the host system via PowerShell. Requires confirmation if configured.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": { "type": "string", "description": "The PowerShell command line to execute" },
                        "timeout": { "type": "integer", "description": "Execution timeout in seconds", "default": 30 }
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "read_file",
                "description": "Read the contents of a local file in the workspace or homelab directory.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": { "type": "string", "description": "Relative or absolute file path to read" }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "list_directory",
                "description": "List files and subdirectories at a local path.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": { "type": "string", "description": "Relative or absolute directory path to list", "default": "." }
                    }
                }
            }
        ]

        # Include tools from registered external MCP servers if configured
        custom_servers = mcp_cfg.get('servers', [])
        for s in custom_servers:
            if s.get('enabled', True):
                tools.append({
                    "name": f"mcp_{s.get('name', 'custom')}",
                    "description": f"External MCP tool provided by server '{s.get('name')}' ({s.get('transport', 'stdio')})",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "input": { "type": "string", "description": "Input payload for external MCP server" }
                        }
                    }
                })

        self.send_json({
            "ok": True,
            "mcp_enabled": mcp_cfg.get('enabled', True),
            "tools": tools,
            "servers": custom_servers
        })

    def handle_mcp_call(self):
        body = self.read_json_body()
        tool_name = body.get('tool', '').strip()
        args = body.get('arguments', {})
        if not tool_name:
            self.send_json({'ok': False, 'error': 'No tool specified'}, 400)
            return

        cfg = load_hub_config()
        mcp_cfg = cfg.get('mcp', {})
        rag_cfg = mcp_cfg.get('rag', {})

        record_bionic_audit("MCP_TOOL_CALL", f"Invoked MCP tool '{tool_name}' with args: {str(args)[:60]}")

        try:
            if tool_name == 'homelab_rag':
                query = args.get('query', '').strip()
                top_k = int(args.get('top_k', rag_cfg.get('top_k', 4)))
                min_score = float(args.get('min_score', rag_cfg.get('min_score', 0.60)))
                embed_endpoint = args.get('embed_endpoint', rag_cfg.get('embed_endpoint', 'http://localhost:11434/api/embeddings'))
                embed_model = args.get('embed_model', rag_cfg.get('embed_model', 'nomic-embed-text'))

                if not query:
                    self.send_json({'ok': False, 'error': 'No search query provided for homelab_rag'}, 400)
                    return

                # Collect documents from local workspace
                all_chunks = []
                chunk_size = int(rag_cfg.get('chunk_size', 512))
                chunk_overlap = int(rag_cfg.get('chunk_overlap', 64))

                # Index workspace files
                workspace_files = []
                try:
                    for root, _, files in os.walk(DIRECTORY):
                        if any(skip in root for skip in ['.git', '__pycache__', 'node_modules']):
                            continue
                        for f in files:
                            if f.endswith(('.md', '.txt', '.json', '.html', '.py', '.bat')):
                                workspace_files.append(os.path.join(root, f))
                except Exception:
                    pass

                for fpath in workspace_files[:20]:
                    try:
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                            c = f.read()
                            if len(c) < 50000:
                                chunks = chunk_text(c, chunk_size, chunk_overlap)
                                rel = os.path.relpath(fpath, DIRECTORY)
                                for ch in chunks:
                                    all_chunks.append({"text": ch, "source": rel})
                    except Exception:
                        pass

                # Also search attached docs or text if provided in args
                extra_docs = args.get('documents', [])
                if isinstance(extra_docs, list):
                    for d in extra_docs:
                        if isinstance(d, str) and d.strip():
                            for ch in chunk_text(d, chunk_size, chunk_overlap):
                                all_chunks.append({"text": ch, "source": "attachment"})
                        elif isinstance(d, dict) and "text" in d:
                            for ch in chunk_text(d["text"], chunk_size, chunk_overlap):
                                all_chunks.append({"text": ch, "source": d.get("name", "attachment")})

                if not all_chunks:
                    self.send_json({'ok': True, 'tool': 'homelab_rag', 'results': [], 'note': 'No documents available to search'})
                    return

                # Rank chunks
                scored = []
                q_vec = fetch_local_embedding(embed_endpoint, embed_model, query)
                if q_vec:
                    method = "vector"
                    for item in all_chunks:
                        c_vec = fetch_local_embedding(embed_endpoint, embed_model, item["text"][:800])
                        score = vector_cosine_similarity(q_vec, c_vec) if c_vec else lexical_cosine_similarity(tokenize_words(query), tokenize_words(item["text"]))
                        if score >= min_score:
                            scored.append({"text": item["text"], "source": item["source"], "score": round(score, 4)})
                else:
                    method = "lexical"
                    q_tokens = tokenize_words(query)
                    for item in all_chunks:
                        score = lexical_cosine_similarity(q_tokens, tokenize_words(item["text"]))
                        if score >= min_score or len(all_chunks) <= top_k:
                            scored.append({"text": item["text"], "source": item["source"], "score": round(score, 4)})

                scored.sort(key=lambda x: x["score"], reverse=True)
                self.send_json({
                    'ok': True,
                    'tool': 'homelab_rag',
                    'query': query,
                    'method': method,
                    'total_chunks_indexed': len(all_chunks),
                    'results': scored[:top_k]
                })

            elif tool_name == 'web_search':
                query = args.get('query', '').strip()
                count = int(args.get('count', 5))
                if not query:
                    self.send_json({'ok': False, 'error': 'No query provided'}, 400)
                    return
                results = search_web_ddg(query, max_results=count)
                self.send_json({'ok': True, 'tool': 'web_search', 'query': query, 'results': results})

            elif tool_name == 'fetch_webpage':
                url = args.get('url', '').strip()
                max_chars = int(args.get('max_chars', 8000))
                if not url:
                    self.send_json({'ok': False, 'error': 'No URL provided'}, 400)
                    return
                res = scrape_url_text(url, max_chars=max_chars)
                self.send_json({'ok': True, 'tool': 'fetch_webpage', 'result': res})

            elif tool_name == 'run_powershell':
                command = args.get('command', '').strip()
                timeout = int(args.get('timeout', 30))
                if not command:
                    self.send_json({'ok': False, 'error': 'No command provided'}, 400)
                    return
                proc = subprocess.run(
                    ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                    cwd=DIRECTORY,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding='utf-8',
                    errors='replace'
                )
                self.send_json({
                    'ok': proc.returncode == 0,
                    'tool': 'run_powershell',
                    'stdout': proc.stdout.strip(),
                    'stderr': proc.stderr.strip(),
                    'code': proc.returncode
                })

            elif tool_name == 'read_file':
                path = args.get('path', '').strip()
                if not path:
                    self.send_json({'ok': False, 'error': 'No path provided'}, 400)
                    return
                target = os.path.abspath(os.path.join(DIRECTORY, path)) if not os.path.isabs(path) else path
                if not os.path.exists(target) or os.path.isdir(target):
                    self.send_json({'ok': False, 'error': f'File not found: {path}'}, 404)
                    return
                with open(target, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read(50000)
                self.send_json({'ok': True, 'tool': 'read_file', 'path': path, 'content': content})

            elif tool_name == 'list_directory':
                path = args.get('path', '.').strip()
                target = os.path.abspath(os.path.join(DIRECTORY, path)) if not os.path.isabs(path) else path
                if not os.path.exists(target) or not os.path.isdir(target):
                    self.send_json({'ok': False, 'error': f'Directory not found: {path}'}, 404)
                    return
                entries = []
                for item in os.listdir(target):
                    ipath = os.path.join(target, item)
                    entries.append({
                        'name': item,
                        'is_dir': os.path.isdir(ipath),
                        'size': os.path.getsize(ipath) if os.path.isfile(ipath) else 0
                    })
                self.send_json({'ok': True, 'tool': 'list_directory', 'path': path, 'entries': entries})

            else:
                self.send_json({'ok': False, 'error': f'Unknown tool: {tool_name}'}, 404)

        except subprocess.TimeoutExpired:
            self.send_json({'ok': False, 'error': f'Tool execution timed out ({tool_name})'}, 504)
        except Exception as e:
            self.send_json({'ok': False, 'error': str(e)}, 500)

    def handle_mcp_servers(self):
        cfg = load_hub_config()
        servers = cfg.get('mcp', {}).get('servers', [])
        self.send_json({'ok': True, 'servers': servers})

    def handle_save_mcp_servers(self):
        body = self.read_json_body()
        servers = body.get('servers', [])
        cfg = load_hub_config()
        if 'mcp' not in cfg:
            cfg['mcp'] = {}
        cfg['mcp']['servers'] = servers
        save_hub_config_to_disk(cfg)
        self.send_json({'ok': True, 'servers': servers})

    def handle_test_mcp_server(self):
        body = self.read_json_body()
        name = body.get('name', '').strip()
        transport = body.get('transport', 'stdio').strip()
        cmd = body.get('command', '').strip()

        if not cmd:
            self.send_json({'ok': False, 'error': 'No command or URL provided'}, 400)
            return

        if transport == 'sse':
            try:
                req = urllib.request.Request(cmd, headers={"User-Agent": DEFAULT_USER_AGENT})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    self.send_json({'ok': True, 'status': resp.status, 'message': f'Connected to SSE endpoint ({resp.status})'})
            except Exception as e:
                self.send_json({'ok': False, 'error': f'Could not reach SSE endpoint: {str(e)}'}, 502)
        else:
            # Test stdio by spawning with --help or version
            try:
                test_cmd = cmd.split()
                proc = subprocess.run(test_cmd, capture_output=True, text=True, timeout=5, shell=True)
                self.send_json({'ok': True, 'message': f'Server responded (exit code {proc.returncode})'})
            except Exception as e:
                self.send_json({'ok': False, 'error': f'Failed to execute command: {str(e)}'}, 500)

    def handle_rag_query(self):
        body = self.read_json_body()
        query = body.get('query', '').strip()
        documents = body.get('documents', [])
        text_corpus = body.get('text', '').strip()
        chunk_size = int(body.get('chunk_size', 512))
        chunk_overlap = int(body.get('chunk_overlap', 64))
        top_k = int(body.get('top_k', 4))
        min_score = float(body.get('min_score', 0.60))
        embed_endpoint = body.get('embed_endpoint', 'http://localhost:11434/api/embeddings')
        embed_model = body.get('embed_model', 'nomic-embed-text')

        if not query:
            self.send_json({'ok': False, 'error': 'No query provided'}, 400)
            return

        all_chunks = []
        if isinstance(documents, list):
            for doc in documents:
                if isinstance(doc, str) and doc.strip():
                    all_chunks.extend(chunk_text(doc, chunk_size, chunk_overlap))
                elif isinstance(doc, dict) and "text" in doc:
                    all_chunks.extend(chunk_text(doc["text"], chunk_size, chunk_overlap))
        if text_corpus:
            all_chunks.extend(chunk_text(text_corpus, chunk_size, chunk_overlap))

        if not all_chunks:
            self.send_json({'ok': True, 'query': query, 'chunks': [], 'method': 'none'})
            return

        # Try Vector Search
        method = "lexical"
        scored_chunks = []
        q_vec = fetch_local_embedding(embed_endpoint, embed_model, query)
        if q_vec:
            method = "vector"
            for idx, ch in enumerate(all_chunks):
                c_vec = fetch_local_embedding(embed_endpoint, embed_model, ch[:1000])
                if c_vec:
                    score = vector_cosine_similarity(q_vec, c_vec)
                else:
                    score = lexical_cosine_similarity(tokenize_words(query), tokenize_words(ch))
                if score >= min_score:
                    scored_chunks.append({"chunk": ch, "score": round(score, 4), "index": idx})
        else:
            # Fallback to lexical TF-IDF cosine similarity
            q_tokens = tokenize_words(query)
            for idx, ch in enumerate(all_chunks):
                c_tokens = tokenize_words(ch)
                score = lexical_cosine_similarity(q_tokens, c_tokens)
                if score >= min_score or len(all_chunks) <= top_k:
                    scored_chunks.append({"chunk": ch, "score": round(score, 4), "index": idx})

        scored_chunks.sort(key=lambda x: x["score"], reverse=True)
        record_bionic_audit("RAG_QUERY", f"Query '{query[:30]}' retrieved {min(top_k, len(scored_chunks))} chunks via {method}")
        self.send_json({
            'ok': True,
            'query': query,
            'method': method,
            'total_chunks': len(all_chunks),
            'results': scored_chunks[:top_k]
        })

    # ==========================================
    # Web Search & Scrape Endpoints (Airgap Enforced)
    # ==========================================
    def handle_web_search(self):
        cfg = load_hub_config()
        if cfg.get('bionic', {}).get('strict_airgap', False):
            record_bionic_audit("AIRGAP_BLOCK", "Blocked web search query due to strict airgap policy")
            self.send_json({'ok': False, 'error': 'Blocked: Strict Airgap Mode is enabled in Bionic settings. Outbound web search is disallowed.'}, 403)
            return

        body = self.read_json_body()
        query = body.get('query', '').strip()
        count = int(body.get('count', 6))
        if not query:
            self.send_json({'ok': False, 'error': 'No query provided'}, 400)
            return

        results = search_web_ddg(query, max_results=count)
        record_bionic_audit("WEB_SEARCH", f"DuckDuckGo search for '{query[:30]}'")
        self.send_json({'ok': True, 'query': query, 'results': results})

    def handle_web_scrape(self):
        cfg = load_hub_config()
        if cfg.get('bionic', {}).get('strict_airgap', False):
            record_bionic_audit("AIRGAP_BLOCK", "Blocked URL scrape request due to strict airgap policy")
            self.send_json({'ok': False, 'error': 'Blocked: Strict Airgap Mode is enabled in Bionic settings. External URL scraping is disallowed.'}, 403)
            return

        body = self.read_json_body()
        url = body.get('url', '').strip()
        max_chars = int(body.get('max_chars', 8000))
        if not url:
            self.send_json({'ok': False, 'error': 'No URL provided'}, 400)
            return

        result = scrape_url_text(url, max_chars=max_chars)
        record_bionic_audit("WEB_SCRAPE", f"Scraped URL '{url[:40]}'")
        self.send_json(result)

    # ==========================================
    # Ollama Proxies & SSE Model Pulling
    # ==========================================
    def proxy_ollama_tags(self, host):
        try:
            req = urllib.request.Request(f"{host}/api/tags", headers={"User-Agent": DEFAULT_USER_AGENT})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                self.send_json(data)
        except Exception as e:
            self.send_json({'models': [], 'error': str(e)}, 502)

    def handle_ollama_pull(self):
        body = self.read_json_body()
        model_name = body.get('name', '').strip()
        host = body.get('host', 'http://localhost:11434').rstrip('/')
        if not model_name:
            self.send_json({'ok': False, 'error': 'No model name provided'}, 400)
            return

        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Connection', 'close')
        self.end_headers()

        try:
            pull_payload = json.dumps({"name": model_name, "stream": True}).encode('utf-8')
            req = urllib.request.Request(
                f"{host}/api/pull",
                data=pull_payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=3600) as resp:
                for line in resp:
                    if line:
                        chunk_str = line.decode('utf-8').strip()
                        self.wfile.write(f"data: {chunk_str}\n\n".encode('utf-8'))
                        self.wfile.flush()
        except Exception as e:
            err_payload = json.dumps({'error': str(e)})
            try:
                self.wfile.write(f"data: {err_payload}\n\n".encode('utf-8'))
                self.wfile.flush()
            except Exception:
                pass

    def handle_ollama_delete(self):
        body = self.read_json_body()
        model_name = body.get('name', '').strip()
        host = body.get('host', 'http://localhost:11434').rstrip('/')
        if not model_name:
            self.send_json({'ok': False, 'error': 'No model name provided'}, 400)
            return
        try:
            del_payload = json.dumps({"name": model_name}).encode('utf-8')
            req = urllib.request.Request(
                f"{host}/api/delete",
                data=del_payload,
                headers={"Content-Type": "application/json"},
                method='DELETE'
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.send_json({'ok': True, 'name': model_name})
        except Exception as e:
            self.send_json({'ok': False, 'error': str(e)}, 500)

    def handle_ollama_show(self):
        body = self.read_json_body()
        model_name = body.get('name', '').strip()
        host = body.get('host', 'http://localhost:11434').rstrip('/')
        if not model_name:
            self.send_json({'ok': False, 'error': 'No model name provided'}, 400)
            return
        try:
            show_payload = json.dumps({"name": model_name}).encode('utf-8')
            req = urllib.request.Request(
                f"{host}/api/show",
                data=show_payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                self.send_json({'ok': True, 'details': data})
        except Exception as e:
            self.send_json({'ok': False, 'error': str(e)}, 500)

    # ==========================================
    # LM Studio Proxies & Ping
    # ==========================================
    def handle_lmstudio_ping(self, host):
        t0 = time.time()
        try:
            url = f"{host}/v1/models" if not host.endswith('/v1') else f"{host}/models"
            req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                elapsed_ms = round((time.time() - t0) * 1000, 1)
                models = [m.get('id', '') for m in data.get('data', [])] if 'data' in data else []
                self.send_json({'ok': True, 'status': 'online', 'latency_ms': elapsed_ms, 'models': models})
        except Exception as e:
            elapsed_ms = round((time.time() - t0) * 1000, 1)
            self.send_json({'ok': False, 'status': 'offline', 'latency_ms': elapsed_ms, 'error': str(e)}, 200)

    def handle_agy_models(self):
        global agy_models_cache
        now = time.time()
        if agy_models_cache["models"] and (now - agy_models_cache["timestamp"] < 60):
            self.send_json({'ok': True, 'models': agy_models_cache["models"], 'cached': True})
            return
        try:
            res = subprocess.run(['agy', 'models'], capture_output=True, text=True, timeout=8, shell=True)
            lines = res.stdout.strip().splitlines()
            models = []
            for line in lines:
                line = line.strip()
                if not line or 'Fetching available models' in line:
                    continue
                parts = line.split('\t')
                if len(parts) >= 2:
                    models.append({'id': parts[0].strip(), 'label': parts[1].strip()})
                elif len(parts) == 1 and parts[0].strip():
                    models.append({'id': parts[0].strip(), 'label': parts[0].strip()})
            if models:
                agy_models_cache["timestamp"] = now
                agy_models_cache["models"] = models
            self.send_json({'ok': True, 'models': models, 'cached': False})
        except Exception as e:
            if agy_models_cache["models"]:
                self.send_json({'ok': True, 'models': agy_models_cache["models"], 'stale': True})
            else:
                self.send_json({'ok': False, 'error': str(e), 'models': []}, 500)

    def proxy_lmstudio_models(self, host):
        try:
            url = f"{host}/v1/models" if not host.endswith('/v1') else f"{host}/models"
            req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                self.send_json(data)
        except Exception as e:
            self.send_json({'data': [], 'error': str(e)}, 502)

    def proxy_lmstudio_chat(self):
        body = self.read_json_body()
        host = body.get('host', 'http://localhost:1234').rstrip('/')
        url = f"{host}/v1/chat/completions" if not host.endswith('/v1') else f"{host}/chat/completions"
        payload = body.get('payload', {})

        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Connection', 'close')
        self.end_headers()

        try:
            data_bytes = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={"Content-Type": "application/json", "User-Agent": DEFAULT_USER_AGENT}
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                for line in resp:
                    if line:
                        self.wfile.write(line)
                        self.wfile.flush()
        except Exception as e:
            err_payload = json.dumps({'error': str(e)})
            try:
                self.wfile.write(f"data: {err_payload}\n\n".encode('utf-8'))
                self.wfile.flush()
            except Exception:
                pass

    # ==========================================
    # Server-Side Chat Persistence
    # ==========================================
    def handle_list_chats(self):
        chats = []
        try:
            for fname in os.listdir(CHATS_DIR):
                if fname.endswith('.json'):
                    filepath = os.path.join(CHATS_DIR, fname)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            chats.append({
                                'id': data.get('id', fname[:-5]),
                                'title': data.get('title', 'Untitled Chat'),
                                'pinned': data.get('pinned', False),
                                'updated': data.get('updated', os.path.getmtime(filepath)),
                                'model': data.get('model', ''),
                                'engine': data.get('engine', 'ollama'),
                                'messageCount': len(data.get('messages', []))
                            })
                    except Exception:
                        pass
        except Exception as e:
            self.send_json({'ok': False, 'error': str(e)}, 500)
            return

        chats.sort(key=lambda c: c.get('updated', 0), reverse=True)
        self.send_json({'ok': True, 'chats': chats})

    def handle_get_chat(self, chat_id):
        safe_id = "".join(c for c in chat_id if c.isalnum() or c in ('-', '_'))
        filepath = os.path.join(CHATS_DIR, f"{safe_id}.json")
        if not os.path.exists(filepath):
            self.send_json({'ok': False, 'error': 'Chat not found'}, 404)
            return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.send_json({'ok': True, 'chat': data})
        except Exception as e:
            self.send_json({'ok': False, 'error': str(e)}, 500)

    def handle_save_chat(self):
        body = self.read_json_body()
        chat_id = body.get('id', '').strip()
        if not chat_id:
            chat_id = str(uuid.uuid4())
            body['id'] = chat_id

        safe_id = "".join(c for c in chat_id if c.isalnum() or c in ('-', '_'))
        filepath = os.path.join(CHATS_DIR, f"{safe_id}.json")

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(body, f, indent=2, ensure_ascii=False)
            self.send_json({'ok': True, 'id': safe_id})
        except Exception as e:
            self.send_json({'ok': False, 'error': str(e)}, 500)

    def handle_delete_chat(self):
        body = self.read_json_body()
        chat_id = body.get('id', '').strip()
        if not chat_id:
            self.send_json({'ok': False, 'error': 'No chat ID provided'}, 400)
            return

        safe_id = "".join(c for c in chat_id if c.isalnum() or c in ('-', '_'))
        filepath = os.path.join(CHATS_DIR, f"{safe_id}.json")

        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                self.send_json({'ok': True, 'id': safe_id})
            except Exception as e:
                self.send_json({'ok': False, 'error': str(e)}, 500)
        else:
            self.send_json({'ok': True, 'id': safe_id, 'note': 'File did not exist'})

    # ==========================================
    # PowerShell & Antigravity (agy) Execution
    # ==========================================
    def handle_cancel(self):
        body = self.read_json_body()
        proc_id = body.get('procId')
        killed = []
        with active_procs_lock:
            if proc_id and proc_id in active_procs:
                p = active_procs.pop(proc_id)
                try:
                    p.kill()
                    killed.append(proc_id)
                except Exception:
                    pass
            elif not proc_id:
                for pid, p in list(active_procs.items()):
                    try:
                        p.kill()
                        killed.append(pid)
                    except Exception:
                        pass
                active_procs.clear()

        self.send_json({'ok': True, 'killed': killed})

    def handle_execution(self):
        body = self.read_json_body()
        stream = body.get('stream', True)
        pipe_input = body.get('pipeInput', '').strip()
        proc_id = body.get('procId', str(uuid.uuid4()))
        cwd = body.get('cwd', '').strip()
        exec_cwd = cwd if (cwd and os.path.exists(cwd)) else DIRECTORY

        if self.path == '/api/agy':
            prompt = body.get('prompt', '').strip()
            continue_session = body.get('continueSession', False)
            effort = body.get('effort', '').strip()
            mode = body.get('mode', '').strip()
            model = body.get('model', '').strip()
            max_steps = str(body.get('maxSteps', '')).strip()

            if not prompt and not pipe_input and not continue_session:
                self.send_json({'ok': False, 'output': 'No prompt or input provided.'}, 400)
                return

            flags = []
            if continue_session:
                flags.append('-c')
            if effort in ('low', 'medium', 'high'):
                flags.extend(['--effort', effort])
            elif model and any(m in model for m in ('3.8-flash', '3.7-flash', '3.6-flash', '3.1-pro')):
                flags.extend(['--effort', 'medium'])
            if mode in ('plan', 'accept-edits'):
                flags.extend(['--mode', mode])
            if model:
                flags.extend(['--model', model])
            if max_steps and max_steps.isdigit():
                flags.extend(['--max-steps', max_steps])
            if cwd and os.path.exists(cwd):
                flags.extend(['-C', cwd])

            flags_str = (' ' + ' '.join(flags)) if flags else ''

            if pipe_input:
                escaped_pipe = pipe_input.replace("'", "''")
                if prompt:
                    ps_script = f"@'\n{escaped_pipe}\n'@ | agy{flags_str} -p {json.dumps(prompt)}"
                else:
                    ps_script = f"@'\n{escaped_pipe}\n'@ | agy{flags_str} -p 'Process the piped input.'"
            else:
                ps_script = f"agy{flags_str} -p {json.dumps(prompt)}"

            cmd = ['powershell.exe', '-ExecutionPolicy', 'Bypass', '-Command', ps_script]

        else:  # /api/ps or /api/exec
            command = body.get('command', '').strip()
            if not command:
                self.send_json({'ok': False, 'output': 'No command provided.'}, 400)
                return

            if pipe_input:
                escaped_pipe = pipe_input.replace("'", "''")
                ps_script = f"@'\n{escaped_pipe}\n'@ | {command}"
            else:
                ps_script = command

            cmd = ['powershell.exe', '-ExecutionPolicy', 'Bypass', '-Command', ps_script]

        if stream:
            self.stream_process(cmd, proc_id, exec_cwd)
        else:
            self.run_process_sync(cmd, exec_cwd)

    def stream_process(self, cmd, proc_id, exec_cwd):
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Connection', 'close')
        self.end_headers()

        def sse_send(event_dict):
            try:
                line = f"data: {json.dumps(event_dict)}\n\n"
                self.wfile.write(line.encode('utf-8'))
                self.wfile.flush()
                return True
            except Exception:
                return False

        sse_send({'type': 'start', 'procId': proc_id})

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=exec_cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1
            )
        except Exception as e:
            sse_send({'type': 'error', 'text': f'Failed to launch process: {str(e)}'})
            sse_send({'type': 'done', 'code': -1})
            return

        with active_procs_lock:
            active_procs[proc_id] = proc

        def reader(stream_pipe, stream_type):
            try:
                for line in iter(stream_pipe.readline, ''):
                    if not line:
                        break
                    if not sse_send({'type': stream_type, 'text': line}):
                        break
            except Exception:
                pass
            finally:
                stream_pipe.close()

        t_out = threading.Thread(target=reader, args=(proc.stdout, 'stdout'))
        t_err = threading.Thread(target=reader, args=(proc.stderr, 'stderr'))
        t_out.daemon = True
        t_err.daemon = True
        t_out.start()
        t_err.start()

        t_out.join()
        t_err.join()
        retcode = proc.wait()

        with active_procs_lock:
            active_procs.pop(proc_id, None)

        sse_send({'type': 'done', 'code': retcode})

    def run_process_sync(self, cmd, exec_cwd):
        try:
            proc = subprocess.run(
                cmd,
                cwd=exec_cwd,
                capture_output=True,
                text=True,
                timeout=120,
                encoding='utf-8',
                errors='replace'
            )
            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()
            output = stdout if stdout else stderr
            self.send_json({
                'ok': proc.returncode == 0,
                'output': output,
                'code': proc.returncode
            })
        except subprocess.TimeoutExpired:
            self.send_json({'ok': False, 'output': 'Execution timed out after 120 seconds.'}, 504)
        except Exception as err:
            self.send_json({'ok': False, 'output': f'Error executing command: {str(err)}'}, 500)

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    server = http.server.ThreadingHTTPServer(('0.0.0.0', PORT), EasyDashHandler)
    print("=======================================================")
    print("[EasyDash] Server & Open WebUI Suite Ready")
    print(f" Local Web URL:   http://localhost:{PORT}")
    print(f" Web Search API:  http://localhost:{PORT}/api/web/search")
    print(f" Web Scraper API: http://localhost:{PORT}/api/web/scrape")
    print(f" Bionic RAG API:  http://localhost:{PORT}/api/rag/query")
    print(f" Hub Config API:  http://localhost:{PORT}/api/config")
    print(f" LM Studio Ping:  http://localhost:{PORT}/api/lmstudio/ping")
    print(f" Ollama Proxy:    http://localhost:{PORT}/api/ollama/tags")
    print(f" Chats Storage:   http://localhost:{PORT}/api/chats")
    print(f" PowerShell API:  http://localhost:{PORT}/api/ps")
    print(f" Antigravity API: http://localhost:{PORT}/api/agy")
    print(f" Directory:       {DIRECTORY}")
    print("=======================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping EasyDash server...")
        server.server_close()
