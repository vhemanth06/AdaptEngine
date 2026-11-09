"""Rebuild and verify data/external/ (WP7, T7.1).

as.csv and ct.csv come from the pyBKT-examples GitHub repo. The collapsed ASSISTments file
(assist09_skill_builder.csv) is a manual download from the ASSISTments data page; this script
only prints instructions for it and verifies its checksum when present.

Usage:
    python scripts/download_data.py                # download missing/bad files, then verify
    python scripts/download_data.py --verify-only  # no network; exit 1 on any mismatch/missing
"""

import argparse
import hashlib
import os
import sys
import urllib.request

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXTERNAL = os.path.join(REPO_ROOT, "data", "external")
CHECKSUMS = os.path.join(EXTERNAL, "CHECKSUMS")
PYBKT_BASE = "https://raw.githubusercontent.com/CAHLR/pyBKT-examples/master/data/"
URLS = {"as.csv": PYBKT_BASE + "as.csv", "ct.csv": PYBKT_BASE + "ct.csv"}
MANUAL = {
    "assist09_skill_builder.csv": (
        "Manual download (Google Drive, needs a browser):\n"
        "  1. Open https://sites.google.com/site/assistmentsdata/home/2009-2010-assistment-data/"
        "skill-builder-data-2009-2010\n"
        "  2. Follow the 'corrected version' link (one row per student-problem, collapsed skills):\n"
        "     https://drive.google.com/file/d/1NNXHFRxcArrU0ZJSb9BIL56vmUt5FhlE/view?usp=sharing\n"
        "  3. Save it as data/external/assist09_skill_builder.csv and re-run with --verify-only."
    )
}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_checksums(path: str = CHECKSUMS) -> dict[str, str]:
    """Parse `sha256sum` output: '<hex>  <name>' per line."""
    out = {}
    with open(path) as f:
        for line in f:
            if line.strip():
                digest, name = line.split(maxsplit=1)
                out[name.strip().lstrip("*")] = digest
    return out


def verify(name: str, expected: str, dest: str = EXTERNAL) -> str:
    path = os.path.join(dest, name)
    if not os.path.exists(path):
        return "missing"
    return "ok" if sha256(path) == expected else "mismatch"


def download(name: str, dest: str = EXTERNAL) -> None:
    os.makedirs(dest, exist_ok=True)
    tmp = os.path.join(dest, name + ".part")
    print(f"downloading {URLS[name]}")
    urllib.request.urlretrieve(URLS[name], tmp)
    os.replace(tmp, os.path.join(dest, name))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--verify-only", action="store_true", help="no network; just check hashes")
    ap.add_argument("--dest", default=EXTERNAL, help="target directory (default data/external)")
    args = ap.parse_args(argv)

    expected = read_checksums()
    bad = 0
    for name, digest in sorted(expected.items()):
        status = verify(name, digest, args.dest)
        if status != "ok" and not args.verify_only and name in URLS:
            download(name, args.dest)
            status = verify(name, digest, args.dest)
        if status != "ok" and name in MANUAL:
            print(MANUAL[name])
        print(f"{status:8s} {name} (expected sha256 {digest[:16]}...)")
        bad += status != "ok"
    print("all checksums OK" if not bad else f"{bad} file(s) missing or mismatched")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
