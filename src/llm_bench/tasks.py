"""Benchmark task suite: deterministic, scored automatically, fully offline.

Each task has: id, category, prompt, and a scorer(output:str)->float in [0,1].
Categories: coding, math, reasoning, longcontext, instruction.
No judge model is needed: every task is checked by code.
"""

import json
import os
import re
import subprocess
import sys
import tempfile


# ---------- scoring helpers ----------
def extract_code(text):
    m = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return max(m, key=len)
    return text  # fall back to raw (model may have skipped fences)


def run_python(code, appended_tests, timeout=15):
    """Run model-written code + hidden tests. Return True if exit 0 (asserts passed).

    This executes code a model wrote, which is how the coding tasks are scored.
    It is contained, not sandboxed: a private temp directory as the working
    directory (deleted afterwards), Python's isolated mode (-I: no user
    site-packages, no PYTHON* env vars, no script-dir imports) and a timeout.
    Only benchmark models you trust; see README "Safety"."""
    src = code + "\n\n" + appended_tests
    with tempfile.TemporaryDirectory(prefix="llmbench-") as d:
        path = os.path.join(d, "candidate.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(src)
        try:
            r = subprocess.run(
                [sys.executable, "-I", path],
                cwd=d,
                capture_output=True,
                timeout=timeout,
                text=True,
            )
            return r.returncode == 0
        except Exception:
            return False


def last_number(text):
    # prefer an explicit "answer: N", else last number in the text
    m = re.findall(r"-?\d[\d,]*\.?\d*", text.replace("$", ""))
    if not m:
        return None
    return m[-1].replace(",", "").rstrip(".")


def num_match(text, target):
    n = last_number(text)
    if n is None:
        return 0.0
    try:
        return 1.0 if abs(float(n) - float(target)) < 1e-6 else 0.0
    except ValueError:
        return 0.0


def contains(text, needle):
    return 1.0 if needle.lower() in text.lower() else 0.0


def tail(text, n=2):
    """Last n non-empty lines, lowercased, so a model thinking out loud first still scores."""
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    return " ".join(lines[-n:]).lower()


# ---------- long-context document (needle in a haystack) ----------
def _haystack(needle_sentence, approx_tokens=6000):
    filler = (
        "The quarterly logistics report noted routine warehouse throughput and "
        "nominal transit times across regional distribution centers. "
    )
    body = []
    n = approx_tokens // 12
    for i in range(n):
        if i == n // 2:
            body.append(needle_sentence)
        body.append(f"Section {i}: " + filler)
    return " ".join(body)


NEEDLE = "The secret authorization code for the Meridian project is ZX-7741-Qory."
LONGDOC = _haystack(NEEDLE)


# ---------- the suite ----------
TASKS = [
    # ===== CODING (run hidden tests) =====
    dict(
        id="code_fizzbuzz_variant",
        category="coding",
        prompt="Write a Python function `solve(n)` that returns a list of strings for 1..n: "
        "'fizz' if divisible by 3, 'buzz' if by 5, 'fizzbuzz' if both, else str(i). "
        "Return ONLY a python code block.",
        scorer=lambda o: (
            1.0
            if run_python(
                extract_code(o),
                "assert solve(5)==['1','2','fizz','4','buzz']\n"
                "assert solve(15)[-1]=='fizzbuzz'\n"
                "assert solve(15)[2]=='fizz' and solve(15)[4]=='buzz'",
            )
            else 0.0
        ),
    ),
    dict(
        id="code_two_sum",
        category="coding",
        prompt="Write a Python function `two_sum(nums, target)` returning indices [i,j] (i<j) of the two "
        "numbers that add to target. Assume exactly one solution. Return ONLY a python code block.",
        scorer=lambda o: (
            1.0
            if run_python(
                extract_code(o),
                "r=two_sum([2,7,11,15],9); assert sorted(r)==[0,1]\n"
                "r=two_sum([3,2,4],6); assert sorted(r)==[1,2]",
            )
            else 0.0
        ),
    ),
    dict(
        id="code_bug_fix",
        category="coding",
        prompt="This function should return the factorial but has a bug:\n"
        "```python\ndef fact(n):\n    r=0\n    for i in range(1,n+1):\n        r*=i\n    return r\n```\n"
        "Return a corrected version as `fact(n)` in a python code block ONLY.",
        scorer=lambda o: (
            1.0
            if run_python(
                extract_code(o), "assert fact(5)==120\nassert fact(0)==1\nassert fact(1)==1"
            )
            else 0.0
        ),
    ),
    # ===== MATH (numeric exact-match) =====
    dict(
        id="math_gsm1",
        category="math",
        prompt="A store sells pens at 3 for $2. Maria buys 18 pens and pays with a $20 bill. "
        "How much change does she get? Give the final number on the last line.",
        scorer=lambda o: num_match(o, 8),
    ),
    dict(
        id="math_gsm2",
        category="math",
        prompt="A tank holds 240 liters. It drains at 8 L/min for 5 minutes, then is refilled at 12 L/min "
        "for 10 minutes (it cannot exceed capacity). How many liters are in the tank at the end? "
        "End with the final number.",
        scorer=lambda o: num_match(o, 240),
    ),
    dict(
        id="math_pct",
        category="math",
        prompt="A jacket costs $80. It is discounted 25%, then 8% sales tax is applied to the discounted "
        "price. What is the final price in dollars? End with the final number.",
        scorer=lambda o: num_match(o, 64.8),
    ),
    dict(
        id="math_seq",
        category="math",
        prompt="What is the sum of all integers from 1 to 100 inclusive? End with the final number.",
        scorer=lambda o: num_match(o, 5050),
    ),
    # ===== REASONING (deterministic answers) =====
    dict(
        id="reason_logic",
        category="reasoning",
        prompt="Alice is older than Bob. Bob is older than Carol. Carol is older than Dave. "
        "Who is the second oldest? Answer with just the name on the last line.",
        scorer=lambda o: contains(tail(o), "bob"),
    ),
    dict(
        id="reason_count",
        category="reasoning",
        prompt="How many times does the letter 'r' appear in the word 'strawberry'? "
        "Answer with just the number on the last line.",
        scorer=lambda o: num_match(o, 3),
    ),
    dict(
        id="reason_deduce",
        category="reasoning",
        prompt="Three boxes are labeled Apples, Oranges, Mixed. ALL labels are wrong. You pick one fruit "
        "from the box labeled 'Mixed' and it is an Apple. What does the 'Mixed'-labeled box actually "
        "contain? Answer with one word on the last line.",
        scorer=lambda o: contains(tail(o), "apple"),
    ),
    # ===== LONG CONTEXT (needle retrieval) =====
    dict(
        id="longctx_needle",
        category="longcontext",
        prompt="Read the following document and answer the question at the end.\n\n"
        + LONGDOC
        + "\n\nQUESTION: What is the secret authorization code for the Meridian project? "
        "Reply with only the code.",
        scorer=lambda o: contains(o, "ZX-7741-Qory"),
    ),
    # ===== INSTRUCTION FOLLOWING (programmatic constraint checks) =====
    dict(
        id="instr_json",
        category="instruction",
        prompt="Output ONLY a JSON object (no prose, no code fence) with exactly these keys: "
        '"name" (string "Ada"), "age" (number 36), "langs" (list of two strings). ',
        scorer=lambda o: _check_json(o),
    ),
    dict(
        id="instr_format",
        category="instruction",
        prompt="List exactly three primary colors. Format: each on its own line, each line starting "
        "with '- ' (dash space). No other text, no header, no trailing commentary.",
        scorer=lambda o: _check_three_bullets(o),
    ),
]


def _check_json(o):
    # find candidate {...} objects anywhere (our target has no nested braces) and validate
    for c in reversed(re.findall(r"\{[^{}]*\}", o, re.DOTALL)):
        try:
            d = json.loads(c)
        except Exception:
            continue
        if (
            isinstance(d, dict)
            and set(d.keys()) == {"name", "age", "langs"}
            and isinstance(d.get("langs"), list)
            and len(d["langs"]) == 2
        ):
            return 1.0
    return 0.0


def _check_three_bullets(o):
    # capability: did it produce exactly three '- ' bullet lines (thinking preamble allowed)
    bullets = [ln for ln in o.splitlines() if ln.lstrip().startswith("- ")]
    return 1.0 if len(bullets) == 3 else 0.0


CATEGORIES = ["coding", "math", "reasoning", "longcontext", "instruction"]

if __name__ == "__main__":
    print(f"{len(TASKS)} tasks across {len(CATEGORIES)} categories")
    for c in CATEGORIES:
        print(f"  {c}: {sum(1 for t in TASKS if t['category'] == c)}")
    print(f"Long-context doc length: ~{len(LONGDOC.split())} words")
