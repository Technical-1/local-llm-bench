"""The models the benchmark knows about, and how much memory each needs.

Each entry maps a short logical name to its id on every runtime, so the same
model can be compared across Ollama and MLX. ``params_b`` is the TOTAL
parameter count in billions (for mixture-of-experts models too: every expert
must be resident even though only a few are active per token).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Model:
    name: str
    ollama: str
    mlx: str
    vendor: str
    arch: str
    params_b: float
    mlx_alt: str | None = None

    @property
    def need_gb(self) -> float:
        """Estimated memory to run at 4-bit.

        ~0.6 GB per billion parameters for weights (Q4_K_M averages ~4.8 bits
        per weight) plus ~1.5 GB for the KV cache and runtime. An estimate for
        triage only: every run records the measured peak.
        """
        return round(self.params_b * 0.6 + 1.5, 1)


# fmt: off
MODELS: tuple[Model, ...] = (
    #     name                 ollama tag            mlx repo                                          vendor       arch                      params_b
    # small: laptops, 8 GB GPUs
    Model("llama3.2-3b",       "llama3.2:3b",        "mlx-community/Llama-3.2-3B-Instruct-4bit",       "Meta",      "Dense 3B",               3.2),
    Model("phi4-mini",         "phi4-mini",          "mlx-community/Phi-4-mini-instruct-4bit",         "Microsoft", "Dense 3.8B",             3.8),
    Model("qwen2.5-7b",        "qwen2.5:7b",         "mlx-community/Qwen2.5-7B-Instruct-4bit",         "Alibaba",   "Dense 7B",               7.6),
    Model("granite-4-h-tiny",  "granite4:tiny-h",    "mlx-community/granite-4.0-h-tiny-3bit-MLX",      "IBM",       "MoE 7B / 1B active",     7.0),
    Model("lfm2-8b-a1b",       "lfm2:8b-a1b",        "mlx-community/LFM2-8B-A1B-3bit-MLX",             "LiquidAI",  "MoE 8.3B / 1.5B active", 8.3,
          mlx_alt="mlx-community/LFM2-8B-A1B-4bit"),
    Model("gemma-4-e4b",       "gemma4:e4b",         "mlx-community/gemma-4-e4b-it-qat-OptiQ-4bit",    "Google",    "Dense e4B (PLE)",        8.0),
    # medium: 12-16 GB GPUs, 24-32 GB Macs
    Model("qwen3.5-9b",        "qwen3.5:9b",         "mlx-community/Qwen3.5-9B-4bit",                  "Alibaba",   "Dense 9B",               9.0,
          mlx_alt="mlx-community/Qwen3.5-9B-Instruct-4bit"),
    Model("gemma-4-12b",       "gemma4:12b",         "mlx-community/gemma-4-12B-it-qat-4bit",          "Google",    "Dense 12B",              12.0),
    # large: 24 GB GPUs, 48 GB+ Macs
    Model("gemma-4-26b-a4b",   "gemma4:27b",         "mlx-community/gemma-4-26B-A4B-it-4bit",          "Google",    "MoE 26B / 4B active",    26.0,
          mlx_alt="mlx-community/gemma-4-26B-A4B-it-OptiQ-4bit"),
    Model("qwen3.6-27b",       "qwen3.6:27b",        "mlx-community/Qwen3.6-27B-4bit",                 "Alibaba",   "Dense 27B",              27.0),
    Model("nemotron3-30b-a3b", "nemotron3",          "mlx-community/NVIDIA-Nemotron-3-Nano-30B-A3B-4bit", "NVIDIA", "MoE 30B / 3B active",    31.6,
          mlx_alt="mlx-community/NVIDIA-Nemotron-3-Nano-30B-A3B-OptiQ-4bit"),
    Model("qwen2.5-coder-32b", "qwen2.5-coder:32b",  "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit",  "Alibaba",   "Dense 32B",              32.8),
    Model("qwen2.5-32b",       "qwen2.5:32b",        "mlx-community/Qwen2.5-32B-Instruct-4bit",        "Alibaba",   "Dense 32B",              32.8),
    Model("qwen3.6-35b-a3b",   "qwen3.6:35b-a3b",    "mlx-community/Qwen3.6-35B-A3B-4bit",             "Alibaba",   "MoE 35B / 3B active",    35.0),
    # workstation: 64 GB+
    Model("llama3.3-70b",      "llama3.3:70b",       "mlx-community/Llama-3.3-70B-Instruct-4bit",      "Meta",      "Dense 70B",              70.6),
)
# fmt: on

BY_NAME: dict[str, Model] = {m.name: m for m in MODELS}
