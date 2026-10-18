"""Shared fixtures: reference answers for every task, and fake hardware."""

import pytest

# A correct answer for every task, phrased the way a chatty model would.
REFERENCE_ANSWERS = {
    "code_fizzbuzz_variant": (
        "```python\ndef solve(n):\n    out = []\n    for i in range(1, n + 1):\n"
        "        if i % 15 == 0:\n            out.append('fizzbuzz')\n"
        "        elif i % 3 == 0:\n            out.append('fizz')\n"
        "        elif i % 5 == 0:\n            out.append('buzz')\n"
        "        else:\n            out.append(str(i))\n    return out\n```"
    ),
    "code_two_sum": (
        "```python\ndef two_sum(nums, target):\n    seen = {}\n"
        "    for j, x in enumerate(nums):\n        if target - x in seen:\n"
        "            return [seen[target - x], j]\n        seen[x] = j\n```"
    ),
    "code_bug_fix": (
        "```python\ndef fact(n):\n    r = 1\n    for i in range(1, n + 1):\n"
        "        r *= i\n    return r\n```"
    ),
    "math_gsm1": "18 pens is 6 groups of 3, so $12. Change from $20:\n8",
    "math_gsm2": "After draining: 200 L. Refill would reach 320 but caps at capacity.\n240",
    "math_pct": "80 * 0.75 = 60, plus 8% tax = 64.80\n64.8",
    "math_seq": "n(n+1)/2 = 5050",
    "reason_logic": "Order: Alice > Bob > Carol > Dave.\nBob",
    "reason_count": "s-t-r-a-w-b-e-r-r-y\n3",
    "reason_deduce": "Every label is wrong, so it can't be mixed.\nApples",
    "longctx_needle": "ZX-7741-Qory",
    "instr_json": '{"name": "Ada", "age": 36, "langs": ["Python", "Lisp"]}',
    "instr_format": "- Red\n- Yellow\n- Blue",
}

WRONG_ANSWERS = {
    "code_fizzbuzz_variant": (
        "```python\ndef solve(n):\n    return [str(i) for i in range(1, n+1)]\n```"
    ),
    "code_two_sum": "```python\ndef two_sum(nums, target):\n    return [0, 0]\n```",
    "code_bug_fix": "```python\ndef fact(n):\n    return n\n```",
    "math_gsm1": "12",
    "math_gsm2": "320",
    "math_pct": "60",
    "math_seq": "5000",
    "reason_logic": "Carol",
    "reason_count": "2",
    "reason_deduce": "Oranges",
    "longctx_needle": "ZX-7741-Qorx",
    "instr_json": '{"name": "Ada", "age": 36}',
    "instr_format": "- Red\n- Blue",
}


@pytest.fixture
def nvidia_hw():
    """A Windows desktop: 12 GB RTX card, 32 GB RAM."""
    return {
        "os": "Windows 11",
        "arch": "amd64",
        "cpu": "Fake CPU",
        "ram_gb": 32.0,
        "gpu": {"name": "NVIDIA GeForce RTX 4070", "vram_gb": 12.0, "kind": "nvidia"},
        "accelerator": "nvidia",
        "mlx_ok": False,
        "fast_gb": 11.5,
        "spill_gb": 30.7,
        "notes": [],
    }
