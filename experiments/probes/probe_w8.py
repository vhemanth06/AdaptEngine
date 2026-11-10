"""W8 probes on the Week 7 code (scratch only; nothing in the project is modified).

A. Diagnose-then-plan: does running the shipped diagnostic before the closed loop help?
   (diagnostic item minutes are charged to day 1's budget; diagnostic answers do not change theta)
B. Horizon: same arms with the deadline doubled (calm), to see whether short horizons hide differences.
C. Unlock threshold: closed loop with a lower mastery threshold theta (0.75) for comparison.
"""
import os, sys, statistics, dataclasses
ROOT = os.environ.get("ADAPTENGINE_ROOT", os.getcwd())
sys.path[:0] = [os.path.join(ROOT, "src"), ROOT]
os.chdir(ROOT)
from adaptengine.api import Engine
from adaptengine.core.config import DEFAULT_CONFIG
from adaptengine.core.schema import PlanContext, ActivityType, Event, EventType
from adaptengine.learner.state import ExecutionLog
from experiments import arms
from experiments.arms import Scenario
from experiments.sim import PROFILES, TRUE_MASTERY_CUTOFF, make_sim
from experiments.checks import count_executed_prereq_violations
from experiments.stats import paired_bootstrap_ci

C4, A4 = "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
PROF = PROFILES["nominal"]
GOAL, B = "C4", 15
SEEDS = range(100, 300)


def closed_loop(engine, seed, sc, world, diagnose=False):
    sim = make_sim(engine, seed, PROF, world=world)
    state, log = engine.init_learner(), ExecutionLog()
    start = state
    dx_min = 0
    if diagnose:
        r = engine.diagnose(state, response_provider=lambda a: sim.respond(a.target_concept, a.activity_id, a.difficulty, tag="diag"),
                            session_id=f"s{seed}")
        state = r.state
        start = state
        dx_min = sum(engine.activities[i.activity_id].duration for i in r.item_log)
    minutes = dx_min
    for day in range(1, sc.deadline + 1):
        used = dx_min if day == 1 else 0
        if any(e[0] == day and e[1] == EventType.MISSED for e in sc.events):
            state, log = engine.record(state, log, Event(day=day, kind=EventType.MISSED)); continue
        while used < B:
            ctx = PlanContext(goal=GOAL, deadline_day=sc.deadline, budget=B, current_day=day)
            today, _ = engine.next_activities(state, log, ctx)
            if today is None:
                break
            surprised = False; progressed = False
            for aid in today.activities:
                a = engine.activities[aid]
                if used + a.duration > B:
                    break
                c = a.target_concept
                ok = None
                if a.type == ActivityType.EXERCISE:
                    ok = sim.respond(c, aid, a.difficulty, tag="run")
                state, log = engine.record(state, log, Event(day=day, kind=EventType.COMPLETED, activity_id=aid, minutes_elapsed=a.duration, correct=ok))
                sim.apply_activity(c, is_lesson=a.type == ActivityType.LESSON, day=day)
                used += a.duration; minutes += a.duration; progressed = True
                if ok is False:
                    surprised = True; break
            if not surprised or not progressed:
                break
    sim.settle(sc.deadline)
    need = {GOAL} | engine.graph.ancestors(GOAL)
    return {"goal": sim.theta[GOAL] >= TRUE_MASTERY_CUTOFF, "theta": sim.theta[GOAL],
            "allreq": all(sim.theta[c] >= TRUE_MASTERY_CUTOFF for c in need), "minutes": minutes,
            "viol": count_executed_prereq_violations(engine, start, log)}


def static(engine, seed, sc, world):
    r = arms.run_episode(engine, seed, sc, "static", PROF, world=world)
    return {"goal": r["goal_mastered"], "theta": r["goal_true_mastery"], "allreq": None,
            "minutes": sum(r["executed_minutes_per_day"].values()) if "executed_minutes_per_day" in r else None,
            "viol": r.get("executed_prereq_violations")}


def summary(name, rows, ref):
    mr = statistics.mean(1.0 if x["goal"] else 0.0 for x in rows)
    d = [(1.0 if a["goal"] else 0.0) - (1.0 if b["goal"] else 0.0) for a, b in zip(rows, ref)]
    ar = statistics.mean(1.0 if x["allreq"] else 0.0 for x in rows) if rows[0]["allreq"] is not None else float("nan")
    v = sum(x["viol"] or 0 for x in rows)
    print(f"    {name:34s} goal-mastery={mr:6.1%}  Δ vs static={statistics.mean(d):+.3f} {paired_bootstrap_ci(d)}  all-req={ar:6.1%}  exec.viol={v}")



# ---- D. Fairer baseline for long horizons: static that keeps cycling exercises until the deadline ----
def static_loop(engine, seed, sc, world):
    sim = make_sim(engine, seed, PROF, world=world)
    state, log = engine.init_learner(), ExecutionLog()
    order = engine.graph.topological_order()
    need = {GOAL} | engine.graph.ancestors(GOAL)
    lessons = [a for c in order if c in need for a in engine.activities.values() if a.target_concept == c and a.type == ActivityType.LESSON]
    exs = [a for c in order if c in need for a in sorted(engine.activities.values(), key=lambda x: x.activity_id) if a.target_concept == c and a.type == ActivityType.EXERCISE]
    queue = list(lessons) + exs
    i = 0
    for day in range(1, sc.deadline + 1):
        if any(e[0] == day and e[1] == EventType.MISSED for e in sc.events):
            continue
        used = 0
        while True:
            a = queue[i] if i < len(queue) else exs[(i - len(queue)) % len(exs)]
            if used + a.duration > B:
                break
            ok = sim.respond(a.target_concept, a.activity_id, a.difficulty, tag="run") if a.type == ActivityType.EXERCISE else None
            state, log = engine.record(state, log, Event(day=day, kind=EventType.COMPLETED, activity_id=a.activity_id, minutes_elapsed=a.duration, correct=ok))
            sim.apply_activity(a.target_concept, is_lesson=a.type == ActivityType.LESSON, day=day)
            used += a.duration; i += 1
    sim.settle(sc.deadline)
    return {"goal": sim.theta[GOAL] >= TRUE_MASTERY_CUTOFF, "theta": sim.theta[GOAL],
            "allreq": all(sim.theta[c] >= TRUE_MASTERY_CUTOFF for c in need), "minutes": None,
            "viol": count_executed_prereq_violations(engine, engine.init_learner(), log)}


def main():
    global eng, eng_t75, s0
    eng = Engine.from_files(C4, A4)
    eng_t75 = Engine.from_files(C4, A4, config=dataclasses.replace(DEFAULT_CONFIG, theta=0.75))
    s0 = eng.init_learner()
    for world in ("S1", "S0"):
        for scen in ("calm", "missed_day"):
            sc = arms.get_scenario(scen, eng, s0, goal=GOAL, budget=B)
            for label, scx in (("deadline as in grid", sc), ("deadline x2", dataclasses.replace(sc, deadline=sc.deadline * 2))):
                print(f"\n[{world} | {scen} | {label} = {scx.deadline} days | 4-node, B={B}, N={len(SEEDS)}]")
                st = [static(eng, s, scx, world) for s in SEEDS]
                summary("static", st, st)
                summary("adapt (W7 closed loop)", [closed_loop(eng, s, scx, world) for s in SEEDS], st)
                summary("adapt + diagnose first", [closed_loop(eng, s, scx, world, diagnose=True) for s in SEEDS], st)
                summary("adapt, theta=0.75", [closed_loop(eng_t75, s, scx, world) for s in SEEDS], st)
                summary("adapt + diagnose, theta=0.75", [closed_loop(eng_t75, s, scx, world, diagnose=True) for s in SEEDS], st)
    print("\n\n==== D. static that keeps practising until the deadline (fair long-horizon baseline) ====")
    for world in ("S1", "S0"):
        sc = arms.get_scenario("calm", eng, s0, goal=GOAL, budget=B)
        for label, scx in (("deadline as in grid", sc), ("deadline x2", dataclasses.replace(sc, deadline=sc.deadline * 2))):
            print(f"\n[{world} | calm | {label} = {scx.deadline} days]")
            sl = [static_loop(eng, s, scx, world) for s in SEEDS]
            summary("static_loop (reference)", sl, sl)
            summary("adapt (W7 closed loop)", [closed_loop(eng, s, scx, world) for s in SEEDS], sl)


if __name__ == '__main__':
    main()
