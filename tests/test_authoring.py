"""W8 WP-K A0 authoring aid with the stub provider only (no network). Links TC1.2 (review gate)."""

import json
import os
import shutil
import sys

import pytest

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "scripts")) if p not in sys.path]

from adaptengine.api import Engine  # noqa: E402
from adaptengine.authoring import checks  # noqa: E402
from adaptengine.authoring.draft import PENDING, generate_draft  # noqa: E402
from adaptengine.authoring.providers import CachedProvider, ProviderError, StubProvider  # noqa: E402
from adaptengine.core.errors import UnreviewedContentError  # noqa: E402
import record_review  # noqa: E402


def draft(tmp_path, provider=None, name="py_dicts", n=6):
    return generate_draft(
        provider or StubProvider(), name=name, topic="Python dictionaries", n_concepts=n,
        drafts_root=str(tmp_path / "data" / "drafts"),
    )  # fmt: skip


def test_stub_draft_passes_loaders_and_is_marked_pending(tmp_path):
    res = draft(tmp_path)
    assert res["first_pass_valid"] and res["report"]["ok"]
    d = tmp_path / "data" / "drafts" / "py_dicts"
    meta = json.load(open(d / "draft_meta.json"))
    assert meta["ai_assisted"] is True and meta["reviewer"] == PENDING
    assert meta["provider"] == "stub" and len(meta["prompt_hash"]) == 64
    e = Engine.from_files(
        str(d / "curriculum_py_dicts.json"), str(d / "activities_py_dicts.json"),
        allow_unreviewed=True,
    )  # fmt: skip
    assert len(e.graph.concepts()) == 6
    assert not (tmp_path / "data" / "curriculum").exists()  # never written there


def test_unreviewed_draft_rejected_by_live_loader(tmp_path):
    draft(tmp_path)
    d = tmp_path / "data" / "drafts" / "py_dicts"
    with pytest.raises(UnreviewedContentError):
        Engine.from_files(
            str(d / "curriculum_py_dicts.json"), str(d / "activities_py_dicts.json"),
            manifest_path=str(tmp_path / "manifest.json"),
        )  # fmt: skip


def test_retry_on_validation_error_then_success(tmp_path):
    calls = []

    def flaky(payload):
        calls.append(1)
        if len(calls) == 1:
            return "not json"
        from adaptengine.authoring.draft import template_draft

        obj = template_draft(payload)
        if len(calls) == 2:
            obj["concepts"][0]["prerequisites"] = ["K3"]  # cycle K1 <- K3 <- K2 <- K1
        return json.dumps(obj)

    res = draft(tmp_path, StubProvider({"draft": flaky}), n=3)
    assert len(res["attempts"]) == 3 and not res["first_pass_valid"]
    assert res["attempts"][0]["schema_errors"] and res["attempts"][1]["schema_errors"]
    assert res["report"]["ok"]


def test_retry_gives_up_after_two_retries(tmp_path):
    res = draft(tmp_path, StubProvider({"draft": lambda p: "{}"}), n=2)
    assert len(res["attempts"]) == 3 and all(a["schema_errors"] for a in res["attempts"])


def test_bad_draft_names_rejected(tmp_path):
    for bad in ("../evil", "Upper", "", "a/b"):
        with pytest.raises(ValueError):
            draft(tmp_path, name=bad)


# ------------------------------------------------------------------ K.3 one fixture per check


def _content(entries):
    return {aid: {"type": "EXERCISE", "prompt": p, "correct": c} for aid, p, c in entries}


def test_check_duplicates():
    c = _content(
        [("E1", "What is `len({})`?", 0), ("E2", "what is len({})?", 1), ("E3", "Other", 2)]
    )
    issues = checks.check_duplicates(c)
    assert [i.where for i in issues] == ["E1,E2"] and issues[0].severity == "error"


def test_check_answer_position_bias():
    assert (
        checks.check_answer_position(_content([(f"E{i}", "q", 0) for i in range(6)]))[0].severity
        == "error"
    )
    assert not checks.check_answer_position(_content([(f"E{i}", "q", i % 4) for i in range(8)]))


def test_check_difficulty_spread():
    from adaptengine.core.schema import Activity, ActivityType

    mk = lambda c, d: Activity(f"E-{c}-{d}", ActivityType.EXERCISE, c, 1, d)  # noqa: E731
    issues = checks.check_difficulty_spread(
        [mk("A", 0.2), mk("A", 0.3), mk("B", 0.2), mk("B", 0.5), mk("C", 0.2), mk("C", 0.8)]
    )
    assert {(i.where, i.severity) for i in issues} == {("A", "error"), ("B", "warning")}


def test_check_reading_length():
    c = {
        "L1": {"type": "LESSON", "markdown": "too short"},
        "E1": {"type": "EXERCISE", "prompt": "w " * 100},
    }
    assert {i.where for i in checks.check_reading_length(c)} == {"L1", "E1"}


# ----------------------------------------------------------------- K.4 human review gate


@pytest.mark.parametrize(
    "name",
    ["", "  ", "PENDING_HUMAN_REVIEW", "AI", "Claude", "gpt-5", "stub", "LLM reviewer", "model"],
)
def test_review_gate_rejects_ai_and_pending(name):
    with pytest.raises(record_review.ReviewRejected):
        record_review.check_reviewer(name)


def test_promote_draft_requires_human_and_records_manifest(tmp_path):
    draft(tmp_path)
    manifest = tmp_path / "data" / "review_manifest.json"
    with pytest.raises(record_review.ReviewRejected):
        record_review.promote_draft("py_dicts", "AI", root=str(tmp_path), manifest=str(manifest))
    assert not (tmp_path / "data" / "curriculum").exists()
    rec = record_review.promote_draft(
        "py_dicts", "Hemanth V", root=str(tmp_path), manifest=str(manifest)
    )
    assert len(rec) == 3
    m = json.load(open(manifest))
    assert all(v["reviewer"] == "Hemanth V" and v["ai_assisted"] for v in m.values())
    for rel in rec:  # the manifest hash matches the promoted file
        assert m[rel]["sha256"] == record_review.hash_file(str(tmp_path / rel))
    assert m["data/curriculum/curriculum_py_dicts.json"]["edges_reviewed"] is True
    with pytest.raises(record_review.ReviewRejected):  # no silent overwrite
        record_review.promote_draft(
            "py_dicts", "Hemanth V", root=str(tmp_path), manifest=str(manifest)
        )


def test_cli_author_draft_and_validate(tmp_path, capsys):
    from adaptengine.cli import main

    root = str(tmp_path / "drafts")
    assert (
        main(
            [
                "author",
                "draft",
                "--name",
                "mini",
                "--topic",
                "Sets",
                "--concepts",
                "3",
                "--drafts-root",
                root,
            ]
        )
        == 0
    )
    assert main(["author", "validate", "--name", "mini", "--drafts-root", root]) == 0
    shutil.rmtree(os.path.join(root, "mini"))
    assert main(["author", "validate", "--name", "mini", "--drafts-root", root]) == 1


# ------------------------------------------------------------------------------ L.2 cache


def test_cache_hit_returns_identical_output_and_replays_offline(tmp_path):
    inner = StubProvider()
    cp = CachedProvider(inner, str(tmp_path / "cache"))
    a = cp.complete("prompt", task="rank", payload={"candidates": ["x", "y"]})
    b = cp.complete("prompt", task="rank", payload={"candidates": ["y", "x"]})
    assert a == b and inner.calls == 1 and (cp.hits, cp.misses) == (1, 1)
    rec = json.load(open(next((tmp_path / "cache").iterdir())))
    assert rec["model"] == "template-stub-1" and rec["prompt"] == "prompt"
    replay = CachedProvider(StubProvider(), str(tmp_path / "cache"), replay_only=True)
    assert replay.complete("prompt", task="rank") == a
    with pytest.raises(ProviderError):
        replay.complete("new prompt", task="rank")
