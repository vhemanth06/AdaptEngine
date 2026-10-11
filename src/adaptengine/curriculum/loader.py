import json
import os
import hashlib
from ..core.errors import (
    ValidationError,
    DuplicateIdError,
    UnknownConceptError,
    UnreviewedContentError,
    AdaptEngineError,
)
from ..core.schema import Concept, Activity, ActivityType
from ..core.config import EngineConfig, DEFAULT_CONFIG


def _check_review_gate(path: str, manifest_path: str = None, *, is_curriculum: bool = False):
    abs_path = os.path.abspath(path)
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

    if manifest_path is None:
        manifest_path = os.path.join(repo_root, "data", "review_manifest.json")
    else:
        manifest_path = os.path.abspath(manifest_path)

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        raise UnreviewedContentError(f"File {path}: Cannot read manifest: {e}")

    rel_repo = os.path.relpath(abs_path, repo_root).replace("\\", "/")
    manifest_dir = os.path.dirname(manifest_path)
    rel_manifest = os.path.relpath(abs_path, manifest_dir).replace("\\", "/")

    entry = None
    if rel_repo in manifest:
        entry = manifest[rel_repo]
    elif rel_manifest in manifest:
        entry = manifest[rel_manifest]
    else:
        raise UnreviewedContentError(f"File {path}: No entry in manifest for {rel_repo}")

    reviewer = entry.get("reviewer")
    date_val = entry.get("date")
    if not reviewer or not date_val:
        raise UnreviewedContentError(f"File {path}: Missing reviewer or date in manifest")

    if isinstance(reviewer, str) and reviewer.strip().upper() == "AI":
        raise UnreviewedContentError(
            f"File {path}: Reviewer cannot be 'AI'. Named human review required for live content."
        )

    if is_curriculum:
        if entry.get("edges_reviewed") is not True:
            raise UnreviewedContentError(f"File {path}: edges_reviewed not true")

    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        hasher.update(f.read())
    file_hash = hasher.hexdigest()

    if file_hash != entry.get("sha256"):
        raise UnreviewedContentError(f"File {path}: Hash mismatch. File edited after review.")


def load_curriculum(path, manifest_path=None, *, allow_unreviewed=False) -> tuple[Concept, ...]:
    if not allow_unreviewed:
        _check_review_gate(path, manifest_path, is_curriculum=True)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValidationError(f"File {path}: failed to parse json: {e}")

    if not isinstance(data, dict):
        raise ValidationError(f"File {path}: root must be a JSON object")

    if data.get("schema_version") != 1:
        raise ValidationError(f"File {path}: invalid schema_version")

    raw_concepts = data.get("concepts")
    if not isinstance(raw_concepts, list):
        raise ValidationError(f"File {path}: 'concepts' must be a list")

    # Collect declared concept IDs first to validate prerequisites
    declared_ids = set()
    for c_data in raw_concepts:
        if not isinstance(c_data, dict):
            raise ValidationError(f"File {path}: each concept must be a JSON object")
        cid = c_data.get("concept_id")
        if not isinstance(cid, str) or not cid.strip() or any(c.isspace() for c in cid):
            raise ValidationError(f"File {path}: invalid concept_id: {cid!r}")
        if cid in declared_ids:
            raise DuplicateIdError(f"Duplicate concept_id {cid} in {path}")
        declared_ids.add(cid)

    # Now validate prerequisites and construct Concept objects
    concepts = []
    for c_data in raw_concepts:
        cid = c_data["concept_id"]
        prereqs = c_data.get("prerequisites", [])
        if not isinstance(prereqs, list):
            raise ValidationError(f"File {path}: prerequisites for {cid} must be a list")
        for p in prereqs:
            if not isinstance(p, str) or not p.strip() or any(c.isspace() for c in p):
                raise ValidationError(f"File {path}: invalid prerequisite {p!r} in {cid}")
            if p not in declared_ids:
                raise UnknownConceptError(f"Concept {cid} has unknown prerequisite {p} in {path}")

        try:
            concepts.append(
                Concept(
                    concept_id=cid,
                    prerequisites=tuple(prereqs),
                    description=c_data.get("description", ""),
                )
            )
        except AdaptEngineError as e:
            raise e.__class__(f"File {path}: {e}")

    return tuple(concepts)


def load_activities(
    path,
    concepts,
    manifest_path=None,
    *,
    allow_unreviewed=False,
    cfg: EngineConfig = DEFAULT_CONFIG,
) -> tuple[Activity, ...]:
    if not allow_unreviewed:
        _check_review_gate(path, manifest_path, is_curriculum=False)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValidationError(f"File {path}: failed to parse json: {e}")

    if not isinstance(data, dict):
        raise ValidationError(f"File {path}: root must be a JSON object")

    if data.get("schema_version") != 1:
        raise ValidationError(f"File {path}: invalid schema_version")

    raw_activities = data.get("activities")
    if not isinstance(raw_activities, list):
        raise ValidationError(f"File {path}: 'activities' must be a list")

    valid_concept_ids = {c.concept_id for c in concepts}
    activities = []
    seen_ids = set()

    for a_data in raw_activities:
        if not isinstance(a_data, dict):
            raise ValidationError(f"File {path}: each activity must be a JSON object")
        aid = a_data.get("activity_id")
        if not isinstance(aid, str) or not aid.strip() or any(c.isspace() for c in aid):
            raise ValidationError(f"File {path}: invalid activity_id: {aid!r}")
        if aid in seen_ids:
            raise DuplicateIdError(f"Duplicate activity_id {aid} in {path}")
        seen_ids.add(aid)

        target = a_data.get("target_concept")
        if target not in valid_concept_ids:
            raise UnknownConceptError(f"Activity {aid} targets unknown concept {target} in {path}")

        raw_type = a_data.get("type")
        try:
            atype = ActivityType(raw_type)
        except (ValueError, TypeError):
            raise ValidationError(f"File {path}: unknown type {raw_type}")

        duration = a_data.get("duration")
        if type(duration) is not int or duration < 1:
            raise ValidationError(f"File {path}: invalid duration: {duration}")

        try:
            activities.append(
                Activity(
                    activity_id=aid,
                    type=atype,
                    target_concept=target,
                    duration=duration,
                    difficulty=a_data.get("difficulty"),
                    text=a_data.get("text", ""),
                    d_min=cfg.d_min,
                    d_max=cfg.d_max,
                )
            )
        except AdaptEngineError as e:
            raise e.__class__(f"File {path}: {e}")

    return tuple(activities)
