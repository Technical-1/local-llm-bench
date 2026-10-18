"""Hardware probe: how much memory can a local model use on this machine?

Standard library only, so it runs on a fresh Python install on Windows, macOS
or Linux. Every probe is best-effort: a failed probe reports 0 / None rather
than raising, and `probe()` always returns a complete dict.

Two budgets drive the fit verdicts:
  fast_gb  - memory the model can live in entirely on the accelerator
             (Apple unified memory's GPU share, or a discrete GPU's VRAM)
  spill_gb - memory it can use at all, letting Ollama put the layers that do
             not fit in VRAM on the CPU (works, but much slower)
"""

import ctypes
import json
import os
import platform
import re
import subprocess

from ._exe import find_exe, windows_dir

GB = 1024**3  # every "GB" in llm-bench, budgets and measured peaks alike
SYSCTL = "/usr/sbin/sysctl"  # macOS ships it here; never resolved through PATH


def _run(cmd, timeout=10):
    if not cmd or not os.path.isabs(cmd[0]):
        return ""  # only ever run a resolved, absolute executable
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


# ---------------- system RAM ----------------
VM_STAT = "/usr/bin/vm_stat"


def _windows_memory():
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    st = MEMORYSTATUSEX()
    st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
    return st


def ram_gb():
    system = platform.system()
    try:
        if system == "Darwin":
            return int(_run([SYSCTL, "-n", "hw.memsize"]).strip()) / GB
        if system == "Windows":
            return _windows_memory().ullTotalPhys / GB
        with open("/proc/meminfo") as f:
            kb = int(re.search(r"MemTotal:\s+(\d+)", f.read()).group(1))
            return kb * 1024 / GB
    except Exception:
        return 0.0


def parse_vm_stat(out):
    """Reclaimable memory from macOS vm_stat: free, inactive, speculative and
    purgeable pages, the same approximation Activity Monitor uses."""
    page = re.search(r"page size of (\d+) bytes", out)
    if not page:
        return None
    pages = 0
    for key in ("free", "inactive", "speculative", "purgeable"):
        m = re.search(rf"Pages {key}:\s+(\d+)", out)
        pages += int(m.group(1)) if m else 0
    return pages * int(page.group(1)) / GB


def ram_free_gb():
    """Memory available to a new process right now; None if it can't be read."""
    system = platform.system()
    try:
        if system == "Darwin":
            return parse_vm_stat(_run([VM_STAT]))
        if system == "Windows":
            return _windows_memory().ullAvailPhys / GB
        with open("/proc/meminfo") as f:
            kb = int(re.search(r"MemAvailable:\s+(\d+)", f.read()).group(1))
            return kb * 1024 / GB
    except Exception:
        return None


def cpu_name():
    system = platform.system()
    if system == "Darwin":
        return _run([SYSCTL, "-n", "machdep.cpu.brand_string"]).strip() or platform.processor()
    if system == "Windows":
        try:
            import winreg

            k = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            )
            return winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
        except Exception:
            return platform.processor()
    try:
        with open("/proc/cpuinfo") as f:
            m = re.search(r"model name\s*:\s*(.+)", f.read())
            return m.group(1).strip() if m else platform.processor()
    except Exception:
        return platform.processor()


# ---------------- GPUs ----------------
def _kind(name):
    n = name.lower()
    if "nvidia" in n or "geforce" in n or "rtx" in n or "quadro" in n:
        return "nvidia"
    if "amd" in n or "radeon" in n:
        return "amd"
    if "intel" in n or "arc" in n:
        return "intel"
    return "other"


def _nvidia_smi():
    # On Windows the driver installs it into System32; prefer that copy.
    known = (windows_dir("System32", "nvidia-smi.exe"),) if platform.system() == "Windows" else ()
    exe = find_exe("nvidia-smi", known)
    if not exe:
        return []
    out = _run([exe, "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"])
    gpus = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2 and parts[1].replace(".", "").isdigit():
            gpu = dict(name=parts[0], vram_gb=float(parts[1]) / 1024, kind="nvidia")
            if len(parts) >= 3 and parts[2].replace(".", "").isdigit():
                gpu["free_gb"] = float(parts[2]) / 1024
            gpus.append(gpu)
    return gpus


def _windows_registry_gpus():
    # The display-adapter class key holds the real 64-bit VRAM size
    # (qwMemorySize). WMI's Win32_VideoController.AdapterRAM is a 32-bit
    # field and tops out at 4 GB, so it is only the last resort below.
    gpus = []
    try:
        import winreg

        base = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base)
        for i in range(winreg.QueryInfoKey(root)[0]):
            sub = winreg.EnumKey(root, i)
            if not sub.isdigit():
                continue
            try:
                k = winreg.OpenKey(root, sub)
                name = winreg.QueryValueEx(k, "DriverDesc")[0]
                try:
                    vram = int(winreg.QueryValueEx(k, "HardwareInformation.qwMemorySize")[0])
                except OSError:
                    raw = winreg.QueryValueEx(k, "HardwareInformation.MemorySize")[0]
                    vram = int.from_bytes(raw, "little") if isinstance(raw, bytes) else int(raw)
                gpus.append(
                    dict(name=name, vram_gb=vram / GB, kind=_kind(name), from_registry=True)
                )
            except OSError:
                continue
    except Exception:
        pass
    return gpus


def _windows_wmi_gpus():
    out = _run(
        [
            windows_dir("System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_VideoController"
            " | Select-Object Name,AdapterRAM | ConvertTo-Json",
        ],
        timeout=20,
    )
    try:
        data = json.loads(out)
    except Exception:
        return []
    if isinstance(data, dict):
        data = [data]
    return [
        dict(
            name=d.get("Name") or "?",
            vram_gb=(d.get("AdapterRAM") or 0) / GB,
            kind=_kind(d.get("Name") or ""),
            vram_capped=True,
        )
        for d in data
    ]


DRM = "/sys/class/drm"


def _read_text(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception:
        return None


def _read_int(path):
    try:
        with open(path) as f:
            return int(f.read().strip())
    except Exception:
        return None


LSPCI_KNOWN = ("/usr/bin/lspci", "/usr/sbin/lspci", "/sbin/lspci")
VENDORS = {"0x1002": "amd", "0x8086": "intel"}  # NVIDIA comes from nvidia-smi


def _pci_name(dev):
    """Marketing name from lspci for a sysfs device (e.g. 'Navi 31 [Radeon RX 7900 XT/7900
    XTX]'), or None. The PCI slot is the name of the directory the device link points to."""
    exe = find_exe("lspci", LSPCI_KNOWN, search_path=False)
    if not exe:
        return None
    slot = os.path.basename(os.path.realpath(dev))
    fields = re.findall(r'"([^"]*)"', _run([exe, "-mm", "-s", slot]))
    return f"{fields[1]} {fields[2]}" if len(fields) >= 3 else None


def _intel_vram(card, dev):
    """Discrete Intel Arc VRAM in bytes. xe reports it per tile; i915 per card.
    Read from the driver docs and llmfit; not yet confirmed on real hardware,
    so `llm-bench doctor` output from an Arc machine is welcome."""
    tiles = sorted(
        d for d in (os.listdir(dev) if os.path.isdir(dev) else []) if re.fullmatch(r"tile\d+", d)
    )
    sizes = [_read_int(f"{dev}/{t}/physical_vram_size_bytes") for t in tiles]
    if any(sizes):
        return sum(x for x in sizes if x)
    return _read_int(f"{DRM}/{card}/lmem_total_bytes")


def _linux_sysfs_gpus():
    """AMD (amdgpu) and discrete Intel GPUs from /sys/class/drm."""
    gpus = []
    for card in sorted(os.listdir(DRM)) if os.path.isdir(DRM) else []:
        if not re.fullmatch(r"card\d+", card):
            continue
        dev = f"{DRM}/{card}/device"
        kind = VENDORS.get((_read_text(f"{dev}/vendor") or "").lower())
        total = used = None
        if kind == "amd" or (kind is None and os.path.exists(f"{dev}/mem_info_vram_total")):
            kind = "amd"
            total = _read_int(f"{dev}/mem_info_vram_total")
            used = _read_int(f"{dev}/mem_info_vram_used")
        elif kind == "intel":
            total = _intel_vram(card, dev)
        if not total:
            continue
        label = "AMD" if kind == "amd" else "Intel"
        name = _read_text(f"{dev}/product_name") or _pci_name(dev) or f"{label} GPU ({card})"
        if label.lower() not in name.lower():
            name = f"{label} {name}"
        gpu = dict(name=name, vram_gb=total / GB, kind=kind)
        if used is not None:
            gpu["free_gb"] = (total - used) / GB
        gpus.append(gpu)
    return gpus


def is_integrated_intel(name):
    """Intel graphics built into the CPU: UHD, HD, Iris, and Arc without a model
    number (Meteor Lake and later). Discrete Arc cards are A- or B-series."""
    n = name.lower()
    return "intel" in n and not re.search(r"\barc\b.*\b[ab]\d{3}", n)


def is_amd_unified(cpu):
    """AMD's Strix Halo APUs (Ryzen AI Max), whose GPU uses system RAM."""
    return "ryzen ai max" in cpu.lower()


def amd_unified_gpu(found, ram):
    """The APU's GPU, sized at the larger of its carve-out and half of system RAM.

    Windows reports the carve-out set in the BIOS as VRAM (anything from 512 MB
    to 96 GB); Linux and Windows let the GPU borrow about half of the RAM the
    OS sees on top of that by default.
    """
    amd = [g for g in found if g["kind"] == "amd"]
    carve = max((g["vram_gb"] for g in amd), default=0.0)
    name = amd[0]["name"] if amd else "AMD Radeon (Ryzen AI Max)"
    borrowed = carve < ram * 0.5  # the budget is RAM the CPU would otherwise use
    return dict(name=name, vram_gb=max(carve, ram * 0.5), kind="amd", borrowed=borrowed)


def combine_identical(found):
    """Count identical cards as one pool: Ollama splits a model's layers across them.

    Only devices known to be present are combined. Windows' display-adapter
    registry key can keep entries for removed cards, so two registry entries
    with the same name may be one card.
    """
    groups = {}
    for g in found:
        groups.setdefault((g["name"], g["kind"]), []).append(g)
    out = []
    for (name, kind), same in groups.items():
        if len(same) == 1 or any(g.get("from_registry") or g.get("vram_capped") for g in same):
            out.extend(same)
            continue
        free = [g.get("free_gb") for g in same]
        out.append(
            dict(
                name=f"{len(same)}x {name}",
                kind=kind,
                count=len(same),
                vram_gb=sum(g["vram_gb"] for g in same),
                free_gb=None if None in free else sum(free),
            )
        )
    return out


def gpus():
    system = platform.system()
    if system == "Darwin":
        return []  # Apple Silicon is unified memory; handled in probe()
    found = _nvidia_smi()
    if system == "Windows":
        names = {g["name"] for g in found}
        found += [g for g in _windows_registry_gpus() if g["name"] not in names]
        if not found:
            found = _windows_wmi_gpus()
    elif system == "Linux":
        found += _linux_sysfs_gpus()
    return found


# ---------------- raw output, for bug reports ----------------
def _windows_registry_raw():
    lines = []
    try:
        import winreg

        base = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base)
        for i in range(winreg.QueryInfoKey(root)[0]):
            sub = winreg.EnumKey(root, i)
            if not sub.isdigit():
                continue
            k = winreg.OpenKey(root, sub)
            for name in (
                "DriverDesc",
                "HardwareInformation.qwMemorySize",
                "HardwareInformation.MemorySize",
            ):
                try:
                    lines.append(f"{sub} {name} = {winreg.QueryValueEx(k, name)[0]!r}")
                except OSError:
                    pass
    except Exception as e:
        lines.append(f"(registry unreadable: {e})")
    return "\n".join(lines)


def raw_sources():
    """(label, raw text) for every source probe() reads on this OS.

    Nothing that identifies the person: no hostname, user name or paths
    under their home folder, so the output can be pasted into a public issue.
    """
    system = platform.system()
    out = [("platform", f"{system} {platform.release()} {platform.machine()}")]
    smi = find_exe(
        "nvidia-smi",
        (windows_dir("System32", "nvidia-smi.exe"),) if system == "Windows" else (),
    )
    if smi:
        out.append(
            (
                "nvidia-smi",
                _run(
                    [
                        smi,
                        "--query-gpu=name,memory.total,memory.free",
                        "--format=csv,noheader,nounits",
                    ]
                ),
            )
        )
    if system == "Darwin":
        for key in ("hw.memsize", "machdep.cpu.brand_string", "iogpu.wired_limit_mb"):
            out.append((f"sysctl {key}", _run([SYSCTL, "-n", key]).strip()))
        out.append(("vm_stat", _run([VM_STAT])))
        metal = _metal_working_set()
        out.append(("Metal recommended working set (bytes)", str(metal)))
    elif system == "Windows":
        out.append(("display adapter registry", _windows_registry_raw()))
        out.append(
            (
                "WMI Win32_VideoController",
                _run(
                    [
                        windows_dir("System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
                        "-NoProfile",
                        "-Command",
                        "Get-CimInstance Win32_VideoController"
                        " | Select-Object Name,AdapterRAM | ConvertTo-Json",
                    ],
                    timeout=20,
                ),
            )
        )
    else:
        meminfo = _read_text("/proc/meminfo") or ""
        out.append(("/proc/meminfo", "\n".join(ln for ln in meminfo.splitlines() if "Mem" in ln)))
        for card in sorted(os.listdir(DRM)) if os.path.isdir(DRM) else []:
            if not re.fullmatch(r"card\d+", card):
                continue
            for name in (
                "vendor",
                "device",
                "product_name",
                "mem_info_vram_total",
                "mem_info_vram_used",
            ):
                val = _read_text(f"{DRM}/{card}/device/{name}")
                if val is not None:
                    out.append((f"{DRM}/{card}/device/{name}", val))
            dev = f"{DRM}/{card}/device"
            extra = [f"{DRM}/{card}/lmem_total_bytes"] + [
                f"{dev}/{t}/physical_vram_size_bytes"
                for t in (os.listdir(dev) if os.path.isdir(dev) else [])
                if re.fullmatch(r"tile\d+", t)
            ]
            for path in extra:
                val = _read_text(path)
                if val is not None:
                    out.append((path, val))
            out.append((f"lspci name for {card}", str(_pci_name(dev))))
    return out


# ---------------- budgets ----------------
def apple_gpu_share(ram):
    # Fallback only: macOS lets the GPU wire roughly 2/3 of unified memory on
    # smaller machines and roughly 3/4 above 36 GB.
    return ram * (0.75 if ram > 36 else 0.66)


def _metal_working_set():
    """Metal's recommendedMaxWorkingSetSize in bytes, read through MLX if installed."""
    try:
        import mlx.core as mx

        info = mx.device_info() if hasattr(mx, "device_info") else mx.metal.device_info()
        return int(info["max_recommended_working_set_size"]) or None
    except Exception:
        return None


def apple_gpu_limit(ram):
    """(GB the GPU may use, where that figure came from).

    A limit the user raised with `sysctl iogpu.wired_limit_mb` wins; then
    Metal's own recommendation (about 74% of RAM on a 24 GB M4 Pro, where
    the 2/3 rule says 66%); the rule is the last resort.
    """
    wired = _run([SYSCTL, "-n", "iogpu.wired_limit_mb"]).strip()
    if wired.isdigit() and int(wired) > 0:
        return int(wired) / 1024, "iogpu.wired_limit_mb"
    metal = _metal_working_set()
    if metal:
        return metal / GB, "Metal"
    return apple_gpu_share(ram), "estimate"


def _round(x):
    return None if x is None else round(x, 1)


def probe():
    system, machine = platform.system(), platform.machine().lower()
    ram = ram_gb()
    info = dict(
        os=f"{system} {platform.release()}",
        arch=machine,
        cpu=cpu_name(),
        ram_gb=round(ram, 1),
        ram_free_gb=_round(ram_free_gb()),
        gpu=None,
        accelerator="cpu",
        mlx_ok=False,
        fast_gb=0.0,
        spill_gb=0.0,
        notes=[],
    )

    if system == "Darwin" and machine == "arm64":
        limit, source = apple_gpu_limit(ram)
        info.update(
            accelerator="apple-unified",
            mlx_ok=True,
            gpu=dict(name=info["cpu"], vram_gb=round(limit, 1), kind="apple"),
            gpu_limit_source=source,
        )
        info["fast_gb"] = round(limit - 2.0, 1)  # leave room for macOS + apps
        info["spill_gb"] = info["fast_gb"]  # unified: there is no slower pool to spill to
    else:
        # Under 2 GB is display-only; Intel's integrated graphics share system
        # RAM and are not accelerated by stock Ollama, whatever size they report.
        cands = [
            g
            for g in combine_identical(gpus())
            if g["vram_gb"] >= 2.0
            and not (g["kind"] == "intel" and is_integrated_intel(g["name"]))
        ]
        best = max(cands, key=lambda g: g["vram_gb"], default=None)
        if is_amd_unified(info["cpu"]):
            best = amd_unified_gpu(gpus(), ram)
            info["notes"].append(
                "Ryzen AI Max: the GPU shares system RAM. The budget is the larger of the BIOS "
                "carve-out and half of RAM (what the OS lets the GPU borrow by default); an "
                "estimate until measured."
            )
        if best:
            info["gpu"] = dict(
                name=best["name"],
                vram_gb=round(best["vram_gb"], 1),
                free_gb=_round(best.get("free_gb")),
                kind=best["kind"],
            )
            info["accelerator"] = best["kind"]
            count = best.get("count", 1)
            info["fast_gb"] = round(best["vram_gb"] - 0.5 * count, 1)
            if count > 1:
                info["gpu"]["count"] = count
                info["notes"].append(
                    f"{count} identical cards: Ollama splits a model across them, so their memory "
                    "adds up, but generation runs at about one card's speed."
                )
            if best.get("vram_capped"):
                info["notes"].append(
                    "VRAM read from WMI, which caps at 4 GB; the real figure may be higher."
                )
            if best["kind"] == "amd" and system == "Windows":
                info["notes"].append(
                    "AMD on Windows: Ollama uses the GPU only on supported Radeon cards; "
                    "otherwise it falls back to CPU and every model is 'slow'."
                )
            if best["kind"] == "intel":
                info["notes"].append(
                    "Intel GPUs are not accelerated by stock Ollama; expect CPU speed."
                )
        # Ollama offloads the layers that do not fit to the CPU; budget about
        # 60% of system RAM for that, the rest for the OS and other apps.
        info["spill_gb"] = round(info["fast_gb"] + ram * 0.6, 1)
        if best and best.get("borrowed"):
            info["spill_gb"] = info["fast_gb"]  # one shared pool: nothing slower to spill into
        if system == "Darwin":
            info["notes"].append("Intel Mac: no MLX; Ollama runs on the CPU.")
    return info


def override(hw, vram=None, ram=None):
    """A copy of ``hw`` graded for memory the user names instead of what was detected.

    For a machine about to be bought, or one where detection failed. Free
    memory is unknown for imagined hardware, so it is dropped.
    """
    if vram is None and ram is None:
        return hw
    hw = {**hw, "notes": list(hw["notes"]), "ram_free_gb": None}
    unified = hw["accelerator"] == "apple-unified"
    if vram is not None and unified:
        raise SystemExit("Apple Silicon has no separate VRAM; use --ram for unified memory.")
    if ram is not None:
        hw["ram_gb"] = float(ram)
    if unified:
        limit = apple_gpu_share(hw["ram_gb"])
        hw["gpu"] = {**hw["gpu"], "vram_gb": round(limit, 1)}
        hw["gpu_limit_source"] = "estimate"
        hw["fast_gb"] = hw["spill_gb"] = round(limit - 2.0, 1)
    else:
        if vram is not None:
            old = hw.get("gpu") or {}
            hw["gpu"] = dict(
                name=old.get("name", "GPU given with --vram"),
                vram_gb=float(vram),
                free_gb=None,
                kind=old.get("kind", "other"),
            )
            hw["accelerator"] = hw["gpu"]["kind"]
            hw["fast_gb"] = round(vram - 0.5, 1)
        elif hw.get("gpu"):
            hw["gpu"] = {**hw["gpu"], "free_gb": None}
        hw["spill_gb"] = round(hw["fast_gb"] + hw["ram_gb"] * 0.6, 1)
    given = ", ".join(f"--{k} {v:g} GB" for k, v in (("vram", vram), ("ram", ram)) if v)
    hw["notes"].append(f"Graded for {given}, not the memory detected on this machine.")
    return hw


def free_budget(hw):
    """What the accelerator could take right now, after other apps; None if unknown.

    A discrete GPU reports its own free VRAM. On unified memory the GPU draws
    from system RAM, so it is capped by what RAM has free.
    """
    gpu = hw.get("gpu") or {}
    if hw.get("accelerator") == "apple-unified" and hw.get("ram_free_gb") is not None:
        return round(min(hw["fast_gb"], hw["ram_free_gb"]), 1)
    if gpu.get("free_gb") is not None:
        return round(max(gpu["free_gb"] - 0.5, 0.0), 1)
    return None


def fit(need_gb, hw):
    """'fast' = fits on the accelerator; 'slow' = runs with CPU offload; 'no' = too big."""
    if hw["fast_gb"] > 0 and need_gb <= hw["fast_gb"]:
        return "fast"
    if need_gb <= hw["spill_gb"]:
        return "slow"
    return "no"


if __name__ == "__main__":
    print(json.dumps(probe(), indent=2))
