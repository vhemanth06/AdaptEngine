"""Authoring checks for AI-assisted drafts (W8 K.3, D54): schema validation through the existing
loaders plus content-quality checks. Returns a typed report; nothing is changed.

Checks: schema (curriculum DAG, activities, content), duplicate / near-duplicate questions,
answer-position bias, difficulty spread per concept, reading length.
"""

from __future__ import annotations

import difflib
import os
from dataclasses import asdict, dataclass, field
from typing import Optional

from ..core.errors import AdaptEngineError
from ..core.schema import ActivityType
from ..curriculum.content import load_content
from ..curriculum.graph import CurriculumGraph
from ..curriculum.loader import load_activities, load_curriculum

NEAR_DUPLICATE = 0.90  # SequenceMatcher ratio on normalised prompts
MAX_POSITION_SHARE = 0.5  # share of exercises whose correct answer sits at one position
LESSON_WORDS = (40, 700)
PROMPT_WORDS = 80


@dataclass(frozen=True)
class Issue:
    check: str
    severity: str  # "error" blocks approval, "warning" is advisory
    message: str
    hint: str = ""
    where: Optional[str] = None


@dataclass
class ValidationReport:
    issues: list[Issue] = field(default_factory=list)
    n_concepts: int = 0
    n_activities: int = 0

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "n_concepts": self.n_concepts,
            "n_activities": self.n_activities,
            "errors": sum(i.severity == "error" for i in self.issues),
            "warnings": sum(i.severity == "warning" for i in self.issues),
            "issues": [asdict(i) for i in self.issues],
        }


def _norm(text: str) -> str:
    return " ".join(text.lower().replace("`", "").split())


def _class(d: float) -> str:
    return "easy" if d < 0.35 else "medium" if d < 0.65 else "hard"


def check_duplicates(content: dict) -> list[Issue]:
    ex = sorted((aid, _norm(e["prompt"])) for aid, e in content.items() if e["type"] == "EXERCISE")
    out = []
    for i, (a, pa) in enumerate(ex):
        for b, pb in ex[i + 1 :]:
            r = difflib.SequenceMatcher(None, pa, pb).ratio()
            if r >= NEAR_DUPLICATE:
                out.append(
                    Issue(
                        "duplicate_question",
                        "error" if r == 1.0 else "warning",
                        f"{a} and {b} ask (almost) the same question (similarity {r:.2f})",
                        "Rewrite one prompt so it tests a different case.",
                        f"{a},{b}",
                    )
                )
    return out


def check_answer_position(content: dict) -> list[Issue]:
    pos = [e["correct"] for e in content.values() if e["type"] == "EXERCISE"]
    if len(pos) < 4:
        return []
    out = []
    for k in range(4):
        share = pos.count(k) / len(pos)
        if share > MAX_POSITION_SHARE:
            out.append(
                Issue(
                    "answer_position_bias",
                    "error" if share == 1.0 else "warning",
                    f"{share:.0%} of correct answers are option {k + 1}",
                    "Shuffle options so the correct answer position varies.",
                )
            )
    return out


def check_difficulty_spread(activities) -> list[Issue]:
    by_c: dict[str, set] = {}
    for a in activities:
        if a.type == ActivityType.EXERCISE:
            by_c.setdefault(a.target_concept, set()).add(_class(a.difficulty))
    out = []
    for c, classes in sorted(by_c.items()):
        if len(classes) < 2:
            out.append(
                Issue(
                    "difficulty_spread",
                    "error",
                    f"concept {c} has exercises in only one difficulty class {sorted(classes)}",
                    "Add easier and harder items (d < 0.35 and d >= 0.65).",
                    c,
                )
            )
        elif "hard" not in classes:
            out.append(
                Issue(
                    "difficulty_spread",
                    "warning",
                    f"concept {c} has no hard item (needed for the verification probe, D50)",
                    "Add one item with difficulty >= 0.65.",
                    c,
                )
            )
    return out


def check_reading_length(content: dict) -> list[Issue]:
    out = []
    for aid, e in sorted(content.items()):
        if e["type"] == "LESSON":
            n = len(e["markdown"].split())
            if not LESSON_WORDS[0] <= n <= LESSON_WORDS[1]:
                out.append(
                    Issue(
                        "reading_length",
                        "warning",
                        f"lesson {aid} has {n} words (expected {LESSON_WORDS[0]}-{LESSON_WORDS[1]})",
                        "Aim for a 2-4 minute read.",
                        aid,
                    )
                )
        elif len(e["prompt"].split()) > PROMPT_WORDS:
            out.append(
                Issue(
                    "reading_length",
                    "warning",
                    f"question {aid} prompt is long ({len(e['prompt'].split())} words)",
                    "Shorten the stem.",
                    aid,
                )
            )
    return out


def validate_draft(draft_dir: str, name: str) -> ValidationReport:
    """Run the loaders (schema, DAG, difficulty ranges, content) and the authoring checks."""
    rep = ValidationReport()
    paths = {
        k: os.path.join(draft_dir, f"{k}_{name}.json")
        for k in ("curriculum", "activities", "content")
    }
    try:
        concepts = load_curriculum(paths["curriculum"], None, allow_unreviewed=True)
        CurriculumGraph.from_concepts(concepts)  # DAG check (cycles, unknown prerequisites)
        acts = load_activities(paths["activities"], concepts, None, allow_unreviewed=True)
        content = dict(load_content(paths["content"], acts))
    except (AdaptEngineError, OSError, KeyError, TypeError) as e:
        rep.issues.append(
            Issue("schema", "error", str(e), "Fix the file named in the message and re-validate.")
        )
        return rep
    rep.n_concepts, rep.n_activities = len(concepts), len(acts)
    rep.issues += check_duplicates(content)
    rep.issues += check_answer_position(content)
    rep.issues += check_difficulty_spread(acts)
    rep.issues += check_reading_length(content)
    return rep
