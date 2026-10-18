"""Print the architecture numbers registry.py needs, read from each MLX repo's config.json.

    python scripts/model_metadata.py            # every model in the registry
    python scripts/model_metadata.py org/repo   # any Hugging Face repo

The KV cache grows with context only in layers that attend over the whole
sequence. Hybrid models (Qwen3.5/3.6, Gemma 4, Granite 4, Nemotron 3, LFM2)
have only a few such layers; the rest are linear attention, sliding window,
Mamba or convolution layers whose state stays small. Sliding-window layers are
left out, which under-counts Gemma 4 by a few hundred MB at most.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

FULL = {"full_attention", "attention"}


def fetch(repo: str) -> dict:
    url = f"https://huggingface.co/{repo}/raw/main/config.json"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def kv_shape(cfg: dict) -> dict:
    c = {**cfg, **cfg.get("text_config", {})}
    layers = c["num_hidden_layers"]
    kv_heads = c.get("num_key_value_heads") or c["num_attention_heads"]
    head_dim = c.get("head_dim") or c["hidden_size"] // c["num_attention_heads"]
    if c.get("layer_types"):
        kv_layers = sum(t in FULL for t in c["layer_types"])
    elif c.get("hybrid_override_pattern"):  # Nemotron-H: '*' marks an attention layer
        kv_layers = c["hybrid_override_pattern"].count("*")
    else:
        kv_layers = layers
    if c.get("global_head_dim"):  # Gemma 4: full-attention layers use their own shape
        head_dim = c["global_head_dim"]
        kv_heads = c.get("num_global_key_value_heads") or kv_heads
    q = c.get("quantization") or c.get("quantization_config") or {}
    return dict(
        kv_layers=kv_layers,
        kv_heads=kv_heads,
        head_dim=head_dim,
        max_ctx=c.get("max_position_embeddings"),
        mlx_bits=q.get("bits"),
    )


def main(argv: list[str]) -> int:
    repos = argv
    if not repos:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from llm_bench.registry import MODELS

        repos = [m.mlx for m in MODELS]
    for repo in repos:
        try:
            print(f"{repo:<55} {kv_shape(fetch(repo))}")
        except Exception as e:
            print(f"{repo:<55} FAILED: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
