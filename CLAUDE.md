# agenteos-dev-kit — regras

Repositório de **autoria de agentes** via MCP. Só specs de trabalho do dev
(YAML + templates) e a skill `/agentos-builder`.

## Não-negociável

- **Toda operação de spec passa pelo MCP** (`/agentos-builder`): list, read,
  write, validate, publish. Sem fallback a filesystem quando o MCP falhar —
  reporte o erro.
- **Zero import/código do core da plataforma.** Falta algo para autorar =
  gap do MCP Server — reportar ao time da plataforma, não contornar.
- Publicado é imutável por versão: mudança = `spec_revise` (abre a próxima
  versão em draft a partir da published) + ciclo write→validate→publish.
- Um agente = `<slug>/vN.yaml` + `templates/` ao lado (unidade autocontida).

## Conexão

`MCP_URL` + `MCP_KEY` no ambiente (ver README). Endpoint JSON-RPC: `{MCP_URL}/mcp`.
