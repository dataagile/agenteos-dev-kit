# Publish

Promotes a draft to `published/<slug>/v<major>.yaml` — the explicit, one-way gate between "editable freely" and "part of the catalog." A promoção JÁ entra no catálogo do ambiente na hora — não existe passo manual de seed neste repositório.

## Before anything: confirm the naming convention live

Do not assume `published/<slug>/v<major>.yaml` from memory — call `mcp_client.list_specs(state="published")` first and confirm every existing entry's `version` is a bare major integer (e.g. `"1"`, not `"1.0.0"` — the MCP's `spec.list`/`spec.read` use the file's version tag directly, matching `v<major>.yaml`). If a future published spec ever deviates from that pattern, follow what the MCP actually reports, not this document's memory of it — this file describes the convention observed at the time it was written, not a guarantee it never changes.

## Interview

1. **Which draft.** Call `mcp_client.list_specs(state="draft")`, filter for the slug. If more than one version exists under that slug, ask which one — never guess.
2. **Target version.** Read the draft's own `version` field (e.g. `"0.5.0"`) and propose the publish target: `<major>` of that semver, e.g. `0.5.0` → `v0.yaml` is almost never right for a *first* publish — the normal first-publish case is `version: "1.0.0"` written into the YAML and `published/<slug>/v1.yaml` as the destination. If the draft's version is still pre-1.0 (`0.x.y`), ask explicitly whether this publish should bump it to `1.0.0` (the typical "first public release" move) or publish as-is at its current major — don't silently rewrite semver the user didn't ask for.
3. **`change_class` coherence.** Compare the draft's `change_class` field against what's being asked of the version bump:
   - `0.x → 1.0.0` (first publish of a previously-unpublished slug) is the **normal case** — no special warning needed even if `change_class` says `major`, because there are no existing contracts on an unpublished slug.
   - If the target slug **already has a published version** and this publish's `change_class` is `major`, surface the R8 warning verbatim (see below) before proceeding — this is the one case that mirrors a real seed-time rejection.

### R8 warning (verbatim — use exactly this wording when the condition applies)

> This skill has no database access and cannot check for active contracts itself. At seed time, a `major` version is rejected if the product has active contracts without `version_pinned` set (R8, `scripts/seed-catalog.py:136-156` `_check_major_active_contracts`) — unless `--allow-major` is passed to the real seed. Confirm with whoever owns the contracts data that this is safe, or expect the seed to reject it.

Condition to show this: `change_class == "major"` **and** the target slug already has at least one file under `published/<slug>/`. Do not show it for a slug's first publish.

## Steps (in order — do not skip or reorder)

1. **Re-validate the draft from scratch.** `mcp_client.validate(content)` on the draft's current content (fetched fresh via `read_spec`, step 1 of the interview) — never trust a validation result from earlier in the conversation; the draft may have changed since.
   - **Pydantic errors present → refuse to publish.** Show the errors, stop here. A spec that fails the blocking check has no business entering the catalog.
   - **JSON-Schema structural errors present** (trigger shape, node `oneOf`, condition grammar) → pause and confirm, do not silently proceed. A spec about to become part of the live catalog deserves a human look at these even though they're non-blocking. Ask the user to confirm they still want to publish as-is, and only continue on explicit confirmation. There is no `known_drift` bucket (see `lifecycle.md` §7) — every non-blocking error is reported flat, not pre-filtered as "expected G6/DAI-526 baseline."

2. **Slug+version collision check across BOTH states** — mirrors `scripts/seed-catalog.py`'s `_detect_duplicates` semantics (same `(slug, version)` tuple uniqueness): `mcp_client.list_specs()` (no state filter) already enumerates every `(slug, version, state)` in the store — confirm the `(slug, version)` pair this publish is about to write does not already exist anywhere else in the catalog. A collision here is exactly what the real seed would reject with "Slug+versão duplicado" — catch it before the write, not after.

3. **Node-type readiness banner.** Call `mcp_client.node_types()` fresh (never reuse an earlier run). Check every node in the draft's `nodes` list against the returned `runtime_ready` set:
   - **All nodes `runtime_ready: true`** → drop any "DRAFT — não carrega no runtime atual" banner and draft-only node callouts from the header comment (see `create.md`'s header-comment precedent) — the spec is fully runnable, the warning is stale.
   - **Any node `runtime_ready: false`** → keep the warning, naming exactly which node(s) and type(s) are not runtime-ready, so the published spec is honest about its own limitations even after leaving draft status.

4. **Bump the `version` field** in the YAML content to the confirmed publish version (step 1 of the interview) — this happens in memory, not by hand-editing the draft file in place.

5. **Write the bumped draft, then publish it — two MCP calls, not one.** The MCP has no single "write straight to published" tool; `spec.publish` only promotes a *draft that already exists on disk at exactly that (slug, version)* (`specs_service.publish_spec` copies `drafts/<slug>/v<major>.yaml` → `published/<slug>/v<major>.yaml` verbatim — it does not rewrite the YAML's internal `version:` field for you).

   Se a base é uma versão JÁ PUBLICADA (revisão), não monte o draft à mão:
   `mcp_client.revise(slug)` abre o draft da próxima versão já semeado da
   última published (idempotente) e devolve a `version` a usar nos passos
   abaixo.
   1. `mcp_client.write_draft(slug, "<major>", bumped_content)` — lands the bumped content as a draft at the target version (e.g. `drafts/<slug>/v1.yaml`). This re-validates server-side (blocking on pydantic).
   2. `mcp_client.publish(slug, "<major>")` — promotes that exact draft to `published/<slug>/v<major>.yaml`. The server re-validates once more and refuses with `McpClientError(code="validation_failed")` if it doesn't pass — treat that as a hard stop, not a warning; something changed between step 5.1 and here (shouldn't happen, but the server is the final gate).
   3. Never use the Write/Edit tool to place the published file directly — same rule as Create.

6. **Ask whether to delete the original (pre-bump) draft.** This refers to the draft at its *original* slug/version (e.g. `v0.5`), not the new bumped-version draft step 5.1 just created (which mirrors what's now published — no reason to delete it right after creating it). Default answer: **keep it.** Deleting a draft is Remove's job (`remove.md`, local filesystem + git-clean gate — there is no MCP delete tool). Only delete on the user's explicit request, and only after confirming the publish write actually succeeded.

7. **Não há passo de seed.** `spec.publish` já entra no catálogo do ambiente na hora — o relatório de sucesso do servidor é a confirmação. (Os alvos `make seed-catalog*` são do monorepo da plataforma e não existem neste repositório.)

## What Publish never does

- Não existe seed manual a rodar — a entrada no catálogo é efeito do próprio `spec.publish`.
- Never renames a slug (a slug rename is a coordinated YAML+DB-migration change — out of scope, redirect to `/w1`, per SKILL.md's boundary).
- Never overwrites an existing `published/<slug>/v<major>.yaml` silently — a version collision at that exact path is exactly what step 2's collision check exists to catch before the write is attempted (and `spec.publish` itself is idempotent no-op on an already-published version, per `interfaces/mcp-tools.md` — it never silently clobbers different content under the same path).
