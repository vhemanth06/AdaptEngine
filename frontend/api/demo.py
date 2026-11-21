"""The demo preset (D94). Chosen by frontend/api/select_demo_preset.py (fixed procedure, Plan FE
§FE.6); the values below are that script's output (2026-11-20, docs/archive/notes/FRONTEND_NOTES.md). The
scripted demo learner answers right exactly on the concepts in KNOWN (no slips, no guesses); it
only answers questions, the engine decides.
"""

CURRICULUM = "8node_x10"
GOAL = "C8"
DIAGNOSTIC_METHOD = "bisection"
PLANNER_METHOD = "cpsat"
MODEL_PROFILE = "heuristic"
KNOWN = ("C1", "C2", "C3", "C6")
DEADLINE_DAY = 10
BUDGET = 10
TIGHT = {"deadline_day": 10, "budget": 5}
HAS_CHECK = True  # the preset's plan has a confirmation check that Study can reach
WRONG_CHECK = "E-C2-0.1"  # Study step 5: a wrong answer replans; C2 stays "check pending"
# §FE.6 criterion 2 split: no candidate asked fewer bisection questions than the sweep (8 vs 6
# here), so that claim is dropped from the walkthrough; INFERRED concepts (2b) are still shown.
FEWER_QUESTIONS = False

PRESET = {
    "curriculum": CURRICULUM,
    "goal": GOAL,
    "deadline_day": DEADLINE_DAY,
    "budget": BUDGET,
    "model_profile": MODEL_PROFILE,
    "diagnostic_method": DIAGNOSTIC_METHOD,
    "planner_method": PLANNER_METHOD,
    "known": list(KNOWN),
    "tight": TIGHT,
    "has_check": HAS_CHECK,
    "wrong_check": WRONG_CHECK,
}
