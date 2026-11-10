"""Human review gate (D7/D54): record a reviewed file in data/review_manifest.json.

W8 K.4: the reviewer must be a human name. Names that are empty, PENDING_*, or identify an AI or
model ("AI", "Claude", "GPT", "LLM", "model", "assistant", "bot", "stub", ...) are rejected.
`--promote-draft NAME` copies data/drafts/NAME/{curriculum,activities,content}_NAME.json into
data/curriculum and data/content and records all three (marked ai_assisted) under that reviewer.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
MANIFEST = os.path.join(ROOT, "data", "review_manifest.json")
_AI_NAME = re.compile(
    r"(^|[^a-z])(ai|claude|gpt|llm|model|assistant|bot|stub|ollama|llama|agent|anthropic|openai)([^a-z]|$)",
    re.IGNORECASE,
)


class ReviewRejected(ValueError):
    pass


def hash_file(path: str) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()


def check_reviewer(name) -> str:
    """Return the cleaned human reviewer name or raise ReviewRejected."""
    if not isinstance(name, str) or not name.strip():
        raise ReviewRejected("a human reviewer name is required")
    name = name.strip()
    if name.upper().startswith("PENDING") or _AI_NAME.search(name):
        raise ReviewRejected(
            f"reviewer {name!r} is not accepted: the review must be by a named human"
        )
    return name


def record(
    path, reviewer, source, edges_reviewed=False, ai_assisted=False, root=ROOT, manifest=None
):
    reviewer = check_reviewer(reviewer)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    manifest = manifest or os.path.join(root, "data", "review_manifest.json")
    rel_path = os.path.relpath(os.path.abspath(path), root)
    data = {}
    if os.path.exists(manifest):
        with open(manifest, "r", encoding="utf-8") as f:
            data = json.load(f)
    entry = {
        "reviewer": reviewer,
        "date": datetime.now(timezone.utc).isoformat(),
        "sha256": hash_file(path),
        "source": source,
    }
    if ai_assisted:
        entry["ai_assisted"] = True
    if edges_reviewed:
        entry["edges_reviewed"] = True
    data[rel_path] = entry
    with open(manifest, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    return rel_path


def promote_draft(name, reviewer, root=ROOT, manifest=None, overwrite=False):
    """Copy an approved draft into the live data folders and record the human review."""
    reviewer = check_reviewer(reviewer)
    src = os.path.join(root, "data", "drafts", name)
    targets = {
        f"curriculum_{name}.json": os.path.join(root, "data", "curriculum"),
        f"activities_{name}.json": os.path.join(root, "data", "curriculum"),
        f"content_{name}.json": os.path.join(root, "data", "content"),
    }
    for fname, dst_dir in targets.items():
        dst = os.path.join(dst_dir, fname)
        if os.path.exists(dst) and not overwrite:
            raise ReviewRejected(f"{os.path.relpath(dst, root)} already exists")
        if not os.path.isfile(os.path.join(src, fname)):
            raise FileNotFoundError(os.path.join(src, fname))
    recorded = []
    for fname, dst_dir in targets.items():
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, fname)
        shutil.copyfile(os.path.join(src, fname), dst)
        recorded.append(
            record(
                dst,
                reviewer,
                f"AI-assisted draft {name}, reviewed by a human",
                edges_reviewed=fname.startswith("curriculum_"),
                ai_assisted=True,
                root=root,
                manifest=manifest,
            )
        )
    return recorded


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("file", nargs="?")
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--source", default="hand-written")
    parser.add_argument("--edges-reviewed", action="store_true")
    parser.add_argument("--ai-assisted", action="store_true")
    parser.add_argument("--promote-draft", metavar="NAME")
    args = parser.parse_args(argv)
    try:
        if args.promote_draft:
            for p in promote_draft(args.promote_draft, args.reviewer):
                print(f"Recorded review for {p}")
            return 0
        if not args.file:
            parser.error("file is required unless --promote-draft is given")
        rel = record(args.file, args.reviewer, args.source, args.edges_reviewed, args.ai_assisted)
    except (ReviewRejected, FileNotFoundError) as e:
        print(f"Rejected: {e}")
        return 1
    if args.edges_reviewed:
        print("Note: You confirmed edges were reviewed.")
    print(f"Recorded review for {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
