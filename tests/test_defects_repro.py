import pytest
import json
import sys
from adaptengine.core.schema import Activity, ActivityType, Event, EventType
from adaptengine.core.errors import (
    ValidationError,
    UnknownConceptError,
    UnreviewedContentError,
)
from adaptengine.curriculum.loader import load_curriculum
from adaptengine.learner.mastery import guess, learn
from adaptengine.learner.state import initial_state, LearnerConcept
from adaptengine.session import apply_lesson
from adaptengine.core.config import EngineConfig


# --- D-A: CLI and API review gate on by default ---
def test_repro_da_cli_unreviewed_accepted():
    """Defect D-A: CLI update/show/init loads unreviewed content because allow_unreviewed=True is hardcoded."""
    import subprocess

    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "adaptengine",
            "show",
            "--curriculum",
            "tests/fixtures/invalid/bad_duration.json",
        ],
        capture_output=True,
        text=True,
    )
    # With default review gate, unreviewed content is rejected
    assert res.returncode != 0


# --- D-B: Strict validation of boolean, enums, probabilities, ranges ---
def test_repro_db_string_false_accepted():
    """Defect D-B: Event.correct='false' accepted instead of strict bool."""
    with pytest.raises(ValidationError):
        Event(day=1, kind=EventType.COMPLETED, activity_id="A1", minutes_elapsed=5, correct="false")  # type: ignore


def test_repro_db_learner_concept_invalid_fields():
    """Defect D-B: LearnerConcept accepts uncertainty=-5, assessed='false', negative day/count/half-life."""
    with pytest.raises(ValidationError):
        LearnerConcept(mastery=0.5, uncertainty=-5.0)

    with pytest.raises(ValidationError):
        LearnerConcept(mastery=0.5, uncertainty=0.5, assessed="false")  # type: ignore

    with pytest.raises(ValidationError):
        LearnerConcept(mastery=0.5, uncertainty=0.5, last_practice_day=-1)

    with pytest.raises(ValidationError):
        LearnerConcept(mastery=0.5, uncertainty=0.5, half_life_days=-2.0)


# --- D-C: Unknown prerequisite creates phantom node and JSON list root raw error ---
def test_repro_dc_unknown_prereq_phantom_node():
    """Defect D-C: unknown_prereq.json raises UnknownConceptError."""
    with pytest.raises(UnknownConceptError):
        load_curriculum("tests/fixtures/invalid/unknown_prereq.json", allow_unreviewed=True)


def test_repro_dc_json_list_root_raw_error(tmp_path):
    """Defect D-C: JSON list root raises raw AttributeError instead of ValidationError."""
    path = tmp_path / "list_root.json"
    path.write_text(json.dumps([{"concept_id": "C1"}]))
    with pytest.raises(ValidationError):
        load_curriculum(str(path), allow_unreviewed=True)


# --- D-D: apply_lesson sets assessed=True and replay gives p > theta ---
def test_repro_dd_lesson_assessed_and_replay():
    """Defect D-D: apply_lesson sets assessed=True; 8x replay gives p > theta without quiz."""
    state = initial_state(("C1",))
    act = Activity("L1", ActivityType.LESSON, "C1", duration=5)
    for _ in range(8):
        state, _ = apply_lesson(state, act)

    c = state.concepts["C1"]
    assert not c.assessed, "Lesson should not set assessed=True"
    assert not c.evidence_mastered, "Lesson exposure must not mark evidence_mastered"


def test_repro_dd_last_practice_day_rewind():
    """Defect D-D: day 20 then day 1 rewinds last_practice_day to 1."""
    state = initial_state(("C1",))
    act = Activity("L1", ActivityType.LESSON, "C1", duration=5)
    state, _ = apply_lesson(state, act, day=20)
    state, _ = apply_lesson(state, act, day=1)
    assert state.concepts["C1"].last_practice_day == 20


# --- D-E: Config validation, d_min/d_max in guess/slip, learn(0.5, 1.5) bound ---
def test_repro_de_learn_t_out_of_bounds():
    """Defect D-E: learn(0.5, 1.5) returns 1.25 instead of raising ValidationError."""
    with pytest.raises(ValidationError):
        learn(0.5, 1.5)


def test_repro_de_guess_slip_uses_resolved_config():
    """Defect D-E: guess/slip ignores cfg.d_min/d_max and uses global constants."""
    custom_cfg = EngineConfig(d_min=0.10, d_max=0.90)
    with pytest.raises(ValidationError):
        guess(0.08, cfg=custom_cfg)


# --- D-F: Passing data/review_manifest.json explicitly fails, reviewer='AI' accepted ---
def test_repro_df_explicit_manifest_path():
    """Defect D-F: Passing data/review_manifest.json explicitly fails due to path resolution."""
    concepts = load_curriculum(
        "data/curriculum/curriculum_4node.json",
        manifest_path="data/review_manifest.json",
        allow_unreviewed=False,
    )
    assert len(concepts) == 4


def test_repro_df_ai_reviewer_rejected(tmp_path):
    """Defect D-F: reviewer='AI' accepted; live loads require named human reviewer."""
    import hashlib

    content = b'{"schema_version": 1, "concepts": [{"concept_id": "C1"}]}'
    curr_path = tmp_path / "data" / "curriculum" / "curr.json"
    curr_path.parent.mkdir(parents=True, exist_ok=True)
    curr_path.write_bytes(content)

    manifest_data = {
        "data/curriculum/curr.json": {
            "reviewer": "AI",
            "date": "2026-10-11T00:00:00",
            "sha256": hashlib.sha256(content).hexdigest(),
            "edges_reviewed": True,
        }
    }
    manifest_path = tmp_path / "data" / "review_manifest.json"
    manifest_path.write_text(json.dumps(manifest_data))

    with pytest.raises(UnreviewedContentError) as exc_info:
        load_curriculum(str(curr_path), manifest_path=str(manifest_path), allow_unreviewed=False)
    assert "ai" in str(exc_info.value).lower()
