#!/usr/bin/env python3
"""Render every profile in profiles.json into generated/<profile>/.

Inputs (all in the repository root):
  upstream/gh-aw/ecosystem_domains.json  ecosystems and engine-defaults (copied from github/gh-aw)
  overlay.json                           this repository's own domains, each with status
  profiles.json                          which ecosystems / engines / overlay statuses each profile takes

Outputs per profile:
  domains.txt                 one domain per line, sorted (Squid, proxies, diffing)
  claude-code.settings.json   {"sandbox": {"network": {"allowedDomains": [...]}}} - merge into ~/.claude/settings.json
  srt-settings.json           {"network": {"allowedDomains": [...]}}            - ~/.srt-settings.json for sandbox-runtime
  codex.config.toml           [network] allowed_domains = [...]                  - append to ~/.codex/config.toml (verify key names against current Codex docs)
  MANIFEST.json               what went in: ecosystems, engines, overlay entries, upstream commit

Standard library only. Run from anywhere: python3 scripts/build.py
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = ROOT / "upstream" / "gh-aw"


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve(profiles, name, seen=()):
    """Flatten `extends` chains. A child adds to its parent's lists; overlay_statuses is replaced if given."""
    if name in seen:
        sys.exit(f"profiles.json: cycle at {name}")
    p = profiles[name]
    if "extends" in p:
        base = resolve(profiles, p["extends"], seen + (name,))
        return {
            "ecosystems": base["ecosystems"] + p.get("ecosystems", []),
            "engines": base["engines"] + p.get("engines", []),
            "overlay_statuses": p.get("overlay_statuses", base["overlay_statuses"]),
        }
    return {
        "ecosystems": list(p.get("ecosystems", [])),
        "engines": list(p.get("engines", [])),
        "overlay_statuses": list(p.get("overlay_statuses", [])),
    }


def main():
    data = load(UPSTREAM / "ecosystem_domains.json")
    source = load(UPSTREAM / "SOURCE.json")
    overlay = load(ROOT / "overlay.json")["domains"]
    profiles = load(ROOT / "profiles.json")["profiles"]

    for name in profiles:
        r = resolve(profiles, name)
        domains = set()
        for eco in r["ecosystems"]:
            if eco not in data["ecosystems"]:
                sys.exit(f"profile {name}: unknown ecosystem {eco!r}")
            domains.update(data["ecosystems"][eco])
        for eng in r["engines"]:
            if eng not in data["engine-defaults"]:
                sys.exit(f"profile {name}: unknown engine {eng!r}")
            domains.update(data["engine-defaults"][eng])
        used_overlay = [d for d in overlay if d["status"] in r["overlay_statuses"]]
        domains.update(d["domain"] for d in used_overlay)
        ordered = sorted(domains, key=lambda s: s.lstrip("*."))

        out = Path(os.environ.get("SANDBOX_ALLOWLIST_OUT", ROOT / "generated")) / name
        out.mkdir(parents=True, exist_ok=True)
        (out / "domains.txt").write_text("\n".join(ordered) + "\n", encoding="utf-8")
        (out / "claude-code.settings.json").write_text(
            json.dumps({"sandbox": {"network": {"allowedDomains": ordered}}}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        (out / "srt-settings.json").write_text(
            json.dumps({"network": {"allowedDomains": ordered}}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        toml = "[network]\nallowed_domains = [\n" + "".join(f'  "{d}",\n' for d in ordered) + "]\n"
        (out / "codex.config.toml").write_text(toml, encoding="utf-8")
        (out / "MANIFEST.json").write_text(json.dumps({
            "profile": name,
            "description": profiles[name].get("description", ""),
            "ecosystems": sorted(set(r["ecosystems"])),
            "engines": sorted(set(r["engines"])),
            "overlay": [d["domain"] for d in used_overlay],
            "count": len(ordered),
            "upstream": source,
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{name:12s} {len(ordered):4d} domains")


if __name__ == "__main__":
    main()
