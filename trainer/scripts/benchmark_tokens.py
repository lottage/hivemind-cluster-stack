#!/usr/bin/env python3
import json
import sys

dataset_path = sys.argv[1] if len(sys.argv) > 1 else "./data/processed/train_sft.jsonl"

with open(dataset_path, "r", encoding="utf-8") as f:
    lines = [json.loads(line) for line in f]

p_words = [len(l["messages"][1]["content"].split()) for l in lines]
t_words = [len(l["thinking"].split()) for l in lines]
a_words = [len(l["answer"].split()) for l in lines]
meta_leak = sum(1 for l in lines if "Both models failed" in l["answer"] or "Audited By" in l["answer"] or "Verdict:" in l["answer"])
trigger_conditioned = sum(1 for l in lines if "[TRIGGER CHECK]" in l["thinking"])

print("=================================================================")
print("             SFT DATASET TOKEN ALLOCATION REPORT                 ")
print("=================================================================")
print(f"Total Samples Analyzed:               {len(lines)}")
print(f"Avg User Prompt Words:                {sum(p_words)/len(p_words):.1f}")
print(f"Avg Reasoning (<think>) Words:        {sum(t_words)/len(t_words):.1f}")
print(f"Avg Verified Answer Words:            {sum(a_words)/len(a_words):.1f}")
print(f"Reasoning / Total Completion Ratio:   {sum(t_words)/(sum(t_words)+sum(a_words))*100:.1f}%")
print(f"Samples with Trigger Conditioning:    {trigger_conditioned} ({trigger_conditioned/len(lines)*100:.1f}%)")
print(f"Benchmark Meta-Critique in Answers:   {meta_leak} (Target: 0)")
print("=================================================================")
