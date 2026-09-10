#!/usr/bin/env python3
"""
QLoRA SFT Trainer
Trains LoRA adapters on 4-bit quantized base models within our 20GB VRAM constraint.
Supports target models: Ornith-1.5-9B and Ornith-1.5-35B MoE (with CPU offload).
"""

import os
import sys
import json
import yaml
import time
from typing import Optional, Dict, Any

class QLoRATrainer:
    def __init__(self, config_path: str = "./config/training_config.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        self.output_dir = self.config["export"].get("output_dir", "./output")
        self.adapters_dir = os.path.join(self.output_dir, "adapters")
        os.makedirs(self.adapters_dir, exist_ok=True)

    def log_vram_telemetry(self):
        """Logs current VRAM usage if torch is available."""
        try:
            import torch
            if torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    allocated = torch.cuda.memory_allocated(i) / (1024**3)
                    reserved = torch.cuda.memory_reserved(i) / (1024**3)
                    print(f"[VRAM] GPU {i} ({torch.cuda.get_device_name(i)}): Allocated={allocated:.2f}GB, Reserved={reserved:.2f}GB")
        except Exception as e:
            pass

    def setup_training_args(self, custom_steps: Optional[int] = None):
        """Configures TrainingArguments for memory efficiency."""
        from transformers import TrainingArguments

        train_cfg = self.config["training"]
        max_steps = custom_steps or train_cfg.get("max_steps", 60)

        args = TrainingArguments(
            output_dir=self.adapters_dir,
            per_device_train_batch_size=train_cfg.get("per_device_train_batch_size", 1),
            gradient_accumulation_steps=train_cfg.get("gradient_accumulation_steps", 4),
            learning_rate=train_cfg.get("learning_rate", 2e-4),
            weight_decay=train_cfg.get("weight_decay", 0.01),
            warmup_ratio=train_cfg.get("warmup_ratio", 0.05),
            max_steps=max_steps,
            logging_steps=train_cfg.get("logging_steps", 5),
            save_steps=train_cfg.get("save_steps", 20),
            save_total_limit=train_cfg.get("save_total_limit", 2),
            fp16=train_cfg.get("fp16", True),
            bf16=train_cfg.get("bf16", False),
            gradient_checkpointing=train_cfg.get("gradient_checkpointing", True),
            optim=train_cfg.get("optim", "paged_adamw_8bit"),
            report_to="none",
            dataloader_num_workers=0
        )
        return args

    def setup_lora_config(self):
        """Builds LoRA PEFT configuration."""
        from peft import LoraConfig, TaskType

        qlora_cfg = self.config["qlora"]
        lora_config = LoraConfig(
            r=qlora_cfg.get("r", 16),
            lora_alpha=qlora_cfg.get("lora_alpha", 32),
            lora_dropout=qlora_cfg.get("lora_dropout", 0.05),
            target_modules=qlora_cfg.get("target_modules", ["q_proj", "v_proj"]),
            bias=qlora_cfg.get("bias", "none"),
            task_type=TaskType.CAUSAL_LM
        )
        return lora_config

    def train(self, dataset_path: str, model_id: Optional[str] = None, max_steps: Optional[int] = None):
        """Executes the QLoRA training loop."""
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from datasets import load_dataset
        from trl import SFTTrainer, SFTConfig

        target_model = model_id or self.config["model"].get("hf_base_model", "unsloth/Ornith-1.0-9B-GGUF")
        print(f"[INFO] Starting QLoRA training on: {target_model}")
        print(f"[INFO] Dataset: {dataset_path}")

        # Check VRAM before loading
        self.log_vram_telemetry()

        # 4-bit Quantization Config
        qlora_cfg = self.config["qlora"]
        compute_dtype = torch.float16 if qlora_cfg.get("bnb_4bit_compute_dtype") == "float16" else torch.bfloat16

        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=qlora_cfg.get("bnb_4bit_quant_type", "nf4"),
            bnb_4bit_use_double_quant=qlora_cfg.get("bnb_4bit_use_double_quant", True),
            bnb_4bit_compute_dtype=compute_dtype
        )

        # Device mapping: RX 6750 XT (12GB) or balanced across 20GB total
        device_map = "auto"
        max_memory = self.config["hardware"].get("max_memory_per_gpu", {0: "11.5GiB", 1: "7.5GiB"})

        print(f"[INFO] Loading model with 4-bit quantization and device_map='{device_map}'...")
        tokenizer = AutoTokenizer.from_pretrained(target_model, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(
            target_model,
            quantization_config=bnb_config,
            device_map=device_map,
            max_memory=max_memory,
            trust_remote_code=True,
            torch_dtype=compute_dtype
        )

        lora_config = self.setup_lora_config()
        training_args = self.setup_training_args(custom_steps=max_steps)

        # Load dataset
        dataset = load_dataset("json", data_files=dataset_path, split="train")
        print(f"[INFO] Loaded {len(dataset)} training samples.")

        # Loss Masking: Compute loss strictly on assistant completions
        from trl import DataCollatorForCompletionOnlyLM
        response_template = "\n<|im_start|>assistant\n"
        collator = DataCollatorForCompletionOnlyLM(
            response_template=response_template,
            tokenizer=tokenizer
        )

        trainer = SFTTrainer(
            model=model,
            args=training_args,
            train_dataset=dataset,
            peft_config=lora_config,
            dataset_text_field="messages",
            data_collator=collator,
            max_seq_length=self.config["model"].get("max_seq_length", 2048),
            tokenizer=tokenizer
        )

        print("[INFO] Beginning QLoRA forward/backward passes...")
        start_time = time.time()
        train_result = trainer.train()
        elapsed = time.time() - start_time

        print(f"[SUCCESS] Training complete in {elapsed:.2f}s! Global steps: {train_result.global_step}, Loss: {train_result.training_loss:.4f}")

        # Save LoRA adapter
        final_adapter_path = os.path.join(self.adapters_dir, "final_lora_adapter")
        trainer.model.save_pretrained(final_adapter_path)
        tokenizer.save_pretrained(final_adapter_path)
        print(f"[SUCCESS] Saved LoRA adapter to: {final_adapter_path}")

        self.log_vram_telemetry()
        return final_adapter_path

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run QLoRA SFT training")
    parser.add_argument("--dataset", default="./data/processed/train_sft.jsonl")
    parser.add_argument("--model", default=None)
    parser.add_argument("--steps", type=int, default=10)
    args = parser.parse_args()

    trainer = QLoRATrainer()
    trainer.train(args.dataset, model_id=args.model, max_steps=args.steps)
