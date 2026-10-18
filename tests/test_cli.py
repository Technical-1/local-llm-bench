"""End to end through the CLI, with the hardware and Ollama faked.

A fake "perfect model" answers every task correctly, so the full pipeline
(selection -> run -> score -> results.json -> scorecard.md) must report 100%.
"""

import json

import pytest
from conftest import REFERENCE_ANSWERS

from llm_bench import cli, hwprobe, runners
from llm_bench.tasks import TASKS

PROMPT_TO_ID = {t["prompt"]: t["id"] for t in TASKS}


@pytest.fixture
def fake_machine(monkeypatch, nvidia_hw):
    monkeypatch.setattr(hwprobe, "probe", lambda: nvidia_hw)
    monkeypatch.setattr(
        runners, "ollama_status", lambda: (True, {"qwen2.5:7b", "phi4-mini:latest"})
    )
    monkeypatch.setattr(runners, "mlx_installed", lambda: False)

    def perfect_model(tag, prompt, max_tokens=None):
        text = REFERENCE_ANSWERS.get(PROMPT_TO_ID.get(prompt), "one two three")
        return runners.Generation(text=text, gen_tps=40.0, peak_gb=5.2)

    monkeypatch.setattr(runners, "run_ollama", perfect_model)
    return nvidia_hw


def test_check_lists_verdicts_and_pull_commands(fake_machine, tmp_path, capsys):
    assert cli.main(["--out", str(tmp_path), "check"]) == 0
    out = capsys.readouterr().out
    assert "NVIDIA GeForce RTX 4070" in out
    assert "fits - fast" in out and "runs - slow" in out and "too big" in out
    assert "ollama pull llama3.2:3b" in out  # fits, not pulled
    assert "ollama pull qwen2.5:7b" not in out  # already pulled
    assert json.loads((tmp_path / "hardware.json").read_text())["fast_gb"] == 11.5


def test_run_scores_a_perfect_model_at_100_percent(fake_machine, tmp_path, capsys):
    assert cli.main(["--out", str(tmp_path), "run"]) == 0
    rows = json.loads((tmp_path / "results.json").read_text())
    assert {r["model"] for r in rows} == {"qwen2.5-7b", "phi4-mini"}
    assert all(r["quality_overall"] == 1.0 for r in rows)
    assert all(r["perf"]["speed_runs"] == 3 for r in rows)  # the speed pass ran
    card = (tmp_path / "scorecard.md").read_text(encoding="utf-8")
    assert "NVIDIA GeForce RTX 4070" in card and "| ✓ |" in card


def test_rerun_replaces_rows_instead_of_duplicating(fake_machine, tmp_path):
    cli.main(["--out", str(tmp_path), "run", "--models", "qwen2.5-7b"])
    cli.main(["--out", str(tmp_path), "run", "--models", "qwen2.5-7b"])
    assert len(json.loads((tmp_path / "results.json").read_text())) == 1


def test_run_with_nothing_downloaded_exits_nonzero(fake_machine, tmp_path, monkeypatch):
    monkeypatch.setattr(runners, "ollama_status", lambda: (True, set()))
    assert cli.main(["--out", str(tmp_path), "run"]) == 1


def test_unknown_model_is_rejected(fake_machine, tmp_path):
    with pytest.raises(SystemExit, match="Unknown model"):
        cli.main(["--out", str(tmp_path), "run", "--models", "gpt-9"])


def test_mlx_on_windows_is_refused(fake_machine, tmp_path):
    with pytest.raises(SystemExit, match="Apple Silicon"):
        cli.main(["--out", str(tmp_path), "run", "--runtime", "mlx"])


def test_missing_ollama_is_explained(fake_machine, tmp_path, monkeypatch):
    monkeypatch.setattr(runners, "ollama_status", lambda: (False, set()))
    with pytest.raises(SystemExit, match="ollama.com"):
        cli.main(["--out", str(tmp_path), "run"])


def test_report_without_results_says_so(fake_machine, tmp_path, capsys):
    assert cli.main(["--out", str(tmp_path), "report"]) == 0
    assert "No results yet" in capsys.readouterr().out


def test_truncated_prompt_is_flagged_in_the_scorecard(fake_machine, tmp_path, monkeypatch):
    def short_window(tag, prompt, max_tokens=None):
        tid = PROMPT_TO_ID.get(prompt)
        return runners.Generation(
            text=REFERENCE_ANSWERS.get(tid, ""), gen_tps=40.0, truncated=tid == "longctx_needle"
        )

    monkeypatch.setattr(runners, "run_ollama", short_window)
    cli.main(["--out", str(tmp_path), "run", "--models", "qwen2.5-7b"])
    row = json.loads((tmp_path / "results.json").read_text())[0]
    assert row["truncated_tasks"] == ["longctx_needle"]
    card = (tmp_path / "scorecard.md").read_text(encoding="utf-8")
    assert "dropped part of the prompt" in card and "longctx_needle" in card


def test_check_marks_models_that_need_more_than_is_free(fake_machine, tmp_path, capsys):
    fake_machine["gpu"]["free_gb"] = 4.0  # a game holds 8 of the 12 GB
    cli.main(["--out", str(tmp_path), "check"])
    out = capsys.readouterr().out
    assert "Free now  3.5 GB" in out
    assert "fits - fast *" in out and "not in the 3.5 GB free right now" in out


def test_check_shows_estimates_and_earlier_measurements(fake_machine, tmp_path, capsys):
    cli.main(["--out", str(tmp_path), "run", "--models", "qwen2.5-7b"])
    capsys.readouterr()
    cli.main(["--out", str(tmp_path), "check"])
    out = capsys.readouterr().out
    assert "est tok/s" in out and "~" in out  # an RTX 4070 has a known bandwidth
    assert "5.2 GB, 40 tok/s (ollama)" in out  # measured by the run above


def test_scorecard_puts_estimates_next_to_measurements(fake_machine, tmp_path):
    cli.main(["--out", str(tmp_path), "run", "--models", "qwen2.5-7b"])
    card = (tmp_path / "scorecard.md").read_text(encoding="utf-8")
    assert "| Est tok/s |" in card and "| Est GB |" in card
    assert "x the estimate" in card


def test_check_at_a_longer_context_needs_more_memory(fake_machine, tmp_path, capsys):
    def need(ctx):
        cli.main(["--out", str(tmp_path), "check", "--ctx", str(ctx)])
        line = next(ln for ln in capsys.readouterr().out.splitlines() if "llama3.2-3b " in ln)
        return float(line.split()[1].removesuffix("GB"))

    assert need(32_768) > need(4096)


def test_check_reports_the_longest_context_that_fits(fake_machine):
    rows = cli.check_models(fake_machine, set(), 8192)
    by = {r["model"]: r for r in rows}
    assert by["qwen2.5-7b"]["max_ctx_fast"] == 32_768  # its own limit fits in 11.5 GB
    assert 0 < by["llama3.2-3b"]["max_ctx_fast"] < 131_072  # KV-heavy: runs out first
    assert by["llama3.3-70b"]["max_ctx_fast"] == 0


def test_check_with_a_vram_override(fake_machine, tmp_path, capsys):
    cli.main(["--out", str(tmp_path), "check", "--vram", "24"])
    out = capsys.readouterr().out
    assert "Graded for --vram 24 GB" in out
    line = next(ln for ln in out.splitlines() if "qwen2.5-32b " in ln)
    assert "fits - fast" in line


def test_run_writes_rows_that_validate(fake_machine, tmp_path, capsys):
    cli.main(["--out", str(tmp_path), "run"])
    row = json.loads((tmp_path / "results.json").read_text())[0]
    assert row["hardware"]["gpu"] == "NVIDIA GeForce RTX 4070"
    capsys.readouterr()
    assert cli.main(["--out", str(tmp_path), "validate"]) == 0
    assert "all valid" in capsys.readouterr().out


def test_validate_fails_on_a_bad_file(tmp_path, capsys):
    path = tmp_path / "results.json"
    path.write_text('[{"model": "x", "runtime": "ollama"}]')
    assert cli.main(["validate", str(path)]) == 1
    assert "llm-bench 0.1" in capsys.readouterr().out


def test_check_json_is_machine_readable(fake_machine, tmp_path, capsys):
    cli.main(["--out", str(tmp_path), "check", "--json", "--ctx", "16384"])
    data = json.loads(capsys.readouterr().out)
    assert data["context_tokens"] == 16384 and data["estimate_runtime"] == "ollama"
    by = {m["model"]: m for m in data["models"]}
    assert by["qwen2.5-7b"]["pulled"] and by["llama3.3-70b"]["verdict"] == "no"
