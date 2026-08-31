# Lifecycle — shared rules

The transversal rules every operation file cross-references instead of restating in full. If an operation file's local wording ever seems to drift from this, this file wins.

## 1. Draft → Published lifecycle

- **`drafts/<slug>/vN.yaml`** is the free-editing state. A draft has no catalog/DB entanglement — Edit is unrestricted in-place, Remove is allowed (with the git-clean gate, see §4), Clone reads from it freely.
- **`published/<slug>/v<major>.yaml`** is the seeded-into-the-catalog state (o `spec_publish` semeia o catálogo do ambiente na hora — não há seed manual neste repositório). Once published, a spec is no longer "just a file" — a DB row and possibly live contracts depend on it existing at that exact path with that exact content shape. This is why published editing rules are stricter (§2) and Remove refuses outright (see `remove.md`).
- **Publish** (`publish.md`) is the one-way, explicit gate from draft to published. There is no corresponding "unpublish" operation in this skill — taking a published spec out of the catalog is a contract-drain operation through `/w1`, not a file operation.

## 2. Editing rules by state

- **Draft**: in-place edit is always fine — there's nothing else depending on the exact bytes yet.
- **Published, non-behavioral change** (typo in `description`, a comment, a cosmetic `metadata.tags` tweak): in-place edit of the existing `vN.yaml` is allowed — nothing a running agent depends on changes.
- **Published, behavioral change** (node graph, `config_schema` shape/defaults/required-ness, `trigger`, `io`): in-place edit is not appropriate. The correct move is a new version file (`vN+1.yaml`) or a version bump with a `change_class` review — never silently rewriting the version already seeded, since that diverges the file on disk from what the DB/runtime believe they're running.

See `edit.md` for exactly how this classification is applied during an edit interview.

## 3. Versioning and `change_class` semantics

- `version` is semver (`"1.0.0"`, `"0.5.0"`, ...). Published filenames use only the major component: `published/<slug>/v<major>.yaml` (e.g. `version: "1.3.0"` lives at `v1.yaml`). **Verify this convention live** against the actual `published/` directory before relying on it — don't assume it never changes; see `publish.md` for the live-check step.
- `change_class` (`minor` | `major`, following the existing repo convention — the field is a spec-level annotation, not itself schema-enforced by this skill) states how disruptive this version is relative to the previous one:
  - `minor` — safe, backward-compatible change. No special guard.
  - `major` — potentially breaking. Triggers the R8 guard (§5) whenever the target slug already has a published version.
- Bumping `version`/`change_class` never happens silently — every operation that touches a published spec's version asks the user to confirm the target version and `change_class` explicitly (see `edit.md` §5, `publish.md`'s interview step 3).

## 4. Git-backup doctrine

Git is the **only** backup mechanism this skill uses. There is no parallel `backups/` folder, and the skill's own Write tool never functions as an ad hoc backup copy.

- **Per-file clean gate** — the exact plumbing every destructive operation (Edit, Remove) checks before proceeding: `git status --porcelain -- <path>`.
  - Empty output → clean, proceed.
  - Non-empty output (staged or unstaged changes on that file) → block, ask the user to commit first.
  - Untracked (`??`) → the file has no git history at all; a destructive operation on it is unrecoverable. Warn explicitly and require the user to either commit first or explicitly accept no rollback — never silently treat untracked as equivalent to clean.
- **Never `git stash`**, for this gate or anything else the skill does — per the user's global stash-safety rule, stash is destructive if dropped, and this repo's working tree is shared across parallel sessions, so "local changes" are never safely assumed disposable.
- **On-demand snapshot** — when the user wants a restorable point before a destructive change but isn't ready to do a normal commit, the Backup operation takes a dedicated commit of exactly one file, isolated in a throwaway worktree on its own `wip/` branch, never touching the user's checked-out branch or index. See `backup.md` for the exact sequence and restore procedure — that file owns the *how*; this section only establishes that git commits are the *only* form backup ever takes.

## 5. R8 guard

Guarda R8 do catálogo da plataforma: uma versão `major` num slug que já tem contratos ativos sem `version_pinned` pode ser rejeitada ou quebrar tenants no update.

This skill has **no database access** and cannot check for active contracts itself — so wherever this guard applies (Edit or Publish producing `change_class: major` on an already-published slug), it is a **warning only**, not an enforced block. Surface it so the user can check with the admin do ambiente (quem enxerga os contratos) before publishing, rather than being surprised later. See `publish.md`'s R8 warning for the exact wording used.

## 6. Slug rename — banned everywhere, including disguised as Clone+Remove

A slug rename is never performed by this skill, in any form, under any framing. Lesson from feature 007: a slug rename requires a YAML change **and** a DB migration together, executed as one coordinated delivery — this skill operates on YAML only and cannot do half of that safely. Refuse and point to `/w1`. This is the one canonical statement of the rule; `edit.md`, `clone.md`, and `remove.md` reference it rather than re-deriving it.

**The disguised composition**: "clone the spec to a new slug, then remove the old one" is functionally a rename split into two operations, neither of which is individually a rename. Watch for this composition — either as an explicit clone-then-remove sequence in one session, or as rename-flavored language ("rename," "replace," "migrate the slug," "move X to Y") even when the user technically invokes Clone or Remove separately.

- **If the source/origin spec is published** → refuse the composition (not just the individual operations). Point to `/w1`. The Clone half alone remains fine if the user confirms they want a genuinely distinct new agent, not a rename — but Remove of the published original is refused regardless (see `remove.md`'s unconditional published refusal, which holds independent of this tripwire too).
- **If the source/origin spec is only ever a draft** → allowed, since drafts have no DB/catalog entanglement to strand — but say plainly that this is a rename performed as clone + remove, so the user understands what happened to the git history (two files, not one renamed).

## 7. DAI-526 schema drift — canonical explanation (pre-MCP history) + what changed under 024/T017

Before feature 024, this skill ran `scripts/validate_spec.py` locally, which layered the pydantic MVP schema (layer 1) with the frozen JSON Schema contract (layer 2, `cdm.agent_spec.validate_agent_spec` against `agent_spec_v1.json`). The two disagreed **structurally** — tracked as Jira DAI-526 / gap G6 (2 of the 5 currently published specs fail layer 2 today — `analise-estoque`, `resumo-financeiro`; the layer-2 fatal check in `AgentFactory` is dead code, never wired to the real dispatch path) — so layer 2 ran non-blocking, split into `known_drift: true` (the expected G6 baseline) vs `known_drift: false`/`layer2_novel` (real, spec-specific problems).

**Since 024/T017, spec validation is MCP-mediated** (`mcp_client.validate(content)`, called from every operation instead of the local script). The MCP's validator runs the **same two functions** the local script did: pydantic (`agent_specs.schema.AgentSpecSchema`, blocking) + `cdm.agent_spec.validate_agent_spec` (JSON-Schema structural, non-blocking) — a Round 2 dogfood (`_reversa_forward/024-separacao-repo-mcp/dogfood.md`) initially found the MCP running `agent_specs.lint.lint_config_schema` instead (a different, config-copy check), which would have let structurally-invalid specs publish clean; this was a real bug, fixed the same day in `packages/mcp-server/src/mcp_server/validation.py` and re-proven by `dogfood_check.py` + a rebaselined `test_parity.py`. One difference from the old local behavior remains: the MCP's `errors` list carries no `known_drift` flag — it doesn't sub-classify "expected G6/DAI-526 baseline" vs "novel to this spec" the way `validate_spec.py` did; every non-blocking error is reported flat, worth a look, not auto-bucketed.

**Since 024/T027, node-type/trigger discovery is also MCP-mediated** (`mcp_client.node_types()`, §3 of SKILL.md's shared rules) — the MCP reads `packages/cdm/schemas/agent_spec_v1_builder_map.json` and parses `apps/agent-runtime/src/agent_runtime/executors.py` (dispatch table + `_execute_transform` strategy vocabulary) server-side and serves the result; this skill no longer reads either file directly. `scripts/validate_spec.py --list-node-types` still exists (own test suite, `.claude/skills/agentos-builder/tests/test_validate_spec.py`, kept green) but is no longer part of any documented skill operation — Backup and Remove (git/fs, §4 above and `remove.md`) are now the only local exceptions.
