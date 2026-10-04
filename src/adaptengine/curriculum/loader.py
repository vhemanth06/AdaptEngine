import json
from ..core.errors import ValidationError, DuplicateIdError, UnknownConceptError, UnreviewedContentError, AdaptEngineError
from ..core.schema import Concept, Activity, ActivityType
import os
import hashlib

def _check_review_gate(path: str, manifest_path: str = None):
    abs_path = os.path.abspath(path)
    if manifest_path is None:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        manifest_path = os.path.join(repo_root, "data", "review_manifest.json")
    else:
        repo_root = os.path.dirname(os.path.abspath(manifest_path))

    rel_path = os.path.relpath(abs_path, repo_root)

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        raise UnreviewedContentError(f"File {path}: Cannot read manifest: {e}")

    if rel_path not in manifest:
        raise UnreviewedContentError(f"File {path}: No entry in manifest for {rel_path}")

    entry = manifest[rel_path]
    if not entry.get("reviewer") or not entry.get("date"):
        raise UnreviewedContentError(f"File {path}: Missing reviewer or date in manifest")

    if "curriculum" in rel_path and "activities" not in rel_path:
        if not entry.get("edges_reviewed"):
            raise UnreviewedContentError(f"File {path}: edges_reviewed not true")

    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        hasher.update(f.read())
    file_hash = hasher.hexdigest()

    if file_hash != entry.get("sha256"):
        raise UnreviewedContentError(f"File {path}: Hash mismatch. File edited after review.")

def load_curriculum(path, manifest_path=None, *, allow_unreviewed=False) -> tuple[Concept, ...]:
    if not allow_unreviewed:
        _check_review_gate(path, manifest_path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValidationError(f"File {path}: failed to parse json: {e}")
        
    if data.get("schema_version") != 1:
        raise ValidationError(f"File {path}: invalid schema_version")
        
    concepts = []
    seen_ids = set()
    
    try:
        for c_data in data.get("concepts", []):
            cid = c_data["concept_id"]
            if cid in seen_ids:
                raise DuplicateIdError(f"Duplicate concept_id {cid} in {path}")
            seen_ids.add(cid)
            try:
                concepts.append(Concept(
                    concept_id=cid,
                    prerequisites=tuple(c_data.get("prerequisites", [])),
                    description=c_data.get("description", "")
                ))
            except AdaptEngineError as e:
                raise e.__class__(f"File {path}: {e}")
    except KeyError as e:
        raise ValidationError(f"File {path}: missing key {e}")
        
    return tuple(concepts)

def load_activities(path, concepts, manifest_path=None, *, allow_unreviewed=False) -> tuple[Activity, ...]:
    if not allow_unreviewed:
        _check_review_gate(path, manifest_path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValidationError(f"File {path}: failed to parse json: {e}")
        
    if data.get("schema_version") != 1:
        raise ValidationError(f"File {path}: invalid schema_version")
        
    valid_concept_ids = {c.concept_id for c in concepts}
    activities = []
    seen_ids = set()
    
    try:
        for a_data in data.get("activities", []):
            aid = a_data["activity_id"]
            if aid in seen_ids:
                raise DuplicateIdError(f"Duplicate activity_id {aid} in {path}")
            seen_ids.add(aid)
            
            target = a_data["target_concept"]
            if target not in valid_concept_ids:
                raise UnknownConceptError(f"Activity {aid} targets unknown concept {target} in {path}")
                
            try:
                atype = ActivityType(a_data["type"])
            except ValueError:
                raise ValidationError(f"File {path}: unknown type {a_data['type']}")
                
            try:
                activities.append(Activity(
                    activity_id=aid,
                    type=atype,
                    target_concept=target,
                    duration=a_data["duration"],
                    difficulty=a_data.get("difficulty"),
                    text=a_data.get("text", "")
                ))
            except AdaptEngineError as e:
                raise e.__class__(f"File {path}: {e}")
    except KeyError as e:
        raise ValidationError(f"File {path}: missing key {e}")
        
    return tuple(activities)
