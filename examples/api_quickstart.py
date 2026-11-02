#!/usr/bin/env python3
"""AdaptEngine API Quickstart Example.

Demonstrates initializing the engine, generating an initial adaptive plan,
recording execution events, replanning upon disruption, and serializing output.
"""

from adaptengine.api import Engine
from adaptengine.core.schema import Event, EventType, PlanContext
from adaptengine.learner.state import ExecutionLog
from adaptengine.planner.plan import serialize_plan


def main() -> None:
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json",
        "data/curriculum/activities_4node.json",
    )
    state, log = engine.init_learner(), ExecutionLog()
    ctx = PlanContext(goal="C4", deadline_day=5, budget=15)

    plan = engine.plan(state, ctx)
    print(plan.status.value, [d.activities for d in plan.days])

    first = plan.days[0].activities[0]
    first_dur = engine.activities[first].duration
    state, log = engine.record(
        state,
        log,
        Event(
            day=1,
            kind=EventType.COMPLETED,
            activity_id=first,
            minutes_elapsed=first_dur,
        ),
    )
    state, log = engine.record(state, log, Event(day=2, kind=EventType.MISSED))
    revised = engine.replan(state, log, ctx)
    print(revised.status.value, [d.day for d in revised.days])
    print(serialize_plan(revised, engine.config)["config_hash"][:12])


if __name__ == "__main__":
    main()
