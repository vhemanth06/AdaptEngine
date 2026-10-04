from adaptengine.api import Engine
from adaptengine.session import load_learner, load_log
from adaptengine.core.schema import Event, EventType
import json


def run_experiment():
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    state = load_learner("data/learner_novice.json", engine.graph.concepts())
    log = load_log("data/nonexistent.json")

    steps = [
        ("E-C1-0.4", True),
        ("E-C1-0.6", True),
        ("E-C1-0.6", False),
        ("E-C1-0.4", True),
        ("E-C1-0.6", True),
        ("E-C1-0.8", True),
    ]

    print(
        json.dumps(
            {"initial": {"p": state.concepts["C1"].mastery, "H": state.concepts["C1"].uncertainty}}
        )
    )

    for i, (aid, correct) in enumerate(steps):
        duration = engine.activities[aid].duration
        event = Event(
            day=1,
            kind=EventType.COMPLETED,
            activity_id=aid,
            minutes_elapsed=duration,
            correct=correct,
        )
        state, log = engine.record(state, log, event)
        print(
            json.dumps(
                {
                    "step": i + 1,
                    "activity": aid,
                    "correct": correct,
                    "p": round(state.concepts["C1"].mastery, 4),
                    "H": round(state.concepts["C1"].uncertainty, 4),
                }
            )
        )


if __name__ == "__main__":
    run_experiment()
