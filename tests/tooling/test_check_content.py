"""Plan 1 (F5-T3, D85): scripts/check_content.py and the 8node_x10 content (F5-TC3, F5-TC4)."""

import json
import os
import sys

import pytest

from adaptengine.curriculum.content import load_content
from adaptengine.curriculum.loader import load_activities, load_curriculum

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if os.path.join(repo_root, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(repo_root, "scripts"))

from check_content import check_content, main, run_snippet  # noqa: E402

X10 = os.path.join(repo_root, "data/content/content_8node_x10.json")
OLD = os.path.join(repo_root, "data/content/content_8node.json")


def _doc(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_x10_content_covers_catalogue_and_keeps_old_entries_f5_tc3():
    cur = os.path.join(repo_root, "data/curriculum/curriculum_8node_x10.json")
    act = os.path.join(repo_root, "data/curriculum/activities_8node_x10.json")
    acts = load_activities(act, load_curriculum(cur, allow_unreviewed=True), allow_unreviewed=True)
    content = load_content(X10, acts)
    assert set(content) == {a.activity_id for a in acts}
    old = _doc(OLD)["activities"]
    assert all(content[k] == v for k, v in old.items())  # 40 entries copied verbatim
    assert len(content) - len(old) == 48


@pytest.mark.parametrize("path,spread", [(OLD, None), (X10, (3, 4, 3))])
def test_checker_passes_real_content_f5_tc3_tc4(path, spread):
    """Includes running every "verify": "output" snippet (42 in content_8node_x10.json)."""
    assert check_content(path, spread=spread) == []
    assert sum("verify" in e for e in _doc(path)["activities"].values()) == (42 if spread else 0)


def _write_variant(tmp_path, mutate):
    doc = _doc(X10)
    mutate(doc["activities"])
    p = tmp_path / "content.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return str(p)


def test_checker_catches_duplicate_prompt(tmp_path):
    def dup(acts):
        acts["E-C2-0.2"]["prompt"] = acts["E-C6-0.2"]["prompt"]

    problems = check_content(_write_variant(tmp_path, dup))
    assert any("E-C2-0.2 and E-C6-0.2 are duplicates" in p for p in problems)


def test_checker_catches_near_duplicate_with_same_answer(tmp_path):
    def near(acts):
        acts["E-C3-0.1"]["prompt"] = acts["E-C3-0.2"]["prompt"].replace("print", "print ")
        acts["E-C3-0.1"]["options"] = acts["E-C3-0.2"]["options"]
        acts["E-C3-0.1"]["correct"] = acts["E-C3-0.2"]["correct"]
        acts["E-C3-0.1"].pop("verify")

    problems = check_content(_write_variant(tmp_path, near))
    assert any("near-duplicates" in p and "E-C3-0.1" in p for p in problems)


def test_checker_catches_unbalanced_answer_key(tmp_path):
    def all_first(acts):
        for e in acts.values():
            if e["type"] == "EXERCISE" and e["target_concept"] == "C5":
                i = e["correct"]
                e["options"][0], e["options"][i] = e["options"][i], e["options"][0]
                e["correct"] = 0

    problems = check_content(_write_variant(tmp_path, all_first))
    assert problems == ["balance: C5 has correct index 0 in 10 of 10 exercises"]


def test_checker_catches_wrong_verified_answer(tmp_path):
    def wrong(acts):
        acts["E-C1-0.3"]["correct"] = 2  # "2.0", but the snippet prints 2.5

    problems = check_content(_write_variant(tmp_path, wrong))
    assert "verify: E-C1-0.3 prints '2.5' but the correct option is '2.0'" in problems


def test_checker_catches_wrong_spread():
    problems = check_content(X10, spread=(4, 3, 3))
    assert len(problems) == 8 and all(p.startswith("spread:") for p in problems)


def test_schema_problem_reported(tmp_path):
    problems = check_content(_write_variant(tmp_path, lambda acts: acts.pop("E-C1-0.1")))
    assert len(problems) == 1 and problems[0].startswith("schema:")


def test_cli_exit_codes(tmp_path, capsys):
    assert main([X10, "--spread", "3,4,3"]) == 0
    bad = _write_variant(tmp_path, lambda acts: acts["E-C1-0.3"].update(correct=2))
    assert main([bad]) == 1
    assert "1 problem(s)" in capsys.readouterr().out


@pytest.mark.parametrize(
    "code,expected",
    [
        ('print("ok")', "ok"),
        ("x = 1\nx()", "TypeError"),
        ('open("/etc/hostname").read()', "PermissionError"),
        ("import os", "PermissionError"),
        ('__import__("socket")', "PermissionError"),
    ],
)
def test_sandbox_runs_code_and_blocks_files_imports_and_network(code, expected):
    assert run_snippet(code) == expected


def test_sandbox_times_out():
    assert run_snippet("while True:\n    pass", timeout=1.0) in ("<timeout>", "<exit -9>")
