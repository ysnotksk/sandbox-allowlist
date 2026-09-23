#!/usr/bin/env python3
"""Check overlay.json and profiles.json, and that generated/ matches a fresh build.

Exit 1 on the first class of problem found. Standard library only.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import filecmp
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOMAIN = re.compile(r"^(\*\.)?([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")
FIELDS = {"domain", "category", "purpose", "needed_by", "evidence", "added", "status"}
STATUSES = {"active", "candidate", "retired"}
PRIVATE = re.compile(r"(^|\.)(localhost|local|internal|corp|lan|home|test|example)$|^\d+\.\d+\.\d+\.\d+$")


def fail(msg):
    print(f"validate: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    overlay = json.loads((ROOT / "overlay.json").read_text(encoding="utf-8"))["domains"]
    seen = set()
    for e in overlay:
        missing = FIELDS - set(e)
        if missing:
            fail(f"{e.get('domain')}: missing fields {sorted(missing)}")
        d = e["domain"]
        if not DOMAIN.match(d):
            fail(f"{d}: not a bare host name (no scheme, path, port, or uppercase)")
        if d == "*" or d.startswith("*.") and d.count(".") < 2:
            fail(f"{d}: wildcard too broad")
        if PRIVATE.search(d):
            fail(f"{d}: looks private or local; this list is public")
        if d in seen:
            fail(f"{d}: duplicate")
        seen.add(d)
        if e["status"] not in STATUSES:
            fail(f"{d}: status must be one of {sorted(STATUSES)}")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", e["added"]):
            fail(f"{d}: added must be YYYY-MM-DD")
        if not e["evidence"].strip():
            fail(f"{d}: evidence is empty")

    data = json.loads((ROOT / "upstream" / "gh-aw" / "ecosystem_domains.json").read_text(encoding="utf-8"))
    upstream = {x for v in data["ecosystems"].values() for x in v} | {x for v in data["engine-defaults"].values() for x in v}
    dup = seen & upstream
    if dup:
        fail(f"already in upstream gh-aw, drop from overlay: {sorted(dup)}")

    # generated/ must equal a fresh build
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "build.py")], check=True,
                       cwd=ROOT, env={**os.environ, "SANDBOX_ALLOWLIST_OUT": tmp}, capture_output=True)
        for prof in sorted(Path(tmp).iterdir()):
            for f in sorted(prof.iterdir()):
                have = ROOT / "generated" / prof.name / f.name
                if not have.exists() or not filecmp.cmp(f, have, shallow=False):
                    fail(f"generated/{prof.name}/{f.name} is stale; run python3 scripts/build.py")
    print(f"validate: ok ({len(overlay)} overlay entries)")


if __name__ == "__main__":
    main()
