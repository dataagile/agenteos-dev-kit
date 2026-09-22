# Descoberta — fase 0 do Create

Antes de perguntar `slug`, `trigger` ou nó, descubra o **domínio**. Esta fase é
a única conversa com o humano no fluxo de Create — `create.md` não pergunta
nada, só deriva a partir da ficha que esta fase produz. Quem não sabe o que o
negócio faz responde campo por campo e descobre tarde que o grafo inteiro
estava errado.

Destilado de Domain-Driven Design (Evans, 2003) para o tamanho de UM agente.
Não é Event Storming de projeto: são uma triagem, até três rodadas curtas e uma decisão. O
produto é a **ficha de domínio**, que vira o cabeçalho do YAML e é a única
entrada da derivação em `create.md`.

## Falando com quem decide

Quem responde essa entrevista **normalmente não é dev** — é analista de negócio.
Nunca use termo de schema com essa pessoa. Memorize a tabela, não a repita para
o usuário:

| Termo técnico | Como falar |
|---|---|
| trigger | o que "liga" o agente — todo dia num horário, quando algo acontece, ou só quando alguém manda |
| node / nó | um passo da receita que o agente segue, em ordem |
| io (reads/writes) | o que ele vai buscar / o que ele entrega no fim |
| config_schema | os ajustes que dá pra mudar depois, sem chamar o dev de novo |
| approval | um ponto onde ele para e pede seu ok antes de continuar |
| invariante | o que nunca pode acontecer, nem que tudo dê errado |

## Regras da conversa (não negociáveis)

1. **Nunca modele tecnologia.** Nesta fase não existe nó, conexão, `config_schema`
   nem template. Existe "quem faz o quê, quando, e o que não pode acontecer".
   Se o usuário responder "aí chama a API do Drive", devolva a pergunta em termos
   de negócio: "o que a pessoa precisa encontrar lá?".
2. **Poucas perguntas por vez.** Uma rodada = no máximo três perguntas. Espere a
   resposta. Nunca despeje a entrevista inteira.
3. **Não aceite resposta superficial.** Pergunte o exemplo, a exceção e o caso
   ruim. "E quando não tem nada para listar?" acha mais bug do que qualquer
   validação.
4. **Descubra antes de decidir.** Não proponha o grafo na rodada 1. O usuário vai
   pedir — segure até a decisão do fim.
5. **Questione, não agrade.** Se dois termos parecem o mesmo conceito, pare e
   resolva antes de seguir. Ambiguidade de palavra vira ambiguidade de nó.

## Triagem — duas perguntas antes de tudo

1. Esse agente **escreve** em algum sistema (cria, muda, apaga, envia) ou só
   consulta e informa?
2. O processo tem **regra que muda por caso** (valor, cliente, dia, tipo)?

| Resposta | Rota | Ficha |
|---|---|---|
| Não escreve **e** não tem regra por caso | **curta**: Rodada 1 + Decisão (as duas perguntas de fecho rodam sempre) | Trabalho, Começa quando, Lê, Termina bem, Descartado |
| Qualquer outra | **completa**: Rodadas 1, 2 e 3 | todas as linhas |

Na rota curta, a linha **Lê** é preenchida a partir da execução real descrita
na Rodada 1 (o que a pessoa consulta e onde), sem pergunta extra; **Descartado**
vem da Decisão. As linhas que a rota curta não pergunta (Escreve, Autoriza,
Nunca pode, Fora do grafo) não ficam em branco: `create.md` as grava como
`(nenhum)`/`(não se aplica)`, e `Termos` deriva dos verbos de Trabalho — ver a
nota acima da tabela de derivação em `create.md`.

A triagem existe porque descoberta em agente simples vira overhead, e a maior
parte dos agentes do AgenteOS é automação, não domínio de cliente. **A triagem
é entrada, não veredito:** se a derivação (`create.md`) encontrar escrita ou
regra condicional numa ficha curta, reabra a Rodada 2 antes de seguir.

## Rodada 1 — Propósito e gatilho

- Que trabalho **uma pessoa faz hoje na mão** que este agente vai fazer? Descreva
  uma execução real, do começo ao fim.
- **O que acontece no mundo** que faz esse trabalho começar? (alguém pede, chega
  um arquivo, é dia 5, caiu um e-mail)
- Como você sabe, no fim, que **deu certo**? E como saberia que deu errado?

→ Preenche `description`, decide `trigger.type` e já diz se o disparo carrega
conteúdo de humano (segure isso para a rodada 2).

→ Anote os **termos do negócio** que aparecerem, com as palavras do usuário: são
o vocabulário dos `id`/`key` dos nós e dos `title`/`description` do
`config_schema`. Se o usuário precisa traduzir o nome do nó para explicar o que
ele faz, o nome está errado — renomeie agora, que ainda é de graça.

## Rodada 2 — Invariantes e a fronteira da escrita

A rodada que paga a fase inteira. Três perguntas, nessa ordem:

- **O que nunca pode acontecer?** ("nunca apagar arquivo que não foi conferido",
  "nunca pagar duas vezes", "nunca mandar e-mail para cliente errado")
- **Quem autoriza?** Uma pessoa precisa olhar antes? Sempre, ou só acima de um
  limite? Quem é essa pessoa?
- **O que o agente ESCREVE** em algum sistema, e o que ele só lê?

Cada resposta aqui fecha uma armadilha conhecida — leve-as para o desenho. Os
`§` são seções do [`ARMADILHAS.md`](../../../../ARMADILHAS.md), na raiz do repo:

| Descoberta | Consequência no desenho | `ARMADILHAS.md` § |
|---|---|---|
| Existe escrita | `approval` + escrita gateada em `<nó>.decision.decision == 'approved'` | §1, §4 |
| Existe alçada ("só acima de X") | `when` do approval só com a gramática de condition — forma ilegível **dispensa o humano** | §4 |
| O disparo vem de chat/humano | `{{run.input.*}}` em nó de escrita mata o run (`untrusted_input_in_write`) | §5 |
| Escreve via conexão | conferir `allowed_ops`/`base_dir` antes de desenhar o path | §6 |
| Algum passo usa LLM | saída é string; parse fica no serviço | §16, §17, §19 |
| Um passo externo pode falhar | `http_request` que falha não aborta; nó `agent` aborta | §18 |

Se a resposta de "o que nunca pode acontecer" não virar um `condition` ou um
`approval` no grafo, ou ela não era invariante, ou o grafo está incompleto.
Volte e pergunte de novo.

## Rodada 3 — Fronteira do grafo

- Que sistemas **de fora** entram nessa história? (ERP, Drive, Fluig, SFTP, banco)
- O que é decidido pelo **autor da spec** (fixo no YAML) e o que o cliente
  escolhe na **ativação** (`config_schema`)?

> Transformação de dado pesada — parsear JSON de LLM, gerar `.docx`, template
> complexo — **não é do grafo**. Vai para uma operation no serviço (§19).
> Descobrir isso aqui evita uma spec de 800 linhas que não roda.

## Decisão — antes de fechar a ficha

Confira primeiro que o desenho **existe no ambiente**: `mcp_client.node_types()`,
`connectors()` e `models()` (a mesma discovery que o `create.md` faz). Forma
impossível descoberta aqui custa uma pergunta; descoberta no meio da derivação
custa o grafo inteiro.

Aí feche com duas perguntas — uma frase cada:

1. **Qual caminho você escolheu?**
2. **Qual alternativa você descartou, e por quê?**

Sem a segunda resposta a fase não fecha: quem não sabe dizer o que descartou
ainda não decidiu, só olhou uma opção. As duas respostas entram na ficha.

## Produto: a ficha de domínio

Feche a fase com a ficha abaixo, confirmada pelo usuário em uma frase por linha.
Ela **é o cabeçalho do YAML** — já está gravada no rascunho linha a linha (ver
"Onde a ficha vive") — e é a única entrada do `create.md`: a derivação lê a
ficha, não pergunta nada ao humano.

```text
# FICHA DE DOMÍNIO — <nome do agente>
# Trabalho:      <o que a pessoa faz hoje na mão>
# Começa quando: <evento do mundo>            -> trigger
# Termos:        <termo = significado; ...>   -> nomes de nó e de config
# Nunca pode:    <invariante>                 -> condition/approval que protege
# Autoriza:      <quem, e a partir de quando> -> approval + alçada
# Lê:            <o quê, de onde>             -> io.reads
# Escreve:       <o quê, onde>                -> io.writes (vazio = sem approval)
# Fora do grafo: <o que é do serviço/do humano>
# Termina bem:   <como se sabe que deu certo>
# Descartado:    <alternativa, e por que não>
```

Regra de saída: **campo da ficha em branco é pergunta não respondida**, não
detalhe menor. Não comece o `create.md` com a ficha incompleta — o custo de
descobrir isso depois é reescrever o grafo, e a §3 diz o que custa publicar
errado.

## Onde a ficha vive: no rascunho, desde a primeira linha

Nada em arquivo local. A memória é o rascunho no MCP.

1. Assim que a linha **Trabalho** é confirmada: proponha `name`, derive o `slug`
   (kebab-case do nome), **cheque colisão** com `mcp_client.list_specs()` e
   grave um rascunho mínimo válido com `mcp_client.write_draft(slug, "0.1",
   content, templates)` — `description`, `trigger`, um nó `render_template` com
   um `.j2` de uma linha enviado no mesmo `templates` (§8: `write_draft` sem
   `templates` grava `templates: []` e a spec quebra em execução) — com a ficha
   parcial como cabeçalho (linhas ainda não respondidas ficam com `<pendente>`).
2. A cada linha da ficha confirmada: `write_draft` de novo, mesma versão, só o
   cabeçalho muda. O YAML cresce junto na fase de derivação.
3. Sessão que cai no meio: `mcp_client.read_spec(slug, "0.1")`, leia o
   cabeçalho, retome da primeira linha `<pendente>`.
4. Reabrir uma decisão é regravar o rascunho com a ficha alterada. Publicado é
   `spec_revise`, como qualquer mudança.

O slug nasce validado porque a primeira gravação já passa pelo MCP — não existe
pasta local a criar antes de o slug ser confirmado.

## Quando pular esta fase

- O usuário já chega com o processo escrito e sabe dizer a invariante → confirme
  a ficha em uma rodada só e siga.
- Ajuste em agente que já existe → não é Create, é `edit.md`. Reabra só a linha
  da ficha que mudou.
