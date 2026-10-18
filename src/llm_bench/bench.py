"""Run models through the task suite and record quality + performance."""

from __future__ import annotations

import json
from pathlib import Path

from . import runners
from .registry import Model
from .tasks import CATEGORIES, TASKS


def _avg(xs: list[float]) -> float:
    return round(sum(xs) / len(xs), 2) if xs else 0.0


def bench_one(model: Model, runtime: str, target: str, log=print) -> dict:
    """Run every task once on one model x runtime; return a result row."""
    run = runners.run_mlx if runtime == "mlx" else runners.run_ollama
    scores: dict[str, list[float]] = {c: [] for c in CATEGORIES}
    load_s = ttft_s = peak_gb = 0.0
    prompt_tps: list[float] = []
    gen_tps: list[float] = []
    details = []
    num_ctx = 0
    gpu_shares: list[float] = []
    truncated: list[str] = []
    for task in TASKS:
        try:
            g = run(target, task["prompt"])
            score = float(task["scorer"](runners.strip_thinking(g.text)))
        except Exception as e:  # a failed task scores 0; the run continues
            g = runners.Generation(text=f"<ERROR {e}>")
            score = 0.0
        scores[task["category"]].append(score)
        load_s, ttft_s = max(load_s, g.load_s), max(ttft_s, g.ttft_s)
        peak_gb = max(peak_gb, g.peak_gb)
        num_ctx = max(num_ctx, g.num_ctx)
        if g.gpu_share is not None:
            gpu_shares.append(g.gpu_share)
        if g.truncated:
            truncated.append(task["id"])
        if g.prompt_tps:
            prompt_tps.append(g.prompt_tps)
        if g.gen_tps:
            gen_tps.append(g.gen_tps)
        details.append(
            {
                "task": task["id"],
                "cat": task["category"],
                "score": score,
                "gen_tps": round(g.gen_tps, 1),
                "prompt_tokens": g.prompt_tokens,
                "truncated": g.truncated,
            }
        )
        flag = "  PROMPT TRUNCATED" if g.truncated else ""
        log(f"    {task['id']:<22} score={score:.2f}  {g.gen_tps:6.1f} tok/s{flag}")
    return {
        "model": model.name,
        "runtime": runtime,
        "target": target,
        "vendor": model.vendor,
        "arch": model.arch,
        "quality": {c: _avg(scores[c]) for c in CATEGORIES},
        "quality_overall": _avg([s for c in CATEGORIES for s in scores[c]]),
        "perf": {
            "load_s": round(load_s, 1),
            "ttft_s": round(ttft_s, 2),
            "prompt_tps": _avg(prompt_tps),
            "gen_tps": _avg(gen_tps),
            "peak_gb": round(peak_gb, 1),
            "num_ctx": num_ctx,
            # the worst task: a long prompt can push layers off the GPU
            "gpu_share": round(min(gpu_shares), 2) if gpu_shares else None,
        },
        "truncated_tasks": truncated,
        "details": details,
    }


class ResultStore:
    """results.json: one row per model x runtime, replaced on re-run, so
    results accumulate across sessions. Saved after every model, so an
    interrupted run keeps what finished."""

    def __init__(self, path: Path):
        self.path = path
        self.rows: list[dict] = (
            json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        )

    def put(self, row: dict) -> None:
        key = (row["model"], row["runtime"])
        self.rows = [r for r in self.rows if (r["model"], r["runtime"]) != key] + [row]
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.rows, indent=2), encoding="utf-8")


def run_models(
    models: list[Model], runtime: str, store: ResultStore, tags: set[str], log=print
) -> int:
    """Benchmark each model on the chosen runtime(s); skip what isn't downloaded."""
    ran = 0
    for m in models:
        if runtime in ("mlx", "both"):
            repo = next((r for r in (m.mlx, m.mlx_alt) if r and runners.mlx_downloaded(r)), None)
            if repo:
                log(f"\n=== {m.name} [mlx: {repo}] ===")
                store.put(bench_one(m, "mlx", repo, log))
                ran += 1
            else:
                log(f"--- skip {m.name} [mlx]: not downloaded (huggingface-cli download {m.mlx})")
        if runtime in ("ollama", "both"):
            if runners.ollama_has(tags, m.ollama):
                log(f"\n=== {m.name} [ollama: {m.ollama}] ===")
                store.put(bench_one(m, "ollama", m.ollama, log))
                ran += 1
            else:
                log(f"--- skip {m.name} [ollama]: not pulled (ollama pull {m.ollama})")
    return ran
