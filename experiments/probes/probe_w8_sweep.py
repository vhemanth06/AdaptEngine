"""Which engine settings close the gap to a keep-practising baseline on an 8-day horizon?"""
import os, sys, dataclasses, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_w8 as P
from adaptengine.api import Engine
from adaptengine.core.config import DEFAULT_CONFIG
from experiments import arms

C = DEFAULT_CONFIG
variants = {
    "W7 default": C,
    "theta 0.95": dataclasses.replace(C, theta=0.95),
    "k = 4 responses": dataclasses.replace(C, k_responses=4),
    "theta 0.95, k = 4": dataclasses.replace(C, theta=0.95, k_responses=4),
    "slower learning (T_lesson .05, T_ex .02)": dataclasses.replace(C, t_lesson=0.05, t_exercise=0.02),
    "higher guess (guess_coef .55)": dataclasses.replace(C, guess_coef=0.55),
    "calibrated-ish: guess .55 + T slower + k 3": dataclasses.replace(C, guess_coef=0.55, t_lesson=0.05, t_exercise=0.02, k_responses=3),
}
base = Engine.from_files(P.C4, P.A4)
s0 = base.init_learner()
for world in ("S0", "S1"):
    sc = arms.get_scenario("calm", base, s0, goal=P.GOAL, budget=P.B)
    for label, scx in (("grid deadline", sc), ("deadline x2", dataclasses.replace(sc, deadline=sc.deadline * 2))):
        print(f"\n[{world} | calm | {label} = {scx.deadline} days | N={len(P.SEEDS)}]")
        sl = [P.static_loop(base, s, scx, world) for s in P.SEEDS]
        P.summary("static_loop (reference)", sl, sl)
        for name, cfg in variants.items():
            e = Engine.from_files(P.C4, P.A4, config=cfg)
            rows = [P.closed_loop(e, s, scx, world) for s in P.SEEDS]
            P.summary(name, rows, sl)
            print(f"{'':40s}mean minutes used {statistics.mean(r['minutes'] for r in rows):.1f} of {scx.deadline*P.B}")
