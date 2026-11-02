import random
from adaptengine.api import Engine
from adaptengine.core.config import EngineConfig, DEFAULT_CONFIG
from adaptengine.core.schema import Event, EventType, ActivityType, PlanContext
from adaptengine.learner.state import ExecutionLog
from adaptengine.planner.workload import WorkloadCache


def _get_engine(is_8node: bool = False, config: EngineConfig = DEFAULT_CONFIG) -> Engine:
    if is_8node:
        return Engine.from_files(
            "data/curriculum/curriculum_8node.json",
            "data/curriculum/activities_8node.json",
            config=config,
            allow_unreviewed=True,
        )
    return Engine.from_files(
        "data/curriculum/curriculum_4node.json",
        "data/curriculum/activities_4node.json",
        config=config,
    )


def test_frontier_replan_equivalence_grid():
    """Equivalence across curricula, budgets, and event kinds."""
    budgets = [5, 10, 15, 30]
    for is_8node in [False, True]:
        engine = _get_engine(is_8node)
        goal = "C4" if not is_8node else "C8"
        exercises = [a for a in engine.activities.values() if a.type == ActivityType.EXERCISE]
        lessons = [a for a in engine.activities.values() if a.type == ActivityType.LESSON]

        for budget in budgets:
            ctx = PlanContext(goal=goal, deadline_day=10, budget=budget, current_day=1)

            # 1. Missed day
            state = engine.init_learner()
            log = ExecutionLog()
            cache = WorkloadCache()
            state, log = engine.record(state, log, Event(day=1, kind=EventType.MISSED))
            plan_full = engine.replan(state, log, ctx)
            plan_front = engine.replan(state, log, ctx, workload_cache=cache)
            assert plan_full == plan_front

            # 2. Failed assessment
            state = engine.init_learner()
            log = ExecutionLog()
            cache = WorkloadCache()
            ex = exercises[0]
            state, log = engine.record(
                state,
                log,
                Event(
                    day=1,
                    kind=EventType.FAILED_ASSESSMENT,
                    activity_id=ex.activity_id,
                    minutes_elapsed=ex.duration,
                ),
            )
            plan_full = engine.replan(state, log, ctx)
            plan_front = engine.replan(state, log, ctx, workload_cache=cache)
            assert plan_full == plan_front

            # 3. Deadline change
            state = engine.init_learner()
            log = ExecutionLog()
            cache = WorkloadCache()
            state, log = engine.record(
                state, log, Event(day=1, kind=EventType.DEADLINE_CHANGED, value=12)
            )
            plan_full = engine.replan(state, log, ctx)
            plan_front = engine.replan(state, log, ctx, workload_cache=cache)
            assert plan_full == plan_front

            # 4. Budget change
            new_b = 10 if budget != 10 else 15
            state = engine.init_learner()
            log = ExecutionLog()
            cache = WorkloadCache()
            state, log = engine.record(
                state, log, Event(day=1, kind=EventType.BUDGET_CHANGED, value=new_b)
            )
            plan_full = engine.replan(state, log, ctx)
            plan_front = engine.replan(state, log, ctx, workload_cache=cache)
            assert plan_full == plan_front

            # 5. Completed lesson
            les = lessons[0]
            state = engine.init_learner()
            log = ExecutionLog()
            cache = WorkloadCache()
            state, log = engine.record(
                state,
                log,
                Event(
                    day=1,
                    kind=EventType.COMPLETED,
                    activity_id=les.activity_id,
                    minutes_elapsed=les.duration,
                ),
            )
            plan_full = engine.replan(state, log, ctx)
            plan_front = engine.replan(state, log, ctx, workload_cache=cache)
            assert plan_full == plan_front


def test_frontier_replan_random_sequences():
    """At least 50 seeded random sequences of 5-10 events, comparing after every event."""
    engine = _get_engine(is_8node=False)
    goal = "C4"
    exercises = [a for a in engine.activities.values() if a.type == ActivityType.EXERCISE]
    lessons = [a for a in engine.activities.values() if a.type == ActivityType.LESSON]

    for seed in range(50):
        rng = random.Random(f"seq-{seed}")
        state = engine.init_learner()
        log = ExecutionLog()
        cache = WorkloadCache()
        ctx = PlanContext(goal=goal, deadline_day=15, budget=15, current_day=1)

        seq_len = rng.randint(5, 10)
        day = 1
        for step in range(seq_len):
            kind_choice = rng.choice(
                ["missed", "completed_lesson", "exercise_correct", "exercise_wrong"]
            )
            if kind_choice == "missed":
                evt = Event(day=day, kind=EventType.MISSED)
                day += 1
            elif kind_choice == "completed_lesson":
                act = rng.choice(lessons)
                evt = Event(
                    day=day,
                    kind=EventType.COMPLETED,
                    activity_id=act.activity_id,
                    minutes_elapsed=act.duration,
                )
            elif kind_choice == "exercise_correct":
                act = rng.choice(exercises)
                evt = Event(
                    day=day,
                    kind=EventType.COMPLETED,
                    activity_id=act.activity_id,
                    minutes_elapsed=act.duration,
                    correct=True,
                )
            else:
                act = rng.choice(exercises)
                evt = Event(
                    day=day,
                    kind=EventType.COMPLETED,
                    activity_id=act.activity_id,
                    minutes_elapsed=act.duration,
                    correct=False,
                )

            state, log = engine.record(state, log, evt)
            full_plan = engine.replan(state, log, ctx)
            front_plan = engine.replan(state, log, ctx, workload_cache=cache)
            assert full_plan == front_plan, f"Mismatch at seed {seed}, step {step}"


def test_frontier_cache_hits_and_non_vacuous():
    """Assert cache.hits > 0 after second step, and misses correspond to changed concepts."""
    engine = _get_engine(is_8node=False)
    goal = "C4"
    ctx = PlanContext(goal=goal, deadline_day=10, budget=15, current_day=1)
    state = engine.init_learner()
    log = ExecutionLog()
    cache = WorkloadCache()

    # Step 1: Initial replan (primes cache)
    _ = engine.replan(state, log, ctx, workload_cache=cache)
    initial_misses = cache.misses
    initial_hits = cache.hits
    assert initial_misses > 0
    assert initial_hits == 0

    # Step 2: Event on a single concept C1 (completed exercise)
    c1_exercises = [
        a
        for a in engine.activities.values()
        if a.target_concept == "C1" and a.type == ActivityType.EXERCISE
    ]
    ex = c1_exercises[0]
    state, log = engine.record(
        state,
        log,
        Event(
            day=1,
            kind=EventType.COMPLETED,
            activity_id=ex.activity_id,
            minutes_elapsed=ex.duration,
            correct=True,
        ),
    )

    _ = engine.replan(state, log, ctx, workload_cache=cache)
    # Concepts C2, C3, C4 were not modified, so they should be cache hits
    assert cache.hits > 0
    # C1 changed, so C1 was a cache miss
    c1_misses = cache.misses - initial_misses
    assert c1_misses == 1


def test_frontier_cache_engine_isolation():
    """Two engines with different configs never return each other's cached entries."""
    from dataclasses import replace

    engine_a = _get_engine(is_8node=False, config=DEFAULT_CONFIG)
    cfg_b = replace(DEFAULT_CONFIG, theta=0.95, k_responses=5)
    engine_b = _get_engine(is_8node=False, config=cfg_b)

    cache = WorkloadCache()
    state_a = engine_a.init_learner()
    log_a = ExecutionLog()
    ctx = PlanContext(goal="C4", deadline_day=10, budget=15, current_day=1)

    plan_a = engine_a.replan(state_a, log_a, ctx, workload_cache=cache)

    # Now use same cache with engine_b
    state_b = engine_b.init_learner()
    log_b = ExecutionLog()
    plan_b = engine_b.replan(state_b, log_b, ctx, workload_cache=cache)

    # engine_b must not have reused engine_a's workload because cfg differs in key
    # Let's check plan_b is identical to uncached engine_b.replan
    uncached_b = engine_b.replan(state_b, log_b, ctx)
    assert plan_b == uncached_b
    assert plan_a != plan_b
