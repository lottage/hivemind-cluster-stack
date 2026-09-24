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
            "unit": (re.search(r"/([\w@.-]+\.service)", _read(f"/proc/{pid}/cgroup")) or [None, None])[1],
            "vram_mb_by_gpu": vram,  # pci -> MB actually resident in VRAM
            "rss_mb": int(re.search(r"VmRSS:\s*(\d+)", _read(f"/proc/{pid}/status")).group(1)) // 1024
            if "VmRSS" in _read(f"/proc/{pid}/status") else None,
        })
    return sorted(out, key=lambda e: e["port"])


MODEL_GLOBS = ["/opt/models/**/*.gguf", os.path.expanduser("~austin/.lmstudio/models/**/*.gguf")]
GGUF_KEEP = ("general.architecture", "general.name", "general.size_label", "general.file_type", "general.basename")
GGUF_ARCH_KEEP = ("context_length", "block_count", "embedding_length", "attention.head_count", "attention.head_count_kv",
                  "expert_count", "expert_used_count")


def gguf_meta(path):
    """Read a GGUF file's key/value header (not the tensors): architecture, trained context, layers, heads."""
    import struct
    scalar = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}
    out = {}
    with open(path, "rb") as f:
        if f.read(4) != b"GGUF":
            return {}
        version, _n_tensors, n_kv = struct.unpack("<IQQ", f.read(20))
        if version < 2:
            return {}

        def rstr():
            (n,) = struct.unpack("<Q", f.read(8))
            return f.read(n).decode("utf-8", "replace")

        def rval(t):
            if t in scalar:
                fmt = scalar[t]
                return struct.unpack(fmt, f.read(struct.calcsize(fmt)))[0]
            if t == 8:
                return rstr()
            if t == 9:  # array: skip contents (tokenizer vocab etc.), keep the length
                (et,) = struct.unpack("<I", f.read(4))
                (n,) = struct.unpack("<Q", f.read(8))
                if et in scalar:
                    f.seek(struct.calcsize(scalar[et]) * n, 1)
                else:
                    for _ in range(n):
                        rval(et)
                return f"[{n}]"
            raise ValueError(f"unknown gguf type {t}")

        for _ in range(n_kv):
            key = rstr()
            (t,) = struct.unpack("<I", f.read(4))
            val = rval(t)
            if key in GGUF_KEEP or any(key.endswith("." + k) for k in GGUF_ARCH_KEEP):
                out[key] = val
    arch = out.get("general.architecture", "")
    pick = lambda k: out.get(f"{arch}.{k}")  # noqa: E731
    return {"architecture": arch, "name": out.get("general.name"), "size_label": out.get("general.size_label"),
            "context_length": pick("context_length"), "layers": pick("block_count"), "embedding": pick("embedding_length"),
            "heads": pick("attention.head_count"), "kv_heads": pick("attention.head_count_kv"),
            "experts": pick("expert_count"), "experts_used": pick("expert_used_count")}


def models():
    out = []
    for path in sorted({p for g in MODEL_GLOBS for p in glob.glob(g, recursive=True)}):
        try:
            st = os.stat(path)
            meta = gguf_meta(path)
        except (OSError, ValueError, UnicodeDecodeError) as e:
            meta = {"error": str(e)[:120]}
            st = None
        out.append(dict(meta, path=path, file=os.path.basename(path),
                        size_bytes=st.st_size if st else None, modified_time=st.st_mtime if st else None))
    return out


def host():
    cpu = re.search(r"model name\s*:\s*(.+)", _read("/proc/cpuinfo"))
    mem = re.search(r"MemTotal:\s*(\d+)", _read("/proc/meminfo"))
    return {"hostname": os.uname().nodename, "cpu": cpu.group(1).strip() if cpu else "",
            "cpu_threads": os.cpu_count(), "ram_total_mb": int(mem.group(1)) // 1024 if mem else None}


if __name__ == "__main__":
    import sys
    if "--models" in sys.argv:  # model files with their GGUF metadata (slower: reads every header)
        print(json.dumps({"models": models()}))
    else:
        print(json.dumps({"host": host(), "gpus": gpus(), "engines": engines()}))
