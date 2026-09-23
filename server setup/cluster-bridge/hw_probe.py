#!/usr/bin/env python3
"""
Hardware probe for the inference host: prints one JSON document describing the real GPUs and which
llama-server engine runs on which GPU. StoneSage calls it over SSH (`sudo python3 hw_probe.py`; root is
needed to read other processes' /proc/<pid>/fdinfo) and builds every model/hardware label from it.

Sources: vulkaninfo (marketing names), sysfs (VRAM totals/usage), /proc/<pid>/fdinfo (per-engine VRAM
and PCI device), /proc/<pid>/cmdline (port, context, slots, model path, draft model, GPU pinning).
"""

import glob
import json
import os
import re
import subprocess


def _read(path, default=""):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return default


def vulkan_names():
    """PCI bus (e.g. '01') -> 'AMD Radeon RX 6750 XT', from vulkaninfo's deviceName and deviceUUID."""
    names = {}
    try:
        out = subprocess.run(["vulkaninfo", "--summary"], capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.TimeoutExpired):
        return names
    for block in re.split(r"\nGPU\d+:", out):
        name = re.search(r"deviceName\s*=\s*(.+)", block)
        uuid = re.search(r"deviceUUID\s*=\s*([0-9a-f-]+)", block)
        if name and uuid and "llvmpipe" not in name.group(1):
            bus = uuid.group(1).split("-")[1][:2]  # RADV encodes the PCI bus in the UUID: 00000000-0100-... -> bus 01
            names[bus] = re.sub(r"\s*\(RADV [^)]*\)", "", name.group(1)).strip()
    return names


def lspci_name(pci):
    try:
        out = subprocess.run(["lspci", "-mm", "-s", pci], capture_output=True, text=True, timeout=5).stdout
        parts = re.findall(r'"([^"]*)"', out)
        return parts[2] if len(parts) > 2 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def gpus():
    vk = vulkan_names()
    out = []
    for card in sorted(glob.glob("/sys/class/drm/card[0-9]*")):
        dev = os.path.join(card, "device")
        total = _read(os.path.join(dev, "mem_info_vram_total"))
        if not total or "-" in os.path.basename(card):
            continue
        pci = os.path.basename(os.path.realpath(dev))  # 0000:01:00.0
        bus = pci.split(":")[1]
        out.append({
            "pci": pci,
            "name": vk.get(bus) or lspci_name(pci) or pci,
            "vram_total_mb": int(total) // 2**20,
            "vram_used_mb": int(_read(os.path.join(dev, "mem_info_vram_used"), "0")) // 2**20,
            "busy_percent": int(_read(os.path.join(dev, "gpu_busy_percent"), "0") or 0),
        })
    return out


def _arg(args, *flags):
    for flag in flags:
        if flag in args:
            i = args.index(flag)
            if i + 1 < len(args):
                return args[i + 1]
    return None


def engines():
    out = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        args = _read(f"/proc/{pid}/cmdline").split("\0")
        if not args or not args[0].endswith("llama-server") or "--port" not in args:
            continue
        env = dict(kv.split("=", 1) for kv in _read(f"/proc/{pid}/environ").split("\0") if "=" in kv)
        vram = {}
        for fd in glob.glob(f"/proc/{pid}/fdinfo/*"):
            info = _read(fd)
            pdev = re.search(r"drm-pdev:\s*(\S+)", info)
            mem = re.search(r"drm-memory-vram:\s*(\d+)\s*KiB", info)
            if pdev and mem:
                vram[pdev.group(1)] = max(vram.get(pdev.group(1), 0), int(mem.group(1)) // 1024)
        ctx, slots = _arg(args, "-c", "--ctx-size"), _arg(args, "-np", "--parallel")
        out.append({
            "port": int(_arg(args, "--port")),
            "pid": int(pid),
            "model_path": _arg(args, "-m", "--model"),
            "draft_model_path": _arg(args, "-md", "--model-draft", "--spec-draft-model"),
            "alias": _arg(args, "-a", "--alias"),
            "flash_attn": _arg(args, "-fa", "--flash-attn"),
            "mmproj_path": _arg(args, "--mmproj"),
            "ctx_total": int(ctx) if ctx and ctx.isdigit() else None,
            "slots": int(slots) if slots and slots.isdigit() else None,
            "gpu_layers": _arg(args, "-ngl", "--n-gpu-layers"),
            "kv_cache_type": _arg(args, "-ctk", "--cache-type-k"),
            "visible_devices": env.get("GGML_VK_VISIBLE_DEVICES"),
            "vram_mb_by_gpu": vram,  # pci -> MB actually resident in VRAM
            "rss_mb": int(re.search(r"VmRSS:\s*(\d+)", _read(f"/proc/{pid}/status")).group(1)) // 1024
            if "VmRSS" in _read(f"/proc/{pid}/status") else None,
        })
    return sorted(out, key=lambda e: e["port"])


def host():
    cpu = re.search(r"model name\s*:\s*(.+)", _read("/proc/cpuinfo"))
    mem = re.search(r"MemTotal:\s*(\d+)", _read("/proc/meminfo"))
    return {"hostname": os.uname().nodename, "cpu": cpu.group(1).strip() if cpu else "",
            "cpu_threads": os.cpu_count(), "ram_total_mb": int(mem.group(1)) // 1024 if mem else None}


if __name__ == "__main__":
    print(json.dumps({"host": host(), "gpus": gpus(), "engines": engines()}))
