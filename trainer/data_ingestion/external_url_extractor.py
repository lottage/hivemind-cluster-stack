#!/usr/bin/env python3
"""
External URL and Document Extractor
Extracts knowledge from URLs, articles, and external documents,
splits them into clean bounded chunks (< 900 chars to respect BGE embedder limits),
and generates instruction tuning QA pairs.
"""

import os
import re
import json
import urllib.request
from typing import List, Dict, Any, Optional

class ExternalUrlExtractor:
    def __init__(
        self,
        cluster_worker_url: str = "http://127.0.0.1:8002/v1",
        vault_paths: Optional[List[str]] = None
    ):
        self.worker_url = cluster_worker_url
        self.headers = {"User-Agent": "AntigravityClusterTrainer/1.0"}
        self.vault_paths = vault_paths or [
            r"C:\Users\operator\OneDrive\Documents\obsidian",
            "/opt/cluster-bridge/obsidian_vault",
            "/opt/obsidian_vault",
            "./vault_backup"
        ]

    def resolve_obsidian_url(self, url: str) -> Optional[str]:
        """
        Parses an obsidian:// URL or local vault path and reads the markdown content.
        Supports:
          - obsidian://open?vault=obsidian&file=Path%2FTo%2FNote
          - obsidian://open?path=/path/to/note.md
          - CouchDB sync endpoints (:5984)
          - Local relative/absolute markdown paths
        """
        import urllib.parse
        parsed = urllib.parse.urlparse(url)

        if parsed.scheme == "obsidian":
            params = urllib.parse.parse_qs(parsed.query)
            # Direct path parameter
            if "path" in params:
                direct_path = params["path"][0]
                if os.path.exists(direct_path):
                    with open(direct_path, "r", encoding="utf-8", errors="ignore") as f:
                        return f.read()

            # File parameter
            if "file" in params:
                rel_file = params["file"][0]
                if not rel_file.endswith(".md"):
                    rel_file += ".md"

                # Search known vault directories
                for v_dir in self.vault_paths:
                    candidate = os.path.join(v_dir, rel_file)
                    if os.path.exists(candidate):
                        with open(candidate, "r", encoding="utf-8", errors="ignore") as f:
                            return f.read()

                    # Try normalized forward/backward slashes
                    candidate = os.path.join(v_dir, *rel_file.replace("\\", "/").split("/"))
                    if os.path.exists(candidate):
                        with open(candidate, "r", encoding="utf-8", errors="ignore") as f:
                            return f.read()

            # CouchDB fallback for Linux hosts where Windows OneDrive isn't mounted
            try:
                doc_name = params.get("file", [""])[0]
                if doc_name:
                    doc_id = urllib.parse.quote(doc_name if doc_name.endswith(".md") else f"{doc_name}.md", safe="")
                    couch_url = f"http://austin:your_couchdb_password@127.0.0.1:5984/obsidiannotes/{doc_id}"
                    req = urllib.request.Request(couch_url)
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        if "data" in data:
                            return data["data"]
            except Exception:
                pass

        # Check if direct file path exists
        if os.path.exists(url):
            with open(url, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

        return None

    def clean_obsidian_markdown(self, markdown: str) -> str:
        """
        Cleans Obsidian-specific syntax for LLM instruction ingestion:
        - Strips YAML frontmatter
        - Converts wikilinks [[Page Name|Display Text]] -> Display Text
        - Converts wikilinks [[Page Name]] -> Page Name
        - Strips block identifiers (^blockid)
        - Formats callouts
        """
        # Strip YAML frontmatter
        text = re.sub(r"^---\n[\s\S]*?\n---\n", "", markdown)
        # Convert [[Link|Text]] -> Text
        text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
        # Strip block references
        text = re.sub(r"\s+\^[a-zA-Z0-9\-]+$", "", text, flags=re.MULTILINE)
        # Clean callouts: > [!NOTE] -> **Note**:
        text = re.sub(r"^>\s*\[!([A-Za-z_-]+)\]", r"**\1**:", text, flags=re.MULTILINE)
        # Strip residual blockquote symbols
        text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)
        return text.strip()

    def fetch_url(self, url: str) -> str:
        """Fetches raw content from a URL or Obsidian URI."""
        # Handle Obsidian URIs and local files
        if url.startswith("obsidian://") or url.endswith(".md"):
            obs_content = self.resolve_obsidian_url(url)
            if obs_content is not None:
                return obs_content
            raise FileNotFoundError(f"Could not locate Obsidian note for URI: {url}")

        req = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        return raw

    def clean_html_to_markdown(self, html: str) -> str:
        """Converts raw HTML to clean plaintext/markdown."""
        # Strip scripts, styles, headers, footers
        text = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
        text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<nav[\s\S]*?</nav>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<footer[\s\S]*?</footer>", "", text, flags=re.IGNORECASE)
        
        # Replace headings
        for i in range(6, 0, -1):
            text = re.sub(rf"<h{i}[^>]*>([\s\S]*?)</h{i}>", rf"\n\n{'#' * i} \1\n\n", text, flags=re.IGNORECASE)

        # Replace links
        text = re.sub(r'<a\s+(?:[^>]*?\s+)?href="([^"]*)"[^>]*>([\s\S]*?)</a>', r"[\2](\1)", text, flags=re.IGNORECASE)
        # Replace list items
        text = re.sub(r"<li[^>]*>([\s\S]*?)</li>", r"- \1\n", text, flags=re.IGNORECASE)
        # Replace paragraphs and linebreaks
        text = re.sub(r"<p[^>]*>([\s\S]*?)</p>", r"\n\n\1\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        # Strip remaining tags
        text = re.sub(r"<[^>]+>", "", text)
        # Decode basic entities
        text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", "\"")
        # Collapse whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def chunk_text(self, text: str, max_chunk_chars: int = 900) -> List[str]:
        """Splits text into bounded paragraphs under max_chunk_chars."""
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""

        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            if len(current_chunk) + len(p) + 2 <= max_chunk_chars:
                current_chunk += ("\n\n" + p if current_chunk else p)
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                # If paragraph itself exceeds max_chunk_chars, split by sentence
                if len(p) > max_chunk_chars:
                    sentences = re.split(r"(?<=[.?!])\s+", p)
                    sub_chunk = ""
                    for s in sentences:
                        if len(sub_chunk) + len(s) + 1 <= max_chunk_chars:
                            sub_chunk += (" " + s if sub_chunk else s)
                        else:
                            if sub_chunk:
                                chunks.append(sub_chunk)
                            sub_chunk = s[:max_chunk_chars]
                    if sub_chunk:
                        chunks.append(sub_chunk)
                    current_chunk = ""
                else:
                    current_chunk = p

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def synthesize_qa_local(self, chunk: str) -> Optional[Dict[str, str]]:
        """Calls local worker model to synthesize a high-quality Q&A pair from a chunk."""
        prompt = (
            f"Given the technical reference excerpt below, create one high-quality training instruction (Question) "
            f"and a complete, rigorous, and technically accurate answer based strictly on the excerpt.\n\n"
            f"Excerpt:\n\"\"\"\n{chunk}\n\"\"\"\n\n"
            f"Respond ONLY with valid JSON in this exact structure:\n"
            f'{{"question": "...", "answer": "..."}}'
        )

        payload = {
            "model": "worker",
            "messages": [
                {"role": "system", "content": "You are a synthetic dataset generator. Return strictly valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.4,
            "max_tokens": 512
        }

        try:
            req = urllib.request.Request(
                f"{self.worker_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                # Parse JSON block
                json_m = re.search(r"\{[\s\S]*\}", content)
                if json_m:
                    parsed = json.loads(json_m.group(0))
                    if "question" in parsed and "answer" in parsed:
                        return parsed
        except Exception as e:
            # Fallback heuristic QA if local LLM call fails
            lines = [l.strip() for l in chunk.split("\n") if len(l.strip()) > 20]
            if lines:
                return {
                    "question": f"Explain the core concept and technical implications described in: '{lines[0][:80]}...'",
                    "answer": chunk
                }
        return None

    def process_url(self, url: str) -> List[Dict[str, Any]]:
        """Extracts and converts a web URL or Obsidian note URI into QA training items."""
        print(f"[INFO] Fetching URL/Resource: {url}")
        raw = self.fetch_url(url)
        if url.startswith("obsidian://") or url.endswith(".md"):
            markdown = self.clean_obsidian_markdown(raw)
        else:
            markdown = self.clean_html_to_markdown(raw)
        chunks = self.chunk_text(markdown)
        print(f"[INFO] Extracted {len(chunks)} bounded chunks from {url}")

        dataset = []
        for i, chunk in enumerate(chunks[:20]): # Limit to first 20 chunks per URL
            qa = self.synthesize_qa_local(chunk)
            if qa:
                dataset.append({
                    "id": f"URL-{abs(hash(url)) % 100000}-{i:02d}",
                    "source": url,
                    "prompt": qa["question"],
                    "chosen": qa["answer"]
                })
        return dataset

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Extract training data from URLs")
    parser.add_argument("url", help="URL to ingest")
    parser.add_argument("--output", default="./data/processed/url_qa.jsonl")
    args = parser.parse_args()

    extractor = ExternalUrlExtractor()
    items = extractor.process_url(args.url)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item) + "\n")
    print(f"[SUCCESS] Wrote {len(items)} QA items to {args.output}")
