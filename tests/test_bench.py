"""The speed pass, with a scripted runtime."""

from llm_bench import bench, runners


def test_speed_pass_takes_load_from_warmup_and_the_median_rate():
    calls = []
    speeds = iter([0.0, 30.0, 50.0, 40.0])  # warmup, then three timed runs

    def run(target, prompt, max_tokens):
        calls.append((prompt, max_tokens))
        first = not calls[:-1]
        return runners.Generation(
            text="x", load_s=4.0 if first else 0.0, ttft_s=0.2, gen_tps=next(speeds)
        )

    perf = bench.speed_pass(run, "m", log=lambda *_: None)
    assert perf["load_s"] == 4.0
    assert perf["gen_tps"] == 40.0
    assert (perf["gen_tps_min"], perf["gen_tps_max"], perf["speed_runs"]) == (30.0, 50.0, 3)
    timed = calls[1:]
    assert len({p for p, _ in timed}) == 3, "each timed prompt differs, so none is cached"
    assert all(n == bench.SPEED_TOKENS for _, n in timed)


def test_speed_pass_ignores_untrusted_runs():
    speeds = iter([0.0, 0.0, 60.0, 0.0])

    def run(target, prompt, max_tokens):
        return runners.Generation(text="x", gen_tps=next(speeds))

    perf = bench.speed_pass(run, "m", log=lambda *_: None)
    assert perf["gen_tps"] == 60.0 and perf["speed_runs"] == 1


def test_speed_pass_with_no_usable_rate_raises_so_task_timings_are_kept():
    import pytest

    def run(target, prompt, max_tokens):
        return runners.Generation(text="x", gen_tps=0.0)

    with pytest.raises(RuntimeError):
        bench.speed_pass(run, "m", log=lambda *_: None)


def test_every_ollama_request_to_a_model_uses_one_window(monkeypatch):
    from llm_bench.registry import BY_NAME

    windows = set()

    def fake_ollama(tag, prompt, max_tokens=None, num_ctx=None):
        windows.add(num_ctx)
        return runners.Generation(text="x", gen_tps=40.0)

    monkeypatch.setattr(runners, "run_ollama", fake_ollama)
    bench.bench_one(BY_NAME["qwen2.5-7b"], "ollama", "qwen2.5:7b", log=lambda *_: None)
    assert windows == {bench.BENCH_CTX}, "a changed window makes Ollama reload the model"


def test_run_models_unloads_each_model_and_anything_already_resident(monkeypatch, tmp_path):
    from llm_bench.registry import BY_NAME

    unloaded = []
    monkeypatch.setattr(runners, "ollama_resident", lambda: ["someone-elses:model"])
    monkeypatch.setattr(runners, "unload_ollama", unloaded.append)
    monkeypatch.setattr(
        runners, "run_ollama", lambda *a, **k: runners.Generation(text="x", gen_tps=40.0)
    )
    hw = {"accelerator": "cpu", "gpu": None, "ram_gb": 16.0, "cpu": "c", "os": "Linux 6"}
    store = bench.ResultStore(tmp_path / "results.json")
    models = [BY_NAME["qwen2.5-7b"], BY_NAME["phi4-mini"]]
    tags = {"qwen2.5:7b", "phi4-mini"}
    assert bench.run_models(models, "ollama", store, tags, hw, log=lambda *_: None) == 2
    assert unloaded == ["someone-elses:model", "qwen2.5:7b", "phi4-mini"]
