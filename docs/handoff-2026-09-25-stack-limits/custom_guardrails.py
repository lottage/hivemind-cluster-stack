"""
custom_guardrails.py

LiteLLM custom callback that enforces the two hard limits your local stack
already crashes on if violated:
  - BGE-large embedder (:8003): inputs must stay under ~512 tokens / ~900 chars
  - Vision server (:8004): images must already be <=640px, since the gateway
    can't run Lanczos resizing itself — this fails fast with a clear error
    instead of letting a 500 come back from the vision server opaquely.

Drop this file next to litellm_config.yaml and reference it via
`callbacks: ["custom_guardrails.enforce_local_stack_limits"]`.

Install: pip install litellm Pillow
"""

import base64
import io
from litellm.integrations.custom_logger import CustomLogger
from litellm import ModelResponse

BGE_CHAR_LIMIT = 900  # conservative proxy for ~512 tokens
MAX_VISION_DIM = 640


class LocalStackGuardrails(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        model = data.get("model", "")

        # --- Embedding length guard ---
        if model == "local-embed":
            inputs = data.get("input", [])
            if isinstance(inputs, str):
                inputs = [inputs]
            for text in inputs:
                if len(text) > BGE_CHAR_LIMIT:
                    raise ValueError(
                        f"Embedding input is {len(text)} chars, exceeds the "
                        f"{BGE_CHAR_LIMIT}-char safety ceiling for BGE-large "
                        f"(hard limit is ~512 tokens; the server 500s past this). "
                        f"Chunk the text before sending."
                    )

        # --- Vision frame dimension guard ---
        if model == "local-vision":
            messages = data.get("messages", [])
            for msg in messages:
                content = msg.get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if block.get("type") != "image_url":
                        continue
                    url = block.get("image_url", {}).get("url", "")
                    if not url.startswith("data:image"):
                        continue  # can't inspect remote URLs cheaply; skip
                    try:
                        from PIL import Image

                        b64_data = url.split(",", 1)[1]
                        img_bytes = base64.b64decode(b64_data)
                        img = Image.open(io.BytesIO(img_bytes))
                        if max(img.size) > MAX_VISION_DIM:
                            raise ValueError(
                                f"Vision frame is {img.size}, exceeds the "
                                f"{MAX_VISION_DIM}px max dimension the vision "
                                f"server expects. Resize with Lanczos before "
                                f"sending to keep tokens under 200."
                            )
                    except ImportError:
                        # Pillow not installed — skip the check rather than block traffic
                        pass

        return data


enforce_local_stack_limits = LocalStackGuardrails()
