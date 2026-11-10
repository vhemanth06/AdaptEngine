"""A0 Authoring Aid draft generation (W8 K.2, D54).

A provider drafts a mini-curriculum as one JSON object
  {"concepts": [{concept_id, description, prerequisites}],
   "activities": [{activity_id, type, target_concept, duration, difficulty?}],
   "content": {activity_id: {type, target_concept, title/markdown | prompt/options/correct/explanation}}}
which is split into the three existing schemas and written ONLY to data/drafts/<name>/ with
draft_meta.json (ai_assisted: true, reviewer: "PENDING_HUMAN_REVIEW", provider, model, prompt
hash, timestamp). If the loaders reject the draft, the provider is asked again with the error
(at most MAX_RETRIES times). Promotion to data/curriculum needs a named human reviewer
(scripts/record_review.py); this module never writes there.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from .checks import ValidationReport, validate_draft

MAX_RETRIES = 2
PENDING = "PENDING_HUMAN_REVIEW"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,40}$")
DIFFICULTIES = (0.2, 0.4, 0.6, 0.8)

PROMPT = """Draft a short beginner curriculum for: {topic}.
Use exactly {n_concepts} concepts with ids K1..K{n_concepts} forming a prerequisite DAG (no cycles).
For every concept write one lesson (id L-Kx, 3-5 minutes, markdown of 80-300 words) and
{n_items} multiple-choice exercises (ids E-Kx-<difficulty>) with difficulties spread from easy to hard
({difficulties}), each with exactly 4 distinct options, the index of the correct option (vary it),
and a one-sentence explanation.
Return ONE JSON object with keys "concepts", "activities" and "content" in this shape:
{{"concepts": [{{"concept_id": "K1", "description": "...", "prerequisites": []}}],
 "activities": [{{"activity_id": "L-K1", "type": "LESSON", "target_concept": "K1", "duration": 4}},
                {{"activity_id": "E-K1-0.2", "type": "EXERCISE", "target_concept": "K1", "duration": 1, "difficulty": 0.2}}],
 "content": {{"L-K1": {{"type": "LESSON", "target_concept": "K1", "title": "...", "markdown": "..."}},
             "E-K1-0.2": {{"type": "EXERCISE", "target_concept": "K1", "prompt": "...", "options": ["a","b","c","d"], "correct": 2, "explanation": "..."}}}}}}
"""


def template_draft(payload: dict) -> dict:
    """Deterministic offline draft used by the stub provider (tests, CI, demo)."""
    topic = payload.get("topic", "a topic")
    n = int(payload.get("n_concepts", 3))
    concepts, acts, content = [], [], {}
    for i in range(1, n + 1):
        cid = f"K{i}"
        pre = [f"K{i - 1}"] if i > 1 else []
        desc = f"{topic}: part {i}"
        concepts.append({"concept_id": cid, "description": desc, "prerequisites": pre})
        acts.append(
            {"activity_id": f"L-{cid}", "type": "LESSON", "target_concept": cid, "duration": 4}
        )
        body = " ".join(
            f"Step {k} of {desc.lower()} explains one idea with a short worked example."
            for k in range(1, 9)
        )
        content[f"L-{cid}"] = {
            "type": "LESSON",
            "target_concept": cid,
            "title": desc,
            "markdown": body,
        }
        for j, d in enumerate(DIFFICULTIES):
            aid = f"E-{cid}-{d}"
            acts.append(
                {
                    "activity_id": aid,
                    "type": "EXERCISE",
                    "target_concept": cid,
                    "duration": 1 + (d > 0.5),
                    "difficulty": d,
                }
            )
            correct = (i + j) % 4
            opts = [f"Option {chr(65 + k)} for item {aid}" for k in range(4)]
            content[aid] = {
                "type": "EXERCISE",
                "target_concept": cid,
                "prompt": f"({topic}, part {i}) Question {j + 1} at difficulty {d}: which statement is right?",
                "options": opts,
                "correct": correct,
                "explanation": f"Option {chr(65 + correct)} is the statement the lesson showed.",
            }
    return {"concepts": concepts, "activities": acts, "content": content}


def _split_and_write(obj: Any, out_dir: str, name: str, meta: dict) -> None:
    if not isinstance(obj, dict) or not {"concepts", "activities", "content"} <= set(obj):
        raise ValueError("draft must be an object with concepts, activities and content")
    os.makedirs(out_dir, exist_ok=True)
    files = {
        f"curriculum_{name}.json": {"schema_version": 1, "concepts": obj["concepts"]},
        f"activities_{name}.json": {"schema_version": 1, "activities": obj["activities"]},
        f"content_{name}.json": {
            "schema_version": 1,
            "curriculum": f"data/curriculum/curriculum_{name}.json",
            "activities_file": f"data/curriculum/activities_{name}.json",
            "activities": obj["content"],
        },
        "draft_meta.json": meta,
    }
    for fname, data in files.items():
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")


def generate_draft(
    provider, *, name: str, topic: str, n_concepts: int = 3, drafts_root: str
) -> dict:
    """Draft -> data/drafts/<name>/ -> validate; on loader errors re-ask (max MAX_RETRIES)."""
    if not NAME_RE.match(name):
        raise ValueError("draft name must be lowercase letters, digits or _ (max 41 chars)")
    out_dir = os.path.join(drafts_root, name)  # NAME_RE keeps it inside drafts_root
    payload = {"topic": topic, "n_concepts": n_concepts, "name": name}
    prompt = PROMPT.format(
        topic=topic,
        n_concepts=n_concepts,
        n_items=len(DIFFICULTIES),
        difficulties=", ".join(map(str, DIFFICULTIES)),
    )
    attempts = []
    report = ValidationReport()
    for attempt in range(MAX_RETRIES + 1):
        meta = {
            "name": name,
            "topic": topic,
            "ai_assisted": True,
            "reviewer": PENDING,
            "provider": getattr(provider, "name", "?"),
            "model": getattr(provider, "model", "?"),
            "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "attempt": attempt + 1,
        }
        text = provider.complete(prompt, task="draft", payload=payload)
        try:
            _split_and_write(json.loads(text), out_dir, name, meta)
            report = validate_draft(out_dir, name)
            schema_errors = [i for i in report.issues if i.check == "schema"]
        except ValueError as e:  # malformed JSON or wrong top-level shape
            schema_errors = [str(e)]
        attempts.append(
            {
                "attempt": attempt + 1,
                "schema_errors": [str(getattr(x, "message", x)) for x in schema_errors],
            }
        )
        if not schema_errors:
            break
        prompt += f"\n\nYour previous answer was rejected by the validator: {attempts[-1]['schema_errors'][0]}\nReturn a corrected JSON object."
    return {
        "name": name,
        "dir": out_dir,
        "attempts": attempts,
        "first_pass_valid": not attempts[0]["schema_errors"],
        "report": report.to_dict(),
    }
