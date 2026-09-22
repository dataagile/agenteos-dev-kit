# Chamado no GLPI aberto pelo kit — trava vira chamado, com consentimento

**Data:** 2026-09-22
**Estado:** proposta, aprovada em brainstorm com Gianluka; aguardando revisão do spec
**Baseline:** dev-kit `main` em `0124614` (#28: `gap.md`, `feedback()`, `publish_guard`); Agente_OS `main` com `spec_feedback` (154/#908) e feedback do console → GLPI (#946/#950/#958)
**Brief de origem:** `/tmp/guia-dataagileos-glpi/brief-devkit-glpi-mcp.md`

## 1. Pedido e o que mudou no brainstorm

Pedido: quando quem usa o kit encontra uma trava, bug ou qualquer coisa na
plataforma que impeça o desenvolvimento, o kit sugere e consegue abrir o
chamado no GLPI da TBC. O pedido nomeava "um MCP do GLPI dentro do dev-kit".

Quatro decisões tomadas no brainstorm mudaram a forma sem mudar o objetivo:

| Pergunta | Decisão | Por quê |
|---|---|---|
| Onde o chamado é aberto? | **Pela plataforma, via MCP do AgenteOS** | Zero credencial na máquina de quem autora; o api-gateway já abre chamado hoje; anexo só funciona de dentro da rede dokploy, onde o MCP está; dedup no servidor; analista sem dev não configura segredo |
| Relação com a esteira atual (`spec_feedback` → Sentry)? | **Tudo vai para o GLPI**; o Sentry sai | Uma esteira só, a que o time já tria |
| Quem aparece como reportante, se a chave do MCP é do tenant? | **O kit pergunta nome e e-mail uma vez** e envia no `context` | Simples; funciona para analista; requerente no GLPI continua o usuário técnico, como no console |
| Quando o kit sugere? | **Gap do `gap.md`; MCP falhando 2x no mesmo passo; o usuário pede** | Cobre trava de plataforma sem virar ruído de erro local |
| Forma da mudança? | **Estender `spec_feedback`** (abordagem A) | Mesma tool, mesmo contrato; nenhum cliente antigo quebra; "tool nova" contradiz "tudo vai para o GLPI"; "MCP separado no kit" já descartado |

Consequência: **não existe MCP do GLPI no kit.** O GLPI é um destino do MCP
do AgenteOS. O kit fica com gatilho, consentimento, conteúdo e retorno — que
o `gap.md` já define — mais um comando explícito.

## 2. Plataforma — contrato da tool `spec_feedback` (repo Agente_OS)

Mesma tool, mesmo nome (`spec.feedback` → `spec_feedback`), mesmo escopo
`spec.read` (🔍 lido em `tools/spec_feedback.py`: `required_scope="spec.read"`;
logo a chave de 6 scopes do README já a cobre — fecha a nota "a confirmar").

**Entrada** (tudo string; teto 4000 chars por valor, como hoje):

| campo | obrig. | uso |
|---|---|---|
| `category` | sim | `erro` → Incidente (type 1); `melhoria`, `feedback` → Requisição (type 2). Mesmo mapa `_CATEGORY_TYPE` do console |
| `message` | sim | primeira linha vira o título; corpo inteiro vai no chamado |
| `context.reporter_name`, `context.reporter_email` | **sim** (novo) | "Reportado por" no corpo. Ausente → `validation_failed` |
| `context.slug`, `version`, `run_id`, `tool` | não | como hoje |
| `context.kit_version`, `context.step` | não (novo) | versão do `SKILL.md` e passo da skill onde travou |

**Chamado** (reaproveita `build_ticket` do console, movido junto com o cliente):

- título: `[dev-kit] <Categoria>: <primeira linha, ≤ _TITLE_MAX>`
- corpo HTML: mensagem escapada, `<hr>`, tabela com Reportado por, Tenant
  (nome + slug, como `_load_context` já resolve), Slug/versão, Tool/passo,
  Versão do kit, Run, Data UTC. Requerente do GLPI = usuário técnico
  `agenteos-api` (grant `password`), como no console.
- `external_id` = 12 hex de `sha256(tenant_id | category | primeira_linha_normalizada | slug-ou-tool)`.

**Saída:** `{"status": "ok", "ticket_id": N, "url": "<glpi_url>/front/ticket.form.php?id=N", "deduplicated": bool}`.

**O que sai:** `sentry_sdk.capture_message` e as tags. O docstring/descrição da
tool passa a dizer GLPI. A descrição mantém o aviso de que o texto vai cru.

**Onde o cliente vive:** `apps/api-gateway/src/api_gateway/glpi.py` (só depende
de `cdm.config` e `httpx`) sobe para `packages/cdm/src/cdm/glpi.py`, com
`GlpiClient`, `GlpiError`, `GlpiTicket`, `build_ticket` e o `FakeGlpi` de
teste. O api-gateway e o mcp-server importam de `cdm.glpi`. O mcp-server já
depende de `cdm` e `httpx` (📏 `pyproject.toml`). Settings: as mesmas
`glpi_*` de `BaseServiceSettings`; o mcp-server passa a exigir as cinco da v2
(`feedback_enabled`) no spoke onde roda.

## 3. Plataforma — dedup, falhas, fora de escopo

**Dedup.** Antes de criar: `GET /Assistance/Ticket?filter=external_id==<hash>`.
Existe → devolve o existente com `deduplicated: true`, e acrescenta um
followup "reportado de novo por <reporter> em <data>" (`POST
.../Timeline/Followup`, endpoint já validado). 🔍 A busca por `filter=` é
sugerida na referência (`2026-09-21-glpi-api-feedback-reference.md`, linha
69) e **não foi validada ao vivo**: é o primeiro item do plano. Se não
funcionar, fallback: buscar por `name` igual nos últimos 7 dias. Dedup só
dentro do tenant (o hash já carrega `tenant_id`).

**Falhas → códigos MCP** (o kit só precisa distinguir dois casos):

| GLPI | tool devolve | kit faz |
|---|---|---|
| 201 | `ok` | mostra número + link |
| resposta não-JSON (NPM em manutenção), 5xx, rede, token recusado | `McpToolError("upstream_unavailable", …)` | fallback do `gap.md` (issue/texto) e diz que o GLPI não respondeu |
| `reporter_*` ausente, categoria inválida | `validation_failed` | bug do kit; corrige e reenvia |

Nunca 500 do MCP por falha do GLPI (mesma regra do console: `GlpiError` vira
resposta controlada).

**Fora desta versão, de propósito:**

- **Anexo.** O trecho de log vai no corpo, já redigido. A tool não recebe
  binário. Quando receber, o servidor está na rede dokploy e a API v1 funciona
  (`attach_document` já existe no cliente).
- **Acompanhar status.** O kit devolve número e link; status é no link.
- **Followup pelo kit.** Só o de dedup, automático.

## 4. Kit — gatilho, consentimento, conteúdo, retorno (repo agenteos-dev-kit)

Três gatilhos. Todos terminam numa **pergunta**; nada abre chamado sem "sim"
ao rascunho inteiro.

1. **Gap do `gap.md`.** Já é o ponto onde o kit para. O canal 1 continua sendo
   `mcp_client.feedback(...)`; o que muda é o retorno (número + link) e o
   registro no cabeçalho do rascunho.
2. **MCP falhando duas vezes no mesmo passo.** `spec_write`, `spec_validate`,
   `spec_test_run` ou `spec_publish` devolvendo `McpClientError` com código de
   servidor (`internal`, `upstream_unavailable`, HTTP 5xx, sem código) **duas
   vezes seguidas no mesmo passo**. Não conta: `validation_failed`,
   `not_found`, `unauthorized` (são do autor ou da chave). Se o próprio MCP
   está fora, o chamado não sobe por ele: o kit diz isso na frase e cai no
   fallback de texto.
3. **O usuário pede.** "travou", "bug", "abre um chamado", ou `/reportar` —
   comando da skill, sempre disponível, sem heurística.

**Rascunho que o usuário aprova** — as duas camadas do `gap.md` §3, sem
mudança: uma frase em negócio; o pedido técnico com classe entre colchetes,
passo/linha da ficha, tool/conector **por nome**, código de erro, seção do
ARMADILHAS. Antes de mostrar, a redação mecânica do `gap.md` §4 (sem
`default:` de conexão, UUID, payload, conteúdo de run, CPF, PIX, segredo).

**Reportante.** Na primeira vez, o kit pergunta nome e e-mail e grava em
`.claude/agentos-builder.local.json` (`{"reporter_name": …, "reporter_email": …}`),
entrada no `.gitignore`. Não é segredo; é o que vai no corpo do chamado. As
próximas vezes só confirma.

**Retorno.** "Chamado #N aberto: <url>" ou "Já existe o #N para isto: <url>".
No cabeçalho do rascunho: `# Gap reportado: glpi #N — <data>`. Sem `gh` e
sem MCP: `# Gap reportado: texto — <data>`, como hoje.

**Cliente.** `mcp_client.feedback(category, message, context)` não muda de
assinatura; passa a exigir `reporter_name`/`reporter_email` no `context`
(`ValueError` local, antes da rede) e devolve o dict com `ticket_id`/`url`.

## 5. Testes

**Plataforma (Agente_OS):**

- `FakeGlpi` sobe para `cdm` com o cliente e ganha `GET /Assistance/Ticket`
  com `filter=external_id==` e o `POST .../Followup`. Mantém a página HTML de
  manutenção (lição PR #168: fake fiel, nunca stub conveniente).
- Testes da tool: erro → type 1; melhoria/feedback → type 2; segundo relato
  igual → `deduplicated: true` + followup; HTML de manutenção →
  `upstream_unavailable`; `reporter_*` ausente → `validation_failed`;
  `external_id` estável para a mesma entrada e diferente entre tenants.
- Testes do api-gateway continuam passando após a mudança de import.
- **Smoke real** contra `glpi.totvstbc.com.br` com um chamado de teste
  fechado em seguida — é o que valida o `filter=` e é o gate do plano.

**Kit (scripts stdlib, como os existentes):**

- `test_mcp_client_feedback.py`: `reporter_*` ausente não chega na rede; com
  eles, o `context` viaja inteiro; retorno com `ticket_id` é repassado.
- `test_gap_redacao.py` (novo, mínimo): dado um texto com UUID de conexão,
  `default:` e um CPF, a função de redação (a criar em `scripts/gap_redact.py`,
  regex stdlib) devolve o texto sem eles. É a única lógica do kit que precisa
  de teste; os gatilhos são texto de referência, provados por sessão.

## 6. Documentação

- **Kit:** `gap.md` ganha "o chamado" (retorno, dedup, o que fazer se o GLPI
  não respondeu) e o gatilho 2; `SKILL.md` ganha `/reportar` no router;
  `README.md` fecha a nota de escopo do `spec_feedback` e diz que gap vira
  chamado; `ARMADILHAS.md` ganha uma seção curta: "GLPI responde HTML com 200
  quando o NPM está em manutenção — o MCP traduz para `upstream_unavailable`".
- **Guia Keycloak/GLPI:** capítulo "O dev-kit abre chamado", entregue como
  fragmento HTML pronto para colar em `~/shared/keycloak-glpi-guia.html`
  (fonte na VM do Gianluka). Publicação por `scp` para
  `agente-requisitos:/root/docker/guias/html/` fica com o Gianluka.

## 7. Onde cada parte é executada

| Parte | Repo | Depende de |
|---|---|---|
| Mover `glpi.py` + `FakeGlpi` para `cdm`; estender `spec_feedback`; testes; smoke | Agente_OS | — |
| Deploy do mcp-server com `glpi_*` no env do spoke | infra do spoke | parte 1 |
| `feedback()` exige `reporter_*`; `gap_redact.py`; `gap.md`/`SKILL.md`/README/ARMADILHAS | agenteos-dev-kit | contrato da parte 1 (pode ser escrito em paralelo contra o `FakeGlpi`) |
| Capítulo do guia | HTML entregue no kit em `docs/guia/glpi-chamado.html` | parte 3 |

O plano de implementação será um por repo. A parte 1 é repassada à sessão que
cuida do Agente_OS com este spec como contrato.

## 8. Riscos aceitos

- **`filter=external_id==` não funciona na v2.** Mitigação: fallback por
  `name` em 7 dias; o smoke real decide antes de qualquer merge.
- **Reportante é auto-declarado.** Quem tria vê nome e e-mail que o autor
  digitou. Aceito: o tenant é verificado pela chave; identidade forte exige
  chave por pessoa (descartado no brainstorm).
- **Sentry deixa de ver relatos de autoria.** Aceito pela decisão "tudo vai
  para o GLPI". O `sentry-monitor` continua vendo erros de plataforma, que não
  passam por esta tool.
- **Gatilho de 2 falhas pode disparar em instabilidade passageira.** Aceito:
  é sugestão, não abertura; o usuário decide.
