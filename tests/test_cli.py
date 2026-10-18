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
