#!/usr/bin/env python3
"""Content quality checks for data/content/content_*.json (Plan 1, F5-T3, D85).

Checks, on top of the schema and catalogue match done by load_content:
- correct-answer positions are balanced within each concept (no index used for more than half
  of a concept's exercises);
- no duplicate or near-duplicate exercise prompts, within or across concepts (near-duplicate:
  normalised prompts at least 90% similar and the same correct answer, so two short "what does
  this print" questions with different code are not flagged);
- optional: each concept has the given easy/medium/hard spread under the D6 classes;
- every exercise marked "verify": "output" is run in a sandboxed subprocess, and what it prints
  (or the name of the exception it raises) must equal the correct option.

    python scripts/check_content.py data/content/content_8node_x10.json --spread 3,4,3

Exit status 1 and one line per problem if any check fails. The catalogue and curriculum are read
with allow_unreviewed=True: this script checks content, the review gate (D9) is separate.
"""

from __future__ import annotations

import argparse
import difflib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.join(repo_root, "src") not in sys.path:
    sys.path.insert(0, os.path.join(repo_root, "src"))

from adaptengine.core.errors import ValidationError  # noqa: E402
from adaptengine.curriculum.content import load_content  # noqa: E402
from adaptengine.curriculum.loader import load_activities, load_curriculum  # noqa: E402
from adaptengine.learner.adapter import get_difficulty_class  # noqa: E402

NEAR_DUPLICATE_RATIO = 0.90  # difflib ratio on normalised prompts (plus the same answer)
CODE_BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)

# Runs inside the child interpreter. The audit hook is installed after compiling the snippet and
# before running it: any file, network, process, os-level or import event raises PermissionError.
_SANDBOX = r"""
import sys
try:
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_AS, (512 << 20, 512 << 20))
except Exception:
    pass
_BLOCKED = ("open", "import", "os.", "socket.", "subprocess.", "shutil.", "ctypes.", "urllib.",
            "http.", "ftplib.", "smtplib.", "webbrowser.", "pty.", "fcntl.", "mmap.", "sys._getframe")
def _hook(event, args):
    if event.startswith(_BLOCKED):
        raise PermissionError("sandbox: " + event + " blocked")
code = compile(sys.stdin.read(), "<snippet>", "exec")
sys.addaudithook(_hook)
try:
    exec(code, {"__name__": "__main__", "__builtins__": __builtins__})
except BaseException as e:
    sys.stdout.flush()
    sys.stderr.write("\nEXC:" + type(e).__name__)
"""


def run_snippet(code: str, timeout: float = 5.0) -> str:
    """Printed output of `code` (stripped), or the exception name if it raises."""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            r = subprocess.run(
                [sys.executable, "-I", "-S", "-c", _SANDBOX],
                input=code,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmp,
                env={},
            )
        except subprocess.TimeoutExpired:
            return "<timeout>"
    out = r.stdout.strip()
    exc = r.stderr.rpartition("EXC:")[2].strip() if "EXC:" in r.stderr else ""
    if r.returncode != 0 and not exc:
        exc = f"<exit {r.returncode}>"
    return "\n".join(x for x in (out, exc) if x)


def _norm(prompt: str) -> str:
    return " ".join(prompt.lower().split())


def check_content(content_path, activities_path=None, curriculum_path=None, spread=None):
    """Return a list of problems (empty when the file passes)."""
    with open(content_path, encoding="utf-8") as f:
        doc = json.load(f)
    curriculum_path = curriculum_path or os.path.join(repo_root, doc["curriculum"])
    activities_path = activities_path or os.path.join(repo_root, doc["activities_file"])
    concepts = load_curriculum(curriculum_path, allow_unreviewed=True)
    activities = load_activities(activities_path, concepts, allow_unreviewed=True)
    try:
        content = load_content(content_path, activities)
    except ValidationError as e:
        return [f"schema: {e}"]
    catalogue = {a.activity_id: a for a in activities}
    exercises = {k: v for k, v in content.items() if v["type"] == "EXERCISE"}
    problems = []

    by_concept: dict[str, list[str]] = {}
    for aid, e in exercises.items():
        by_concept.setdefault(e["target_concept"], []).append(aid)
    for c, ids in sorted(by_concept.items()):
        counts = Counter(exercises[a]["correct"] for a in ids)
        index, n = counts.most_common(1)[0]
        if n > math.ceil(len(ids) / 2):
            problems.append(
                f"balance: {c} has correct index {index} in {n} of {len(ids)} exercises"
            )
        if spread is not None:
            classes = Counter(get_difficulty_class(catalogue[a].difficulty) for a in ids)
            got = (classes["easy"], classes["medium"], classes["hard"])
            if got != tuple(spread):
                problems.append(f"spread: {c} has easy/medium/hard {got}, expected {tuple(spread)}")

    ids = sorted(exercises)
    prompts = {a: _norm(exercises[a]["prompt"]) for a in ids}
    answers = {a: _norm(exercises[a]["options"][exercises[a]["correct"]]) for a in ids}
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            if prompts[a] == prompts[b]:
                problems.append(f"prompt: {a} and {b} are duplicates")
            elif answers[a] == answers[b]:
                ratio = difflib.SequenceMatcher(None, prompts[a], prompts[b]).ratio()
                if ratio >= NEAR_DUPLICATE_RATIO:
                    problems.append(f"prompt: {a} and {b} are near-duplicates ({ratio:.2f})")

    for aid in ids:
        e = exercises[aid]
        if "verify" not in e:
            continue
        if e["verify"] != "output":
            problems.append(f"verify: {aid} has unknown verify mode {e['verify']!r}")
            continue
        blocks = CODE_BLOCK.findall(e["prompt"])
        if len(blocks) != 1:
            problems.append(f"verify: {aid} needs exactly one ```python block, found {len(blocks)}")
            continue
        actual, expected = run_snippet(blocks[0]), e["options"][e["correct"]].strip()
        if actual != expected:
            problems.append(
                f"verify: {aid} prints {actual!r} but the correct option is {expected!r}"
            )
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("content")
    ap.add_argument("--activities", help="default: the file's activities_file field")
    ap.add_argument("--curriculum", help="default: the file's curriculum field")
    ap.add_argument("--spread", help="easy,medium,hard exercises per concept, e.g. 3,4,3")
    a = ap.parse_args(argv)
    spread = tuple(int(x) for x in a.spread.split(",")) if a.spread else None
    problems = check_content(a.content, a.activities, a.curriculum, spread)
    for p in problems:
        print(p)
    print(f"{a.content}: {'OK' if not problems else f'{len(problems)} problem(s)'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
