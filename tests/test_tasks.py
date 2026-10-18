"""Every scorer accepts a correct answer and rejects a wrong one.

A scorer that can't award full marks to a right answer would silently cap a
model's quality score, so each task is checked both ways.
"""

import pytest
from conftest import REFERENCE_ANSWERS, WRONG_ANSWERS

from llm_bench.runners import strip_thinking
from llm_bench.tasks import CATEGORIES, TASKS, extract_code, last_number, run_python

TASK_IDS = [t["id"] for t in TASKS]


def test_every_task_has_reference_answers():
    assert set(REFERENCE_ANSWERS) == set(TASK_IDS)
    assert set(WRONG_ANSWERS) == set(TASK_IDS)


def test_every_task_has_a_known_category():
    assert {t["category"] for t in TASKS} == set(CATEGORIES)


@pytest.mark.parametrize("task", TASKS, ids=TASK_IDS)
def test_correct_answer_scores_full_marks(task):
    assert task["scorer"](REFERENCE_ANSWERS[task["id"]]) == 1.0


@pytest.mark.parametrize("task", TASKS, ids=TASK_IDS)
def test_wrong_answer_scores_zero(task):
    assert task["scorer"](WRONG_ANSWERS[task["id"]]) == 0.0


@pytest.mark.parametrize("task", TASKS, ids=TASK_IDS)
def test_reasoning_block_does_not_change_the_score(task):
    # A thinking model's scratch work must not be graded, only its answer.
    noisy = "<think>Maybe the answer is 7? Or Carol. ZX-0000.</think>\n"
    assert task["scorer"](strip_thinking(noisy + REFERENCE_ANSWERS[task["id"]])) == 1.0


def test_extract_code_prefers_the_longest_block():
    text = "```python\nx = 1\n```\nthen\n```python\ndef f():\n    return 2\n```"
    assert "def f" in extract_code(text)


def test_last_number_handles_currency_and_commas():
    assert last_number("Total: $1,250.") == "1250"


def test_run_python_is_isolated_and_times_out():
    assert run_python("import os", "assert os.getcwd()") is True
    assert run_python("while True: pass", "", timeout=1) is False
