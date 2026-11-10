#!/usr/bin/env python3
"""W8 H.1: one-command demo. Checks the environment, rebuilds frontend/web/dist when any file
in frontend/web/src is newer than dist/index.html, then starts uvicorn and prints the URL.

  python scripts/demo.py [--port 8000] [--no-build]
"""

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WEB = REPO / "frontend" / "web"


def fail(msg: str) -> None:
    print(f"demo: {msg}", file=sys.stderr)
    sys.exit(1)


def stale() -> bool:
    index = WEB / "dist" / "index.html"
    if not index.exists():
        return True
    newest = max((p.stat().st_mtime for p in (WEB / "src").rglob("*") if p.is_file()), default=0)
    return newest > index.stat().st_mtime


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-build", action="store_true")
    a = ap.parse_args()
    for mod in ("fastapi", "uvicorn"):
        if importlib.util.find_spec(mod) is None:
            fail(f"{mod} is missing: pip install -e '.[demo]'")
    if not (REPO / "data" / "curriculum" / "curriculum_8node.json").exists():
        fail("run from a full checkout (data/curriculum is missing)")
    if not a.no_build and stale():
        if shutil.which("npm") is None:
            fail("frontend/web/dist is missing or stale and npm is not installed")
        if not (WEB / "node_modules").exists():
            print("demo: installing web dependencies (npm ci)...")
            subprocess.run(["npm", "ci"], cwd=WEB, check=True)
        print("demo: building the web app (src is newer than dist)...")
        subprocess.run(["npm", "run", "build"], cwd=WEB, check=True)
    url = f"http://127.0.0.1:{a.port}/"
    print(f"demo: AdaptEngine demo at {url}  (API health: {url}api/health; Ctrl+C to stop)")
    os.chdir(REPO)
    os.execv(
        sys.executable,
        [sys.executable, "-m", "uvicorn", "frontend.api.app:app", "--port", str(a.port)],
    )


if __name__ == "__main__":
    main()
