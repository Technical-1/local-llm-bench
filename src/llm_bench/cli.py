"""Command line: ``llm-bench check | run | report``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, estimate, hwprobe, runners
from .bench import ResultStore, run_models
from .registry import BY_NAME, DEFAULT_CTX, MODELS, Model
from .report import render

VERDICT = {"fast": "fits - fast", "slow": "runs - slow (CPU offload)", "no": "too big"}


def _utf8_console() -> None:
    # Windows consoles default to a legacy code page; keep output printable.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def estimate_runtime(hw: dict) -> str:
    """Which build the memory estimate assumes: MLX's on Apple Silicon, else Ollama's."""
    return "mlx" if hw["mlx_ok"] else "ollama"


def _load_rows(out: Path) -> list[dict]:
    path = out / "results.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _measured(rows: list[dict], name: str, runtime: str) -> str:
    """'5.3 GB, 61 tok/s' from an earlier run on this machine, or '-'."""
    mine = [r for r in rows if r["model"] == name]
    row = next((r for r in mine if r["runtime"] == runtime), mine[0] if mine else None)
    if not row:
        return "-"
    p = row["perf"]
    return f"{p['peak_gb']:.1f} GB, {p['gen_tps']:.0f} tok/s ({row['runtime']})"


def cmd_check(hw: dict, ollama_ok: bool, tags: set[str], ctx: int = DEFAULT_CTX, rows=()) -> int:
    gpu = hw["gpu"]
    source = f", limit from {hw['gpu_limit_source']}" if hw.get("gpu_limit_source") else ""
    gpu_line = (
        f"{gpu['name']} ({gpu['vram_gb']:.1f} GB usable{source})"
        if gpu
        else "none detected - CPU only"
    )
    print("== This machine ==")
    print(f"  OS        {hw['os']} ({hw['arch']})")
    print(f"  CPU       {hw['cpu']}")
    ram_free = hw.get("ram_free_gb")
    free_txt = f" ({ram_free:.1f} GB free now)" if ram_free is not None else ""
    print(f"  RAM       {hw['ram_gb']:.1f} GB{free_txt}")
    print(f"  GPU       {gpu_line}")
    print(f"  Budget    {hw['fast_gb']:.1f} GB fast, {hw['spill_gb']:.1f} GB with CPU offload")
    free_now = hwprobe.free_budget(hw)
    if free_now is not None:
        print(f"  Free now  {free_now:.1f} GB on the accelerator, after the apps already running")
    ollama = "found" if ollama_ok else "NOT FOUND - install from https://ollama.com"
    mlx = (
        ("installed" if runners.mlx_installed() else "available (pip install mlx-lm)")
        if hw["mlx_ok"]
        else "n/a (Apple Silicon only)"
    )
    print(f"  Runtimes  ollama: {ollama} | mlx: {mlx}")
    for note in hw["notes"]:
        print(f"  note: {note}")

    rt = estimate_runtime(hw)
    print(f"\n== Models (estimates at {ctx:,} tokens of context, {rt} weights) ==")
    print(
        f"  {'model':<20} {'needs':>7} {'est tok/s':>9}  {'verdict':<27} {'pulled':<7} "
        f"{'measured here':<32} next step"
    )
    busy = False
    for m in sorted(MODELS, key=lambda m: m.need_gb(ctx, rt)):
        need = m.need_gb(ctx, rt)
        verdict = hwprobe.fit(need, hw)
        label = VERDICT[verdict]
        if verdict == "fast" and free_now is not None and need > free_now:
            label += " *"
            busy = True
        tps = estimate.tokens_per_sec(m, hw, rt, ctx=ctx)
        speed = f"~{tps:.0f}" if tps else "?"
        pulled = runners.ollama_has(tags, m.ollama)
        step = f"ollama pull {m.ollama}" if verdict != "no" and not pulled else ""
        print(
            f"  {m.name:<20} {need:>5.1f}GB {speed:>9}  {label:<27} "
            f"{'yes' if pulled else '-':<7} {_measured(rows, m.name, rt):<32} {step}"
        )
    if busy:
        print(
            f"\n  * fits this machine, but not in the {free_now:.1f} GB free right now. "
            "Close other apps first, or it will be slow."
        )
    print(
        "\n  needs and est tok/s are estimates from the model's size and this machine's "
        "memory bandwidth;\n  ? means no basis for one (unknown or laptop GPU, or CPU "
        "offload). 'measured here' is from llm-bench run."
    )
    print("\nNext: pull one or more models marked 'fits', then  llm-bench run")
    return 0


def _select(spec: str, include_slow: bool, hw: dict) -> list[Model]:
    if spec == "all":
        return list(MODELS)
    if spec == "fit":
        ok = {"fast", "slow"} if include_slow else {"fast"}
        rt = estimate_runtime(hw)
        return [m for m in MODELS if hwprobe.fit(m.need_gb(DEFAULT_CTX, rt), hw) in ok]
    names = [n.strip() for n in spec.split(",") if n.strip()]
    unknown = [n for n in names if n not in BY_NAME]
    if unknown:
        raise SystemExit(f"Unknown model(s): {', '.join(unknown)}. Known: {', '.join(BY_NAME)}")
    return [BY_NAME[n] for n in names]


def _resolve_runtime(requested: str, hw: dict, ollama_ok: bool) -> str:
    mlx_ready = hw["mlx_ok"] and runners.mlx_installed()
    if requested == "auto":
        if mlx_ready:
            return "both" if ollama_ok else "mlx"
        requested = "ollama"
    if requested in ("mlx", "both") and not hw["mlx_ok"]:
        raise SystemExit("MLX needs an Apple Silicon Mac. Use --runtime ollama.")
    if requested in ("mlx", "both") and not mlx_ready:
        raise SystemExit("mlx-lm is not installed: pip install mlx-lm (or --runtime ollama).")
    if requested in ("ollama", "both") and not ollama_ok:
        raise SystemExit("Ollama not found. Install it from https://ollama.com, start it, re-run.")
    return requested


def cmd_run(args, hw: dict, ollama_ok: bool, tags: set[str]) -> int:
    runtime = _resolve_runtime(args.runtime, hw, ollama_ok)
    models = _select(args.models, args.include_slow, hw)
    print(f"Runtime: {runtime} | models: {', '.join(m.name for m in models) or 'none'}")
    store = ResultStore(args.out / "results.json")
    ran = run_models(models, runtime, store, tags)
    print(
        f"\nRan {ran} model x runtime configuration(s); {len(store.rows)} row(s) in {store.path}"
    )
    if ran == 0:
        print("Nothing ran. See  llm-bench check  for what to download.")
        return 1
    return cmd_report(args, hw)


def cmd_report(args, hw: dict) -> int:
    results = args.out / "results.json"
    rows = json.loads(results.read_text(encoding="utf-8")) if results.exists() else []
    md = render(rows, hw)
    (args.out / "scorecard.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"-> {args.out / 'scorecard.md'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    ap = argparse.ArgumentParser(
        prog="llm-bench",
        description="Which local LLMs can this machine run, and how good are they?",
    )
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("llm-bench-results"),
        help="where results.json, hardware.json and scorecard.md go "
        "(default: ./llm-bench-results)",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="show this machine's budget and which models fit; runs nothing")
    run = sub.add_parser("run", help="benchmark models, then write the scorecard")
    run.add_argument(
        "--models",
        default="fit",
        help="'fit' (default: downloaded models that fit), 'all', or a comma list",
    )
    run.add_argument(
        "--include-slow",
        action="store_true",
        help="with --models fit, also run models that need CPU offload",
    )
    run.add_argument(
        "--runtime",
        choices=["auto", "ollama", "mlx", "both"],
        default="auto",
        help="auto = both on Apple Silicon with mlx-lm installed, else ollama",
    )
    sub.add_parser("report", help="re-render the scorecard from saved results")
    args = ap.parse_args(argv)

    hw = hwprobe.probe()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "hardware.json").write_text(json.dumps(hw, indent=2), encoding="utf-8")
    if args.cmd == "report":
        return cmd_report(args, hw)
    ollama_ok, tags = runners.ollama_status()
    if args.cmd == "check":
        return cmd_check(hw, ollama_ok, tags, rows=_load_rows(args.out))
    return cmd_run(args, hw, ollama_ok, tags)


if __name__ == "__main__":
    sys.exit(main())
