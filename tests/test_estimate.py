"""Speed estimates from memory bandwidth."""

import pytest

from llm_bench import estimate
from llm_bench.registry import BY_NAME

M4_PRO = {
    "gpu": {"name": "Apple M4 Pro", "vram_gb": 17.8, "kind": "apple"},
    "fast_gb": 15.8,
    "spill_gb": 15.8,
}

# Measured MLX generation speeds on that machine (README sample results).
MEASURED_MLX_TPS = {"llama3.2-3b": 102, "phi4-mini": 97, "qwen2.5-7b": 61}


@pytest.mark.parametrize("name,measured", MEASURED_MLX_TPS.items())
def test_estimate_is_within_30_percent_of_measured(name, measured):
    est = estimate.tokens_per_sec(BY_NAME[name], M4_PRO, "mlx")
    assert est == pytest.approx(measured, rel=0.30)


@pytest.mark.parametrize(
    "name,bw",
    [
        ("NVIDIA GeForce RTX 4070 Ti SUPER", 672),
        ("NVIDIA GeForce RTX 4070", 504),
        ("AMD Radeon RX 7900 XTX", 960),
        ("Apple M4 Max", 546),
        ("Apple M4", 120),
        ("NVIDIA GeForce RTX 4070 Laptop GPU", None),  # narrower bus than the desktop card
        ("Some Future GPU", None),
    ],
)
def test_bandwidth_lookup(name, bw):
    assert estimate.bandwidth_gbps(name) == bw


def test_moe_speed_uses_active_parameters():
    dense = estimate.tokens_per_sec(BY_NAME["qwen3.6-27b"], M4_PRO, "mlx")
    moe = estimate.tokens_per_sec(BY_NAME["gemma-4-26b-a4b"], M4_PRO, "mlx")
    assert moe > 4 * dense


def test_no_estimate_when_it_would_spill_or_the_gpu_is_unknown():
    assert estimate.tokens_per_sec(BY_NAME["llama3.3-70b"], M4_PRO, "mlx") is None
    unknown = {**M4_PRO, "gpu": {"name": "Mystery GPU", "vram_gb": 24, "kind": "other"}}
    assert estimate.tokens_per_sec(BY_NAME["llama3.2-3b"], unknown, "ollama") is None


def test_trademark_marks_do_not_hide_the_bandwidth():
    assert estimate.bandwidth_gbps("AMD Radeon(TM) 8060S Graphics") == 256
    assert estimate.bandwidth_gbps("NVIDIA GeForce(R) RTX 4090") == 1008
