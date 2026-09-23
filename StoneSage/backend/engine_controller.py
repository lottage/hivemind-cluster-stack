import json
import logging
import re
import socket
import subprocess
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from typing import Generator, Dict, Any, List

logger = logging.getLogger("StoneSage.EngineController")

def engine_registry() -> Dict[str, Dict[str, Any]]:
    """Engines from config.json (URLs) and the live system profile (GPU, model, systemd unit). Nothing hardcoded."""
    import system_profile
    from urllib.parse import urlparse
    cfg = system_profile.load_cfg()
    prof = system_profile.get_profile(cfg)
    reg = {}
    for role, key, purpose in system_profile.ROLES:
        url = cfg.get("cluster", {}).get(key)
        if not url:
            continue
        u = urlparse(url)
        eng = prof.get("engines", {}).get(role) or {}
        gpu = eng.get("gpu") or {}
        device = gpu.get("name") or ("CPU" if eng.get("offloaded") else "unknown")
        reg[role] = {
            "port": u.port, "host": u.hostname,
            "service": eng.get("unit") or f"llama-{role}",
            "device": device,
            "role": f"{purpose} ({eng['model']})" if eng.get("model") else purpose,
            "is_local": True,
        }
    return reg


def _is_valid_service_name(service_name: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9\-]+$", service_name))

def probe_engine_health(host: str, port: int, timeout: float = 1.0) -> dict:
    """Probes engine health via TCP and HTTP GET /health."""
    start_time = time.time()
    try:
        url = f"http://{host}:{port}/health"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.getcode()
            if status == 200:
                latency_ms = (time.time() - start_time) * 1000
                return {"online": True, "status": "ok", "latency_ms": latency_ms}
    except Exception as e:
        logger.debug(f"Health probe failed for {host}:{port}: {e}")
        pass
    return {"online": False, "status": "error", "latency_ms": 0.0}

def fetch_engine_props(host: str, port: int, timeout: float = 1.5) -> dict:
    """Fetches engine properties via GET /props."""
    try:
        url = f"http://{host}:{port}/props"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode('utf-8'))
                return {
                    "model_path": data.get("model_path", ""),
                    "model_alias": data.get("model_alias", ""),
                    "model_ftype": data.get("model_ftype", ""),
                    "total_slots": data.get("total_slots", 0),
                    "modalities": data.get("modalities", {}),
                    "chat_template_caps": data.get("chat_template_caps", {}),
                    "n_ctx": data.get("default_generation_settings", {}).get("n_ctx", 0),
                    "raw": data
                }
    except Exception as e:
        logger.debug(f"Props fetch failed for {host}:{port}: {e}")
        return {"error": str(e)}
    return {"error": "Unknown error"}

def fetch_engine_slots(host: str, port: int, timeout: float = 1.5) -> list:
    """Fetches engine slots via GET /slots."""
    try:
        url = f"http://{host}:{port}/slots"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode('utf-8'))
                if isinstance(data, list):
                    return data
    except Exception as e:
        logger.debug(f"Slots fetch failed for {host}:{port}: {e}")
    return []

def parse_prometheus_metrics(text: str) -> dict:
    """Parses Prometheus exposition format text into a flat dict."""
    metrics = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(" ", 1)
        if len(parts) == 2:
            key, val_str = parts
            try:
                if "." in val_str or "e" in val_str.lower():
                    metrics[key] = float(val_str)
                else:
                    metrics[key] = int(val_str)
            except ValueError:
                pass
    return metrics

def fetch_engine_metrics(host: str, port: int, timeout: float = 1.5) -> dict:
    """Fetches engine metrics via GET /metrics."""
    try:
        url = f"http://{host}:{port}/metrics"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.getcode() == 200:
                text = response.read().decode('utf-8')
                return parse_prometheus_metrics(text)
    except Exception as e:
        logger.debug(f"Metrics fetch failed for {host}:{port}: {e}")
    return {}

def build_engine_state(engine_key: str) -> dict:
    """Builds a unified engine state dictionary."""
    registry = engine_registry()
    if engine_key not in registry:
        return {"error": f"Unknown engine key: {engine_key}"}
    
    config = registry[engine_key]
    host = config["host"]
    port = config["port"]
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        f_health = executor.submit(probe_engine_health, host, port)
        f_props = executor.submit(fetch_engine_props, host, port)
        f_slots = executor.submit(fetch_engine_slots, host, port)
        f_metrics = executor.submit(fetch_engine_metrics, host, port)
        
        health = f_health.result()
        props = f_props.result()
        slots = f_slots.result()
        metrics = f_metrics.result()
        
    return {
        "key": engine_key,
        "host": host,
        "port": port,
        "device": config["device"],
        "role": config["role"],
        "service": config["service"],
        "online": health.get("online", False),
        "latency_ms": health.get("latency_ms", 0.0),
        "model": {
            "path": props.get("model_path", ""),
            "alias": props.get("model_alias", ""),
            "quantization": props.get("model_ftype", ""),
            "modalities": props.get("modalities", {}),
        },
        "slots": slots,
        "metrics": metrics,
        "props": props,
    }

def build_all_engine_states() -> dict:
    """Builds state for all registered engines in parallel."""
    states = {}
    registry = engine_registry()
    with ThreadPoolExecutor(max_workers=max(len(registry), 1)) as executor:
        futures = {executor.submit(build_engine_state, key): key for key in registry}
        for future in futures:
            key = futures[future]
            states[key] = future.result()
            
    return {
        "engines": states,
        "timestamp": time.time()
    }

def build_dynamic_engine_state(host: str, port: int, name: str = "dynamic") -> dict:
    """Builds state for an arbitrary dynamic engine (LM Studio, llama-server, or any OpenAI-compat server)."""
    models_data = {}
    model_alias = ""
    model_path = ""
    model_context = 0

    # Attempt 1: LM Studio native API (/api/v1/models) — has loaded_instances detail
    try:
        url = f"http://{host}:{port}/api/v1/models"
        req = urllib.request.Request(url, headers={"User-Agent": "StoneSage-EngineConsole"})
        with urllib.request.urlopen(req, timeout=1.5) as response:
            if response.getcode() == 200:
                models_data = json.loads(response.read().decode('utf-8'))
                raw_models = models_data.get("models", models_data.get("data", []))
                loaded = [m for m in raw_models if m.get("loaded_instances")]
                if loaded:
                    m = loaded[0]
                    model_alias = m.get("key") or m.get("display_name") or m.get("id", "")
                    model_path = m.get("path", "")
                    inst = m.get("loaded_instances", [])[0] if m.get("loaded_instances") else {}
                    model_context = inst.get("config", {}).get("context_length", m.get("max_context_length", 0))
    except Exception:
        pass

    # Attempt 2: OpenAI-compatible /v1/models — fallback
    if not model_alias:
        try:
            url = f"http://{host}:{port}/v1/models"
            req = urllib.request.Request(url, headers={"User-Agent": "StoneSage-EngineConsole"})
            with urllib.request.urlopen(req, timeout=1.5) as response:
                if response.getcode() == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    model_list = data.get("data", [])
                    if model_list:
                        model_alias = model_list[0].get("id", "")
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=4) as executor:
        f_health = executor.submit(probe_engine_health, host, port)
        f_props = executor.submit(fetch_engine_props, host, port)
        f_slots = executor.submit(fetch_engine_slots, host, port)
        f_metrics = executor.submit(fetch_engine_metrics, host, port)

        health = f_health.result()
        props = f_props.result()
        slots = f_slots.result()
        metrics = f_metrics.result()

    # Overlay props data if LM Studio didn't provide it
    if not model_alias:
        model_alias = props.get("model_alias", "")
    if not model_path:
        model_path = props.get("model_path", "")

    return {
        "key": name,
        "host": host,
        "port": port,
        "device": "Roaming / Dynamic",
        "role": "Dynamic Node",
        "service": "unknown",
        "online": health.get("online", False),
        "latency_ms": health.get("latency_ms", 0.0),
        "model": {
            "path": model_path,
            "alias": model_alias,
            "quantization": props.get("model_ftype", ""),
            "modalities": props.get("modalities", {}),
            "context": model_context,
        },
        "slots": slots,
        "metrics": metrics,
        "props": props,
        "is_dynamic": True
    }

def reload_service(service_name: str, ssh_host: str = "192.168.1.105", ssh_user: str = "austin") -> dict:
    """Restarts a systemd service via SSH and polls for health."""
    if not _is_valid_service_name(service_name):
        return {"ok": False, "error": "Invalid service name"}
        
    start_time = time.time()
    cmd = ["ssh", f"{ssh_user}@{ssh_host}", f"sudo systemctl restart {service_name}.service"]
    
    try:
        subprocess.run(cmd, timeout=35, check=True, capture_output=True)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "SSH command timed out"}
    except subprocess.CalledProcessError as e:
        return {"ok": False, "error": f"SSH command failed: {e.stderr.decode()}"}
        
    # Poll for health
    engine_key = None
    registry = engine_registry()
    for k, v in registry.items():
        if v["service"] == service_name and v["host"] == ssh_host:
            engine_key = k
            break
            
    if not engine_key:
        return {"ok": True, "restart_time_ms": (time.time() - start_time) * 1000, "new_state": {}}
        
    config = registry[engine_key]
    host = config["host"]
    port = config["port"]
    
    # Poll up to 30 seconds
    for _ in range(60):
        health = probe_engine_health(host, port, timeout=1.0)
        if health["online"]:
            break
        time.sleep(0.5)
        
    new_state = build_engine_state(engine_key)
    return {
        "ok": True,
        "restart_time_ms": (time.time() - start_time) * 1000,
        "new_state": new_state
    }

def write_systemd_override(service_name: str, overrides: dict, ssh_host: str = "192.168.1.105", ssh_user: str = "austin") -> dict:
    """Writes a systemd override file via SSH."""
    # TODO: Implement this stub
    if not _is_valid_service_name(service_name):
        return {"ok": False, "error": "Invalid service name"}
    return {"ok": False, "error": "Not implemented"}

def stream_debug_completion(host: str, port: int, prompt: str, params: dict = None) -> Generator[dict, None, None]:
    """Streams a completion request yielding SSE data."""
    if params is None:
        params = {}
        
    payload = {
        "prompt": prompt,
        "stream": True,
        "timings_per_token": True,
        "post_sampling_probs": True,
        "n_probs": 5,
        "n_predict": 512,
    }
    payload.update(params)
    
    url = f"http://{host}:{port}/completion"
    req = urllib.request.Request(
        url, 
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            for line in response:
                line_str = line.decode('utf-8').strip()
                if not line_str:
                    continue
                if line_str.startswith("data:"):
                    data_str = line_str[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        yield json.loads(data_str)
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        logger.error(f"Stream completion failed: {e}")

def fetch_journal_logs(service_name: str, lines: int = 100, ssh_host: str = "192.168.1.105", ssh_user: str = "austin") -> list:
    """Fetches journalctl logs via SSH."""
    if not _is_valid_service_name(service_name):
        return ["Invalid service name"]
        
    cmd = [
        "ssh", 
        f"{ssh_user}@{ssh_host}", 
        f"journalctl -u {service_name}.service -n {lines} --no-pager"
    ]
    
    try:
        result = subprocess.run(cmd, timeout=10, capture_output=True, text=True, check=True)
        return result.stdout.splitlines()
    except subprocess.TimeoutExpired:
        return ["Error: SSH command timed out"]
    except subprocess.CalledProcessError as e:
        return [f"Error: SSH command failed: {e.stderr}"]
