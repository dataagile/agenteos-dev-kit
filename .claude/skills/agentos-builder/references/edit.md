# Edit

Guided edit of an existing spec — field-level or node-level — in either `drafts/` or `published/`. Precise questions only, one round at a time, each citing the field it targets.

## 1. Locate

Same lookup as Read: `mcp_client.list_specs()`, filter for the slug (published takes precedence if it exists in both states). If ambiguous (multiple matches), ask ONE disambiguation question — never guess. If the target doesn't exist, say so and suggest Read (list) instead of guessing further. Fetch current content via `mcp_client.read_spec(slug, version)`.

## 2. Git-clean gate (exact plumbing — do this precisely)

The git-clean gate still runs against the local disk path — it's a git safety check on a known path, not a spec-content read, so it isn't MCP-mediated (see SKILL.md's Boundary section on why Backup/Remove/this gate stay local during dogfooding). Derive `<path>` structurally as `a raiz deste repo: <drafts-or-published>/<slug>/v<version>.yaml` and run `git status --porcelain -- <path>` on it.

- **Output is empty** → clean, proceed.
- **Output is non-empty** (staged or unstaged changes) → block. Tell the user the file has uncommitted changes and ask them to commit first. Never run `git stash` on it.
- **File is untracked** (`git status --porcelain -- <path>` reports `??`) → this is a draft that was never committed. It has no git safety net — a bad edit can't be rolled back via git history. Warn explicitly and require one of: (a) the user commits it first, or (b) the user explicitly accepts editing with no rollback available. Do not silently proceed as if it were clean.

This check runs before any question about *what* to edit — no point interviewing the user just to block at the end.

## 3. Interview: what to change

Ask which field(s) or which node(s) the user wants to change. Two paths:

- **Root-level field edit** (name, description, category, config_schema property, trigger, io, etc.) — ask for the new value, citing the field.
- **Node edit** (add/change/remove a node) — reuse the Create node-interview rules from `create.md` in full: call `mcp_client.node_types()` fresh (never stale), house style applies (a real spec's `config` shape wins over the builder-map per-type shape when they disagree, per `create.md`), state the condition-expression grammar *before* the user writes one if editing a condition node, and dual-write `id`+`key` with the same value for any new or renamed node identifier.

## 4. Slug rename — refuse

If the requested edit is (or amounts to) changing `slug`, refuse immediately per the SKILL.md boundary — this is RN-07: a slug rename requires a YAML change **and** a DB migration together (lesson from feature 007 / a entrega da feature 007), which this skill cannot do half of safely. Point to `/w1`. Do not proceed with any other part of the edit in the same turn if the user bundled a slug rename with other changes — ask them to drop the rename and resubmit the rest.

## 5. Published-spec versioning (RN-04)

If the target is under `published/`, classify the edit before writing:

- **Non-behavioral metadata only** (typo in `description`, a comment, a cosmetic `metadata.tags` tweak) — conceptually an in-place edit of the existing `vN.yaml` is fine, **but the MCP's `spec.write` tool only ever writes to `drafts/` (`specs_service.write_draft` — there is no server-side path that targets `published/`)**. There is currently **no MCP-mediated way to edit an already-published spec in place**, even for a trivial typo. This is a real MCP-server gap (`dogfood.md`), not a skill limitation to work around — do not fall back to Write/Edit on the published YAML directly to fulfill this request; tell the user the operation isn't available via MCP yet and point them at `/w1` for a manual, coordinated fix in the meantime.
- **Anything behavioral** (node graph, `config_schema` shape/defaults/required-ness, `trigger`, `io`) — never an in-place edit regardless of MCP support: abra a próxima versão com `mcp_client.revise(slug)` (semeia o draft `vN+1` a partir da última published, idempotente, e devolve a `version` a usar), edite ESSE draft e siga o Publish flow, with a `change_class` review. Published specs are already seeded into the catalog/DB, so a silent behavioral change to the same version file diverges the YAML from what's running. Ask the user to confirm the version bump and `change_class` (patch/minor/major) before proceeding.
- If the resulting `change_class` is `major`, surface the R8 guard reminder (`lifecycle.md` §5): major com contratos ativos sem `version_pinned` pode ser rejeitado ou quebrar tenants na plataforma.

## 6. Diff before write

Assemble the proposed new YAML content in memory/scratch (never written into `drafts/` e `published/` deste repo directly — the skill's own Write tool is never the mechanism that lands a spec, `mcp_client.py` is). Show the user a unified diff between the current content (from step 1's `read_spec`) and the proposed version. Get explicit confirmation before proceeding — no silent writes.

## 7. Write sequence

This sequence only applies to a **draft** target, or a **published** target going through a new version (§5's behavioral path — o draft `vN+1` vem do `mcp_client.revise(slug)`, nunca montado à mão; use a `version` que ele retornou nos passos abaixo). An in-place edit of an already-published `vN.yaml` has no MCP path at all right now (§5) — stop there, don't reach this sequence.

1. On confirmation, validate: `mcp_client.validate(new_content)`.
2. **Pydantic errors** (blocking) → show them, fix with the user, do not write. Loop back to step 3/6.
3. **Pydantic clean** → `mcp_client.write_draft(slug, version, new_content)`. `McpClientError(code="immutable_published")` here means the (slug, version) is already published — confirms this should have gone through a version bump instead.
4. Report `validate`'s errors (JSON-Schema structural), if any — non-blocking but real, call them out. No `known_drift` bucket (see `lifecycle.md` §7) — every non-blocking error is reported flat.

## Boundary reminder

If mid-interview the user asks for a node type that isn't in the freshly-fetched `node_types()` output, refuse per the SKILL.md boundary (that's a new executor, not a YAML edit) and continue with only the types that exist.
