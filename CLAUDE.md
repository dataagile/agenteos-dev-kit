# agenteos-dev-kit — regras

Repositório de **autoria de agentes** via MCP. Só specs de trabalho do dev
(YAML + templates) e a skill `/agentos-builder`.

## Não-negociável

- **Toda operação de spec passa pelo MCP** (`/agentos-builder`): list, read,
  write, validate, publish, revise e a discovery (node_types, context,
  connectors, tools, models). Sem fallback a filesystem quando o MCP falhar —
  reporte o erro.
- **Zero import/código do core da plataforma.** Falta algo para autorar =
  gap do MCP Server — reportar ao time da plataforma, não contornar.
- Publicado é imutável por versão: mudança = `spec_revise` (abre a próxima
  versão em draft a partir da published) + ciclo write→validate→publish.
- Um agente = `<slug>/vN.yaml` + `templates/` ao lado (unidade autocontida).

## Antes de publicar

Leia [`ARMADILHAS.md`](ARMADILHAS.md) — armadilhas medidas ao vivo, com as
consequências reais. As três que mais custam tempo:

1. O veredito do approval é `aprovar.decision.decision`, não `aprovar.decision`
   (o de fora é o dict do item). Comparar errado = humano aprova e nada escreve.
2. Approval que gera item sem `action` derruba a `/inbox` do tenant INTEIRA —
   inclusive os itens dos outros agentes. E o approval MÍNIMO (sem
   `config.context_from`) é justamente o que produz item vazio: todo autor
   começando cai nisto.
3. `spec_publish` grava o arquivo ANTES de validar o catálogo: publish recusado
   ainda queima o número da versão, e não há unpublish. O `id` da spec é ESTÁVEL
   entre versões — mudá-lo é a causa mais comum da recusa.

Ao descobrir uma armadilha nova, **acrescente lá** — o kit é o que impede o
próximo autor de repetir o mesmo tropeço.

## Conexão

`MCP_URL` + `MCP_KEY` no ambiente (ver README). Endpoint JSON-RPC: `{MCP_URL}/mcp`.
