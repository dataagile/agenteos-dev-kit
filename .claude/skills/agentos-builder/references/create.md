# Create

Guided interview that builds a brand-new AgentSpec YAML from scratch and writes it to `a raiz deste repo: drafts/<slug>/v0.1.yaml`. Precise questions only — every question names the schema field it fills. One round at a time; don't front-load the whole interview in a wall of text.

Before asking anything, call `mcp_client.node_types()` fresh — `{node_types: [{type, runtime_ready, required, optional, ux_hint, variants: [...]}], trigger: {...}, spec_level: {...}, transform_strategies: [...]}`. Never reuse a list from an earlier turn or from memory, and never read `packages/cdm/schemas/agent_spec_v1_builder_map.json` or `apps/agent-runtime/src/agent_runtime/executors.py` directly (T027 — this tool is the only source of truth for *which node types exist*, and it can change between sessions).

**Node `config` shape comes from `variants` (063/#484).** Each entry's `variants` lists every form the validator accepts for that type, derived from `agent_spec_v1.json` itself — including the `config` sub-schema with its required fields and enums. Use the variant marked `current: true`; the other one is the alternative form (e.g. `tool` accepts either top-level `tool_name`, dispatched by the Tool Registry, or `config.primitive` — the form every shipped spec uses). `identifier.one_of` says the node id field may be `key` **or** `id`. The entry's `required`/`optional` describe only the builder-map form and omit `config` — do not build a node from them.

Reading an existing spec to copy conventions is now optional (and impossible without the repo). If a `variants` entry and a shipped spec ever disagree, the variant wins: it is the same schema `spec.validate` enforces.

**Before writing any `.j2` template, call `mcp_client.context()`.** It returns what resolves inside `{{ ... }}` per scope. Two traps it exists to prevent: step refs need the `result` level (`steps.x.result.erp_response`, not `steps.x.erp_response`), and the run id is `run.id` inside a node but `run.run_id` inside a template (`run.tenant_id` and `run.input` do not exist in templates at all).

**For any `model_ref` / `intent_model_ref`, call `mcp_client.models()`** and pick an alias with `available: true`. Never invent an alias, and never write a literal model or provider name.

## Interview flow

### a. Identity

Ask, one line each, citing the field:
- **name** (`name` — human-readable display name)
- **slug** (`slug` — kebab-case; validate the pattern; check for collisions via `mcp_client.list_specs()` — if the slug already exists anywhere (either state), say where and ask for a different one, or confirm this is meant to extend an existing agent, in which case redirect to `edit.md` or `clone.md` instead of Create)
- **category** (`category`)
- **requires_erp** (`requires_erp` — boolean)
- **description** (`description`)

Derive and propose `id` = `agt_<slug_with_underscores>_v<major>` from the slug once known; let the user confirm or override.

### b. Trigger block

Required by layer 2 and by every real spec in the repo. Use the `trigger` entry from the `node_types()` call above — its `type_enum` and per-type `constraints` (e.g. a schedule type needs a cron expression) — do not assume you already know the enum values from a prior read. Ask trigger type first, then only the fields that type's constraints require.

### c. config_schema

Iterate parameter by parameter: for each tenant-configurable value ask name, type, default, whether it's required, and a one-line description. Mention (as pattern examples, not a menu) the two `x-` conventions already used in the repo: `x-ref: connection` for a connection-selector field, and `x-format: cron` for a cron-string field — point to `published/fin-pagamentos/v1.yaml` as the live example if the user wants to see one in context.

### d. io

Ask for `reads` and `writes` as CDM entity+label pairs (what the agent reads from/writes to, in domain terms).

### e. Nodes, one at a time

For each node:
1. Offer the current set of node types from the `node_types()` call above, annotated with `runtime_ready`. Node types where `runtime_ready` is `false` are still valid to place in the YAML — some (e.g. the structural/interpreter-level ones like trigger and condition) are routed by the interpreter rather than dispatched as executors, so `runtime_ready: false` does not always mean "broken," just "not an executor dispatch target." Others may be genuinely unimplemented (executor falls through or raises). Say plainly which is which when the user picks a non-runtime_ready type, and warn that the resulting spec is draft-only for that node — mirror the precedent header in `drafts/fin-collections/v0.5.yaml`.
2. Ask ONE question for the node's identifier (snake_case) and write the same value into **both** `id` and `key` on the node, plus `type`. Layer 1 (pydantic `NodeSpec`, the blocking layer) requires `id`; the runtime prefers `key` (`node.get("key") or node.get("id")` in `hatchet_app.py`). Dual-writing both fields with the same value keeps the node valid on the blocking layer and executable at runtime — until DAI-526 unifies the field, every node needs both.
3. Ask for the required/optional fields for that type per the builder map — required fields are not optional to skip; optional ones can be deferred with their default noted.
4. **Condition nodes specifically**: before the user writes an expression, state the supported grammar so they don't waste a round on something that will fail validation — only two forms are accepted:
   - `len(<cross-step-ref>) <op> <int>` where `<op>` is one of `==`, `!=`, `>=`, `<=`, `>`, `<`
   - `<cross-step-ref> <op> '<string>'` where `<op>` is `==` or `!=`
   Arbitrary Jinja2 (filters, math, function calls) is forbidden and fails at validation time. Following house style (see above), write the expression to `config.expr`, and ask which node to go to on true and which on false, writing those to `config.on_true` / `config.on_false` (omit `on_true` if the node simply falls through to `next` on the true path, matching the `fin-pagamentos` precedent).
5. **Transform nodes specifically**: use `node_types()`'s `transform_strategies` list (the MCP parses `executors.py`'s `_execute_transform` dispatch server-side — T027). Offer the user only the strategy names it returned. If `transform_strategies` is `null`/empty, say so plainly — do not guess a name — and ask the user for the intended strategy, then flag that node as **unverified** in the header comment so it gets a second look before this spec is trusted.

## File conventions

- Destination: `a raiz deste repo: drafts/<slug>/v0.1.yaml`.
- `version: "0.1.0"`, `change_class: "minor"`.
- Prepend a header comment block following the precedent in `drafts/fin-collections/v0.5.yaml`: a status line (draft, doesn't load on current runtime if any node isn't `runtime_ready`), which nodes (if any) are draft-only and why, and a pointer to a design doc if the user has one.

## Write sequence

`mcp_client.py` is the **only** sanctioned way this skill writes a spec to the store. Never use the Write/Edit tool to place the final spec directly in `drafts/` e `published/` deste repo — always go through `mcp_client.write_draft`.

1. Assemble the full YAML from the interview answers, in memory (or a scratch/temp path if easier to work with) — this draft-in-progress copy is disposable scratch work, not the deliverable.
2. Validate: `mcp_client.validate(content)`.
3. **Pydantic errors present** (blocking) → show them, fix the offending answers with the user, do not proceed to write. Loop back to the relevant interview step, update the draft content, re-validate.
4. **Pydantic clean** → `mcp_client.write_draft(slug, "0.1", content)`. This both re-validates server-side and performs the write; `McpClientError(code="parse_error")` means the YAML itself is malformed (show the message) and `code="immutable_published"` should never happen here (0.1 is a fresh slug) — if it does, stop and say the slug collided with something already published.
5. Report the `validate` result's `errors` (JSON-Schema structural — trigger shape, node `oneOf`, condition grammar), if any — non-blocking but real; suggest fixes. There is no `known_drift` bucket in the MCP validator (see `lifecycle.md` §7) — every non-blocking error is reported flat, not sub-classified as "expected drift" vs "novel."
6. Nada de seed manual — a validação final é o próprio servidor no `spec_validate`/`spec_publish`; publicou, entrou no catálogo.

## Boundary reminders during the interview

If the user asks, mid-interview, for a node **type** that doesn't exist in the freshly-fetched node-type list — that's a request for a new runtime executor, not a YAML change. Refuse per the SKILL.md boundary (point to `/w1`), then continue the interview offering only the types that actually exist right now.
