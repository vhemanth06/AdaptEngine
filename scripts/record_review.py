import argparse
import hashlib
import json
import os
from datetime import datetime, timezone

def hash_file(path: str) -> str:
    hasher = hashlib.sha256()
    with open(path, 'rb') as f:
        hasher.update(f.read())
    return hasher.hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--edges-reviewed", action="store_true")
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"File not found: {args.file}")
        exit(1)

    # Relative path from project root
    abs_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    abs_file = os.path.abspath(args.file)
    rel_path = os.path.relpath(abs_file, abs_root)

    manifest_path = os.path.join(abs_root, "data", "review_manifest.json")
    
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    else:
        manifest = {}

    entry = {
        "reviewer": args.reviewer,
        "date": datetime.now(timezone.utc).isoformat(),
        "sha256": hash_file(args.file),
        "source": args.source
    }
    
    if args.edges_reviewed:
        entry["edges_reviewed"] = True
        print("Note: You confirmed edges were reviewed.")
        
    manifest[rel_path] = entry

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
        
    print(f"Recorded review for {rel_path}")

if __name__ == "__main__":
    main()
