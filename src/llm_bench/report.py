"""Render result rows into a Markdown scorecard: ranking, quality, performance."""

from __future__ import annotations

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
        f"(generation tok/s, full marks at {SPEED_FULL_MARKS_TPS:.0f}).",
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
        "| Model | Runtime | Load s | TTFT s | Prompt tok/s | Gen tok/s | Peak GB |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda r: r["perf"]["gen_tps"], reverse=True):
        p = r["perf"]
        out.append(
            f"| {r['model']} | {r['runtime']} | {p['load_s']:.1f} | {p['ttft_s']:.2f} | "
            f"{p['prompt_tps']:.0f} | {p['gen_tps']:.0f} | {p['peak_gb']:.1f} |"
        )

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
