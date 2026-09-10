#!/usr/bin/env python3
"""
GGUF Exporter & Quantizer
Converts merged FP16 models into GGUF format and produces quantized binaries
(Q4_K_M for Worker 80+ t/s, Q8_0 for Coordinator lossless reasoning).
"""

import os
import sys
import yaml
import subprocess
import shutil
from typing import List, Optional

class GGUFExporter:
    def __init__(self, config_path: str = "./config/training_config.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        self.output_dir = self.config["export"].get("output_dir", "./output")
        self.gguf_output_dir = os.path.join(self.output_dir, "gguf")
        os.makedirs(self.gguf_output_dir, exist_ok=True)
        self.llama_cpp_path = self.config["export"].get("llama_cpp_path", "/opt/.unsloth/llama.cpp")

    def find_convert_script(self) -> str:
        """Finds the convert_hf_to_gguf.py script."""
        candidates = [
            os.path.join(self.llama_cpp_path, "convert_hf_to_gguf.py"),
            "/usr/local/bin/convert_hf_to_gguf.py",
            "./llama.cpp/convert_hf_to_gguf.py"
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return candidates[0]

    def find_llama_quantize(self) -> str:
        """Finds the llama-quantize binary."""
        candidates = [
            os.path.join(self.llama_cpp_path, "build/bin/llama-quantize"),
            os.path.join(self.llama_cpp_path, "llama-quantize"),
            "/usr/local/bin/llama-quantize",
            shutil.which("llama-quantize") or ""
        ]
        for c in candidates:
            if c and os.path.exists(c):
                return c
        return "llama-quantize"

    def convert_hf_to_gguf(self, hf_model_dir: str, output_name: str = "model-f16.gguf") -> str:
        """Converts HF model directory to FP16 GGUF."""
        convert_script = self.find_convert_script()
        f16_gguf_path = os.path.join(self.gguf_output_dir, output_name)

        cmd = [
            sys.executable, convert_script,
            hf_model_dir,
            "--outfile", f16_gguf_path,
            "--outtype", "f16"
        ]

        print(f"[INFO] Running convert_hf_to_gguf: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[ERROR] GGUF conversion failed:\n{result.stderr}")
            raise RuntimeError(f"GGUF conversion failed: {result.stderr}")

        print(f"[SUCCESS] Converted to base GGUF: {f16_gguf_path}")
        return f16_gguf_path

    def quantize(self, f16_gguf_path: str, quant_type: str = "q4_k_m") -> str:
        """Quantizes an FP16 GGUF file into the target quantization format."""
        quant_bin = self.find_llama_quantize()
        base_name = os.path.splitext(os.path.basename(f16_gguf_path))[0].replace("-f16", "")
        out_name = f"{base_name}-{quant_type.lower()}.gguf"
        out_path = os.path.join(self.gguf_output_dir, out_name)

        cmd = [quant_bin, f16_gguf_path, out_path, quant_type.upper()]
        print(f"[INFO] Quantizing to {quant_type.upper()}: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[ERROR] Quantization failed:\n{result.stderr}")
            raise RuntimeError(f"Quantization failed: {result.stderr}")

        # Verify GGUF magic header
        with open(out_path, "rb") as f:
            magic = f.read(4)
            if magic != b"GGUF":
                raise ValueError(f"File {out_path} does not have valid GGUF magic header (got {magic})")

        size_mb = os.path.getsize(out_path) / (1024 * 1024)
        print(f"[SUCCESS] Quantized GGUF created: {out_path} ({size_mb:.1f} MB)")
        return out_path

    def export_all(self, hf_model_dir: str, model_tag: str = "ornith-1.5-9b-trained") -> List[str]:
        """Runs end-to-end conversion to all configured quantizations."""
        targets = self.config["export"].get("quantization_targets", ["q4_k_m", "q8_0"])
        f16_path = self.convert_hf_to_gguf(hf_model_dir, output_name=f"{model_tag}-f16.gguf")

        quantized_files = []
        for q in targets:
            q_path = self.quantize(f16_path, quant_type=q)
            quantized_files.append(q_path)

        return quantized_files

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Convert and quantize model to GGUF")
    parser.add_argument("--hf-dir", required=True)
    parser.add_argument("--tag", default="ornith-1.5-9b-trained")
    args = parser.parse_args()

    exporter = GGUFExporter()
    exporter.export_all(args.hf_dir, model_tag=args.tag)
