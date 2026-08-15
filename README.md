# AgenteOS — Dev Kit

Kit de partida para **desenvolver agentes AgenteOS** num ambiente de sandbox.
Você não precisa (e não recebe) o código da plataforma nem os agentes internos:
**toda a autoria acontece via MCP**, contra o servidor do seu ambiente.

Fluxo validado ao vivo contra o sandbox da TBC em 13/08/2026.

## O que você precisa

| Item | Quem fornece |
|------|--------------|
| Usuário no ambiente (convite por e-mail) | Admin da plataforma |
| Chave MCP de **autoria** (6 scopes) | Admin da plataforma |
| Este repositório | — |
| Claude Code (ou outro cliente MCP) | Você |

A chave de autoria precisa exatamente destes scopes — menos que isso dá 401
"Tool fora do escopo":

```
spec.list spec.read spec.node_types spec.validate spec.write spec.publish
```

## Conectando o Claude Code

O endpoint é o **`/mcp`** do ambiente (JSON-RPC sobre TLS):

```bash
claude mcp add --transport http agenteos-sandbox \
  https://sandbox-tbc.dataagile.com.br/mcp \
  --header "Authorization: Bearer <SUA_CHAVE>"
```

Para os scripts da skill (`.claude/skills/agentos-builder/scripts/mcp_client.py`):

```bash
export MCP_URL=https://sandbox-tbc.dataagile.com.br   # sem /mcp — o client acrescenta
export MCP_KEY=<SUA_CHAVE>
```

## Autorando

Abra o Claude Code **neste repositório** e use a skill:

```
/agentos-builder criar um agente que <o que você quer>
```

A skill conduz o ciclo completo, sempre via MCP:

1. `spec_node_types` / `spec_context` / `spec_connectors` / `spec_tools` /
   `spec_models` — descobrir o que existe no ambiente (nunca de memória:
   `connector_id` vem do `spec_connectors`, `tool_name` do `spec_tools`);
2. `spec_write` — gravar o rascunho (`drafts/<slug>/v<N>.yaml` no servidor;
   os `.j2` viajam junto no parâmetro `templates`, como `{nome: conteúdo}`);
3. `spec_validate` — validar (`{ok: true}` libera; erros vêm com `field_path`);
4. `spec_publish` — publicar. **A publicação já entra no catálogo do ambiente
   na hora** (não há passo manual de seed).

Para mudar um agente já publicado: `spec_revise` (abre a PRÓXIMA versão em
draft semeada da última published — published é imutável), e daí o ciclo
normal 2→3→4. Não requer escopo extra: `spec.write` cobre.

O rascunho e a publicação **persistem no servidor** (volume durável — sobrevivem
a redeploy). A pasta `drafts/` deste repo é para o seu trabalho local/backup;
a fonte da verdade é o store do ambiente.

Um exemplo mínimo que passou pelo ciclo inteiro está em
[`examples/sbx-hello/v1.yaml`](examples/sbx-hello/v1.yaml).

## Limitações conhecidas

- **Não existe unpublish/delete** (DAI-637): o que você publicar fica no
  catálogo do ambiente. Valide bem antes do `spec_publish`; versão errada
  publicada exige limpeza manual pelo admin.
- Cada nó da spec deve ter `id` **e** `key` com o mesmo valor (compatibilidade
  entre as duas camadas de validação em imagens antigas).

## Regra de ouro

**Zero código do core.** Se para autorar você sentir falta de algo da
plataforma, isso é um gap do MCP Server — reporte ao time da plataforma
(Jira DAI), nunca contorne.
