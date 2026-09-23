#!/bin/bash
# Refresh upstream/gh-aw/ from github/gh-aw main, record the commit, rebuild.
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEST=$ROOT/upstream/gh-aw
commit=$(curl -sf https://api.github.com/repos/github/gh-aw/commits/main | python3 -c 'import json,sys; print(json.load(sys.stdin)["sha"])')
curl -sfL "https://raw.githubusercontent.com/github/gh-aw/$commit/pkg/workflow/data/ecosystem_domains.json" -o "$DEST/ecosystem_domains.json"
curl -sfL "https://raw.githubusercontent.com/github/gh-aw/$commit/LICENSE" -o "$DEST/LICENSE"
python3 - "$DEST/SOURCE.json" "$commit" <<'PY'
import json, sys, datetime
p, commit = sys.argv[1], sys.argv[2]
src = json.load(open(p))
src["commit"] = commit
src["fetched"] = datetime.date.today().isoformat()
json.dump(src, open(p, "w"), indent=2)
open(p, "a").write("\n")
PY
python3 "$ROOT/scripts/build.py"
echo "upstream at $commit"
