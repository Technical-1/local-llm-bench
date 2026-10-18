"""The result format and its validator."""

import copy
from datetime import datetime, timedelta, timezone

import pytest

from llm_bench import schema
from llm_bench.tasks import CATEGORIES


@pytest.fixture
def row(nvidia_hw):
    return schema.stamp(
        {
            "model": "qwen2.5-7b",
            "runtime": "ollama",
            "target": "qwen2.5:7b",
            "quality": dict.fromkeys(CATEGORIES, 1.0),
            "quality_overall": 1.0,
            "perf": {
                "load_s": 2.0,
                "ttft_s": 0.1,
                "prompt_tps": 900.0,
                "gen_tps": 40.0,
                "gen_tps_min": 38.0,
                "gen_tps_max": 41.0,
                "speed_runs": 3,
                "peak_gb": 5.2,
                "gpu_share": 1.0,
            },
        },
        nvidia_hw,
    )


def test_a_fresh_row_is_valid(row):
    assert schema.validate_row(row) == []
    assert row["schema_version"] == schema.SCHEMA_VERSION and row["tool_version"]


def test_hardware_block_describes_the_machine_not_the_person(row):
    h = row["hardware"]
    assert h["hw_class"] == "discrete_gpu" and h["mem_tier_gb"] == 12
    assert h["os"] == "Windows"
    assert set(h) == {
        "hw_class", "gpu", "vram_gb", "gpu_limit_source", "mem_tier_gb",
        "ram_gb", "cpu", "os", "arch",
    }  # fmt: skip


@pytest.mark.parametrize("gb,tier", [(11.99, 12), (15.8, 16), (24.0, 24), (7.6, 8)])
def test_mem_tier_snaps_to_marketed_sizes(gb, tier):
    assert schema.mem_tier(gb) == tier


@pytest.mark.parametrize(
    "path,value,message",
    [
        (("perf", "gen_tps"), 50_000.0, "faster than any local runtime"),
        (("perf", "gen_tps"), 80.0, "outside its own min to max"),
        (("perf", "peak_gb"), -1.0, "perf.peak_gb must be a number"),
        (("perf", "gpu_share"), 1.5, "gpu_share must be between 0 and 1"),
        (("quality", "math"), 1.2, "quality.math must be between 0 and 1"),
        (("hardware", "ram_gb"), 99_999, "ram_gb must be between"),
        (("target",), "/Users/jacob/models/qwen", "home-folder path"),
        (("target",), "C:\\Users\\jacob\\qwen", "home-folder path"),
        (("runtime",), "vllm", "is not ollama or mlx"),
    ],
)
def test_validator_rejects(row, path, value, message):
    bad = copy.deepcopy(row)
    node = bad
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    errs = schema.validate_row(bad)
    assert any(message in e for e in errs), errs


def test_validator_rejects_a_future_timestamp(row):
    row["measured_at"] = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    assert any("future" in e for e in schema.validate_row(row))


def test_rows_from_before_versioning_are_named_as_such():
    (err,) = schema.validate_row({"model": "x", "runtime": "ollama"})
    assert "llm-bench 0.1" in err


def test_validate_rows_labels_each_problem(row):
    bad = copy.deepcopy(row)
    bad["quality_overall"] = 2
    errs = schema.validate_rows([row, bad])
    assert errs == ["row 2 (qwen2.5-7b, ollama): quality_overall must be between 0 and 1"]
