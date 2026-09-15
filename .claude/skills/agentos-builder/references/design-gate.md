# Design gate — DDD → prd.md → spec.md → human decision

Runs once per new agent, as **Create's mandatory step 0**, before the Identity interview
(`create.md` §a). Produces three artifacts under `drafts/<slug>/`: `prd.md`, `spec.md`,
`gate.json`. Create refuses to start its interview until `gate.json` exists with
`status: "closed"`.

This is the **third** documented exception to the MCP-only boundary (SKILL.md), alongside
Backup and Remove — no MCP tool exists for PRD/spec/gate content, so this step writes local
files with Read/Write/Edit, git-tracked like everything else under `drafts/`.

## 0. Falando com quem decide

Quem conduz essa conversa **normalmente não é dev** — é analista de negócio. Nunca use termo de
schema/YAML com essa pessoa. Uma frase curta, sem jargão, nunca parágrafo. Tabela — memorize,
não repita ela pro usuário:

| Termo técnico | Como falar |
|---|---|
| trigger | o que "liga" o agente — todo dia num horário, quando algo acontece, ou só quando alguém manda |
| node / nó | um passo da receita que o agente segue, em ordem |
| io (reads/writes) | o que ele vai buscar / o que ele entrega no fim |
| config_schema | os ajustes que dá pra mudar depois, sem chamar o dev de novo |
| approval node | um ponto onde ele para e pede seu ok antes de continuar |
| DDD Modo 1 | checagem rápida — esse assunto é complicado o bastante pra merecer um mapeamento antes, tipo perguntar se a reforma precisa de projeto de engenheiro ou só de pedreiro |
| spec.md | a tradução técnica do que você decidiu, pra quem monta o agente — você confirma se bate, não precisa ler linha a linha |

`prd.md` e as perguntas do gate (§4) já usam essa linguagem. `spec.md` (§3) é o único artefato
técnico — nunca peça pra essa pessoa ler ele direto, resuma.

## 1. DDD Modo 1 — fit assessment (mandatory call, optional depth)

Invoke `Skill(ddd)` Modo 1 against what's known about the agent so far (the user's request,
any domain vocabulary mentioned, an early io sketch). Frame the check to the user per the
glossary above (§0) — never say "DDD" or "fit assessment" out loud. The call itself is not
optional — always run the fit assessment before writing `prd.md` — but its **verdict** decides
how much more DDD work happens:

- **Pular** — most agent specs land here (automation/IT-shaped, not client-domain-shaped). Go
  straight to §2.
- **Discovery enxuto / completo** — pause here, run `Skill(ddd)` Modo 2 per its own phased
  process (`references/processo-descoberta.md` in that skill) — that process already talks
  business language on its own, no extra translation needed. Its output — one Markdown doc per
  aggregate — is saved to `drafts/<slug>/domain/<aggregate>.md`. Do not fold it into `prd.md`;
  link to it instead.

Record the verdict and which criteria matched — it goes into `gate.json` §4.

## 2. prd.md — product requirements

Only after §1 resolves (verdict applied, Modo 2 docs written if triggered). Sections, one pass,
don't front-load the whole doc in one message:

- **Propósito** — business outcome this agent exists to produce, one paragraph.
- **Gatilho** — what starts a run, in plain language (cadence, event, manual).
- **Entradas** — what it reads, in domain terms (link `domain/*.md` aggregates if DDD ran).
- **Saídas** — what it writes/produces, in domain terms.
- **Critério de pronto** — how a run is judged successful.
- **Casos de borda e falha** — known edge cases, expected behavior for each.
- **Pontos de decisão humana** — any approval/human-in-the-loop moments and why.
- **Fora de escopo** — explicitly excluded, to stop scope creep once Create starts.

Write to `drafts/<slug>/prd.md`.

## 3. spec.md — technical translation

Before writing it, run the same discovery calls the Create interview itself uses —
`mcp_client.node_types()`, `mcp_client.connectors()`, `mcp_client.tools()`,
`mcp_client.models()` (SKILL.md §3, discovery-not-memory) — so the sketch only proposes node
types, trigger types, and model aliases that actually exist right now. Catching an infeasible
shape here is cheap; catching it after the gate is closed is not.

Abre com um **resumo de 3-4 linhas em português simples** (o que o agente faz, passo a passo, sem
termo técnico) — é a parte que a pessoa não-dev de fato lê. O resto do arquivo é técnico, existe
pro Create consumir depois, não pra ser lido linha a linha por quem está decidindo.

Sections:

- **slug, category, requires_erp** — proposed values.
- **Trigger** — type + one-line why (cite the live `trigger` constraints if relevant).
- **Sequência de nós** — ordered list, each entry: id (snake_case), type, one-line purpose, key
  config fields by name only — Create still asks the full interview per node.
- **io** — reads/writes as CDM entity+label pairs.
- **config_schema** — parameter list: name, type, required y/n (no defaults yet).
- **model_ref / intent_model_ref** — alias if already resolvable from `mcp_client.models()`,
  else "a decidir no Create".
- **Alternativas descartadas** — at node-shape level (e.g. "trigger webhook — descartado:
  cliente sem endpoint exposto").

Write to `drafts/<slug>/spec.md`.

## 4. Gate — human decision (same vision as `/como-fazer`)

Apresente pelo resumo do `spec.md` (§3) e pelo `prd.md` — nunca jogue o `spec.md` técnico
inteiro na tela pra essa pessoa decidir em cima. Two questions, one frase cada — mirrors
`protheus:como-fazer` / `fluig:como-fazer` exactly:

1. **Qual caminho você escolheu?**
2. **Qual alternativa você descartou, e por quê?**

Sem a segunda resposta o gate não fecha — quem não sabe dizer o que descartou ainda não
decidiu, só comparou uma opção só.

Write `drafts/<slug>/gate.json`:

```json
{
  "status": "closed",
  "decision": "...",
  "discarded_alternative": "...",
  "discarded_reason": "...",
  "decided_by": "...",
  "decided_at": "ISO-8601",
  "ddd_verdict": "pular|enxuto|completo",
  "sources": [{"claim": "...", "label": "CONFIRMADO|INFERIDO", "source": "..."}]
}
```

Every technical claim behind the decision gets a `sources[]` line labeled `CONFIRMADO`
(checked live — MCP call, existing spec, explicit user statement) or `INFERIDO` (assumed) —
same discipline as the trilho's `gates.json`.

## 5. Reopening

If `prd.md` or `spec.md` change after `gate.json` is `closed`, treat it like any other
destructive edit under this skill: git-clean gate first (`lifecycle.md` §4), then re-run §4 —
the two questions again, a new `gate.json`. Never patch a closed gate in place.

## 6. What Create checks

Before asking Identity §a, Create checks `drafts/<slug>/gate.json` exists and
`status == "closed"`. If missing or open, stop and run this file first — never start the
interview against an open gate, even if the user seems ready to skip ahead.
