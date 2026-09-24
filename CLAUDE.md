# agenteos-dev-kit — regras

Repositório de **autoria de agentes** via MCP. Só specs de trabalho do dev
(YAML + templates) e a skill `/agentos-builder`.

## Não-negociável

- **Toda operação de spec passa pelo MCP** (`/agentos-builder`): list, read,
  write, validate, publish, revise e a discovery (node_types, context,
  connectors, tools, models). Sem fallback a filesystem quando o MCP falhar —
  reporte o erro.
- **Zero import/código do core da plataforma.** Falta algo para autorar =
  gap — reportar, não contornar. O caminho é `references/gap.md`: parar,
  gravar `# Pendente:` no rascunho, montar o rascunho do chamado já redigido,
  **perguntar**, e só depois do "sim" abrir o chamado no GLPI pela tool
  `spec_feedback` (fallback: issue `gap` neste repo); retomar quando fechar.
- Publicado é imutável por versão: mudança = `spec_revise` (abre a próxima
  versão em draft a partir da published) + ciclo write→validate→publish.
- Um agente = `<slug>/vN.yaml` + `templates/` ao lado (unidade autocontida).

## Antes de publicar

Leia [`ARMADILHAS.md`](ARMADILHAS.md) — armadilhas **medidas ao vivo (📏) ou
verificadas no código da plataforma (🔍)**, cada uma marcada com a sua origem.
As três que mais custam tempo:

1. O veredito do approval é `aprovar.decision.decision`, não `aprovar.decision`
   (o de fora é o dict do item). Comparar errado = humano aprova e nada escreve.
2. Approval que gera item sem `action` derruba a `/inbox` do tenant INTEIRA —
   inclusive os itens dos outros agentes (📏 medido). O approval mínimo (sem
   `config.context_from`) **aparentemente** é o que produz item vazio — elo lido
   no código, ainda não provado por run: ver `ARMADILHAS.md` §2.
3. `spec_publish` grava o arquivo ANTES de validar o catálogo: publish recusado
   ainda queima o número da versão, e não há unpublish. O `id` da spec é ESTÁVEL
   entre versões — mudá-lo é a causa mais comum da recusa.

E uma que não custa tempo, custa segurança: **`when` em nó `approval` só com
caminhos `config.*`** (📏 caminho de passo vale `None` ali e a aprovação é pulada; §21) **e só com a
gramática de condition** (`len()`, `== 'str'`, `== null` e negações). Até
DAI-918 qualquer outra forma (`>`, truthiness pura, `!= true`, um typo) avaliava
`False` e **pulava a aprovação humana** sem erro; 📏 re-medido em 15/09/2026, a
forma ilegível agora EXIGE o humano. Mas uma forma reconhecida e falsa dispensa
por desenho, e copiar `!= true` de um nó normal continua sendo o erro mais
provável. Detalhe e as duas tabelas na §4.

📏 E há um segundo caminho, que não exige erro do autor: passo anterior que
falha esvazia o `context_from` e o approval vem `skipped` por `empty_context` —
run segue como aprovado. **A defesa que cobre os dois é gatear a escrita no
veredito** (`<nó>.decision.decision == 'approved'`), nunca na presença do nó.

Ao descobrir uma armadilha nova, **acrescente lá** — o kit é o que impede o
próximo autor de repetir o mesmo tropeço.

## Conexão

`MCP_URL` + `MCP_KEY` no ambiente (ver README). Endpoint JSON-RPC: `{MCP_URL}/mcp`.
