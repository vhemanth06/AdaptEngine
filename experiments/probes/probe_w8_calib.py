"""Why does adapt fall behind a keep-practising baseline on longer horizons?
Measures, at the end of each closed-loop episode: minutes used, whether the engine believes the goal
(and each required concept) is evidence-mastered, and the simulated learner's true theta.
"""
import os, sys, statistics, dataclasses
ROOT = os.environ.get("ADAPTENGINE_ROOT", os.getcwd())
sys.path[:0] = [os.path.join(ROOT, "src"), ROOT]
os.chdir(ROOT)
from adaptengine.api import Engine
from adaptengine.core.schema import PlanContext, ActivityType, Event, EventType
from adaptengine.learner.state import ExecutionLog, is_evidence_mastered
from experiments import arms
from experiments.sim import PROFILES, TRUE_MASTERY_CUTOFF, make_sim

eng = Engine.from_files("data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json")
PROF, GOAL, B = PROFILES["nominal"], "C4", 15
s0 = eng.init_learner()
for world in ("S0", "S1"):
    sc = arms.get_scenario("calm", eng, s0, goal=GOAL, budget=B)
    sc = dataclasses.replace(sc, deadline=sc.deadline * 2)
    rows = []
    for seed in range(100, 300):
        sim = make_sim(eng, seed, PROF, world=world)
        state, log = eng.init_learner(), ExecutionLog()
        minutes = 0; idle = 0; first_believed = None
        for day in range(1, sc.deadline + 1):
            used = 0
            while used < B:
                today, _ = eng.next_activities(state, log, PlanContext(goal=GOAL, deadline_day=sc.deadline, budget=B, current_day=day))
                if today is None:
                    break
                surprised = False
                for aid in today.activities:
                    a = eng.activities[aid]
                    if used + a.duration > B: break
                    ok = sim.respond(a.target_concept, aid, a.difficulty, tag="run") if a.type == ActivityType.EXERCISE else None
                    state, log = eng.record(state, log, Event(day=day, kind=EventType.COMPLETED, activity_id=aid, minutes_elapsed=a.duration, correct=ok))
                    sim.apply_activity(a.target_concept, is_lesson=a.type == ActivityType.LESSON, day=day)
                    used += a.duration; minutes += a.duration
                    if first_believed is None and is_evidence_mastered(state.concepts[GOAL], eng.config):
                        first_believed = sim.theta[GOAL]
                    if ok is False: surprised = True; break
                if not surprised: break
            if used == 0: idle += 1
        need = {GOAL} | eng.graph.ancestors(GOAL)
        believed = {c: is_evidence_mastered(state.concepts[c], eng.config) for c in need}
        true = {c: sim.theta[c] >= TRUE_MASTERY_CUTOFF for c in need}
        rows.append((minutes, idle, believed, true, first_believed, state.concepts[GOAL].p, sim.theta[GOAL]))
    n = len(rows)
    fm = sum(1 for r in rows for c in r[2] if r[2][c] and not r[3][c]); tot_b = sum(1 for r in rows for c in r[2] if r[2][c])
    print(f"\n[{world} calm, deadline {sc.deadline} days, budget {B} -> {sc.deadline*B} min available]")
    print(f"  mean minutes used by adapt: {statistics.mean(r[0] for r in rows):.1f}; mean idle days: {statistics.mean(r[1] for r in rows):.2f}")
    print(f"  goal believed evidence-mastered at end: {sum(r[2][GOAL] for r in rows)}/{n}; truly mastered: {sum(r[3][GOAL] for r in rows)}/{n}")
    print(f"  false-mastery rate (believed mastered but true theta < 0.70), all required concepts: {fm}/{tot_b} = {fm/max(1,tot_b):.1%}")
    fb = [r[4] for r in rows if r[4] is not None]
    print(f"  true goal theta at the moment the engine first declared mastery: mean {statistics.mean(fb):.3f}, share < 0.70: {sum(1 for x in fb if x < 0.70)/len(fb):.1%}")
