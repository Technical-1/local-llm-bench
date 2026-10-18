"""The memory estimate: weights by quant, KV cache by context and architecture."""

import pytest

from llm_bench.hwprobe import GB
from llm_bench.registry import BY_NAME, mlx_bytes_per_weight

# Measured MLX peaks on an Apple M4 Pro during the full task suite (the
# long-context task is the largest prompt, about 16k tokens), converted from
# the README's 10^9-byte figures to GiB. The estimate should hold to 15%.
MEASURED_MLX_PEAK_GB = {"llama3.2-3b": 3.54, "phi4-mini": 4.0, "qwen2.5-7b": 5.31}


@pytest.mark.parametrize("name,peak", MEASURED_MLX_PEAK_GB.items())
def test_estimate_tracks_measured_peaks(name, peak):
    est = BY_NAME[name].need_gb(16_384, "mlx")
    assert est == pytest.approx(peak, rel=0.15)


@pytest.mark.parametrize("repo,bpw", [("org/x-4bit", 0.5625), ("org/x-3bit-MLX", 0.4375)])
def test_mlx_group_scales_add_half_a_bit(repo, bpw):
    assert mlx_bytes_per_weight(repo) == bpw


def test_kv_cache_follows_the_architecture():
    llama70 = BY_NAME["llama3.3-70b"]  # 80 full-attention layers
    nemotron = BY_NAME["nemotron3-30b-a3b"]  # 6 attention layers among Mamba blocks
    assert llama70.kv_gb_per_token() * GB == 2 * 80 * 8 * 128 * 2
    assert llama70.kv_gb_per_token() > 50 * nemotron.kv_gb_per_token()


def test_context_raises_the_estimate_up_to_the_model_limit():
    m = BY_NAME["qwen2.5-7b"]  # max context 32k
    assert m.need_gb(4096) < m.need_gb(16_384) < m.need_gb(32_768)
    assert m.need_gb(32_768) == m.need_gb(131_072)


def test_three_bit_build_needs_less_than_its_four_bit_alternative():
    m = BY_NAME["lfm2-8b-a1b"]
    assert m.need_gb(runtime="mlx") < m.need_gb(runtime="mlx", repo=m.mlx_alt)


def test_max_ctx_within_a_budget():
    m = BY_NAME["qwen2.5-7b"]
    ctx = m.max_ctx_within(6.0)
    assert 0 < ctx < m.max_ctx
    assert m.need_gb(ctx) <= 6.05  # rounding to 0.1 GB
    assert m.max_ctx_within(2.0) == 0  # weights alone don't fit
    assert m.max_ctx_within(500.0) == m.max_ctx
