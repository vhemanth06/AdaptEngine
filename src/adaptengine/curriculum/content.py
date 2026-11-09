"""Load and validate learner-facing content (lesson markdown, multiple-choice questions).

Content is display-only: the engine never reads it. Schema: data/content/README.md.
"""

import json
from collections.abc import Iterable, Mapping

from ..core.errors import ValidationError
from ..core.schema import Activity, ActivityType


def _nonempty_str(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def load_content(path, activities: Iterable[Activity]) -> Mapping[str, dict]:
    """Return {activity_id: entry}; raise ValidationError unless the file exactly covers `activities`."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValidationError(f"File {path}: failed to parse json: {e}")

    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValidationError(f"File {path}: root must be an object with schema_version 1")
    entries = data.get("activities")
    if not isinstance(entries, dict):
        raise ValidationError(f"File {path}: 'activities' must be an object keyed by activity_id")

    catalogue = {a.activity_id: a for a in activities}
    missing = sorted(catalogue.keys() - entries.keys())
    unknown = sorted(entries.keys() - catalogue.keys())
    if missing or unknown:
        raise ValidationError(f"File {path}: missing ids {missing}, unknown ids {unknown}")

    for aid, entry in entries.items():
        act = catalogue[aid]
        where = f"File {path}: activity {aid}"
        if not isinstance(entry, dict):
            raise ValidationError(f"{where}: entry must be an object")
        if entry.get("type") != act.type.value:
            raise ValidationError(f"{where}: type {entry.get('type')!r} != {act.type.value!r}")
        if entry.get("target_concept") != act.target_concept:
            raise ValidationError(
                f"{where}: target_concept {entry.get('target_concept')!r} != {act.target_concept!r}"
            )
        if act.type == ActivityType.LESSON:
            if not _nonempty_str(entry.get("markdown")):
                raise ValidationError(f"{where}: lesson needs non-empty 'markdown'")
            continue
        options = entry.get("options")
        if not _nonempty_str(entry.get("prompt")):
            raise ValidationError(f"{where}: exercise needs non-empty 'prompt'")
        if (
            not isinstance(options, list)
            or len(options) != 4
            or not all(_nonempty_str(o) for o in options)
            or len({o.strip() for o in options}) != 4
        ):
            raise ValidationError(f"{where}: exercise needs exactly 4 non-empty unique options")
        correct = entry.get("correct")
        if type(correct) is not int or not 0 <= correct <= 3:
            raise ValidationError(f"{where}: 'correct' must be an int in 0..3")
        if not _nonempty_str(entry.get("explanation")):
            raise ValidationError(f"{where}: exercise needs non-empty 'explanation'")

    return entries
