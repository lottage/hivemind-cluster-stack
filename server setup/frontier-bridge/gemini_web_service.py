#!/usr/bin/env python3
"""
Gemini Web Session Microservice (Port 8086)
Runs on Node 2 (bigserv - LXC 120) alongside Frontier Bridge.
Provides zero-token-cost Gemini Advanced access for homelab cluster via Google One AI Plus subscription.
"""

import os
import sys
import json
import time
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)
from gemini_web_client import GeminiWebClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [GeminiWeb] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("GeminiWeb")

SESSION_FILE = os.environ.get("GEMINI_SESSION_FILE", os.path.join(BACKEND_DIR, "gemini_session.json"))
PORT = int(os.environ.get("GEMINI_WEB_PORT", 8087))

def load_session() -> dict:
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error reading {SESSION_FILE}: {e}")
    # Also check /opt/stonesage/backend/config.json
    ss_conf = "/opt/stonesage/backend/config.json"
    if os.path.exists(ss_conf):
        try:
            with open(ss_conf, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                gw = cfg.get("gemini_web", {})
                if gw.get("psid"):
                    return gw
        except Exception:
            pass
    return {}

def save_session(data: dict):
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

session_data = load_session()
client = GeminiWebClient(
    psid=session_data.get("psid", ""),
    psidts=session_data.get("psidts", ""),
    extra_cookies=session_data.get("extra_cookies", {})
)

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class GeminiWebHandler(BaseHTTPRequestHandler):
    def send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            is_valid, msg = client.validate_session()
            self.send_json({
                "status": "online" if is_valid else "awaiting_cookies",
                "service": "gemini-web-bridge",
                "tier": "Google One AI Plus / Gemini Advanced ($0 token cost)",
                "port": PORT,
                "session_active": is_valid,
                "message": msg,
                "psid_configured": bool(client.psid),
                "psidts_configured": bool(client.psidts)
            })
            return
        self.send_json({"error": "Not Found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            body = json.loads(raw_body)
        except Exception as e:
            self.send_json({"ok": False, "error": f"Invalid JSON: {e}"}, 400)
            return

        if self.path == "/api/cookies":
            psid = body.get("psid", "").strip()
            psidts = body.get("psidts", "").strip()
            extra = body.get("extra_cookies", {})
            if not psid:
                self.send_json({"ok": False, "error": "Missing psid cookie"}, 400)
                return
            client.update_cookies(psid, psidts, extra)
            save_session({"psid": psid, "psidts": psidts, "extra_cookies": extra, "updated_at": time.time()})
            is_valid, msg = client.validate_session(force=True)
            self.send_json({
                "ok": is_valid,
                "session_active": is_valid,
                "message": msg
            })
            return

        elif self.path in ("/api/audit", "/api/frontier/audit"):
            res = client.audit_challenge(body)
            self.send_json(res, 200 if res.get("ok") else 502)
            return

        elif self.path in ("/api/chat", "/api/frontier/chat"):
            prompt = body.get("prompt", "")
            if not prompt:
                self.send_json({"ok": False, "error": "Missing prompt"}, 400)
                return
            res = client.generate_content(prompt)
            self.send_json(res, 200 if res.get("ok") else 502)
            return

        self.send_json({"error": "Endpoint not supported"}, 404)

def run():
    server = ThreadedHTTPServer(("0.0.0.0", PORT), GeminiWebHandler)
    logger.info(f"Gemini Web Bridge listening on http://0.0.0.0:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopping Gemini Web Bridge...")

if __name__ == "__main__":
    run()
