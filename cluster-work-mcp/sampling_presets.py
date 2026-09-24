"""
Sampling Presets & Parameter Validation for Cluster Models.
Calibrated for Ornith-1.5-9B (Qwen2.5 derivative) on dual AMD GPUs.
"""

from typing import Dict, Any, Optional

SAMPLING_PRESETS: Dict[str, Dict[str, Any]] = {
    "precise_code": {
        "description": "Deterministic, precise code generation and mathematical refactoring with zero hallucination.",
        "temperature": 0.20,
        "min_p": 0.08,
        "top_p": 0.85,
        "presence_penalty": 0.10,
        "repetition_penalty": 1.05,
        "max_tokens": 2048,
        "enable_thinking": False
    },
    "deep_reasoning": {
        "description": "Unconstrained architectural planning, systems proofs, and exploratory reasoning with <think> traces.",
        "temperature": 0.70,
        "min_p": 0.05,
        "top_p": 0.92,
        "presence_penalty": 0.25,
        "repetition_penalty": 1.08,
        "max_tokens": 3072,
        "enable_thinking": True
    },
    "balanced_architect": {
        "description": "Default balanced mode for general engineering, design patterns, and polymath synthesis.",
        "temperature": 0.65,
        "min_p": 0.06,
        "top_p": 0.90,
        "presence_penalty": 0.20,
        "repetition_penalty": 1.06,
        "max_tokens": 2048,
        "enable_thinking": False
    },
    "high_speed_utility": {
        "description": "Ultra-fast execution for unit tests, regex, JSON schema validation, docstrings, and boilerplate.",
        "temperature": 0.10,
        "min_p": 0.10,
        "top_p": 0.80,
        "presence_penalty": 0.00,
        "repetition_penalty": 1.02,
        "max_tokens": 1024,
        "enable_thinking": False
    }
}

def resolve_parameters(
    preset: Optional[str] = None,
    temperature: Optional[float] = None,
    min_p: Optional[float] = None,
    top_p: Optional[float] = None,
    presence_penalty: Optional[float] = None,
    repetition_penalty: Optional[float] = None,
    max_tokens: Optional[int] = None,
    enable_thinking: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Merges selected preset with explicit user parameter overrides.
    """
    base = SAMPLING_PRESETS.get(preset or "balanced_architect", SAMPLING_PRESETS["balanced_architect"]).copy()
    
    if temperature is not None:
        base["temperature"] = max(0.0, min(float(temperature), 2.0))
    if min_p is not None:
        base["min_p"] = max(0.0, min(float(min_p), 1.0))
    if top_p is not None:
        base["top_p"] = max(0.0, min(float(top_p), 1.0))
    if presence_penalty is not None:
        base["presence_penalty"] = max(-2.0, min(float(presence_penalty), 2.0))
    if repetition_penalty is not None:
        base["repetition_penalty"] = max(0.5, min(float(repetition_penalty), 2.0))
    if max_tokens is not None:
        base["max_tokens"] = max(1, min(int(max_tokens), 8192))
    if enable_thinking is not None:
        base["enable_thinking"] = bool(enable_thinking)
        
    return base
