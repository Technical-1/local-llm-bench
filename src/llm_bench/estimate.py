"""Estimated generation speed, before a model is downloaded.

Generating a token reads every active weight once, so speed is bounded by
memory bandwidth: tok/s ~= bandwidth / bytes read per token x efficiency.
Bandwidths are public spec-sheet figures. Laptop GPUs return no estimate:
the same name as a desktop card often hides a narrower memory bus. An
unknown GPU, or a model that spills to the CPU, also gets no estimate.

Every number here is labelled an estimate wherever it is shown, and the
scorecard puts it next to the measured speed so the formula stays honest.
"""

from __future__ import annotations

import re

from . import hwprobe
from .registry import DEFAULT_CTX, Model

# Share of peak bandwidth a runtime achieves while generating.
#   apple: calibrated on three MLX runs on an M4 Pro (measured 0.67 to 0.89).
#   other: llmfit's figure for discrete GPUs, not yet checked against our runs.
EFFICIENCY = {"apple": 0.75, "other": 0.55}

# GB/s. Longest matching key wins, so "rtx 4070 ti" is found before "rtx 4070".
BANDWIDTH_GBPS = {
    # Apple Silicon
    "apple m1": 68, "apple m1 pro": 200, "apple m1 max": 400, "apple m1 ultra": 800,
    "apple m2": 100, "apple m2 pro": 200, "apple m2 max": 400, "apple m2 ultra": 800,
    "apple m3": 100, "apple m3 pro": 150, "apple m3 max": 400, "apple m3 ultra": 819,
    "apple m4": 120, "apple m4 pro": 273, "apple m4 max": 546,
    "apple m5": 153,
    # NVIDIA desktop
    "rtx 5090": 1792, "rtx 5080": 960, "rtx 5070 ti": 896, "rtx 5070": 672,
    "rtx 5060 ti": 448, "rtx 5060": 448,
    "rtx 4090": 1008, "rtx 4080 super": 736, "rtx 4080": 717,
    "rtx 4070 ti super": 672, "rtx 4070 ti": 504, "rtx 4070 super": 504, "rtx 4070": 504,
    "rtx 4060 ti": 288, "rtx 4060": 272,
    "rtx 3090 ti": 1008, "rtx 3090": 936, "rtx 3080 ti": 912, "rtx 3080": 760,
    "rtx 3070 ti": 608, "rtx 3070": 448, "rtx 3060 ti": 448, "rtx 3060": 360,
    # AMD desktop
    "rx 9070 xt": 644, "rx 9070": 640,
    "rx 7900 xtx": 960, "rx 7900 xt": 800, "rx 7800 xt": 624, "rx 7700 xt": 432,
    "rx 7600": 288,
    # AMD Ryzen AI Max (Strix Halo): 256-bit LPDDR5X-8000 shared with the CPU
    "radeon 8060s": 256, "radeon 8050s": 256,
}  # fmt: skip


def bandwidth_gbps(gpu_name: str) -> float | None:
    name = " ".join(re.sub(r"\((tm|r)\)", "", gpu_name.lower()).split())
    if "laptop" in name or "mobile" in name:
        return None
    # lspci can name two cards at once ("Radeon RX 7900 XT/7900 XTX"); there is
    # no telling which one this is, and their bandwidths differ
    if re.search(r"\[[^\]]*\d[^\]]*/[^\]]*\]", name):
        return None
    for key in sorted(BANDWIDTH_GBPS, key=len, reverse=True):
        if key in name:
            return float(BANDWIDTH_GBPS[key])
    return None


def tokens_per_sec(
    model: Model, hw: dict, runtime: str, repo: str | None = None, ctx: int = DEFAULT_CTX
) -> float | None:
    """Estimated generation tok/s on this machine; None when there is no basis for one."""
    gpu = hw.get("gpu")
    if not gpu or hwprobe.fit(model.need_gb(ctx, runtime, repo), hw) != "fast":
        return None
    bw = bandwidth_gbps(gpu["name"])
    if bw is None:
        return None
    bytes_per_token = model.active_b * 1e9 * model.bytes_per_weight(runtime, repo)
    eff = EFFICIENCY["apple" if gpu.get("kind") == "apple" else "other"]
    return round(bw * 1e9 / bytes_per_token * eff, 1)
