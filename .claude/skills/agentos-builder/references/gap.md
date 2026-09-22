# Gap — parar, explicar, reportar, retomar

Quando um dos gatilhos do §0 dispara, o kit **para naquele ponto**. Nunca entrega rascunho
parcial como pronto. Nunca contorna com código, serviço externo ou "faz na mão".

## 0. Quando o kit sugere — e nunca abre sozinho

Três gatilhos. Todos terminam numa **pergunta** com o rascunho inteiro (§3)
na tela; o chamado só é aberto se o usuário responder que sim.

1. **Gap.** `create.md` ou `proposta.md` esbarra em recurso que o ambiente
   não tem. É o caso deste arquivo inteiro.
2. **MCP falhando duas vezes no mesmo passo.** `spec_write`, `spec_validate`,
   `spec_test_run` ou `spec_publish` levanta `McpClientError` com `code` em
   `internal`, `upstream_unavailable`, HTTP 5xx, ou sem `code` — **duas vezes
   seguidas no mesmo passo**. Não conta: `validation_failed`, `not_found`,
   `unauthorized` (são da spec ou da chave, não da plataforma). Classe
   `[plataforma]`. Se o próprio MCP está fora, o chamado não sobe por ele:
   diga isso na frase e vá direto ao canal 2 ou 3 do §5.
3. **O usuário pede.** "travou", "bug", "abre um chamado", ou `/reportar`.
   Sem heurística; pergunte a classe se não estiver óbvia.

Erro de git, python, rede local ou de um comando fora do MCP **não** dispara
sugestão: é do ambiente de quem autora.

## 1. Classificar

| Classe | Quem resolve | Exemplos |
|---|---|---|
| `[ambiente]` | Admin do ambiente do cliente | conexão que não existe em `connectors()`; modelo com `available: false` |
| `[plataforma]` | Time do Agente_OS | tool fora de `platform_tools`; strategy de `transform` inexistente; nó `runtime_ready: false`; transformação que exige operation no serviço (§19) |
| `[kit]` | Time do kit | pergunta que a descoberta não soube fazer; armadilha nova; regra de derivação que não cobre o caso |

A classe é sugestão; quem tria reencaminha.

## 2. Gravar o rascunho retomável

Antes de reportar, regrave o rascunho com a linha pendente no cabeçalho:

```
# Pendente: <linha da ficha que travou> — <o que falta, em uma frase>
```

`mcp_client.write_draft(slug, "0.1", content, templates)`. É o que permite
retomar quando o gap fechar: `read_spec`, achar `# Pendente:`, continuar da
linha.

## 3. Duas camadas

**Para o analista, uma frase.** O que o agente precisa, o que falta, o que dá
para fazer enquanto isso:

> O agente precisa mandar arquivo para o SFTP da Caixa, e o ambiente ainda não
> tem essa conexão. Pedi ao time. Enquanto isso posso montar a versão que só
> consulta e avisa — quer?

Se o analista aceitar a versão reduzida, a ficha registra: `# Reduzido: <o que
saiu> — <por quê>`. Não é a versão final; é a que roda hoje.

**Para o time interno, o pedido técnico**, nesta ordem, uma linha cada:

1. classe entre colchetes (primeira linha, obrigatório)
2. passo/linha da ficha que travou
3. o que o catálogo devolveu — **nome** de tool/conector/strategy e **código**
   de erro, nunca corpo de resposta
4. seção do ARMADILHAS aplicável, se houver
5. o que destravaria (uma frase)

## 4. Redação mecânica — antes de qualquer envio

A `message` vai **crua** ao chamado do GLPI. Passe o pedido técnico por
`python3 scripts/gap_redact.py` (stdin → stdout) ou `gap_redact.redact(texto)`
**antes** de montar o rascunho, e confira o resultado: **não** pode haver:

- valor de `default:` de conexão, nem UUID de conexão
- payload de conexão, host, usuário, token
- conteúdo de run (corpo de resposta, dado de cliente)
- CPF, chave PIX, segredo
- números de 11 dígitos nus somem (a redação os trata como CPF) — cite pedido, chamado ou nota **com prefixo ou pontuação** (ex.: "pedido nº 2026-0922-001"), nunca como 11 dígitos contíguos

Se precisar citar o conector, cite o **nome** (`"SFTP Protheus TBC — DEV"`),
nunca o id. Se precisar citar erro, cite o **código** (`CONNECTOR_ERROR`),
nunca o corpo.

## 5. Canal, em ordem

**Reportante, uma vez.** O chamado precisa de "Reportado por". Leia
`.claude/agentos-builder.local.json` na raiz do repositório; se não existir ou
faltar chave, pergunte nome e e-mail e grave:

```json
{"reporter_name": "Ana Analista", "reporter_email": "ana@cliente.com.br"}
```

O arquivo está no `.gitignore`; não é segredo, é o que vai no corpo do
chamado. Nas próximas vezes só confirme ("continua sendo Ana?").

1. **`mcp_client.feedback(category, message, context)`** — a plataforma abre
   o chamado no GLPI (o kit não tem credencial). `category`: `"erro"` se algo
   que devia funcionar falhou (vira Incidente); `"melhoria"` se falta recurso
   (vira Requisição). `context`:

   ```python
   {"reporter_name": ..., "reporter_email": ...,          # obrigatórios
    "slug": slug, "version": "0.1",
    "tool": "<tool/nó que travou>", "step": "<derivacao|test_run|publish>",
    "run_id": "<se veio de um test run>", "kit_version": "<metadata.version do SKILL.md>"}
   ```

   Retorno `{"ticket_id": N, "url": ..., "deduplicated": bool}`. Diga ao
   usuário: `Chamado #N aberto: <url>`, ou, se `deduplicated`, `Já existe o
   #N para isto: <url>` (a plataforma acrescentou um followup com o novo
   relato). Cabeçalho do rascunho: `# Gap reportado: glpi #N — <data>`.
2. Se `feedback()` levantar `McpClientError` — **qualquer** código, inclusive
   `upstream_unavailable` (o GLPI não respondeu) e `unauthorized` — não há
   nada a perder tentando o fallback: `gh issue create --label gap --title
   "<classe> <uma linha>" --body "<pedido técnico redigido>"` no repositório
   do kit. Cabeçalho: `# Gap reportado: issue #N — <data>`.
3. Se nem `gh` houver: entregue o pedido técnico redigido para o usuário
   repassar, e diga a quem (time interno da TBC). Cabeçalho:
   `# Gap reportado: texto — <data>`.

## 6. Retomar

Quando o gap fechar: `read_spec`, remova `# Pendente:` e `# Gap reportado:`,
volte à linha da tabela de derivação que travou, siga até o roteiro.
