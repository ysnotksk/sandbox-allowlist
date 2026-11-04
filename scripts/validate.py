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
from policy import check_domain, source_domains

ROOT = Path(__file__).resolve().parent.parent
FIELDS = {"domain", "category", "purpose", "needed_by", "evidence", "added", "status"}
STATUSES = {"active", "candidate", "retired"}


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
        try:
            check_domain(d)
        except ValueError as exc:
            fail(str(exc))
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
    exclusions = json.loads((ROOT / "policy.json").read_text())["excluded_domains"]
    if any(not isinstance(reason, str) or not reason.strip() for reason in exclusions.values()):
        fail("each exclusion needs a review reason")
    try:
        upstream = source_domains(data, exclusions)
    except ValueError as exc:
        fail(str(exc))
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
    expected_profiles = set(json.loads((ROOT / "profiles.json").read_text())["profiles"])
    actual_profiles = {p.name for p in (ROOT / "generated").iterdir()}
    if expected_profiles != actual_profiles:
        fail("generated profiles contain missing or unexpected entries")
    for name in expected_profiles:
        expected_files = {"domains.txt", "claude-code.settings.json", "srt-settings.json", "codex.config.toml", "MANIFEST.json"}
        if {p.name for p in (ROOT / "generated" / name).iterdir()} != expected_files:
            fail(f"generated/{name}: unexpected or missing file")
        for domain in (ROOT / "generated" / name / "domains.txt").read_text().splitlines():
            try:
                check_domain(domain)
            except ValueError as exc:
                fail(str(exc))
            if domain in exclusions:
                fail(f"{name}: excluded domain {domain}")
    print(f"validate: ok ({len(overlay)} overlay entries)")


if __name__ == "__main__":
    main()
