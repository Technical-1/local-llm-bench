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
