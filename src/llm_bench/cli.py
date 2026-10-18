"""Command line: ``llm-bench check | run | report | validate | doctor``."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__, estimate, hwprobe, runners, schema
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


def _measured(rows, name: str, runtime: str) -> dict | None:
    """An earlier run of this model on this machine, preferring the same runtime."""
    mine = [r for r in rows if r["model"] == name]
    row = next((r for r in mine if r["runtime"] == runtime), mine[0] if mine else None)
    if not row:
        return None
    p = row["perf"]
    return {"runtime": row["runtime"], "peak_gb": p["peak_gb"], "gen_tps": p["gen_tps"]}


def check_models(hw: dict, tags: set[str], ctx: int, rows=()) -> list[dict]:
    """One row per registry model: estimates, verdict, and any earlier measurement."""
    rt = estimate_runtime(hw)
    free_now = hwprobe.free_budget(hw)
    out = []
    for m in sorted(MODELS, key=lambda m: m.need_gb(ctx, rt)):
        need = m.need_gb(ctx, rt)
        verdict = hwprobe.fit(need, hw)
        out.append(
            {
                "model": m.name,
                "ollama": m.ollama,
                "mlx": m.mlx,
                "need_gb": need,
                "est_tps": estimate.tokens_per_sec(m, hw, rt, ctx=ctx),
                "verdict": verdict,
                "short_of_free_memory": verdict == "fast"
                and free_now is not None
                and need > free_now,
                "max_ctx_fast": m.max_ctx_within(hw["fast_gb"], rt) if hw["fast_gb"] > 0 else 0,
                "pulled": runners.ollama_has(tags, m.ollama),
                "measured": _measured(rows, m.name, rt),
            }
        )
    return out


def _ctx_label(n: int) -> str:
    return "-" if n <= 0 else f"{n // 1024}k"


def check_json(hw: dict, ollama_ok: bool, tags: set[str], ctx: int, rows=()) -> dict:
    """Everything check prints, as data for scripts and other tools."""
    return {
        "schema_version": schema.SCHEMA_VERSION,
        "tool_version": __version__,
        "context_tokens": ctx,
        "estimate_runtime": estimate_runtime(hw),
        "hardware": hw,
        "free_now_gb": hwprobe.free_budget(hw),
        "runtimes": {"ollama": ollama_ok, "mlx": hw["mlx_ok"] and runners.mlx_installed()},
        "models": check_models(hw, tags, ctx, rows),
    }


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
    models = check_models(hw, tags, ctx, rows)
    print(f"\n== Models (estimates at {ctx:,} tokens of context, {rt} weights) ==")
    print(
        f"  {'model':<20} {'needs':>7} {'est tok/s':>9} {'max ctx':>7}  {'verdict':<27} "
        f"{'pulled':<7} {'measured here':<26} next step"
    )
    for r in models:
        label = VERDICT[r["verdict"]] + (" *" if r["short_of_free_memory"] else "")
        speed = f"~{r['est_tps']:.0f}" if r["est_tps"] else "?"
        meas = r["measured"]
        meas_txt = (
            f"{meas['peak_gb']:.1f} GB, {meas['gen_tps']:.0f} tok/s ({meas['runtime']})"
            if meas
            else "-"
        )
        step = f"ollama pull {r['ollama']}" if r["verdict"] != "no" and not r["pulled"] else ""
        print(
            f"  {r['model']:<20} {r['need_gb']:>5.1f}GB {speed:>9} "
            f"{_ctx_label(r['max_ctx_fast']):>7}  {label:<27} "
            f"{'yes' if r['pulled'] else '-':<7} {meas_txt:<26} {step}"
        )
    if any(r["short_of_free_memory"] for r in models):
        print(
            f"\n  * fits this machine, but not in the {free_now:.1f} GB free right now. "
            "Close other apps first, or it will be slow."
        )
    print(
        "\n  needs, est tok/s and max ctx are estimates from the model's architecture and this "
        "machine's\n  memory and bandwidth. max ctx is the longest context that still fits "
        "fast. ? means no basis\n  for an estimate (unknown or laptop GPU, or CPU offload). "
        "'measured here' is from llm-bench run."
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
    ran = run_models(models, runtime, store, tags, hw)
    print(
        f"\nRan {ran} model x runtime configuration(s); {len(store.rows)} row(s) in {store.path}"
    )
    if ran == 0:
        print("Nothing ran. See  llm-bench check  for what to download.")
        return 1
    return cmd_report(args, hw)


def cmd_doctor(hw: dict) -> int:
    """Raw probe output beside the conclusions, ready to paste into an issue."""
    print(f"llm-bench {__version__} doctor. Paste everything below into a GitHub issue.\n")
    for label, text in hwprobe.raw_sources():
        print(f"--- {label}")
        print(text.strip() if text and text.strip() else "(empty)")
    print("--- ollama")
    print(f"OLLAMA_HOST set: {'yes' if os.environ.get('OLLAMA_HOST') else 'no'}")
    for path in ("/api/version", "/api/tags", "/api/ps"):
        print(f"{path}: {runners.ollama_get(path)}")
    print("--- what llm-bench concluded (probe)")
    print(json.dumps(hw, indent=2))
    return 0


def cmd_validate(path: Path) -> int:
    """Check a results file against the result format; exit 1 if anything is wrong."""
    if not path.exists():
        raise SystemExit(f"No results at {path}. Run  llm-bench run  first.")
    if path.stat().st_size > schema.MAX_FILE_BYTES:
        print(f"{path}: larger than {schema.MAX_FILE_BYTES // 1024} KiB")
        return 1
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        print(f"{path}: not valid JSON ({e})")
        return 1
    errs = schema.validate_rows(rows)
    for e in errs:
        print(e)
    print(f"{path}: {len(rows)} row(s), " + (f"{len(errs)} problem(s)" if errs else "all valid"))
    return 1 if errs else 0


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
    check = sub.add_parser(
        "check", help="show this machine's budget and which models fit; runs nothing"
    )
    check.add_argument(
        "--ctx",
        type=int,
        default=DEFAULT_CTX,
        help=f"grade at this many tokens of context (default {DEFAULT_CTX})",
    )
    check.add_argument(
        "--vram",
        type=float,
        metavar="GB",
        help="grade a graphics card with this much VRAM instead of the detected one",
    )
    check.add_argument(
        "--ram",
        type=float,
        metavar="GB",
        help="grade this much system RAM (unified memory on a Mac) instead of the detected amount",
    )
    check.add_argument("--json", action="store_true", help="print the result as JSON")
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
    sub.add_parser("doctor", help="print raw hardware and Ollama details for a bug report")
    validate = sub.add_parser("validate", help="check a results file against the result format")
    validate.add_argument("file", nargs="?", type=Path, help="default: <out>/results.json")
    args = ap.parse_args(argv)

    if args.cmd == "validate":
        return cmd_validate(args.file or args.out / "results.json")

    hw = hwprobe.probe()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "hardware.json").write_text(json.dumps(hw, indent=2), encoding="utf-8")
    if args.cmd == "report":
        return cmd_report(args, hw)
    if args.cmd == "doctor":
        return cmd_doctor(hw)
    ollama_ok, tags = runners.ollama_status()
    if args.cmd == "check":
        if args.ctx <= 0:
            raise SystemExit("--ctx must be a positive number of tokens.")
        graded = hwprobe.override(hw, vram=args.vram, ram=args.ram)
        rows = _load_rows(args.out)
        if args.json:
            print(json.dumps(check_json(graded, ollama_ok, tags, args.ctx, rows), indent=2))
            return 0
        return cmd_check(graded, ollama_ok, tags, args.ctx, rows=rows)
    return cmd_run(args, hw, ollama_ok, tags)


if __name__ == "__main__":
    sys.exit(main())
