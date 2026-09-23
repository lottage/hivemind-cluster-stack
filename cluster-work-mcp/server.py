"""
Universal Model Context Protocol (MCP) Server for Issuing Work to Cluster Models & Agents.
Supports standard JSON-RPC 2.0 stdio (Claude Desktop, Cursor, Antigravity, Continue)
and optional HTTP/SSE mode for web UIs.
"""

import os
import sys
import json
import time
import logging
import argparse
from typing import Dict, Any, Optional

from tools_def import TOOLS
from cluster_client import ClusterClient
from sampling_presets import SAMPLING_PRESETS

# Configure Logging to stderr (Never write logs to stdout in stdio mode!)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [ClusterWorkMCP] %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("ClusterWorkMCP")

client = ClusterClient()

def handle_tool_call(name: str, args: Dict[str, Any]) -> str:
    logger.info(f"Executing tool: {name} with args: {list(args.keys())}")
    try:
        if name == "cluster_execute":
            res = client.execute_model(
                model_target=args.get("model", "coordinator"),
                prompt=args["prompt"],
                system_prompt=args.get("system_prompt"),
                preset=args.get("preset"),
                temperature=args.get("temperature"),
                min_p=args.get("min_p"),
                top_p=args.get("top_p"),
                presence_penalty=args.get("presence_penalty"),
                repetition_penalty=args.get("repetition_penalty"),
                max_tokens=args.get("max_tokens"),
                enable_thinking=args.get("enable_thinking")
            )
            return json.dumps(res, indent=2)

        elif name == "list_available_models":
            res = client.list_models()
            return json.dumps(res, indent=2)

        elif name == "issue_work_to_coordinator":
            res = client.execute_model(
                model_target="coordinator",
                prompt=args["prompt"],
                system_prompt=args.get("system_prompt"),
                preset=args.get("preset", "balanced_architect"),
                temperature=args.get("temperature"),
                min_p=args.get("min_p"),
                max_tokens=args.get("max_tokens", 2048),
                enable_thinking=args.get("enable_thinking", False)
            )
            return json.dumps(res, indent=2)

        elif name == "issue_work_to_worker":
            res = client.execute_model(
                model_target="worker",
                prompt=args["prompt"],
                system_prompt=args.get("system_prompt"),
                preset="high_speed_utility",
                temperature=args.get("temperature", 0.10),
                min_p=args.get("min_p", 0.10),
                max_tokens=args.get("max_tokens", 1024),
                enable_thinking=False
            )
            return json.dumps(res, indent=2)

        elif name == "orchestrate_hybrid_work":
            task = args["task"]
            retrieve_context = args.get("retrieve_context", True)
            force_model = args.get("force_model")
            preset = args.get("preset")

            # Context retrieval
            context_hits = []
            if retrieve_context:
                context_hits = client.search_memory(task, limit=3)

            # Heuristic model selection if not forced
            if force_model:
                target = force_model
            else:
                complex_keywords = ["architect", "system", "prove", "algorithm", "concurrency", "refactor", "security", "design"]
                if any(kw in task.lower() for kw in complex_keywords):
                    target = "coordinator"
                else:
                    target = "worker"

            context_str = ""
            if context_hits and not any("error" in h for h in context_hits):
                context_str = "\nRelevant Homelab Context & Invariants from Qdrant:\n" + "\n".join(
                    f"- {h.get('text', '')}" for h in context_hits
                ) + "\n\n"

            prompt_with_context = context_str + task

            res = client.execute_model(
                model_target=target,
                prompt=prompt_with_context,
                preset=preset or ("balanced_architect" if target == "coordinator" else "high_speed_utility")
            )
            res["hybrid_orchestration"] = {
                "routed_model": target,
                "context_retrieved_count": len(context_hits)
            }
            return json.dumps(res, indent=2)

        elif name == "spawn_cluster_agent":
            res = client.spawn_agent(
                name=args["name"],
                role=args["role"],
                mission=args["mission"],
                system_prompt=args.get("system_prompt"),
                max_iterations=args.get("max_iterations", 5),
                model_preference=args.get("model_preference", "worker")
            )
            return json.dumps(res, indent=2) if isinstance(res, dict) else str(res)

        elif name == "list_cluster_agents":
            res = client.list_agents()
            return json.dumps(res, indent=2) if isinstance(res, (dict, list)) else str(res)

        elif name == "interact_with_agent":
            res = client.interact_agent(args["agent_id"], args["message"])
            return json.dumps(res, indent=2) if isinstance(res, (dict, list)) else str(res)

        elif name == "stop_cluster_agent":
            res = client.stop_agent(args["agent_id"])
            return str(res)

        elif name == "broadcast_to_assembly":
            res = client.broadcast_assembly(
                sender=args["sender"],
                message=args["message"],
                channel=args.get("channel", "general")
            )
            return json.dumps(res, indent=2) if isinstance(res, (dict, list)) else str(res)

        elif name == "read_assembly_channel":
            res = client.read_assembly(
                channel=args.get("channel", "general"),
                limit=args.get("limit", 10)
            )
            return json.dumps(res, indent=2) if isinstance(res, (dict, list)) else str(res)

        elif name == "search_cluster_memory":
            res = client.search_memory(
                query=args["query"],
                limit=args.get("limit", 4),
                collection_name=args.get("collection_name", "codebase_knowledge")
            )
            return json.dumps(res, indent=2)

        elif name == "cluster_health_check":
            res = client.health_check()
            return json.dumps(res, indent=2)

        else:
            return json.dumps({"error": f"Unknown tool: {name}"})

    except Exception as e:
        logger.error(f"Error handling tool {name}: {e}", exc_info=True)
        return json.dumps({"ok": False, "error": str(e)})

def process_jsonrpc(req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = req.get("method")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {
                        "listChanged": False
                    }
                },
                "serverInfo": {
                    "name": "cluster-work-mcp",
                    "version": "1.0.0"
                }
            }
        }

    elif method == "notifications/initialized":
        logger.info("Client completed MCP initialization handshake.")
        return None

    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS
            }
        }

    elif method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        output_text = handle_tool_call(tool_name, arguments)

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": output_text
                    }
                ],
                "isError": False
            }
        }

    else:
        if req_id is not None:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
        return None

def run_stdio():
    """
    Standard JSON-RPC 2.0 loop over stdin/stdout.
    Handles both Content-Length framed packets and raw newline-delimited JSON-RPC.
    """
    logger.info("Cluster Work MCP Server started in STDIO mode.")
    stdin = sys.stdin.buffer

    while True:
        try:
            line = stdin.readline()
            if not line:
                break

            line_str = line.decode("utf-8", errors="replace").strip()
            if not line_str:
                continue

            content_length = None
            framed = False  # reply in the same framing the client used
            if line_str.lower().startswith("content-length:"):
                framed = True
                try:
                    content_length = int(line_str.split(":")[1].strip())
                    # Read empty separator line (\r\n)
                    while True:
                        sep = stdin.readline().decode("utf-8", errors="replace").strip()
                        if not sep:
                            break
                    raw_body = stdin.read(content_length).decode("utf-8", errors="replace")
                except Exception as ex:
                    logger.error(f"Error parsing Content-Length: {ex}")
                    continue
            else:
                raw_body = line_str

            if not raw_body.strip():
                continue

            req = json.loads(raw_body)
            resp = process_jsonrpc(req)

            if resp is not None:
                body_bytes = json.dumps(resp, ensure_ascii=False).encode("utf-8")
                if framed:
                    # Legacy LSP-style framing (some older clients)
                    header = f"Content-Length: {len(body_bytes)}\r\n\r\n".encode("ascii")
                    sys.stdout.buffer.write(header + body_bytes)
                else:
                    # MCP stdio spec: newline-delimited JSON (Claude Code, Claude Desktop)
                    sys.stdout.buffer.write(body_bytes + b"\n")
                sys.stdout.buffer.flush()

        except json.JSONDecodeError as jde:
            logger.error(f"JSON decode error: {jde}")
        except Exception as ex:
            logger.error(f"Unexpected loop exception: {ex}", exc_info=True)

def run_sse(port: int = 8768):
    """
    Optional lightweight HTTP/SSE server for web UIs and remote HTTP MCP clients.
    """
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from socketserver import ThreadingMixIn

    class ThreadedServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    class MCPHttpHandler(BaseHTTPRequestHandler):
        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()

        def do_GET(self):
            if self.path in ("/health", "/status"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "online", "service": "cluster-work-mcp"}).encode("utf-8"))
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self):
            content_length = int(self.headers.get("Content-Length", 0))
            body_str = self.rfile.read(content_length).decode("utf-8", errors="replace")
            try:
                req = json.loads(body_str)
                resp = process_jsonrpc(req)
                resp_bytes = json.dumps(resp or {}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(resp_bytes)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    server = ThreadedServer(("0.0.0.0", port), MCPHttpHandler)
    logger.info(f"Cluster Work MCP Server started in HTTP mode on port {port}.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cluster Work MCP Server")
    parser.add_argument("mode", nargs="?", default="stdio", choices=["stdio", "sse"], help="Server mode (stdio or sse)")
    parser.add_argument("--port", type=int, default=8768, help="Port for SSE/HTTP mode (default: 8768)")
    args = parser.parse_args()

    if args.mode == "sse":
        run_sse(args.port)
    else:
        run_stdio()
