"""
Home Assistant REST Client for StoneSage
Queries entities, states, and telemetry from Home Assistant (127.0.0.1:8123)
and executes service calls (climate/Nest control, lights, switches, scenes).
"""

import json
import urllib.request
import urllib.error
import time
from typing import Dict, Any, List, Optional

class HomeAssistantClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8123", token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.token = token.strip()

    def set_token(self, token: str):
        self.token = token.strip()

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def ping(self) -> Dict[str, Any]:
        """Verify connectivity to Home Assistant."""
        start = time.perf_counter()
        req = urllib.request.Request(f"{self.base_url}/api/", headers=self._get_headers())
        try:
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                latency = round((time.perf_counter() - start) * 1000, 1)
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "online": True,
                    "latency_ms": latency,
                    "message": data.get("message", "API running"),
                    "token_valid": True
                }
        except urllib.error.HTTPError as e:
            latency = round((time.perf_counter() - start) * 1000, 1)
            if e.code == 401:
                return {"online": True, "latency_ms": latency, "token_valid": False, "error": "401 Unauthorized (Invalid or missing token)"}
            return {"online": False, "latency_ms": latency, "error": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            return {"online": False, "error": str(e)}

    def get_states(self, domain_filter: Optional[str] = None) -> Dict[str, Any]:
        """Fetch entity states, optionally filtered by domain (e.g. 'climate', 'light')."""
        if not self.token:
            return {"ok": False, "error": "Home Assistant Token not configured", "entities": []}

        req = urllib.request.Request(f"{self.base_url}/api/states", headers=self._get_headers())
        try:
            with urllib.request.urlopen(req, timeout=4) as resp:
                raw_states = json.loads(resp.read().decode("utf-8"))
                filtered = []
                for s in raw_states:
                    entity_id = s.get("entity_id", "")
                    if domain_filter and not entity_id.startswith(f"{domain_filter}."):
                        continue
                    filtered.append({
                        "entity_id": entity_id,
                        "state": s.get("state"),
                        "friendly_name": s.get("attributes", {}).get("friendly_name", entity_id),
                        "attributes": s.get("attributes", {}),
                        "last_updated": s.get("last_updated")
                    })
                return {"ok": True, "entities": filtered, "count": len(filtered)}
        except Exception as e:
            return {"ok": False, "error": str(e), "entities": []}

    def call_service(self, domain: str, service: str, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """Call a Home Assistant service (e.g. climate.set_temperature, light.turn_on)."""
        if not self.token:
            return {"ok": False, "error": "Home Assistant Token not configured"}

        url = f"{self.base_url}/api/services/{domain}/{service}"
        payload = json.dumps(service_data).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=self._get_headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=4) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return {"ok": True, "result": res}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Convenience method returning organized entities for the Sage & Stone dashboard."""
        all_res = self.get_states()
        if not all_res.get("ok"):
            return all_res

        entities = all_res.get("entities", [])
        climate = [e for e in entities if e["entity_id"].startswith("climate.")]
        lights = [e for e in entities if e["entity_id"].startswith("light.")]
        switches = [e for e in entities if e["entity_id"].startswith("switch.")]
        sensors = [e for e in entities if e["entity_id"].startswith("sensor.") and any(k in e["entity_id"] for k in ["temp", "humid", "power", "battery"])]

        return {
            "ok": True,
            "climate": climate,
            "lights": lights,
            "switches": switches,
            "sensors": sensors[:12]  # top 12 relevant sensors
        }
