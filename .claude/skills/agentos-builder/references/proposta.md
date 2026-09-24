# Proposta — o que o analista vê

Depois da derivação (`create.md`), o humano recebe **um roteiro**, nunca o YAML.
Uma linha por nó, em linguagem de negócio, usando os termos da ficha (linha
"Termos"). Slug, nó, `when` e `config_schema` não aparecem.

## 1. Montar o roteiro

Leia o rascunho (`mcp_client.read_spec(slug, "0")`) e traduza nó a nó, na
ordem do grafo, com a tabela abaixo. O vocabulário dentro de cada linha vem do
glossário "Falando com quem decide" de `descoberta.md` e da linha "Termos" da
ficha:

| Nó | Como falar |
|---|---|
| trigger `schedule` | "Liga <cadência em palavras: toda segunda às 7h / todo dia 5>." |
| trigger `chat` | "Liga quando alguém pede no chat." |
| trigger `event`/`webhook`/`email` | "Liga quando <evento da ficha> acontece." |
| nó de leitura | "Busca <o que a ficha diz que lê> em <sistema>." |
| `condition` de status (guarda com `on_true`) | "Se não conseguir buscar, não faz o passo seguinte e avisa no fim." |
| `transform` | "Separa/organiza <o que a strategy faz, em palavras>." |
| `approval` | "**Para e pede o ok de <quem autoriza>**<, só acima de <alçada>>." |
| `condition` no veredito | (não vira linha — está implícito na anterior) |
| nó de escrita | "Só depois do ok, <o que escreve> em <onde>." |
| escrita pulada pela guarda (`condition_guard`) | (não vira linha — o template final diz "não foi aprovado, nada foi feito") |
| `render_template` final | "No fim, entrega <o resumo>." |
| `agent` | "Lê <entrada> e escreve <saída>, com apoio de IA." |

Exemplo:

> Liga toda segunda às 7h. Busca os títulos vencidos no ERP. Se não conseguir,
> avisa e para. Monta a lista e **para e pede o ok do financeiro**. Só depois do
> ok, envia a remessa ao banco. Se não for aprovado, avisa e não faz nada. No
> fim, entrega o resumo por e-mail.

Feche o roteiro com duas linhas fixas, que são as que o analista sabe julgar:

- **Onde ele para para pedir ok:** <lista, ou "em lugar nenhum — este agente só consulta">
- **O que ele nunca faz:** <a linha "Nunca pode" da ficha>

## 2. Correção em negócio

O analista corrige em negócio ("não é segunda, é dia 5"; "quem aprova é o
gerente, não o financeiro"). Você atualiza a linha correspondente da **ficha**
no cabeçalho, **re-deriva** (`create.md`), regrava e reapresenta o roteiro.
Nunca edite um nó "na mão" sem passar pela ficha — a ficha é a fonte.

## 3. Decisão

As duas perguntas do fecho de `descoberta.md`, uma frase cada:

1. Qual caminho você escolheu?
2. Qual alternativa você descartou, e por quê?

Sem a segunda, não segue. As respostas vão para a linha "Descartado" da ficha.

## 4. Prova: test run traduzido

Antes de chamar `spec_test_run`: se o `config_schema` do rascunho tiver alguma
property marcada `x-company-scoped`, passe `erp_company_id` junto. Peça esse id
ao **admin do ambiente** — nunca ao analista, não é pergunta de negócio. Sem
ele o run cai na empresa default do tenant, que num sandbox costuma não ter
parâmetro nenhum preenchido e morre em `COMPANY_CONFIG_INCOMPLETE` (§9).

Chame a tool MCP `spec_test_run(slug, "0"[, erp_company_id])` → `run_id`;
depois `spec_run_status(run_id)` até `status` sair de `received`/`running`.
Traduza o trace para o analista, um passo por linha:

| `steps[].status` / `status` do run | Como falar |
|---|---|
| passo `completed`/`ok` | "<nome do passo em negócio>: rodou." (+ um número se houver: "buscou 12 títulos") |
| passo `skipped` com `reason: condition_jump` ou `condition_guard` | "<passo>: não precisou rodar" / "<escrita>: não foi feita porque não houve aprovação." |
| passo `skipped` com `reason: when_false` | "<passo>: pulado pela regra <alçada em palavras>." |
| passo `skipped` com `reason: empty_context` | "**Atenção:** a lista veio vazia e a aprovação foi pulada. Confira o passo anterior." (§4) |
| run `awaiting_approval` | "Parou no ponto de aprovação, como esperado. Em teste não dá para aprovar (§13); a prova da escrita vem depois da ativação." |
| run `failed` com `COMPANY_CONFIG_INCOMPLETE` | "Rodou na empresa errada, ou sem empresa: confirmar o `erp_company_id` com o admin. **Não é gap.**" (§9) |
| passo `failed` / run `failed` | "<passo>: falhou — <mensagem do erro em uma frase>." Depois: `gap.md` se for recurso do ambiente; senão corrija a ficha e re-derive. |
| run `completed` sem escrita | "Rodou até o fim." |

**Só ofereça publicar depois de run verde** (`completed`, ou `awaiting_approval`
quando há aprovação). Antes de `publish.md`, remova todo `default:` de property
`x-ref: connection` que a fase de teste tenha colocado — o guard do publish
recusa se sobrar. Publicar continua sendo decisão explícita do humano; a §3
diz o que custa publicar errado.
