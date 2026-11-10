"""Engine-generated closed option set for the A3 orchestrator (W8 N.1, D58).

Only options that are valid now are generated:
  continue        always
  remediate:X     X is flagged needs_remediation, on the goal path and not prerequisite-gated
  review:Y        Y is on the goal path, practised before and its recall is below the threshold
  rediagnose:Z    Z's evidence is stale (not practised for STALE_DAYS) or contradictory (believed
                  mastered but the latest answer was wrong)
  consolidate     every required concept is believed evidence-mastered (C.1 applies)
The deterministic default follows the engine's tier order: remediate, then review, then continue
(consolidate when nothing else is left).
"""

from __future__ import annotations

from typing import Optional

from ..core.config import DEFAULT_CONFIG, EngineConfig
from ..curriculum.graph import CurriculumGraph
from ..learner.state import LearnerState, is_evidence_mastered
from ..review.forgetting import recall_at

STALE_DAYS = 7


def build_options(
    graph: CurriculumGraph,
    state: LearnerState,
    goal: str,
    day: int,
    cfg: EngineConfig = DEFAULT_CONFIG,
) -> list[dict]:
    path = {goal} | graph.ancestors(goal)
    order = [c for c in graph.topological_order() if c in path]
    m = {c: is_evidence_mastered(state.concepts[c], cfg) for c in order}
    opts = [{"id": "continue", "kind": "continue", "concept": None, "why": "follow the plan"}]
    for c in order:
        s = state.concepts[c]
        gated = any(not m[q] for q in graph.prerequisites(c))
        if s.needs_remediation and not gated:
            opts.append(
                {
                    "id": f"remediate:{c}",
                    "kind": "remediate",
                    "concept": c,
                    "why": "flagged after a failed answer",
                }
            )
        r = recall_at(s.last_practice_day, s.half_life_days, day)
        if m[c] and r is not None and r < cfg.recall_threshold:
            opts.append(
                {
                    "id": f"review:{c}",
                    "kind": "review",
                    "concept": c,
                    "why": f"recall {r:.2f} below {cfg.recall_threshold}",
                }
            )
        stale = s.last_practice_day is not None and day - s.last_practice_day >= STALE_DAYS
        contradictory = m[c] and s.responses > 0 and s.correct_streak == 0
        if (stale or contradictory) and not gated:
            why = (
                "evidence is stale" if stale else "believed mastered but the last answer was wrong"
            )
            opts.append({"id": f"rediagnose:{c}", "kind": "rediagnose", "concept": c, "why": why})
    if all(m.values()):
        opts.append(
            {
                "id": "consolidate",
                "kind": "consolidate",
                "concept": None,
                "why": "all required concepts believed mastered",
            }
        )
    return opts


def default_option(options: list[dict]) -> str:
    for kind in ("remediate", "review"):
        hit: Optional[dict] = next((o for o in options if o["kind"] == kind), None)
        if hit:
            return hit["id"]
    if any(o["kind"] == "consolidate" for o in options):
        return "consolidate"
    return "continue"
