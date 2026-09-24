# Create

> **Este arquivo não pergunta nada ao humano.** A entrada é a ficha de domínio
> gravada no cabeçalho do rascunho por `references/descoberta.md`. O humano que
> autora é analista de negócio: ele nunca vê slug, nó, `when` ou
> `config_schema`. Se a ficha tem linha `<pendente>`, volte para a descoberta.

Procedimento interno que **deriva** o AgentSpec YAML a partir da ficha, valida
pelo MCP e regrava o rascunho `drafts/<slug>/v0` que a descoberta já criou.
O que o humano vê depois disto é o roteiro de `references/proposta.md`.

Before deriving anything, call `mcp_client.node_types()` fresh — `{node_types: [{type, runtime_ready, required, optional, ux_hint, variants: [...]}], trigger: {...}, spec_level: {...}, transform_strategies: [...], semantics: {...}}`. Never reuse a list from an earlier turn or from memory, and never read `packages/cdm/schemas/agent_spec_v1_builder_map.json` or `apps/agent-runtime/src/agent_runtime/executors.py` directly (T027 — this tool is the only source of truth for *which node types exist*, and it can change between sessions). The `semantics` block (keys `condition`, `when`, `jump`, `loop_body_errors`, plus `version` and `partial`) carries the flow semantics the environment actually enforces — read it before writing any `condition`/`loop`/`when` node, per SKILL.md's discovery-not-memory rule. If the artifact behind it is missing or incomplete only that block degrades (`{partial: true, warning: ...}`); the node-type catalog is still served.

**Node `config` shape comes from `variants` (feature 063).** Each entry's `variants` lists every form the validator accepts for that type, derived from `agent_spec_v1.json` itself — including the `config` sub-schema with its required fields and enums. Use the variant marked `current: true`; the other one is the alternative form (e.g. `tool` accepts either top-level `tool_name`, dispatched by the Tool Registry, or `config.primitive` — the form every shipped spec uses). `identifier.one_of` says the node id field may be `key` **or** `id`. The entry's `required`/`optional` describe only the builder-map form and omit `config` — do not build a node from them.

Reading an existing spec to copy conventions is now optional (and impossible without the repo). If a `variants` entry and a shipped spec ever disagree, the variant wins: it is the same schema `spec.validate` enforces.

**Before writing any `.j2` template, call `mcp_client.context()`.** It returns what resolves inside `{{ ... }}` per scope. Two traps it exists to prevent: step refs need the `result` level (`steps.x.result.erp_response`, not `steps.x.erp_response`), and the run id is `run.id` inside a node but `run.run_id` inside a template (`run.tenant_id` and `run.input` do not exist in templates at all).

**For any `model_ref` / `intent_model_ref`, call `mcp_client.models()`** and pick an alias with `available: true`. Never invent an alias, and never write a literal model or provider name.

## Derivação — da ficha ao YAML

Cada linha da ficha decide algo. Cada decisão cita a seção do
[`ARMADILHAS.md`](../../../../ARMADILHAS.md) que a justifica. Aplique na
ordem; se uma linha exigir um recurso que o ambiente não tem (conector, tool,
strategy, modelo), **pare aqui** e siga `references/gap.md` — nunca continue
com o nó faltando.

> **Rota curta (fecha a lacuna do spec §3.1/§5):** na ficha curta
> (`descoberta.md` "Triagem"), as linhas Escreve, Autoriza, Nunca pode e Fora
> do grafo não são perguntadas — e não ficam em branco nem viram `<pendente>`.
> Escreva-as literalmente: `# Escreve: (nenhum)`, `# Autoriza: (não se
> aplica)`, `# Nunca pode: (não se aplica)`, `# Fora do grafo: (nenhum)`.
> `# Termos:` deriva dos verbos da linha **Trabalho**. Só uma linha
> `<pendente>` de verdade manda de volta para a descoberta — as quatro linhas
> acima, na rota curta, nunca chegam a esse estado.

| Linha da ficha | Deriva | Regra |
|---|---|---|
| Trabalho | `name`, `slug` (já validado na descoberta), `description`, `id = agt_<slug_com_underscores>_v1` | `id` é ESTÁVEL entre versões (§3): fixe `_v1` desde o `0.1.0` — derivar do major mudaria o id no primeiro publish `1.0.0` |
| Começa quando | `trigger.type` e campos do tipo | enum de `node_types().trigger`; `schedule` exige cron; `chat` implica a regra da linha "Começa quando = chat" |
| Termos | `id`/`key` dos nós (snake_case do termo do usuário); `title`/`description` das properties | mesmo valor em `id` e `key` (§8); property sempre com `title` e `description` (lint D-02) |
| Lê | `io.reads`; um nó de leitura por fonte (`tool` / `http_request` / `sftp_op` / `erp_query`) | `connector_id` só de `connectors()`; `tool_name` só de `tools().platform_tools`; ler `allowed_ops`/`base_dir` antes de compor path (§6) |
| Escreve | `io.writes`; nó de escrita **sempre precedido** de `approval` e de um `condition` que **autoriza** com **`on_true` apontando o nó de escrita** (guarda) | condition `expr: "<approval>.decision.decision == 'approved'"`, só `on_true` — veredito falso pula o nó de escrita (`condition_guard`) e a execução segue linear até o template final, que diz que nada foi feito (§1, §4, §21). **Nunca** `on_false` para um "nó de aviso": a execução é linear por posição e o aviso roda também no caminho feliz (§21) |
| Autoriza | `approval` com `context_from` apontando o passo que produz a lista; alçada em `config.when` **só sobre `config.*`** (📏 caminho de passo não resolve no `when` do approval: vale `None`, `len` dá 0, e a aprovação é PULADA com `alcada_below_threshold` — §21) | §2 (item sem `action` derruba a inbox), §4, §21; sem alçada = sem `when`; "só pede quando há item" já é o `empty_context` do `context_from`, não precisa de `when` |
| Começa quando = chat | nenhum `{{run.input.*}}` alcança nó de escrita; o pedido do usuário só ESCOLHE entre opções do `config` | §5 |
| Nunca pode | um `condition` ou `approval` que a proteja; se não houver onde encaixar, a ficha está errada — volte à Rodada 2 | descoberta.md |
| Fora do grafo | não vira nó; se exigir operation no serviço, é gap `[plataforma]` | §19 |
| Termina bem | **um único** `render_template` final, sempre o último nó, cujo `.j2` trata os casos (ok / lista vazia / passo falhou / aprovação pendente ou pulada) lendo `steps.<x>.status` e `steps.<x>.result`; `.j2` só com o que `context()` resolve, enviado no mesmo `write_draft` | §8; §21 (não existe "nó terminal": `next: []` não encerra a execução linear) |
| Descartado | linha do cabeçalho; não deriva nó | — |

Regras transversais, aplicadas sem perguntar:

- `http_request` que falha **não** aborta o run (§18); `sftp_op` que falha
  **aborta** (📏 §21). Quando o consumidor de um `http_request` é um nó de
  escrita ou outra chamada externa, guarde-o com um `condition`
  `expr: "<passo>.status == 'ok'"` e **`on_true`** apontando o consumidor. Se o
  consumidor é só o template final, não precisa de condition: o `.j2` trata o
  `status`.
- Nó `agent` só com campos dentro de `config` (§16); o prompt instrui o modelo
  a nunca emitir `{{}}` (§17); a saída é string — parse fica no serviço (§19).
- `http_request`: `body` é objeto só em resposta JSON; fora disso é string sem
  `body_raw` — teste `is string` no template antes de navegar (§11).
- `version: "0.1.0"`, `change_class: "minor"`. Major é conversa com o admin (§3).
- `config_schema`: o que o cliente escolhe na ativação (conexões, pastas,
  limites). O que é fixo fica literal no YAML. Property `x-ref: connection`
  **sem `default`** — exceto no draft de teste, com `# REMOVER antes de publicar`
  (§9); o guard do `publish.md` recusa se sobrar.
- `condition`: leia `semantics.condition` de `node_types()` antes de escrever
  qualquer `expr`; `top_level` e `loop_body` não aceitam as mesmas formas.
- `transform`: só strategies de `node_types().transform_strategies`; lista
  vazia = gap `[plataforma]`.
- Nó com `runtime_ready: false` que não é estrutural (trigger/condition): gap
  `[plataforma]`, não "draft-only".

O analista nunca vê esta tabela. Ela é o contrato entre a ficha e o YAML.

## File conventions

- Destination: no store do MCP (`drafts/<slug>/v0` do servidor) — nunca um
  arquivo local.
- `version: "0.1.0"`, `change_class: "minor"`.
- **Cabeçalho = a ficha de domínio**, já gravada pela descoberta. A derivação
  acrescenta abaixo dela, ainda como comentário: `# Derivado em <data> a partir
  da ficha acima; regras em references/create.md`. Nada de "draft-only": nó que
  não roda é gap, não nota de rodapé.

## Write sequence

`mcp_client.py` is the **only** sanctioned way this skill writes a spec to the store. Never use the Write/Edit tool to place the final spec directly in `drafts/` e `published/` deste repo — always go through `mcp_client.write_draft`.

1. Derive o YAML completo a partir da ficha (tabela acima), em memória. Leia o
   rascunho atual com `mcp_client.read_spec(slug, "0")` para preservar o
   cabeçalho.
2. Validate: `mcp_client.validate(content)`.
3. **Pydantic errors present** (blocking) → do not write. Treat it as a derivation failure: find which line of the ficha and which rule of the table above produced the offending field, re-derive, re-validate. If the ficha itself cannot resolve it (a rule the table does not cover, or a resource the environment lacks), follow `references/gap.md`. Never ask the human for a schema value.
4. **Pydantic clean** → `mcp_client.write_draft(slug, "0", content, templates)` — sempre com os `.j2` no mesmo write (§8). This both re-validates server-side and performs the write; `McpClientError(code="parse_error")` means the YAML itself is malformed (show the message) and `code="immutable_published"` should never happen here (0.1 already exists as the draft descoberta created) — if it does, stop and say the slug collided with something already published.
5. Report the `validate` result's `errors` (JSON-Schema structural — trigger shape, node `oneOf`, condition grammar), if any — non-blocking but real; suggest fixes. There is no `known_drift` bucket in the MCP validator (see `lifecycle.md` §7) — every non-blocking error is reported flat, not sub-classified as "expected drift" vs "novel."

## Quando a derivação não fecha

Tipo de nó, conector, tool, strategy ou modelo que a ficha exige e o ambiente
não tem: **não é** "peça para o dev", nem `/w1`. É gap. Pare na linha da tabela
que travou, grave o rascunho com `# Pendente: <linha> — <o que falta>` no
cabeçalho e siga `references/gap.md`. A regra de ouro do kit continua: zero
código do core, zero contorno.
