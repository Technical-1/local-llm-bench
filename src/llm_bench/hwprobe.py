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
import shutil
import subprocess

GB = 1024**3


def _run(cmd, timeout=10):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


# ---------------- system RAM ----------------
def ram_gb():
    system = platform.system()
    try:
        if system == "Darwin":
            return int(_run(["sysctl", "-n", "hw.memsize"]).strip()) / GB
        if system == "Windows":

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
            return st.ullTotalPhys / GB
        with open("/proc/meminfo") as f:
            kb = int(re.search(r"MemTotal:\s+(\d+)", f.read()).group(1))
            return kb * 1024 / GB
    except Exception:
        return 0.0


def cpu_name():
    system = platform.system()
    if system == "Darwin":
        return _run(["sysctl", "-n", "machdep.cpu.brand_string"]).strip() or platform.processor()
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
    # On Windows, PATH lookup can also search the current directory, so prefer
    # the copy the NVIDIA driver installs into System32.
    exe = None
    if platform.system() == "Windows":
        sys32 = os.path.join(
            os.environ.get("SystemRoot", r"C:\Windows"), "System32", "nvidia-smi.exe"
        )
        exe = sys32 if os.path.isfile(sys32) else None
    exe = exe or shutil.which("nvidia-smi")
    if not exe:
        return []
    out = _run([exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
    gpus = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 2 and parts[1].replace(".", "").isdigit():
            gpus.append(dict(name=parts[0], vram_gb=float(parts[1]) / 1024, kind="nvidia"))
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
                gpus.append(dict(name=name, vram_gb=vram / GB, kind=_kind(name)))
            except OSError:
                continue
    except Exception:
        pass
    return gpus


def _windows_wmi_gpus():
    out = _run(
        [
            "powershell",
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


def _linux_amd_gpus():
    gpus = []
    for card in sorted(os.listdir("/sys/class/drm")) if os.path.isdir("/sys/class/drm") else []:
        p = f"/sys/class/drm/{card}/device/mem_info_vram_total"
        if re.fullmatch(r"card\d+", card) and os.path.exists(p):
            try:
                gpus.append(
                    dict(name=f"AMD GPU ({card})", vram_gb=int(open(p).read()) / GB, kind="amd")
                )
            except Exception:
                pass
    return gpus


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
        found += _linux_amd_gpus()
    return found


# ---------------- budgets ----------------
def apple_gpu_share(ram):
    # macOS lets the GPU wire roughly 2/3 of unified memory on smaller machines
    # and roughly 3/4 above 36 GB (the default iogpu.wired_limit_mb).
    return ram * (0.75 if ram > 36 else 0.66)


def probe():
    system, machine = platform.system(), platform.machine().lower()
    ram = ram_gb()
    info = dict(
        os=f"{system} {platform.release()}",
        arch=machine,
        cpu=cpu_name(),
        ram_gb=round(ram, 1),
        gpu=None,
        accelerator="cpu",
        mlx_ok=False,
        fast_gb=0.0,
        spill_gb=0.0,
        notes=[],
    )

    if system == "Darwin" and machine == "arm64":
        info.update(
            accelerator="apple-unified",
            mlx_ok=True,
            gpu=dict(name=info["cpu"], vram_gb=round(apple_gpu_share(ram), 1), kind="apple"),
        )
        info["fast_gb"] = round(apple_gpu_share(ram) - 2.0, 1)  # leave room for macOS + apps
        info["spill_gb"] = info["fast_gb"]  # unified: there is no slower pool to spill to
    else:
        cands = [
            g for g in gpus() if g["vram_gb"] >= 2.0
        ]  # under 2 GB is integrated / display-only
        best = max(cands, key=lambda g: g["vram_gb"], default=None)
        if best:
            info["gpu"] = dict(
                name=best["name"], vram_gb=round(best["vram_gb"], 1), kind=best["kind"]
            )
            info["accelerator"] = best["kind"]
            info["fast_gb"] = round(best["vram_gb"] - 0.5, 1)
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
        if system == "Darwin":
            info["notes"].append("Intel Mac: no MLX; Ollama runs on the CPU.")
    return info


def fit(need_gb, hw):
    """'fast' = fits on the accelerator; 'slow' = runs with CPU offload; 'no' = too big."""
    if hw["fast_gb"] > 0 and need_gb <= hw["fast_gb"]:
        return "fast"
    if need_gb <= hw["spill_gb"]:
        return "slow"
    return "no"


if __name__ == "__main__":
    print(json.dumps(probe(), indent=2))
