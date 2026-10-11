import json
from adaptengine.api import Engine
from adaptengine.session import load_learner, load_log
from adaptengine.core.schema import Event, EventType
from adaptengine.learner.mastery import update_mastery


def run_experiment():
    # 1. Assert reference constants before run
    # p=0.5, d=0.5: 0.8462 correct / 0.1707 wrong before learning transition
    # 0.8538 / 0.2122 after T=0.05
    # p=0.9, d=0.5 wrong -> 0.6495
    assert abs(update_mastery(0.50, 0.50, True, 0.0) - 0.8462) < 1e-4, "Ref constant 0.8462 failed"
    assert abs(update_mastery(0.50, 0.50, False, 0.0) - 0.1707) < 1e-4, "Ref constant 0.1707 failed"
    assert abs(update_mastery(0.50, 0.50, True, 0.05) - 0.8538) < 1e-4, "Ref constant 0.8538 failed"
    assert (
        abs(update_mastery(0.50, 0.50, False, 0.05) - 0.2122) < 1e-4
    ), "Ref constant 0.2122 failed"
    assert abs(update_mastery(0.90, 0.50, False, 0.0) - 0.6495) < 1e-4, "Ref constant 0.6495 failed"

    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    state = load_learner("data/learner_novice.json", engine.graph.concepts())
    log = load_log("data/nonexistent.json")

    steps = [
        ("E-C1-0.4", True, 0.5643, 0.9880),
        ("E-C1-0.6", True, 0.9014, 0.4645),
        ("E-C1-0.6", False, 0.6913, 0.8916),
        ("E-C1-0.4", True, 0.9179, 0.4094),
        ("E-C1-0.6", True, 0.9874, 0.0974),
        ("E-C1-0.8", True, 0.9990, 0.0111),
    ]

    p_init = state.concepts["C1"].mastery
    h_init = state.concepts["C1"].uncertainty
    print(json.dumps({"initial": {"p": p_init, "H": h_init}}))

    for i, (aid, correct, exp_p, exp_h) in enumerate(steps):
        duration = engine.activities[aid].duration
        event = Event(
            day=1,
            kind=EventType.COMPLETED,
            activity_id=aid,
            minutes_elapsed=duration,
            correct=correct,
            attempt_id=f"smoke-step-{i+1}",
        )
        state, log = engine.record(state, log, event)
        p_curr = round(state.concepts["C1"].mastery, 4)
        h_curr = round(state.concepts["C1"].uncertainty, 4)
        print(
            json.dumps(
                {
                    "step": i + 1,
                    "activity": aid,
                    "correct": correct,
                    "p": p_curr,
                    "H": h_curr,
                }
            )
        )
        assert abs(p_curr - exp_p) < 1e-3, f"Step {i+1} p mismatch: {p_curr} vs {exp_p}"
        assert abs(h_curr - exp_h) < 1e-3, f"Step {i+1} H mismatch: {h_curr} vs {exp_h}"

    print("PASS: run_smoke reference assertions passed.")


if __name__ == "__main__":
    run_experiment()
