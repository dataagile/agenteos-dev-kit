# Autoria pelo analista — descoberta conduz, o kit monta

**Data:** 2026-09-17
**Estado:** proposta, para revisão de Gianluka e João Vitor antes de qualquer PR
**Baseline:** `main` em `5daca20` (#21 mergeado, com a tabela de tradução e o
fecho de duas perguntas trazidos do #19; #20 com a §4 re-medida após DAI-918,
que mantém a regra da seção 5: `when` reconhecido e falso pula o humano por
desenho, e o gate no veredito cobre)

## 1. O problema que sobrou depois do #21

O #21 pôs a descoberta antes do Create. Mas o Create continua sendo uma
entrevista **com o humano** em linguagem de dev: slug, `config_schema`, tipo de
nó, `when`. Quem vai sentar na frente do kit é analista de negócio, sem dev. Para
essa pessoa, a fase 0 hoje é uma boa conversa seguida de uma parede.

Três consequências que este desenho resolve:

- O analista não fecha um agente sozinho. Depois da ficha, precisa de um dev.
- A ficha vive só no chat até o YAML existir. Se a sessão cai no meio, some.
- Quando falta algo no ambiente, o kit não tem saída formal: ou o autor
  contorna, ou desiste. A regra de ouro do kit ("gap = reportar, não contornar")
  não tem caminho concreto.

## 2. Decisões tomadas no brainstorm

| Pergunta | Resposta | Consequência |
|---|---|---|
| Quem conduz a descoberta? | Analista de negócio, sem dev | Tudo o que o humano vê é linguagem de negócio |
| Quem monta o agente? | O próprio analista, com o kit propondo tudo | O Create deixa de ser entrevista e vira procedimento interno do kit |
| O que fazer num gap técnico? | O kit atende tudo; gap vira feedback para o time interno | Saída formal de gap, fail-closed, com rascunho retomável |

Abordagens descartadas:

- **Descoberta separada, Create como hoje.** Exige dev depois. Contradiz a
  segunda decisão.
- **Portão do #19 com arquivos locais** (`prd.md`, `spec.md`, `gate.json`). O
  analista não opera git, o MCP não transporta esses arquivos, e o desenho
  chamava skills (`/ddd` Modo 1 e 2, `/como-fazer`) que não existem fora dos
  plugins da TBC. O que valia dele já entrou no #21: tradução e fecho.

## 3. O fluxo, visto pelo analista

Cinco momentos. Em nenhum deles aparece slug, nó, `when` ou `config_schema`.

### 3.1 Triagem

Duas perguntas antes de tudo:

1. Esse agente **escreve** em algum sistema (cria, muda, apaga, envia) ou só
   consulta e informa?
2. O processo tem **regra que muda por caso** (valor, cliente, dia, tipo)?

Não escreve e não tem regra condicional: descoberta **curta**, uma rodada, ficha
de cinco linhas (Trabalho, Começa quando, Lê, Termina bem, Descartado). Qualquer outra resposta: descoberta **completa**, as três
rodadas do `descoberta.md` atual.

A triagem existe porque o relatório de origem (seção 7) diz que descoberta em
projeto simples vira overhead, e a maior parte das specs do AgentOS é automação,
não domínio de cliente.

### 3.2 Descoberta

O `descoberta.md` de hoje, sem mudança de conteúdo. Muda só a persistência
(seção 4): a ficha vai sendo gravada no rascunho conforme fecha.

### 3.3 Proposta

Com a ficha fechada, o kit faz sozinho o que o `create.md` hoje pergunta:

1. Discovery do ambiente (`node_types`, `context`, `connectors`, `tools`,
   `models`), sempre ao vivo.
2. Deriva o YAML inteiro da ficha pelas regras da seção 5.
3. Valida pelo MCP.
4. Apresenta ao analista como **roteiro**, uma linha por passo, em negócio:

> Liga toda segunda às 7h. Busca os títulos vencidos no ERP. Se não achar
> nenhum, avisa e para. Monta a lista e **para para pedir seu ok**. Só depois do
> ok envia a remessa ao banco. No fim, manda o resumo por e-mail.

Cada linha corresponde a um nó, mas o analista vê o roteiro. Ele corrige em
negócio ("não é segunda, é dia 5"); o kit rederiva.

### 3.4 Decisão

As duas perguntas que já estão no `descoberta.md`: qual caminho escolheu, o que
descartou e por quê. Entram na ficha. Sem a segunda, não segue.

### 3.5 Prova e publicação

O kit roda `spec_test_run` no rascunho e **traduz o trace** para o analista:
"rodou, buscou 12 títulos, parou no ponto de aprovação como esperado". Só oferece
publicar depois de run verde. Se o run parou em `awaiting_approval`, explica que
isso é o desenho funcionando (ARMADILHAS §13: test run de draft não é decidível)
e que a prova da escrita vem depois da ativação.

Publicar continua sendo decisão explícita do humano. A §3 do ARMADILHAS torna o
gate inegociável: publicar errado queima a versão.

## 4. Onde a descoberta vive: no rascunho, desde cedo

Nada em arquivo local. A memória é o rascunho no MCP.

- Assim que a linha **Trabalho** da ficha é confirmada, o kit propõe `name`,
  deriva o `slug`, **checa colisão** com `spec_list` e grava um rascunho mínimo
  válido (`description`, `trigger`, um nó) com a ficha no cabeçalho.
- A cada linha da ficha fechada, `spec_write` de novo. O YAML cresce junto.
- Sessão que cai no meio: o kit lê o rascunho, encontra a ficha parcial no
  cabeçalho e retoma da primeira linha em branco.
- Reabrir uma decisão é regravar o rascunho com a ficha alterada. Publicado é
  `spec_revise`, como qualquer mudança.

Isso resolve de graça o defeito de ordenação apontado no #19 (gravar em
`drafts/<slug>/` antes de validar o slug): aqui o slug nasce validado, porque a
primeira gravação já passa pelo MCP.

Limite conhecido: `spec_test_run` não recebe `config` (ARMADILHAS §9,
Agente_OS#777). Conexões no rascunho de teste continuam entrando por `default:`
marcado `# REMOVER antes de publicar`. O kit faz isso sozinho e **remove antes
do publish**, sem o analista saber que existiu.

## 5. Regras de derivação: da ficha ao YAML

O `create.md` deixa de perguntar e passa a derivar. Cada linha da ficha decide
algo; cada decisão cita a seção do ARMADILHAS que a justifica.

| Linha da ficha | Deriva | Regra |
|---|---|---|
| Trabalho | `name`, `slug`, `description`, `id = agt_<slug>_v<major>` | `id` estável entre versões (§3) |
| Começa quando | `trigger.type` e seus campos | enum vindo de `node_types().trigger`; `schedule` exige cron |
| Termos | `id`/`key` dos nós; `title`/`description` das properties | mesmo valor em `id` e `key` (§8) |
| Lê | `io.reads`; nós de leitura (`tool`/`http_request`/`sftp_op`/`erp_query`) | `connector_id` só de `spec_connectors`; `tool_name` só de `platform_tools` |
| Escreve | `io.writes`; nós de escrita **sempre precedidos** de `approval` | escrita gateada em `<nó>.decision.decision == 'approved'` (§1, §4) |
| Autoriza | `approval` com `context_from` apontando o passo que lista; alçada via `config.when` **só** na gramática de condition | §2 (item sem `action` derruba a inbox), §4 |
| Começa quando = chat | nenhum `{{run.input.*}}` alcança nó de escrita | §5 |
| Escreve via conexão | ler `allowed_ops` e `base_dir` antes de compor path | §6 |
| Nunca pode | um `condition` ou `approval` que a proteja; se não houver onde encaixar, a ficha está errada | `descoberta.md` rodada 2 |
| Fora do grafo | não vira nó; se exigir operation no serviço, vira **gap** (seção 6) | §19 |
| Termina bem | último nó `render_template` com o resumo; `.j2` só com o que `spec_context` resolve | §8 (templates viajam no mesmo write) |

Regras transversais, aplicadas sem perguntar:

- Todo passo externo que pode falhar ganha um `condition` no `status` antes do
  consumidor (§18: `http_request` que falha não aborta).
- Nó `agent` só com campos dentro de `config` (§16); prompt instrui a nunca
  emitir `{{}}` (§17).
- `change_class: minor` no `0.1.0`. Major é conversa com o admin antes (§3).
- Property do `config_schema` sempre com `title` e `description` (lint D-02).

O analista nunca vê esta tabela. Ela é o contrato entre a ficha e o YAML, e é o
que faz o ARMADILHAS.md deixar de ser leitura passiva.

## 6. Gap: parar, explicar, reportar, retomar

Quando a derivação esbarra em algo que o ambiente não tem, o kit **para naquele
ponto**. Nunca entrega rascunho parcial como pronto.

Saída em duas camadas:

- **Para o analista, uma frase:** o que o agente precisa, o que falta, o que dá
  para fazer enquanto isso. Se houver versão reduzida (ex.: só leitura), o kit
  oferece, e a ficha registra que é reduzida e por quê.
- **Para o time interno, o pedido técnico:** passo que travou, o que o catálogo
  devolveu, a seção do ARMADILHAS aplicável, e a classe do gap.

| Classe | Quem resolve | Exemplo |
|---|---|---|
| Ambiente do tenant | Admin do ambiente | Conexão inexistente, modelo indisponível |
| Plataforma | Time do Agente_OS | Tool fora do catálogo, transformação que exige operation no serviço |
| Kit | Time do kit | Pergunta que o kit não soube fazer, armadilha nova |

Canal, em ordem de preferência:

1. **Tool de feedback no MCP** (`spec_feedback`, já exposta no servidor
   `agenteos`: `category: erro|melhoria|feedback`, `message` até 4000
   caracteres, `context: {slug, version, run_id, tool}`; vai para o Sentry com
   `source=mcp`). É o mesmo mecanismo do megafone da tela do AgenteOS, e cai na
   esteira de manutenção do time interno sem passar por ninguém. É o que fecha
   o ciclo para um analista sem `gh` nem git. Regras de uso, que vão para o
   `gap.md`:
   - `context` sempre com `{slug, version}` do rascunho retomável e `tool` do
     passo que travou; é o vínculo gap ↔ rascunho, sem texto livre.
   - A classe do gap (ambiente / plataforma / kit) não tem campo na tool: vai
     como prefixo fixo na primeira linha da `message` (`[ambiente]`,
     `[plataforma]`, `[kit]`).
   - **Redação mecânica antes de chamar:** a `message` vai crua ao Sentry. Nunca
     incluir valor de `default:` de conexão, payload de conexão, conteúdo de
     run, CPF, chave PIX ou segredo. "O que o catálogo devolveu" entra como
     nome de tool/conector e código de erro, nunca como corpo de resposta.
2. **Issue no repositório do kit** com etiqueta `gap`, aberta com `gh` quando
   disponível e autenticado. Fallback de **indisponibilidade** do MCP, não de
   inexistência da tool.
3. **Texto pronto** para o analista repassar, quando nem 1 nem 2 estão
   disponíveis.

O rascunho fica gravado com o passo pendente marcado no cabeçalho, para retomar
quando o gap fechar.

Referência do tamanho que um relato de gap pode ter: o PRD de 18/09/2026 do
José Miguel (TBC) lista dezesseis requisitos, cada um com run de evidência,
levantados autorando um agente real pelo kit. Vários coincidem com gaps já
registrados aqui (#13, fechada, = RF-09 = Agente_OS#777; §18 = RF-05), e o RF-13 contradiz a §11 do
ARMADILHAS. É esse tipo de relato que o canal existe para receber cedo, item a
item, em vez de um documento no fim.

O time interno tria a issue: se for de plataforma ou de ambiente, reencaminha.
O kit não tenta adivinhar o destino final; a classe é sugestão.

## 7. O que muda nos arquivos

| Arquivo | Mudança |
|---|---|
| `references/descoberta.md` | Ganha a triagem (3.1) no topo e a regra de gravar a ficha no rascunho a cada linha (4). Conteúdo das rodadas fica como está. |
| `references/create.md` | Reescrito: de entrevista a procedimento interno. A seção "Interview flow" vira "Derivação" com a tabela da seção 5. O "Write sequence" fica. |
| `references/proposta.md` | **Novo.** Como traduzir o grafo derivado para o roteiro (3.3) e como traduzir o trace do test run de volta (3.5). |
| `references/gap.md` | **Novo.** Formato do pedido nas duas camadas, tabela de classes, comando `gh` e fallback. |
| `SKILL.md` | Router com `proposta` e `gap`. Regra nova: "o humano nunca responde campo de schema". Versão 0.5.0 → 0.6.0. |
| `README.md` | O ciclo em quatro passos passa a descrever os cinco momentos da seção 3. |
| `CLAUDE.md` | A regra de ouro ganha o caminho concreto: gap vira issue `gap`. |

Sem terceira exceção ao MCP-only: não há arquivo local novo. `Backup` e `Remove`
seguem como estão.

Fora de escopo, de propósito: mudar o MCP (parâmetro `config` no test run,
`spec_instance_config`). Continua sendo Agente_OS#777.

## 8. Como provar

Três sessões reais no sandbox, com `spec_test_run`, sem publicar:

1. **Curto.** "Quero um agente que lista os arquivos da pasta X e me avisa." Deve
   cair na descoberta curta, produzir rascunho válido e run verde sem nenhuma
   pergunta de schema.
2. **Completo.** Agente com escrita e alçada. Deve sair com `approval` gateado no
   veredito e `when` na gramática certa, sem o analista ter visto a palavra
   `when`. Ficha inteira no cabeçalho.
3. **Gap forçado.** Pedir conexão que não existe. Deve parar, gerar as duas
   camadas, abrir (ou entregar) a issue e deixar o rascunho retomável.

📏 23/09/2026: provas 1 e 2 feitas (`examples/prova-lista-sftp`, `examples/prova-move-sftp`; runs `f6994f26` e `61faf8fb`), com seis achados devolvidos ao kit (ARMADILHAS §21). A prova 3 ficou coberta pelo canal GLPI (#31, chamado #242).

Os três provam que o mecanismo funciona. **Não provam** que o analista entende o
roteiro. Isso só uma sessão com uma pessoa não-dev responde, e é o primeiro
teste a fazer depois do merge.

## 9. Riscos aceitos

- **O kit deriva errado e o analista confirma sem perceber.** Mitigação: o
  roteiro nomeia explicitamente onde o agente para para pedir ok e o que ele
  nunca faz; são as duas linhas que o analista sabe julgar. O test run é a
  segunda barreira.
- **Descoberta curta pega agente que devia ser completo.** Mitigação: se a
  derivação encontrar escrita ou regra condicional numa ficha curta, o kit
  reabre a descoberta completa. A triagem é entrada, não veredito.
- **`default:` de conexão esquecido no publish.** Mitigação: o passo de publish
  do kit recusa qualquer property `x-ref: connection` com `default` (regra
  mecânica, não confiança).
