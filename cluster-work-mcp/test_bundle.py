"""
Verification & Test Suite for Cluster Work MCP Bundle.
Validates stdio JSON-RPC framing, tool list discovery, and live cluster execution.
"""

import sys
import json
import time
import subprocess
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_PATH = os.path.join(SCRIPT_DIR, "server.py")

def send_framed_msg(proc, req: dict) -> dict:
    body = json.dumps(req).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    proc.stdin.write(header + body)
    proc.stdin.flush()

    # Read response header
    content_len = 0
    while True:
        line = proc.stdout.readline().decode("utf-8", errors="replace")
        if not line:
            raise EOFError("Server process closed stdout.")
        line_clean = line.strip()
        if line_clean.lower().startswith("content-length:"):
            content_len = int(line_clean.split(":")[1].strip())
        elif line_clean == "":
            if content_len > 0:
                break

    raw_resp = proc.stdout.read(content_len).decode("utf-8", errors="replace")
    return json.loads(raw_resp)

def run_tests():
    print("=== Testing Cluster Work MCP Bundle (STDIO Mode) ===")
    
    # Launch server as subprocess
    proc = subprocess.Popen(
        [sys.executable, SERVER_PATH, "stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=SCRIPT_DIR
    )

    try:
        # 1. Initialize
        print("\n1. Testing 'initialize' handshake...")
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "TestHarness", "version": "1.0"}
            }
        }
        init_resp = send_framed_msg(proc, init_req)
        assert init_resp.get("result", {}).get("serverInfo", {}).get("name") == "cluster-work-mcp", f"Init failed: {init_resp}"
        print("   -> Success! Server returned:", init_resp["result"]["serverInfo"])

        # 2. Tools List
        print("\n2. Testing 'tools/list' discovery...")
        list_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        list_resp = send_framed_msg(proc, list_req)
        tools = list_resp.get("result", {}).get("tools", [])
        tool_names = [t["name"] for t in tools]
        print(f"   -> Discovered {len(tools)} tools:")
        for tn in tool_names:
            print(f"      - {tn}")
        assert "cluster_execute" in tool_names
        assert "list_available_models" in tool_names
        assert "issue_work_to_coordinator" in tool_names
        assert "issue_work_to_worker" in tool_names
        assert "orchestrate_hybrid_work" in tool_names

        # 3. List Available Models Tool Call
        print("\n3. Testing 'list_available_models' tool execution...")
        call_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "list_available_models",
                "arguments": {}
            }
        }
        call_resp = send_framed_msg(proc, call_req)
        raw_text = call_resp["result"]["content"][0]["text"]
        model_data = json.loads(raw_text)
        print("   -> Models and status returned:")
        for m in model_data.get("models", []):
            st = "ONLINE" if m.get("online") else "OFFLINE"
            lat = f"{m.get('latency_ms')}ms" if m.get("latency_ms") else "N/A"
            print(f"      [{st}] {m['name']} ({m['device']}) - Latency: {lat}")

        # 4. Direct Model & Parameter Execution (Worker fast test)
        print("\n4. Testing 'cluster_execute' with Worker model + custom hyperparameters...")
        exec_req = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "cluster_execute",
                "arguments": {
                    "model": "worker",
                    "prompt": "Return a JSON object with keys 'status' ('ok') and 'hardware' ('rx6600xt'). Return ONLY the raw json.",
                    "temperature": 0.10,
                    "min_p": 0.10,
                    "max_tokens": 150
                }
            }
        }
        exec_resp = send_framed_msg(proc, exec_req)
        res_text = exec_resp["result"]["content"][0]["text"]
        exec_data = json.loads(res_text)
        assert exec_data.get("ok") is True, f"Execution failed: {exec_data}"
        perf = exec_data.get("performance", {})
        print(f"   -> Result Model: {exec_data.get('model')}")
        print(f"   -> Generated Output: {exec_data.get('content').strip()[:100]}")
        print(f"   -> Speed: {perf.get('tokens_per_second')} tok/s | Latency: {perf.get('latency_ms')}ms")
        print(f"   -> Cloud Tokens Saved: {perf.get('cloud_tokens_saved')} (Est ${perf.get('est_cloud_cost_saved_usd')} saved)")

        # 5. Direct Model Execution (Coordinator with precise_code preset)
        print("\n5. Testing 'cluster_execute' with Coordinator model + 'precise_code' preset...")
        coord_req = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "cluster_execute",
                "arguments": {
                    "model": "coordinator",
                    "prompt": "Write a 1-line Python lambda that tests if an integer n is prime. Return only the code.",
                    "preset": "precise_code",
                    "max_tokens": 200
                }
            }
        }
        coord_resp = send_framed_msg(proc, coord_req)
        c_text = coord_resp["result"]["content"][0]["text"]
        c_data = json.loads(c_text)
        assert c_data.get("ok") is True, f"Coordinator execution failed: {c_data}"
        c_perf = c_data.get("performance", {})
        print(f"   -> Result Model: {c_data.get('model')}")
        print(f"   -> Generated Code: {c_data.get('content').strip()[:100]}")
        print(f"   -> Speed: {c_perf.get('tokens_per_second')} tok/s | Latency: {c_perf.get('latency_ms')}ms")
        print(f"   -> Cloud Tokens Saved: {c_perf.get('cloud_tokens_saved')}")

        print("\n=== All Tests Passed Successfully! ===")

    finally:
        proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=3)

if __name__ == "__main__":
    run_tests()
