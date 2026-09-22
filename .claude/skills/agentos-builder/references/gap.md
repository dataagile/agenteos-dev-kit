# Gap — parar, explicar, reportar, retomar

Quando a derivação (`create.md`) ou o test run (`proposta.md`) esbarra em algo
que o ambiente não tem, o kit **para naquele ponto**. Nunca entrega rascunho
parcial como pronto. Nunca contorna com código, serviço externo ou "faz na mão".

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

A `message` vai **crua** ao Sentry. Confira, linha a linha, que **não** há:

- valor de `default:` de conexão, nem UUID de conexão
- payload de conexão, host, usuário, token
- conteúdo de run (corpo de resposta, dado de cliente)
- CPF, chave PIX, segredo

Se precisar citar o conector, cite o **nome** (`"SFTP Protheus TBC — DEV"`),
nunca o id. Se precisar citar erro, cite o **código** (`CONNECTOR_ERROR`),
nunca o corpo.

## 5. Canal, em ordem

1. **`mcp_client.feedback(category, message, context)`** — `category`:
   `"erro"` se algo que devia funcionar falhou; `"melhoria"` se falta recurso.
   `context={"slug": slug, "version": "0.1", "run_id": "<se veio de um test
   run>", "tool": "<tool/nó que travou>"}`. Cai na esteira do time interno sem
   passar por ninguém.
2. Se `mcp_client.feedback()` levantar `McpClientError` — **qualquer** erro,
   inclusive `code="unauthorized"`: hoje não há confirmação de que
   `spec_feedback` cavalga nos 6 scopes de autoria (README, "a confirmar no
   sandbox"), então um 401 aqui é tão possível quanto qualquer outra falha, e
   não há nada a perder tentando o fallback: `gh issue create --label gap
   --title "<classe> <uma linha>" --body "<pedido técnico>"` no repositório do
   kit.
3. Se nem `gh` houver: entregue o pedido técnico pronto para o analista
   repassar, e diga a quem.

Registre no cabeçalho do rascunho qual canal foi usado:
`# Gap reportado: feedback|issue #N|texto — <data>`.

## 6. Retomar

Quando o gap fechar: `read_spec`, remova `# Pendente:` e `# Gap reportado:`,
volte à linha da tabela de derivação que travou, siga até o roteiro.
