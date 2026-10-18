"""Runtime adapters, with the Ollama HTTP API faked."""

import pytest

from llm_bench import runners
from llm_bench.registry import BY_NAME, MODELS


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("<think>hmm</think>\n42", "42"),
        ("plan<channel|>final", "final"),
        ("  plain  ", "plain"),
    ],
)
def test_strip_thinking(raw, expected):
    assert runners.strip_thinking(raw) == expected


def test_untagged_pull_matches_latest():
    assert runners.ollama_has({"phi4-mini:latest"}, "phi4-mini")
    assert not runners.ollama_has({"qwen2.5:7b"}, "qwen2.5:32b")


@pytest.mark.parametrize(
    "env,url",
    [
        (None, "http://127.0.0.1:11434"),
        ("0.0.0.0", "http://127.0.0.1:11434"),
        ("0.0.0.0:11500", "http://127.0.0.1:11500"),
        ("http://gpu-box:11434/", "http://gpu-box:11434"),
    ],
)
def test_ollama_url_from_env(env, url):
    assert runners._ollama_url(env) == url


def test_registry_is_consistent():
    assert len(BY_NAME) == len(MODELS), "duplicate model names"
    needs = [m.need_gb for m in MODELS]
    assert BY_NAME["llama3.2-3b"].need_gb < BY_NAME["qwen3.5-9b"].need_gb < max(needs)
    assert all(m.params_b > 0 and m.ollama and m.mlx for m in MODELS)


class _Resp:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


def test_run_ollama_converts_timings(monkeypatch):
    import httpx

    payload = {
        "response": "4",
        "load_duration": 2_000_000_000,
        "prompt_eval_count": 100,
        "prompt_eval_duration": 500_000_000,
        "eval_count": 50,
        "eval_duration": 1_000_000_000,
    }
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(payload))
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *a, **k: _Resp(
            {"models": [{"name": "qwen2.5:7b", "size": 5_000_000_000, "size_vram": 4_000_000_000}]}
        ),
    )
    g = runners.run_ollama("qwen2.5:7b", "2+2?")
    assert g.text == "4"
    assert g.load_s == 2.0 and g.ttft_s == 2.5
    assert g.prompt_tps == 200.0 and g.gen_tps == 50.0
    assert g.peak_gb == 5.0 and g.gpu_share == 0.8


def test_run_ollama_falls_back_to_thinking(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp({"response": "", "thinking": "7"}))
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp({"models": []}))
    assert runners.run_ollama("x", "p").text == "7"


def test_ollama_status_from_server(monkeypatch):
    import httpx

    monkeypatch.setattr(
        httpx, "get", lambda *a, **k: _Resp({"models": [{"name": "phi4-mini:latest"}]})
    )
    assert runners.ollama_status() == (True, {"phi4-mini:latest"})


def test_ollama_status_when_absent(monkeypatch):
    import httpx

    def refuse(*a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "get", refuse)
    monkeypatch.setattr(runners, "find_exe", lambda *a, **k: None)
    assert runners.ollama_status() == (False, set())


def test_mlx_downloaded_ignores_partial_blobs(monkeypatch, tmp_path):
    monkeypatch.setattr(runners, "HF_CACHE", tmp_path)
    blobs = tmp_path / "models--org--model" / "blobs"
    blobs.mkdir(parents=True)
    (blobs / "abc.incomplete").write_text("")
    assert not runners.mlx_downloaded("org/model")
    (blobs / "abc").write_text("")
    assert runners.mlx_downloaded("org/model")


def test_num_ctx_holds_the_long_context_task():
    from llm_bench.tasks import TASKS

    longest = max((t["prompt"] for t in TASKS), key=len)
    ctx = runners.ollama_num_ctx(longest)
    assert ctx % 4096 == 0
    # the whole prompt at a pessimistic 3.5 chars per token, plus the answer budget
    assert ctx >= len(longest) / 3.5 + runners.OLLAMA_NUM_PREDICT
    assert runners.ollama_num_ctx("2+2?") == runners.OLLAMA_MIN_CTX


def test_run_ollama_sends_num_ctx_and_flags_truncation(monkeypatch):
    import httpx

    sent = {}
    long_prompt = "word " * 12000  # 60,000 characters, about 12,000 tokens

    def post(url, json, **k):
        sent.update(json["options"])
        # Ollama kept only its 4096-token default window
        return _Resp({"response": "x", "prompt_eval_count": 4096, "eval_count": 1})

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp({"models": []}))
    g = runners.run_ollama("m", long_prompt)
    assert sent["num_ctx"] == runners.ollama_num_ctx(long_prompt) == g.num_ctx
    assert g.prompt_tokens == 4096 and g.truncated


@pytest.mark.parametrize(
    "chars,tokens,cut",
    [(20_000, 5_000, False), (20_000, 3_000, True), (1_000, 10, False)],
)
def test_looks_truncated(chars, tokens, cut):
    assert runners.looks_truncated("a" * chars, tokens) is cut


def test_gpu_share_is_measured_from_api_ps(monkeypatch):
    import httpx

    ps = {
        "models": [
            {"name": "qwen2.5:32b", "size": 20_000_000_000, "size_vram": 10_000_000_000},
            {"name": "qwen2.5:7b", "size": 5_000_000_000, "size_vram": 5_000_000_000},
        ]
    }
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(ps))
    assert runners._ollama_resident("qwen2.5:32b") == (20.0, 0.5)  # exact tag, not the 7b
    assert runners._ollama_resident("qwen2.5:7b") == (5.0, 1.0)
    assert runners._ollama_resident("llama3.2:3b") == (0.0, None)
