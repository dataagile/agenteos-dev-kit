# Read

Two modes: **list** (enumerate all specs) and **inspect `<slug>`** (structured detail on one spec). Both are read-only — never modify anything during Read. Both go through `scripts/mcp_client.py` — never Read the YAML directly off `drafts/**` e `published/**` deste repo (see SKILL.md's Auth/no-fallback section).

## list mode

Call `mcp_client.list_specs()` → `[{"slug", "version", "state"}, ...]`, scoped server-side to your tenant. For each entry, also call `mcp_client.read_spec(slug, version)` to pull `name`/`category`/`requires_erp` for the table (the MCP's `spec.list` only returns `slug`/`version`/`state` — it does not summarize metadata, so a full listing costs one `read_spec` per row; skip this extra round-trip and show just slug/version/state if the user only wants a quick inventory).

Present as a compact table, one row per spec (a slug with both a draft and a published version gets two rows):

| Slug | Version | Name | Category | Requires ERP | Status | Path |
|---|---|---|---|---|---|---|

`state` from the MCP maps directly to the `Status` column (`draft`/`published`). There is no local file path to show anymore in the MCP-mediated flow — if the user wants the on-disk path (e.g. to git-diff it), derive it structurally as `a raiz deste repo: <drafts-or-published>/<slug>/v<version>.yaml` per the naming convention (same one the MCP store itself uses), not by browsing the filesystem.

## inspect `<slug>` mode

1. **Locate.** Call `mcp_client.list_specs()`, filter client-side for the slug. If it appears with both `state: published` and `state: draft`, read and show both (published first, then draft), clearly labeled. Fetch content via `mcp_client.read_spec(slug, version)`.
2. **Disambiguation.** If `<slug>` is ambiguous (e.g. more than one version under either state), ask ONE short question listing the matches — never guess which one the user meant.
3. If the slug matches nothing, say so plainly — the MCP's `not_found` never distinguishes "doesn't exist" from "exists in another tenant" (by design, see `interfaces/mcp-tools.md`), so don't speculate about which case it is — and suggest `list` mode instead of searching further.

### Structured summary format

For each matched spec, present:

**Metadata block** — `id`, `slug`, `name`, `version`, `change_class`, `category`, `requires_erp`, `description`.

**Trigger block** — the spec's `trigger` section as-is (cron/event/manual — whatever it declares).

**config_schema, summarized field-by-field** — for each property: name, type, default (if any), required? (cross-check against the schema's `required` array), one-line description (truncate long descriptions to their first sentence). Do not dump the raw JSON Schema.

**io** — `reads` and `writes` lists, as given.

**Node graph, as an ordered list** — for each node in `nodes`, in order: key/id, `type`, a one-line purpose derived from its `config` (not copied verbatim — summarize what it does), and for condition-type nodes, list the branches (condition expression → next node).

### Node-type runtime annotation

Always call `mcp_client.node_types()` fresh (per the discovery-not-memory rule in SKILL.md — it's a single cheap call, not worth skipping). Annotate each node in the graph list with its `runtime_ready` status; when a node's `type` is not in the returned set, warn inline: "⚠ draft-only node type — not runnable in the current agent-runtime." Never treat this as fatal for Read — it's informational.

### Raw YAML

Never dump the raw YAML file contents unless the user explicitly asks for it (e.g. "show me the raw YAML"). The structured summary is the default and preferred output.
