"""The two inference runtimes, behind one interface.

``run(target, prompt) -> Generation`` for each runtime, plus availability
checks. MLX is imported lazily so the package imports cleanly on Windows and
Linux, where it does not exist.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


def _ollama_url(host: str | None) -> str:
    """Client URL from OLLAMA_HOST, which may be a bind address like 0.0.0.0."""
    host = (host or "127.0.0.1:11434").replace("0.0.0.0", "127.0.0.1")
    if not host.startswith("http"):
        host = f"http://{host}"
    if host.count(":") == 1:  # scheme only, no port
        host += ":11434"
    return host.rstrip("/")


OLLAMA_URL = _ollama_url(os.environ.get("OLLAMA_HOST"))

MLX_MAX_TOKENS = 2048  # generous, so reasoning models can finish thinking AND answer
# Ollama counts reasoning against num_predict; a thinking model can exhaust a
# small budget before it emits the final answer, so give it more room.
OLLAMA_NUM_PREDICT = 6144

# Same resolution order as huggingface_hub: HF_HUB_CACHE, then HF_HOME/hub.
HF_CACHE = Path(
    os.environ.get("HF_HUB_CACHE")
    or Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface") / "hub"
)

THINKING_MARKERS = ("</think>", "</thinking>", "<channel|>", "<|channel|>")


@dataclass
class Generation:
    text: str
    load_s: float = 0.0
    ttft_s: float = 0.0
    prompt_tps: float = 0.0
    gen_tps: float = 0.0
    peak_gb: float = 0.0


def strip_thinking(text: str) -> str:
    """Score only the final answer: drop the model's reasoning block.

    Families mark the boundary differently (Qwen/Nemotron close with
    ``</think>``; Gemma 4 opens its final channel with ``<channel|>``).
    The user-facing answer follows the last marker; non-thinking models are
    unaffected. This keeps reasoning and non-reasoning models comparable.
    """
    for tag in THINKING_MARKERS:
        if tag in text:
            return text.split(tag)[-1].strip()
    return text.strip()


# ---------------- Ollama ----------------
def ollama_status() -> tuple[bool, set[str]]:
    """(installed, pulled tags).

    Asks the server first, so a running Ollama is found even when its CLI is
    not on PATH (common on Windows right after install).
    """
    try:
        import httpx

        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return True, {m["name"] for m in r.json().get("models", [])}
    except Exception:
        pass
    exe = shutil.which("ollama")
    if not exe:
        return False, set()
    try:
        out = subprocess.run([exe, "list"], capture_output=True, text=True, timeout=10).stdout
        return True, {line.split()[0] for line in out.splitlines()[1:] if line.strip()}
    except Exception:
        return True, set()


def ollama_has(tags: set[str], tag: str) -> bool:
    """True if pulled. An untagged pull is listed as ``name:latest``."""
    return tag in tags or (":" not in tag and f"{tag}:latest" in tags)


def _ollama_resident_gb(tag: str) -> float:
    try:
        import httpx

        for m in httpx.get(f"{OLLAMA_URL}/api/ps", timeout=5).json().get("models", []):
            name = m.get("name", "")
            if name == tag or name.split(":")[0] == tag.split(":")[0]:
                return m.get("size", 0) / 1e9
    except Exception:
        pass
    return 0.0


def run_ollama(tag: str, prompt: str) -> Generation:
    import httpx

    r = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": tag,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0, "num_predict": OLLAMA_NUM_PREDICT},
        },
        timeout=900,
    )
    r.raise_for_status()
    d = r.json()
    ns = 1e9
    p_cnt, p_dur = d.get("prompt_eval_count", 0), d.get("prompt_eval_duration", 0) or 1
    e_cnt, e_dur = d.get("eval_count", 0), d.get("eval_duration", 0) or 1
    # Ollama returns `thinking` separately from `response`. Some builds over-think
    # and never emit a final response (done_reason=length); fall back to the
    # thinking text so we score the model's answer, not the runtime's quirk.
    text = (d.get("response") or "").strip() or (d.get("thinking") or "")
    load = d.get("load_duration", 0)
    return Generation(
        text=text,
        load_s=load / ns,
        ttft_s=(load + d.get("prompt_eval_duration", 0)) / ns,
        prompt_tps=p_cnt / (p_dur / ns),
        gen_tps=e_cnt / (e_dur / ns),
        peak_gb=_ollama_resident_gb(tag),
    )


# ---------------- MLX (Apple Silicon) ----------------
def mlx_installed() -> bool:
    try:
        import mlx_lm  # noqa: F401
    except ImportError:
        return False
    return True


def mlx_downloaded(repo: str) -> bool:
    """True if the repo has at least one complete weight blob in the HF cache."""
    blobs = HF_CACHE / ("models--" + repo.replace("/", "--")) / "blobs"
    return blobs.exists() and any(not b.name.endswith(".incomplete") for b in blobs.iterdir())


_mlx_loaded: dict[str, tuple[object, object, float]] = {}


def run_mlx(repo: str, prompt: str) -> Generation:
    import mlx.core as mx
    from mlx_lm import load, stream_generate

    if repo not in _mlx_loaded:
        _mlx_loaded.clear()  # keep one model resident at a time
        t0 = time.time()
        model, tok = load(repo)
        _mlx_loaded[repo] = (model, tok, time.time() - t0)
    model, tok, load_s = _mlx_loaded[repo]

    chat = tok.apply_chat_template(
        [{"role": "user", "content": prompt}], add_generation_prompt=True, tokenize=False
    )
    mx.reset_peak_memory()
    t0 = time.time()
    ttft = None
    out: list[str] = []
    prompt_tps = gen_tps = 0.0
    for resp in stream_generate(model, tok, chat, max_tokens=MLX_MAX_TOKENS):
        if ttft is None:
            ttft = time.time() - t0
        out.append(resp.text)
        prompt_tps = getattr(resp, "prompt_tps", prompt_tps)
        gen_tps = getattr(resp, "generation_tps", gen_tps)
    return Generation(
        text="".join(out),
        load_s=load_s,
        ttft_s=ttft or 0.0,
        prompt_tps=prompt_tps,
        gen_tps=gen_tps,
        peak_gb=mx.get_peak_memory() / 1e9,
    )
