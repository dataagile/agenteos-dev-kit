# Clone

Derive a new agent spec from an existing one — short interview, most content carried over verbatim.

## 1. Interview

Ask, one at a time, citing the field:

- **Source slug** — which existing spec to clone from. Locate it the same way Read does (`mcp_client.list_specs()`, published first, then drafts); if ambiguous, ask ONE disambiguation question. Fetch its content with `mcp_client.read_spec(slug, version)`.
- **New slug** (`slug`) — kebab-case; validate the pattern; check collision via `mcp_client.list_specs()` (covers both states). If it already exists anywhere, say where and ask for a different one.
- **New human name** (`name`).

From the new slug, regenerate `id` = `agt_<new_slug_snake>_v0` (v0, not carried over from the source's `id` — this is a new spec lineage). Set `version: "0.1.0"` and `change_class: "minor"`, regardless of the source's version/change_class — a clone always starts fresh as a draft.

## 2. Carry-over

Everything else — `description` (unless the user wants to adjust it, ask), `category`, `requires_erp`, `trigger`, `config_schema`, `io`, and the full `nodes` graph — carries over **verbatim** from the source. Do not re-run the full Create node interview; this is a copy, not a rebuild. If the user wants to change something beyond identity, that's an Edit performed after the clone lands, not part of Clone itself.

## 3. Header comment

Prepend (or update, if the source already has a header block) a comment noting: "Cloned from `<source-slug>` `vN.yaml` on `<date>`." If the source spec had any draft-only / non-`runtime_ready` nodes, restate that status in the new header — cloning doesn't change runtime readiness, so the same warnings still apply.

## 4. Disguised-rename recognition (always check this before writing)

A slug rename cannot be done directly (see SKILL.md boundary, RN-07) — but "clone to a new slug, then remove the old one" is functionally the same operation, split into two steps. Before writing, check the session for either signal:

- The user already cloned this same source spec to a different slug earlier in this session, or is about to, **and** is now asking (or about to ask) to Remove the source.
- The user's own language frames this as a rename — words like "rename," "replace," "migrate the slug," "move X to Y" — even if they technically invoked Clone.

If either signal is present:

- **Source is published** → refuse the composition. A published slug rename requires YAML + DB migration together (feature 007 / PR #149 lesson) — this two-step Clone+Remove would silently produce that outcome without the migration half. Point to `/w1`. Do not proceed with the Remove half; the Clone half alone (a genuinely new spec that happens to resemble the source) is fine if the user confirms they want a distinct new agent, not a rename.
- **Source is a draft** → allowed (drafts have no DB/catalog entanglement to strand), but say plainly: "this reads like a rename of a draft — proceeding as clone + remove, not a slug rename" so the user knows what actually happened to the git history (two files, not one renamed).

## 5. Write sequence

1. Assemble the new YAML content in memory/scratch — never write directly into `drafts/` e `published/` deste repo with the skill's own tools; `mcp_client.py` is the only sanctioned path.
2. Validate: `mcp_client.validate(content)`.
3. **Pydantic errors** (blocking) → show them, fix, do not write. (Should be rare since content is carried over from an already-valid source, but the identity fields are new and can still collide or mistype.)
4. **Pydantic clean** → `mcp_client.write_draft(new_slug, "0.1", content)`.
5. Report `validate`'s errors (JSON-Schema structural), if any — non-blocking. No `known_drift` bucket (see `lifecycle.md` §7) — every non-blocking error is reported flat.
6. Nada de seed manual — quando o clone for publicado, o `spec_publish` entra no catálogo do ambiente sozinho.
