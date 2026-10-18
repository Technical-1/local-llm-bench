"""The two inference runtimes, behind one interface.

``run(target, prompt) -> Generation`` for each runtime, plus availability
checks. MLX is imported lazily so the package imports cleanly on Windows and
Linux, where it does not exist.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from ._exe import find_exe
from .hwprobe import GB  # one unit everywhere, so peaks compare with budgets


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
# Ollama's default context is small (2k to 4k tokens, depending on version and
# VRAM) and it silently drops the start of a longer prompt. Every request asks
# for a window that holds its prompt plus the answer budget.
OLLAMA_MIN_CTX = 8192
CHARS_PER_TOKEN_LOW = 3.5  # deliberately low for English, so the window is never short

# Same resolution order as huggingface_hub: HF_HUB_CACHE, then HF_HOME/hub.
HF_CACHE = Path(
    os.environ.get("HF_HUB_CACHE")
    or Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface") / "hub"
)

MAX_PLAUSIBLE_TPS = 10_000  # faster than any local runtime; a higher rate is a timing glitch

THINKING_MARKERS = ("</think>", "</thinking>", "<channel|>", "<|channel|>")


@dataclass
class Generation:
    text: str
    load_s: float = 0.0
    ttft_s: float = 0.0
    prompt_tps: float = 0.0
    gen_tps: float = 0.0
    peak_gb: float = 0.0
    prompt_tokens: int = 0
    num_ctx: int = 0  # context window requested (Ollama only)
    truncated: bool = False  # the runtime saw much less of the prompt than was sent
    gpu_share: float | None = None  # measured share of the model on the GPU; None = unknown


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
    local = os.environ.get("LOCALAPPDATA", "")
    known = (os.path.join(local, "Programs", "Ollama", "ollama.exe"),) if local else ()
    exe = find_exe("ollama", known)
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


def _ollama_resident(tag: str) -> tuple[float, float | None]:
    """(GB loaded, share of it on the GPU) from /api/ps; (0, None) if unknown.

    The share is measured, not predicted: below 1.0 means Ollama put some
    layers on the CPU, which is why a model runs slowly.
    """
    try:
        import httpx

        models = httpx.get(f"{OLLAMA_URL}/api/ps", timeout=5).json().get("models", [])
    except Exception:
        return 0.0, None
    exact = [m for m in models if m.get("name") == tag]
    family = [m for m in models if m.get("name", "").split(":")[0] == tag.split(":")[0]]
    for m in exact or family:
        size = m.get("size", 0)
        share = m["size_vram"] / size if size and "size_vram" in m else None
        return size / GB, share
    return 0.0, None


def ollama_num_ctx(prompt: str) -> int:
    """A context window that fits this prompt and the answer, in steps of 4096."""
    need = int(len(prompt) / CHARS_PER_TOKEN_LOW) + OLLAMA_NUM_PREDICT
    return max(OLLAMA_MIN_CTX, -(-need // 4096) * 4096)


def looks_truncated(prompt: str, prompt_tokens: int) -> bool:
    """True when the runtime evaluated far fewer tokens than the prompt holds.

    No tokenizer averages more than about 6 characters per token on English,
    so fewer tokens than that means part of the prompt was dropped. Only long
    prompts are checked: a short one can be mostly served from Ollama's cache.
    """
    return len(prompt) > 4000 and prompt_tokens < len(prompt) / 6


def plausible(tps: float, count: int) -> float:
    """The rate, or 0.0 (unknown) when it can't be trusted: under two tokens
    gives no interval to time, and over 10,000 tok/s is a timing glitch."""
    return tps if count >= 2 and 0 < tps <= MAX_PLAUSIBLE_TPS else 0.0


def rate(count: int, seconds: float) -> float:
    """Tokens per second from a count and a duration, guarded by plausible()."""
    return plausible(count / seconds, count) if seconds > 0 else 0.0


def run_ollama(tag: str, prompt: str, max_tokens: int = OLLAMA_NUM_PREDICT) -> Generation:
    import httpx

    num_ctx = ollama_num_ctx(prompt)
    r = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": tag,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": max_tokens,
                "num_ctx": num_ctx,
            },
        },
        timeout=900,
    )
    r.raise_for_status()
    d = r.json()
    ns = 1e9
    p_cnt, p_dur = d.get("prompt_eval_count", 0), d.get("prompt_eval_duration", 0)
    e_cnt, e_dur = d.get("eval_count", 0), d.get("eval_duration", 0)
    # Ollama returns `thinking` separately from `response`. Some builds over-think
    # and never emit a final response (done_reason=length); fall back to the
    # thinking text so we score the model's answer, not the runtime's quirk.
    text = (d.get("response") or "").strip() or (d.get("thinking") or "")
    load = d.get("load_duration", 0)
    resident_gb, gpu_share = _ollama_resident(tag)
    return Generation(
        text=text,
        load_s=load / ns,
        ttft_s=(load + d.get("prompt_eval_duration", 0)) / ns,
        prompt_tps=rate(p_cnt, p_dur / ns),
        gen_tps=rate(e_cnt, e_dur / ns),
        peak_gb=resident_gb,
        gpu_share=gpu_share,
        prompt_tokens=p_cnt,
        num_ctx=num_ctx,
        truncated=looks_truncated(prompt, p_cnt),
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


def run_mlx(repo: str, prompt: str, max_tokens: int = MLX_MAX_TOKENS) -> Generation:
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
    gen_tokens = 0
    prompt_tokens = 0
    for resp in stream_generate(model, tok, chat, max_tokens=max_tokens):
        if ttft is None:
            ttft = time.time() - t0
        out.append(resp.text)
        prompt_tps = getattr(resp, "prompt_tps", prompt_tps)
        gen_tps = getattr(resp, "generation_tps", gen_tps)
        prompt_tokens = getattr(resp, "prompt_tokens", prompt_tokens)
        gen_tokens = getattr(resp, "generation_tokens", len(out))
    return Generation(
        text="".join(out),
        load_s=load_s,
        ttft_s=ttft or 0.0,
        prompt_tps=plausible(prompt_tps, prompt_tokens),
        gen_tps=plausible(gen_tps, gen_tokens),
        peak_gb=mx.get_peak_memory() / GB,
        prompt_tokens=prompt_tokens,
        gpu_share=1.0,  # MLX runs entirely on the Apple GPU
    )
