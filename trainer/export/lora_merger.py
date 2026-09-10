#!/usr/bin/env python3
"""
LoRA Merger
Merges a trained LoRA adapter back into the 16-bit base model weights,
producing a consolidated model ready for GGUF conversion.
"""

import os
import sys
import yaml
from typing import Optional

class LoRAMerger:
    def __init__(self, config_path: str = "./config/training_config.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        self.output_dir = self.config["export"].get("output_dir", "./output")
        self.merged_dir = os.path.join(self.output_dir, "merged_16bit")

    def merge(self, base_model_id: str, adapter_path: str, output_path: Optional[str] = None) -> str:
        """Merges LoRA adapter into base model and saves FP16 weights."""
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel

        target_output = output_path or self.merged_dir
        os.makedirs(target_output, exist_ok=True)

        print(f"[INFO] Merging adapter '{adapter_path}' into base model '{base_model_id}'...")
        print("[INFO] Loading base model in float16 on CPU/GPU for clean weight fusion...")

        tokenizer = AutoTokenizer.from_pretrained(adapter_path, trust_remote_code=True)

        base_model = AutoModelForCausalLM.from_pretrained(
            base_model_id,
            torch_dtype=torch.float16,
            device_map="cpu", # CPU merge avoids VRAM fragmentation
            trust_remote_code=True
        )

        model = PeftModel.from_pretrained(base_model, adapter_path)
        print("[INFO] Fusing LoRA weights (merge_and_unload)...")
        merged_model = model.merge_and_unload()

        print(f"[INFO] Saving merged FP16 model to {target_output}...")
        merged_model.save_pretrained(target_output, safe_serialization=True)
        tokenizer.save_pretrained(target_output)

        print(f"[SUCCESS] Merged model successfully saved to: {target_output}")
        return target_output

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Merge LoRA adapter into base model")
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    merger = LoRAMerger()
    merger.merge(args.base_model, args.adapter, args.output)
