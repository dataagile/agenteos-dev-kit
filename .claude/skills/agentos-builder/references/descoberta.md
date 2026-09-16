# Descoberta — fase 0 do Create

Antes de perguntar `slug`, `trigger` ou nó, descubra o **domínio**. Esta fase
existe porque a entrevista do `create.md` pergunta campos de schema, e campo de
schema é resposta — não pergunta. Quem não sabe o que o negócio faz responde
campo por campo e descobre tarde que o grafo inteiro estava errado.

Destilado de Domain-Driven Design (Evans, 2003) para o tamanho de UM agente.
Não é Event Storming de projeto: são quatro rodadas curtas. O produto é a
**ficha de domínio**, que vira o cabeçalho do YAML e responde sozinha às
perguntas do `create.md`.

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
   pedir — segure até a rodada 4.
5. **Questione, não agrade.** Se dois termos parecem o mesmo conceito, pare e
   resolva antes de seguir. Ambiguidade de palavra vira ambiguidade de nó.

## Rodada 1 — Propósito e gatilho

- Que trabalho **uma pessoa faz hoje na mão** que este agente vai fazer? Descreva
  uma execução real, do começo ao fim.
- **O que acontece no mundo** que faz esse trabalho começar? (alguém pede, chega
  um arquivo, é dia 5, caiu um e-mail)
- Como você sabe, no fim, que **deu certo**? E como saberia que deu errado?

→ Preenche `description`, decide `trigger.type` e já diz se o disparo carrega
conteúdo de humano (segure isso para a rodada 3).

## Rodada 2 — Linguagem ubíqua

Liste com o usuário os **termos do negócio** que apareceram na rodada 1. Para
cada um que não for óbvio: o que é, o que **não** é, e um exemplo.

- Existe termo que duas áreas usam com sentido diferente? Qual sentido vale aqui?
- Tem termo que o sistema chama de um jeito e a pessoa chama de outro? **Vence a
  pessoa.**

→ Esse glossário é o vocabulário do `name`, dos `id`/`key` dos nós e dos `title`
/`description` de cada property do `config_schema`. Property com nome que o
operador não reconhece é retrabalho garantido na tela de configuração.

> Regra prática: se o usuário precisa traduzir o nome do nó para explicar o que
> ele faz, o nome está errado. Renomeie agora, que ainda é de graça.

## Rodada 3 — Invariantes e a fronteira da escrita

A rodada que paga a fase inteira. Três perguntas, nessa ordem:

- **O que nunca pode acontecer?** ("nunca apagar arquivo que não foi conferido",
  "nunca pagar duas vezes", "nunca mandar e-mail para cliente errado")
- **Quem autoriza?** Uma pessoa precisa olhar antes? Sempre, ou só acima de um
  limite? Quem é essa pessoa?
- **O que o agente ESCREVE** em algum sistema, e o que ele só lê?

Cada resposta aqui fecha uma armadilha conhecida — leve-as para o desenho:

| Descoberta | Consequência no desenho | Armadilha |
|---|---|---|
| Existe escrita | Precisa de `approval` e a escrita gateada em `<nó>.decision.decision == 'approved'` | §1, §4 |
| Existe alçada ("só acima de X") | `when` do approval só com a gramática de condition; forma reconhecida e falsa dispensa o humano | §4 |
| O disparo vem de chat/humano | Esse conteúdo **não pode** alcançar um nó de escrita (`untrusted_input_in_write`) | §5 |
| Escreve via conexão | Conferir `allowed_ops` e `base_dir` no `spec_connectors` antes de desenhar o path | §6 |
| Algum passo usa LLM | Saída é string; `{{}}` no texto derruba a escrita seguinte; parse fica no serviço | §16, §17, §19 |
| Um passo externo pode falhar | `http_request` que falha **não** aborta; nó `agent` aborta | §18 |

Se a resposta de "o que nunca pode acontecer" não virar um `condition` ou um
`approval` no grafo, ou ela não era invariante, ou o grafo está incompleto.
Volte e pergunte de novo.

## Rodada 4 — Fronteiras: o que é do agente e o que não é

- Que sistemas **de fora** entram nessa história? (ERP, Drive, Fluig, SFTP, banco)
- Desse trabalho todo, **o que já existe pronto** em algum lugar? Agente bom
  orquestra o que existe; só constrói o que é diferencial.
- O que precisa ficar **registrado** depois que rodar? Quem vai ler isso?
- O que é decidido pelo **autor da spec** (fixo) e o que o cliente escolhe na
  **ativação**? (o segundo é `config_schema`; o primeiro é literal no YAML)

> Trabalho que é transformação de dado pesada — parsear JSON de LLM, gerar
> `.docx`, aplicar template complexo — **não é do grafo**. Vai para uma operation
> no serviço (§19). Descobrir isso aqui evita uma spec de 800 linhas que não roda.

## Produto: a ficha de domínio

Feche a fase com a ficha abaixo, confirmada pelo usuário em uma frase por linha.
Ela **vira o cabeçalho do YAML** (o `create.md` já exige um bloco de comentário)
e alimenta a entrevista de campos sem precisar perguntar de novo.

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
```

Regra de saída: **campo da ficha em branco é pergunta não respondida**, não
detalhe menor. Não comece o `create.md` com a ficha incompleta — o custo de
descobrir isso depois é reescrever o grafo, e a §3 diz o que custa publicar
errado.

## Quando pular esta fase

- O usuário já chega com o processo escrito e sabe dizer a invariante → confirme
  a ficha em uma rodada só e siga.
- Agente de teste/probe descartável, sem escrita → pule; a ficha é uma linha.
- Ajuste em agente que já existe → não é Create, é `edit.md`. Reabra só a linha
  da ficha que mudou.
