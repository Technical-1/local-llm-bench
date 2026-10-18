"""The result format: what every row in results.json carries, and how it is checked.

Results only compare across machines when the hardware travels with the
numbers, so each row holds a small hardware block. It describes the class of
machine (GPU model, memory sizes, CPU model, OS family) and never the person:
no hostname, user name, serial number or file path. validate_rows() enforces
that, and rejects numbers no real run can produce.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from . import __version__
from .runners import MAX_PLAUSIBLE_TPS
from .tasks import CATEGORIES

SCHEMA_VERSION = 1
MEM_TIERS_GB = (
    2, 3, 4, 6, 8, 10, 12, 16, 18, 20, 24, 32, 36, 40, 48, 64, 80, 96, 128, 192, 256, 512,
)  # fmt: skip
MAX_FILE_BYTES = 1024 * 1024
MAX_ROWS = 500
HOME_PATH = re.compile(r"(/Users/|/home/|[A-Za-z]:\\+Users\\+)", re.IGNORECASE)


def mem_tier(gb: float) -> int:
    """The nearest marketed size: a 12 GB card reports 11.99 GB, a 24 GB Mac 24.0."""
    return min(MEM_TIERS_GB, key=lambda t: abs(t - gb))


def hardware_block(hw: dict) -> dict:
    gpu = hw.get("gpu") or {}
    if hw.get("accelerator") == "apple-unified":
        hw_class, memory = "unified", hw["ram_gb"]
    elif gpu:
        hw_class, memory = "discrete_gpu", gpu["vram_gb"]
    else:
        hw_class, memory = "cpu_only", hw["ram_gb"]
    return {
        "hw_class": hw_class,
        "gpu": gpu.get("name"),
        "vram_gb": gpu.get("vram_gb"),
        "gpu_limit_source": hw.get("gpu_limit_source"),
        "mem_tier_gb": mem_tier(memory) if memory else None,
        "ram_gb": hw["ram_gb"],
        "cpu": hw["cpu"],
        "os": hw["os"].split()[0] if hw.get("os") else None,
        "arch": hw.get("arch"),
    }


def stamp(row: dict, hw: dict) -> dict:
    """Add the version, time and hardware fields to a fresh result row."""
    return {
        "schema_version": SCHEMA_VERSION,
        "tool_version": __version__,
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hardware": hardware_block(hw),
        **row,
    }


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def validate_row(row: dict) -> list[str]:
    """Every problem with one row, as readable messages; empty when it is valid."""
    if row.get("schema_version") is None:
        return ["no schema_version: made before results were versioned (llm-bench 0.1)"]
    if row["schema_version"] != SCHEMA_VERSION:
        return [f"schema_version {row['schema_version']}, this llm-bench reads {SCHEMA_VERSION}"]
    errs = []
    if not isinstance(row.get("model"), str) or not row["model"]:
        errs.append("model is missing")
    if row.get("runtime") not in ("ollama", "mlx"):
        errs.append(f"runtime {row.get('runtime')!r} is not ollama or mlx")

    q = row.get("quality") or {}
    for c in CATEGORIES:
        if not (_num(q.get(c)) and 0 <= q[c] <= 1):
            errs.append(f"quality.{c} must be between 0 and 1")
    if not (_num(row.get("quality_overall")) and 0 <= row["quality_overall"] <= 1):
        errs.append("quality_overall must be between 0 and 1")

    p = row.get("perf") or {}
    for k in ("load_s", "ttft_s", "prompt_tps", "gen_tps", "peak_gb"):
        if not (_num(p.get(k)) and p[k] >= 0):
            errs.append(f"perf.{k} must be a number, 0 or more")
    for k in ("prompt_tps", "gen_tps"):
        if _num(p.get(k)) and p[k] > MAX_PLAUSIBLE_TPS:
            errs.append(f"perf.{k} {p[k]} is faster than any local runtime")
    if _num(p.get("peak_gb")) and p["peak_gb"] > 2048:
        errs.append("perf.peak_gb is over 2 TB")
    if p.get("speed_runs") and not (p["gen_tps_min"] <= p["gen_tps"] <= p["gen_tps_max"]):
        errs.append("perf.gen_tps is outside its own min to max range")
    share = p.get("gpu_share")
    if share is not None and not (_num(share) and 0 <= share <= 1):
        errs.append("perf.gpu_share must be between 0 and 1")

    try:
        when = datetime.fromisoformat(row["measured_at"])
        if when > datetime.now(timezone.utc) + timedelta(minutes=5):
            errs.append("measured_at is in the future")
    except (KeyError, TypeError, ValueError):
        errs.append("measured_at is missing or not an ISO 8601 time")

    h = row.get("hardware") or {}
    if h.get("hw_class") not in ("unified", "discrete_gpu", "cpu_only"):
        errs.append("hardware.hw_class is missing")
    if not (_num(h.get("ram_gb")) and 0 < h["ram_gb"] <= 8192):
        errs.append("hardware.ram_gb must be between 0 and 8192")
    if h.get("vram_gb") is not None and not (_num(h["vram_gb"]) and 0 <= h["vram_gb"] <= 2048):
        errs.append("hardware.vram_gb must be between 0 and 2048")

    if any(HOME_PATH.search(s) for s in _strings(row)):
        errs.append("contains a home-folder path, which can hold a user name")
    return errs


def validate_rows(rows) -> list[str]:
    if not isinstance(rows, list):
        return ["results.json must hold a list of rows"]
    if len(rows) > MAX_ROWS:
        return [f"{len(rows)} rows; at most {MAX_ROWS}"]
    errs = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            errs.append(f"row {i + 1}: not an object")
            continue
        label = f"row {i + 1} ({row.get('model', '?')}, {row.get('runtime', '?')})"
        errs += [f"{label}: {e}" for e in validate_row(row)]
    return errs
