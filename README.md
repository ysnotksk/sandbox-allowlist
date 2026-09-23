# sandbox-allowlist

Egress allowlists for AI coding agents that run commands in a network sandbox
(Claude Code's sandboxed Bash, Anthropic's `sandbox-runtime`, Codex CLI).
One source of truth, rendered into each tool's format.

Vendors each publish their own list in their own shape: Claude Code web has
about 200 trusted domains as a docs page, Codex cloud has 69 preset apex
domains, GitHub Copilot has a Markdown reference, and
[github/gh-aw](https://github.com/github/gh-aw) ships a machine-readable
ecosystem-to-domain map. Nothing crosses vendors. This repository does:

- **upstream/gh-aw/** — the gh-aw ecosystem map, copied verbatim with its commit
  recorded in `SOURCE.json`. 42 ecosystems (`node`, `python`, `swift`, `containers`,
  `dev-tools`, ...) plus per-engine defaults for `claude`, `codex`, `copilot`.
  Refresh with `scripts/sync-upstream.sh`.
- **overlay.json** — domains the upstream map does not have: SaaS APIs, cloud
  deploy targets, model hubs, Japanese public-sector APIs. Every entry says why it
  is here (`purpose`, `evidence`) and whether it has been confirmed
  (`status`: `active` / `candidate` / `retired`).
- **profiles.json** — which ecosystems, engines and overlay statuses make up one
  list. `base`, `node`, `python`, `swift`, `workstation`.
- **generated/<profile>/** — the rendered lists, committed so they can be consumed
  by URL:
  - `domains.txt` — one per line
  - `claude-code.settings.json` — `sandbox.network.allowedDomains`, to merge into `~/.claude/settings.json`
  - `srt-settings.json` — `~/.srt-settings.json` for sandbox-runtime
  - `codex.config.toml` — `[network] allowed_domains` (check the key names against the current Codex docs before use)
  - `MANIFEST.json` — what went in

## Use

```sh
# Claude Code: merge a profile into your user settings (strict mode reads user or
# managed settings only; a repository's .claude/settings.json is not enough)
jq -s '.[0] * .[1]' ~/.claude/settings.json generated/node/claude-code.settings.json > /tmp/s && mv /tmp/s ~/.claude/settings.json

# sandbox-runtime
cp generated/node/srt-settings.json ~/.srt-settings.json
```

## Add a domain

1. Add one object to `overlay.json`. Use `status: candidate` until a sandbox has
   actually blocked it; write what was blocked in `evidence`.
2. `python3 scripts/build.py`, then `python3 scripts/validate.py`.
3. Open a pull request. CI runs the validator: bare host names only, no broad
   wildcards, no private or local hosts, nothing already in upstream, and
   `generated/` must match a fresh build.

Not accepted: internal or personal hosts, URLs carrying tokens, `*` or
`*.tld` wildcards. This is a public list of public endpoints.

## Layout of the data

```json
{"domain": "api.notion.com", "category": "saas-api", "purpose": "Notion API",
 "needed_by": ["notion"], "evidence": "inferred from project stack",
 "added": "2026-09-24", "status": "candidate"}
```

## License

MIT. `upstream/gh-aw/` is MIT from GitHub, Inc. (see the LICENSE there).
