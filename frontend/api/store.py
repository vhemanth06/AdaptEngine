"""Per-session persistence: an engine snapshot (adaptengine.session) plus adapter metadata.

<sid>.snapshot.json holds learner state, execution log and base context (engine format);
<sid>.meta.json holds what only the UI needs (curriculum id, diagnostic answers, last plan).
"""

import json
import os
import re
import uuid
from pathlib import Path

from adaptengine.session import load_snapshot, save_snapshot

_SID = re.compile(r"^[0-9a-f]{32}$")


class SessionNotFound(KeyError):
    pass


def sessions_dir() -> Path:
    default = Path(__file__).resolve().parents[1] / ".sessions"
    return Path(os.environ.get("ADAPTENGINE_SESSIONS_DIR", default))


def new_id() -> str:
    return uuid.uuid4().hex


def _paths(sid: str) -> tuple[Path, Path]:
    if not _SID.match(sid):  # also blocks path traversal
        raise SessionNotFound(sid)
    d = sessions_dir()
    return d / f"{sid}.snapshot.json", d / f"{sid}.meta.json"


def save(sid, state, log, ctx, meta: dict) -> None:
    snap, meta_path = _paths(sid)
    save_snapshot(state, log, str(snap), context=ctx)
    tmp = meta_path.with_name(meta_path.name + ".tmp")
    tmp.write_text(json.dumps(meta), encoding="utf-8")
    os.replace(tmp, meta_path)


def load_meta(sid: str) -> dict:
    _, meta_path = _paths(sid)
    if not meta_path.exists():
        raise SessionNotFound(sid)
    return json.loads(meta_path.read_text(encoding="utf-8"))


def load_state(sid: str, concept_ids):
    snap, _ = _paths(sid)
    if not snap.exists():
        raise SessionNotFound(sid)
    return load_snapshot(str(snap), concept_ids, include_context=True)
