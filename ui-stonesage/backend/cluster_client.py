"""
Dual-GPU Cluster, Qdrant Vector Brain & Frontier Provider Client for StoneSage
Bridges the 14B Coordinator (:8001), 3B Worker (:8002), BGE Embedder (:8003),
Qdrant Memory (:6333), and external frontier APIs (OpenRouter, OpenAI, Anthropic, Gemini).
"""

import json
import urllib.request
import urllib.error
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional, Generator, Tuple

class ClusterClient:
    def __init__(self, config: Dict[str, Any]):
        self.cluster_cfg = config.get("cluster", {})
        self.external_cfg = config.get("external_providers", {})
        self.coordinator_url = self.cluster_cfg.get("coordinator_url", "http://127.0.0.1:8001/v1")
        self.worker_url = self.cluster_cfg.get("worker_url", "http://127.0.0.1:8002/v1")
        self.embedder_url = self.cluster_cfg.get("embedder_url", "http://127.0.0.1:8003/v1")
        self.mcp_url = self.cluster_cfg.get("mcp_url", "http://127.0.0.1:8765")
        self.qdrant_url = self.cluster_cfg.get("qdrant_url", "http://127.0.0.1:6333")

    def ping_endpoint(self, url: str, path: str = "/models", timeout: float = 2.0) -> Dict[str, Any]:
        """Probe latency and status of an AI endpoint."""
        start = time.perf_counter()
        target = f"{url.rstrip('/')}{path}"
        req = urllib.request.Request(target, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                latency = round((time.perf_counter() - start) * 1000, 1)
                return {"online": resp.status == 200, "latency_ms": latency}
        except Exception as e:
            return {"online": False, "error": str(e)}

    def check_all_nodes(self) -> Dict[str, Any]:
        """Concurrently check status and latency across all local cluster nodes."""
        nodes = {
            "coordinator_14b": (self.coordinator_url, "/models"),
            "worker_3b": (self.worker_url, "/models"),
            "embedder_bge": (self.embedder_url, "/models"),
            "mcp_bridge": (self.mcp_url, "/health"),
            "qdrant_brain": (self.qdrant_url, "/readyz")
        }

        results = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_map = {name: executor.submit(self.ping_endpoint, url, path) for name, (url, path) in nodes.items()}
            for name, future in future_map.items():
                results[name] = future.result()

        return results

    def get_embedding(self, text: str) -> List[float]:
        """Generate 1024-dim dense vector embedding on the RX 6600 XT."""
        # Bound text to < 800 characters to strictly respect BGE 512-token context limit
        safe_text = text[:800] if text else ""
        url = f"{self.embedder_url}/embeddings"
        payload = json.dumps({"input": safe_text, "model": "embedder"}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["data"][0]["embedding"]

    def tokenize(self, text: str) -> List[str]:
        import re
        return re.findall(r"\b[a-zA-Z0-9_\.:-]+\b", text.lower())

    def compute_sparse_vector(self, text: str, k1: float = 1.2, b: float = 0.75, avg_len: float = 100.0) -> Dict[str, Any]:
        from collections import Counter
        import hashlib
        tokens = self.tokenize(text)
        if not tokens:
            return {"indices": [], "values": []}
        counts = Counter(tokens)
        doc_len = len(tokens)
        indices = []
        values = []
        for word, tf in sorted(counts.items()):
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest()[:8], 16) & 0x7FFFFFFF
            tf_weight = (tf * (k1 + 1.0)) / (tf + k1 * (1.0 - b + b * (doc_len / avg_len)))
            indices.append(h)
            values.append(round(float(tf_weight), 4))
        return {"indices": indices, "values": values}

    def search_hybrid(self, query: str, collection_name: str = "obsidian_vault", limit: int = 5, filter_dict: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Hybrid search combining dense BGE embeddings and sparse BM25 vectors via Qdrant Universal Query API and RRF."""
        dense_vec = self.get_embedding(query)
        sparse_vec = self.compute_sparse_vector(query)

        prefetch = [
            {
                "query": dense_vec,
                "using": "dense",
                "limit": limit * 3
            }
        ]
        if sparse_vec["indices"]:
            prefetch.append({
                "query": {"indices": sparse_vec["indices"], "values": sparse_vec["values"]},
                "using": "sparse",
                "limit": limit * 3
            })

        body: Dict[str, Any] = {
            "prefetch": prefetch,
            "query": {"rrf": {}},
            "limit": limit,
            "with_payload": True,
            "params": {"hnsw_ef": 128}
        }
        if filter_dict:
            must_clauses = [{"key": k, "match": {"value": v}} for k, v in filter_dict.items()]
            body["filter"] = {"must": must_clauses}

        query_url = f"{self.qdrant_url}/collections/{collection_name}/points/query"
        try:
            req = urllib.request.Request(query_url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                points = data.get("result", {}).get("points")
                if points is not None:
                    return points
        except Exception:
            pass

        return self.search_memory(query, collection_name=collection_name, limit=limit, filter_dict=filter_dict)

    def search_memory(self, query: str, collection_name: str = "codebase_knowledge", limit: int = 5, filter_dict: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Semantic search against Qdrant using hardware embeddings and Universal Query API (Qdrant 1.19+)."""
        if collection_name == "obsidian_vault":
            return self.search_hybrid(query, collection_name=collection_name, limit=limit, filter_dict=filter_dict)

        vector = self.get_embedding(query)
        query_url = f"{self.qdrant_url}/collections/{collection_name}/points/query"
        body: Dict[str, Any] = {
            "query": vector,
            "limit": limit,
            "with_payload": True,
            "params": {"hnsw_ef": 128}
        }
        if filter_dict:
            must_clauses = [{"key": k, "match": {"value": v}} for k, v in filter_dict.items()]
            body["filter"] = {"must": must_clauses}

        try:
            req = urllib.request.Request(query_url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                points = data.get("result", {}).get("points")
                if points is not None:
                    return points
        except Exception:
            pass

        url = f"{self.qdrant_url}/collections/{collection_name}/points/search"
        payload = json.dumps({"vector": vector, "limit": limit, "with_payload": True}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("result", [])

    def store_memory(self, content: str, collection_name: str = "agent_memories", metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store knowledge or architectural decision into Qdrant."""
        vector = self.get_embedding(content)
        point_id = str(uuid.uuid4())
        point = {
            "id": point_id,
            "vector": vector,
            "payload": {
                "content": content,
                "metadata": metadata or {},
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        url = f"{self.qdrant_url}/collections/{collection_name}/points"
        payload = json.dumps({"points": [point]}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="PUT")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return point_id

    def stream_chat(self, target: str, messages: List[Dict[str, str]], params: Dict[str, Any]) -> Generator[str, None, None]:
        """
        Stream chat completions line-by-line via SSE.
        Supports Local Cluster (14B Coordinator, 3B Worker), Google Gemini (OpenAI-compatible),
        OpenAI, Anthropic, and OpenRouter with graceful local fallback if keys are unconfigured.
        """
        target_lower = target.lower()
        notice = None

        if target_lower in ["worker", "3b", "worker_3b", "qwen-3b"]:
            base_url = self.worker_url
            model_name = "worker"
            headers = {"Content-Type": "application/json"}
        elif target_lower in ["coordinator", "14b", "coordinator_14b", "qwen-14b", "pve-coordinator"]:
            base_url = self.coordinator_url
            model_name = "coordinator"
            headers = {"Content-Type": "application/json"}
        elif "gemini" in target_lower:
            gem_cfg = self.external_cfg.get("gemini", {})
            api_key = gem_cfg.get("api_key", "").strip()
            if api_key:
                base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
                model_name = target
                headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
            else:
                notice = f"\n> [!NOTE]\n> **Model Routing ({target})**: Google Gemini API key not configured in Settings (⚙️). Routing request automatically to your local **14B Coordinator (RX 6750 XT)** with zero token limits!\n\n"
                base_url = self.coordinator_url
                model_name = "coordinator"
                headers = {"Content-Type": "application/json"}
        elif "claude" in target_lower or "anthropic" in target_lower:
            ant_cfg = self.external_cfg.get("anthropic", {})
            api_key = ant_cfg.get("api_key", "").strip()
            if api_key:
                base_url = ant_cfg.get("base_url", "https://api.anthropic.com/v1")
                model_name = target
                headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
            else:
                notice = f"\n> [!NOTE]\n> **Model Routing ({target})**: Anthropic API key not configured in Settings (⚙️). Routing request automatically to your local **14B Coordinator (RX 6750 XT)**.\n\n"
                base_url = self.coordinator_url
                model_name = "coordinator"
                headers = {"Content-Type": "application/json"}
        elif "gpt" in target_lower or "openai" in target_lower or "o3" in target_lower:
            oai_cfg = self.external_cfg.get("openai", {})
            api_key = oai_cfg.get("api_key", "").strip()
            if api_key:
                base_url = oai_cfg.get("base_url", "https://api.openai.com/v1")
                model_name = target
                headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
            else:
                notice = f"\n> [!NOTE]\n> **Model Routing ({target})**: OpenAI API key not configured in Settings (⚙️). Routing request automatically to your local **14B Coordinator (RX 6750 XT)**.\n\n"
                base_url = self.coordinator_url
                model_name = "coordinator"
                headers = {"Content-Type": "application/json"}
        elif "deepseek" in target_lower:
            or_cfg = self.external_cfg.get("openrouter", {})
            api_key = or_cfg.get("api_key", "").strip()
            if api_key:
                base_url = or_cfg.get("base_url", "https://openrouter.ai/api/v1")
                model_name = "deepseek/deepseek-r1"
                headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
            else:
                notice = f"\n> [!NOTE]\n> **Model Routing ({target})**: OpenRouter API key not configured in Settings (⚙️). Routing request automatically to your local **14B Coordinator (RX 6750 XT)**.\n\n"
                base_url = self.coordinator_url
                model_name = "coordinator"
                headers = {"Content-Type": "application/json"}
        else:
            base_url = self.coordinator_url
            model_name = "coordinator"
            headers = {"Content-Type": "application/json"}

        # If fallback notice exists, yield it first
        if notice:
            notice_chunk = {"choices": [{"delta": {"content": notice}}]}
            yield f"data: {json.dumps(notice_chunk)}\n\n"

        # RAG Context Augmentation via hybrid search
        rag_enabled = params.get("rag", True)
        dispatch_messages = list(messages)
        if rag_enabled and dispatch_messages:
            last_user_msg = next((m["content"] for m in reversed(dispatch_messages) if m.get("role") == "user"), "")
            if last_user_msg and len(last_user_msg.strip()) > 4:
                try:
                    # Hybrid search across user notes & thinking dossiers
                    obsidian_matches = self.search_hybrid(last_user_msg.strip()[:300], collection_name="obsidian_vault", limit=2)
                    # Semantic search across homelab hardware & codebase knowledge
                    codebase_matches = self.search_memory(last_user_msg.strip()[:300], collection_name="codebase_knowledge", limit=2)
                    all_matches = (obsidian_matches or []) + (codebase_matches or [])

                    if all_matches:
                        rag_snippets = []
                        for pt in all_matches:
                            payload = pt.get("payload", {})
                            title = payload.get("title") or payload.get("path") or "Knowledge Reference"
                            content = payload.get("content") or payload.get("text") or ""
                            if content and content.strip():
                                rag_snippets.append(f"[{title}]:\n{content.strip()[:450]}")
                        if rag_snippets:
                            rag_context = "\n\n".join(rag_snippets)
                            rag_injection = (
                                f"\n\n[RELEVANT KNOWLEDGE VAULT CONTEXT]:\n{rag_context}\n"
                                f"[END KNOWLEDGE VAULT CONTEXT]\nReference this homelab/knowledge context when answering."
                            )
                            aug_messages = []
                            found_sys = False
                            for m in dispatch_messages:
                                if m.get("role") == "system" and not found_sys:
                                    aug_messages.append({"role": "system", "content": m["content"] + rag_injection})
                                    found_sys = True
                                else:
                                    aug_messages.append(dict(m))
                            if not found_sys:
                                aug_messages.insert(0, {"role": "system", "content": f"You are StoneSage AI, a homelab and coding copilot.{rag_injection}"})
                            dispatch_messages = aug_messages
                except Exception:
                    pass

        # Optimal quantized model sampling invariant
        temp_default = 0.72 if model_name in ["coordinator", "worker"] else 0.4
        url = f"{base_url.rstrip('/')}/chat/completions"
        body = {
            "model": model_name,
            "messages": dispatch_messages,
            "stream": True,
            "temperature": float(params.get("temperature", temp_default)),
            "max_tokens": int(params.get("max_tokens", 4096))
        }
        if model_name in ["coordinator", "worker"]:
            body["min_p"] = float(params.get("min_p", 0.06))
            body["presence_penalty"] = float(params.get("presence_penalty", 0.2))
            body["top_p"] = float(params.get("top_p", 0.95))

        for key in ["top_k", "repetition_penalty", "frequency_penalty"]:
            if key in params and params[key] is not None:
                body[key] = params[key]

        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        has_done = False
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                for line in resp:
                    decoded = line.decode("utf-8", errors="replace")
                    if decoded.strip():
                        if "[DONE]" in decoded:
                            has_done = True
                        yield decoded
        except Exception as e:
            err_obj = {"error": {"message": str(e), "type": "backend_error"}}
            yield f"data: {json.dumps(err_obj)}\n\n"
        finally:
            if not has_done:
                yield "data: [DONE]\n\n"

    def multi_model_arena_query(self, models: List[str], prompt: str) -> Dict[str, str]:
        """Execute concurrent generation across multiple models for side-by-side evaluation."""
        messages = [{"role": "user", "content": prompt}]
        
        def run_model(target: str) -> Tuple[str, str]:
            chunks = []
            for chunk in self.stream_chat(target, messages, {"max_tokens": 1024}):
                if chunk.startswith("data: ") and not "[DONE]" in chunk:
                    try:
                        delta = json.loads(chunk[6:])["choices"][0]["delta"].get("content") or ""
                        if delta:
                            chunks.append(delta)
                    except Exception:
                        pass
            return target, "".join(chunks)

        results = {}
        with ThreadPoolExecutor(max_workers=len(models)) as executor:
            future_to_model = {executor.submit(run_model, m): m for m in models}
            for future in future_to_model:
                try:
                    target, output = future.result()
                    results[target] = output
                except Exception as e:
                    results[future_to_model[future]] = f"Error: {str(e)}"

        return results

    def synthesize_answers(self, prompt: str, answers: Dict[str, str]) -> str:
        """Use the 14B Coordinator on the RX 6750 XT to merge and synthesize multiple answers."""
        combined_text = "\n\n".join([f"### Model Response from [{k}]:\n{v}" for k, v in answers.items()])
        synth_prompt = (
            f"You are a master synthesis arbiter. Two or more AI models answered the following user prompt:\n\n"
            f"USER PROMPT: {prompt}\n\n"
            f"MODEL OUTPUTS:\n{combined_text}\n\n"
            f"Analyze all outputs. Identify the most accurate code, best architecture, and clearest insights. "
            f"Synthesize them into one definitive, optimal, production-grade response."
        )
        messages = [
            {"role": "system", "content": "You are a master code and architecture synthesis engine."},
            {"role": "user", "content": synth_prompt}
        ]
        
        url = f"{self.coordinator_url}/chat/completions"
        body = {"model": "coordinator", "messages": messages, "stream": False, "temperature": 0.2}
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Synthesis error: {str(e)}"

    def signal_preemption(self, reason: str = "interactive_user", in_flight: bool = False) -> Dict[str, Any]:
        """Signal real-time interactive activity to the cluster to pause the 24/7 autonomous loop."""
        try:
            url = f"{self.mcp_url}/api/preemption/signal"
            payload = json.dumps({"reason": reason, "in_flight": in_flight}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"error": str(e), "is_preempted": False}

    def get_preemption_status(self) -> Dict[str, Any]:
        """Check whether the cluster is currently preempted for user activity."""
        try:
            url = f"{self.mcp_url}/api/preemption/status"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"error": str(e), "is_preempted": False}
