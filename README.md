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
  - `codex.config.toml` — `features.network_proxy.domains` rules for sandboxed Codex commands
  - `MANIFEST.json` — what went in

## Use

```sh
# Claude Code: merge a profile into your user settings (strict mode reads user or
# managed settings only; a repository's .claude/settings.json is not enough)
jq -s '.[0] * .[1]' ~/.claude/settings.json generated/node/claude-code.settings.json > /tmp/s && mv /tmp/s ~/.claude/settings.json

# sandbox-runtime
cp generated/node/srt-settings.json ~/.srt-settings.json
```

For Codex, merge a generated `codex.config.toml` into the config file for the
environment you intend to use. The snippet enables the experimental network
proxy and adds `allow` rules for the profile's hosts. Command network access
must also be enabled in that environment (for example,
`[sandbox_workspace_write] network_access = true` in `workspace-write` mode).
Do not append the snippet if those TOML tables already exist; merge the keys
instead. The proxy filters sandboxed command traffic only, not web search,
apps, MCP servers, or other hosted tools. See the
[Codex configuration reference](https://developers.openai.com/codex/config-reference).

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

## Security scope and review policy

These profiles are development connectivity templates, not a safe website database.
GitHub, package registries, CDNs and storage hosts can serve arbitrary third-party
content. Domain permission does not restrict repository, tenant, URL path, HTTP
method or data transmission. Verify package provenance and keep runtime controls.

`policy.json` records exact upstream exclusions and their reasons. Upstream copies
remain unchanged for provenance. All non-excluded upstream entries, all overlay
entries and final generated domains pass the same hostname syntax and recognized-local-namespace validation. New
IP literals and recognized local namespaces fail generation. Public-looking
names can still resolve to private addresses; the runtime must enforce DNS
and private-network restrictions. Reviewed exclusions must be removed when
upstream no longer contains them; they are not a general bypass for invalid input.
Telemetry endpoints currently excluded are listed there as well.

Only `active` overlay entries may be included in generated profiles. `candidate`
and `retired` entries remain review records and grant no access. All current overlay
entries are candidates; promote an entry only with an observed requirement and
specific evidence. The workstation profile omits the optional `dev-tools` group;
create a deliberately scoped profile if a particular development service is needed.
Shared registries and CDNs remain because dependency retrieval requires them; this
is a documented trust boundary, not a claim that their contents are safe.

The upstream snapshot was fetched on 2026-09-24; no freshness claim is made.
Profiles are not automatically applied to user configuration or Cloudflare/WARP.
Use the smallest profile and verify allowed and denied destinations in the actual
client after intentional installation. No client configuration was changed by this
repository update.

Verification:

```sh
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/build.py
python3 scripts/validate.py
```

Human acceptance (pending): on the intended Mac and recorded agent version, review
the generated domains and exclusions, merge the chosen profile into an isolated
client configuration, perform a required dependency download, and confirm a benign
non-listed destination is denied. Verify private/loopback access remains blocked
by that client's effective policy. Pass requires both expected access and denial;
a successful static validator alone is insufficient. Applying to daily settings
is a separate rollout, not performed here.
