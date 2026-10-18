"""Render result rows into a Markdown scorecard: ranking, quality, performance."""

from __future__ import annotations

import statistics

from . import estimate
from .registry import BY_NAME, DEFAULT_CTX
from .tasks import CATEGORIES

QUALITY_WEIGHT = 0.70
SPEED_WEIGHT = 0.30
SPEED_FULL_MARKS_TPS = 80.0  # generation speed that earns the full speed score


def composite(row: dict) -> float:
    """70% quality + 30% speed. Speed saturates at 80 tok/s, comfortably
    faster than anyone reads, so a quicker but worse model can't win on speed alone."""
    speed = min(row["perf"]["gen_tps"] / SPEED_FULL_MARKS_TPS, 1.0)
    return round(QUALITY_WEIGHT * row["quality_overall"] + SPEED_WEIGHT * speed, 3)


def _pct(x: float) -> str:
    return f"{round(x * 100)}%"


def bench_ctx(row: dict) -> int:
    """The largest context the run used: Ollama's window, or MLX's longest prompt."""
    if row["perf"].get("num_ctx"):
        return row["perf"]["num_ctx"]
    prompts = [d.get("prompt_tokens", 0) for d in row.get("details", [])]
    return max(prompts, default=0) or DEFAULT_CTX


def estimates(row: dict, hw: dict) -> tuple[float | None, float | None]:
    """(estimated GB at the run's context, estimated tok/s) for a result row."""
    m = BY_NAME.get(row["model"])
    if not m:
        return None, None
    repo = row.get("target") if row["runtime"] == "mlx" else None
    gb = m.need_gb(bench_ctx(row), row["runtime"], repo)
    return gb, estimate.tokens_per_sec(m, hw, row["runtime"], repo)


def _num(x: float | None, fmt: str) -> str:
    return "?" if x is None else format(x, fmt)


def _spread(perf: dict) -> str:
    """Min to max generation speed across the speed-pass runs."""
    if not perf.get("speed_runs"):
        return "-"
    return f"{perf['gen_tps_min']:.0f} to {perf['gen_tps_max']:.0f}"


def _gpu_share(perf: dict) -> str:
    """Measured share of the model on the GPU; under 100% means CPU offload."""
    share = perf.get("gpu_share")
    return "-" if share is None else _pct(share)


def machine_line(hw: dict) -> str:
    if not hw:
        return "hardware unknown"
    gpu = hw.get("gpu") or {}
    accel = f"{gpu['name']}, {gpu['vram_gb']:.0f} GB" if gpu else "CPU only"
    return f"{hw.get('cpu', '?')} · {hw.get('ram_gb', 0):.0f} GB RAM · {accel}"


def render(rows: list[dict], hw: dict) -> str:
    if not rows:
        return "# Local LLM Benchmark: Scorecard\n\nNo results yet. Run `llm-bench run` first.\n"
    budget = hw.get("fast_gb") or 0.0
    ranked = sorted(rows, key=composite, reverse=True)
    out = [
        "# Local LLM Benchmark: Scorecard",
        "",
        f"_{len(rows)} model × runtime configurations · {machine_line(hw)}_",
        "",
        "Composite = 70% quality (auto-scored accuracy) + 30% speed "
        f"(median generation tok/s over the speed pass, full marks at "
        f"{SPEED_FULL_MARKS_TPS:.0f}).",
        f"Fits = measured peak memory ≤ {budget:.1f} GB, this machine's accelerator budget.",
        "",
        "## Overall ranking",
        "",
        "| Rank | Model | Runtime | Vendor | Arch | Composite | Quality "
        "| Gen tok/s | Peak GB | Fits |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(ranked, 1):
        p = r["perf"]
        fits = "✓" if 0 < p["peak_gb"] <= budget else "✗"
        out.append(
            f"| {i} | {r['model']} | {r['runtime']} | {r['vendor']} | {r['arch']} | "
            f"**{composite(r):.3f}** | {_pct(r['quality_overall'])} | {p['gen_tps']:.0f} | "
            f"{p['peak_gb']:.1f} | {fits} |"
        )

    out += [
        "",
        "## Quality by category",
        "",
        "| Model | Runtime | " + " | ".join(c.capitalize() for c in CATEGORIES) + " | Overall |",
        "|---|---|" + "---|" * (len(CATEGORIES) + 1),
    ]
    for r in ranked:
        cells = " | ".join(_pct(r["quality"].get(c, 0.0)) for c in CATEGORIES)
        out.append(
            f"| {r['model']} | {r['runtime']} | {cells} | **{_pct(r['quality_overall'])}** |"
        )

    out += [
        "",
        "## Performance",
        "",
        "Est columns are the formula's prediction for this machine (? = no basis); "
        "every other column is measured.",
        "",
        "| Model | Runtime | Load s | TTFT s | Prompt tok/s | Est tok/s | Gen tok/s "
        "| Gen range | Est GB | Peak GB | On GPU |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    ratios = []
    for r in sorted(rows, key=lambda r: r["perf"]["gen_tps"], reverse=True):
        p = r["perf"]
        est_gb, est_tps = estimates(r, hw)
        if est_tps and p["gen_tps"]:
            ratios.append(p["gen_tps"] / est_tps)
        out.append(
            f"| {r['model']} | {r['runtime']} | {p['load_s']:.1f} | {p['ttft_s']:.2f} | "
            f"{p['prompt_tps']:.0f} | {_num(est_tps, '.0f')} | {p['gen_tps']:.0f} | "
            f"{_spread(p)} | {_num(est_gb, '.1f')} | {p['peak_gb']:.1f} | {_gpu_share(p)} |"
        )
    if ratios:
        out += [
            "",
            f"Measured speed was {statistics.median(ratios):.2f}x the estimate "
            f"(median of {len(ratios)}).",
        ]

    cut = [r for r in rows if r.get("truncated_tasks")]
    if cut:
        out += [
            "",
            "**Warning:** the runtime dropped part of the prompt, so these scores "
            "understate the model:",
            "",
        ]
        out += [f"- {r['model']} ({r['runtime']}): {', '.join(r['truncated_tasks'])}" for r in cut]

    out += ["", "## Per-axis winners", ""]
    out.append(f"- **Best overall:** {ranked[0]['model']} ({ranked[0]['runtime']})")
    for c in CATEGORIES:
        w = max(rows, key=lambda r: r["quality"].get(c, 0.0))
        out.append(f"- **Best {c}:** {w['model']}, {_pct(w['quality'].get(c, 0.0))}")
    fast = max(rows, key=lambda r: r["perf"]["gen_tps"])
    out.append(
        f"- **Fastest:** {fast['model']} ({fast['runtime']}), {fast['perf']['gen_tps']:.0f} tok/s"
    )
    measured = [r for r in rows if r["perf"]["peak_gb"] > 0]
    if measured:
        lean = min(measured, key=lambda r: r["perf"]["peak_gb"])
        out.append(f"- **Leanest:** {lean['model']}, {lean['perf']['peak_gb']:.1f} GB")

    by_model: dict[str, dict[str, dict]] = {}
    for r in rows:
        by_model.setdefault(r["model"], {})[r["runtime"]] = r
    pairs = {m: d for m, d in by_model.items() if {"mlx", "ollama"} <= d.keys()}
    if pairs:
        out += [
            "",
            "## MLX vs Ollama (same model)",
            "",
            "| Model | MLX tok/s | Ollama tok/s | MLX quality | Ollama quality |",
            "|---|---|---|---|---|",
        ]
        for m, d in pairs.items():
            mlx, oll = d["mlx"], d["ollama"]
            out.append(
                f"| {m} | {mlx['perf']['gen_tps']:.0f} | {oll['perf']['gen_tps']:.0f} | "
                f"{_pct(mlx['quality_overall'])} | {_pct(oll['quality_overall'])} |"
            )
    return "\n".join(out) + "\n"
