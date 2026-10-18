"""The models the benchmark knows about, and how much memory each needs.

Each entry maps a short logical name to its id on every runtime, so the same
model can be compared across Ollama and MLX. ``params_b`` is the TOTAL
parameter count in billions (for mixture-of-experts models too: every expert
must be resident even though only a few are active per token); ``active_b``
is what each token actually reads, which is what sets generation speed.

The KV-cache columns come from each MLX repo's config.json; regenerate them
with ``python scripts/model_metadata.py``. ``kv_layers`` counts only layers
whose cache grows with context, so hybrid models (most of the 2026 rows) have
far fewer than their total layer count.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .hwprobe import GB

DEFAULT_CTX = 8192  # the context `check` grades at unless told otherwise
RUNTIME_OVERHEAD_GB = 0.5  # compute buffers and runtime state, beyond weights and KV cache
OLLAMA_BYTES_PER_WEIGHT = 0.60  # Q4_K_M, the quant behind Ollama's default tags (~4.8 bits)
KV_BYTES = 2  # fp16 cache entries, the default on both runtimes


def mlx_bytes_per_weight(repo: str) -> float:
    """MLX stores an fp16 scale and bias per 64 weights: 0.5 extra bits each."""
    m = re.search(r"(\d)bit", repo)
    bits = int(m.group(1)) if m else 4
    return (bits + 0.5) / 8


@dataclass(frozen=True)
class Model:
    name: str
    ollama: str
    mlx: str
    vendor: str
    arch: str
    params_b: float
    active_b: float
    kv_layers: int
    kv_heads: int
    head_dim: int
    max_ctx: int
    mlx_alt: str | None = None

    def bytes_per_weight(self, runtime: str = "ollama", repo: str | None = None) -> float:
        if runtime == "mlx":
            return mlx_bytes_per_weight(repo or self.mlx)
        return OLLAMA_BYTES_PER_WEIGHT

    def weights_gb(self, runtime: str = "ollama", repo: str | None = None) -> float:
        return self.params_b * 1e9 * self.bytes_per_weight(runtime, repo) / GB

    def kv_gb_per_token(self) -> float:
        """Keys and values, for every layer whose cache grows with context."""
        return 2 * self.kv_layers * self.kv_heads * self.head_dim * KV_BYTES / GB

    def need_gb(
        self, ctx: int = DEFAULT_CTX, runtime: str = "ollama", repo: str | None = None
    ) -> float:
        """Estimated memory: weights + KV cache at ``ctx`` tokens + runtime overhead.

        An estimate for triage only: every run records the measured peak, and
        the scorecard puts the two side by side.
        """
        ctx = min(ctx, self.max_ctx)
        kv = self.kv_gb_per_token() * ctx
        return round(self.weights_gb(runtime, repo) + kv + RUNTIME_OVERHEAD_GB, 1)

    def max_ctx_within(self, budget_gb: float, runtime: str = "ollama") -> int:
        """The longest context that fits in ``budget_gb``; 0 if the weights alone don't."""
        room = budget_gb - self.weights_gb(runtime) - RUNTIME_OVERHEAD_GB
        if room <= 0:
            return 0
        return min(self.max_ctx, int(room / self.kv_gb_per_token()))


# fmt: off
MODELS: tuple[Model, ...] = (
    #     name                 ollama tag            mlx repo                                          vendor       arch                      params active kv_layers kv_heads head_dim max_ctx
    # small: laptops, 8 GB GPUs
    Model("llama3.2-3b",       "llama3.2:3b",        "mlx-community/Llama-3.2-3B-Instruct-4bit",       "Meta",      "Dense 3B",               3.2,   3.2,   28, 8, 128, 131072),
    Model("phi4-mini",         "phi4-mini",          "mlx-community/Phi-4-mini-instruct-4bit",         "Microsoft", "Dense 3.8B",             3.8,   3.8,   32, 8, 128, 131072),
    Model("qwen2.5-7b",        "qwen2.5:7b",         "mlx-community/Qwen2.5-7B-Instruct-4bit",         "Alibaba",   "Dense 7B",               7.6,   7.6,   28, 4, 128, 32768),
    Model("granite-4-h-tiny",  "granite4:tiny-h",    "mlx-community/granite-4.0-h-tiny-3bit-MLX",      "IBM",       "MoE 7B / 1B active",     7.0,   1.0,   4,  4, 128, 131072),
    Model("lfm2-8b-a1b",       "lfm2:8b-a1b",        "mlx-community/LFM2-8B-A1B-3bit-MLX",             "LiquidAI",  "MoE 8.3B / 1.5B active", 8.3,   1.5,   6,  8, 64,  128000,
          mlx_alt="mlx-community/LFM2-8B-A1B-4bit"),
    Model("gemma-4-e4b",       "gemma4:e4b",         "mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit",    "Google",    "Dense e4B (PLE)",        8.0,   4.0,   7,  2, 512, 131072),
    # medium: 12-16 GB GPUs, 24-32 GB Macs
    Model("qwen3.5-9b",        "qwen3.5:9b",         "mlx-community/Qwen3.5-9B-4bit",                  "Alibaba",   "Dense 9B",               9.0,   9.0,   8,  4, 256, 262144,
          mlx_alt="mlx-community/Qwen3.5-9B-Instruct-4bit"),
    Model("gemma-4-12b",       "gemma4:12b",         "mlx-community/gemma-4-12B-it-qat-4bit",          "Google",    "Dense 12B",              12.0,  12.0,  8,  1, 512, 262144),
    # large: 24 GB GPUs, 48 GB+ Macs
    Model("gemma-4-26b-a4b",   "gemma4:27b",         "mlx-community/gemma-4-26B-A4B-it-4bit",          "Google",    "MoE 26B / 4B active",    26.0,  4.0,   5,  2, 512, 262144,
          mlx_alt="mlx-community/gemma-4-26B-A4B-it-OptiQ-4bit"),
    Model("qwen3.6-27b",       "qwen3.6:27b",        "mlx-community/Qwen3.6-27B-4bit",                 "Alibaba",   "Dense 27B",              27.0,  27.0,  16, 4, 256, 262144),
    Model("nemotron3-30b-a3b", "nemotron3",          "mlx-community/NVIDIA-Nemotron-3-Nano-30B-A3B-4bit", "NVIDIA", "MoE 30B / 3B active",    31.6,  3.0,   6,  2, 128, 262144,
          mlx_alt="mlx-community/NVIDIA-Nemotron-3-Nano-30B-A3B-OptiQ-4bit"),
    Model("qwen2.5-coder-32b", "qwen2.5-coder:32b",  "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit",  "Alibaba",   "Dense 32B",              32.8,  32.8,  64, 8, 128, 32768),
    Model("qwen2.5-32b",       "qwen2.5:32b",        "mlx-community/Qwen2.5-32B-Instruct-4bit",        "Alibaba",   "Dense 32B",              32.8,  32.8,  64, 8, 128, 32768),
    Model("qwen3.6-35b-a3b",   "qwen3.6:35b-a3b",    "mlx-community/Qwen3.6-35B-A3B-4bit",             "Alibaba",   "MoE 35B / 3B active",    35.0,  3.0,   10, 2, 256, 262144),
    # workstation: 64 GB+
    Model("llama3.3-70b",      "llama3.3:70b",       "mlx-community/Llama-3.3-70B-Instruct-4bit",      "Meta",      "Dense 70B",              70.6,  70.6,  80, 8, 128, 131072),
)
# fmt: on

BY_NAME: dict[str, Model] = {m.name: m for m in MODELS}
