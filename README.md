# AgenteOS — Dev Kit

Kit de partida para **desenvolver agentes AgenteOS** num ambiente de sandbox.
Você não precisa (e não recebe) o código da plataforma nem os agentes internos:
**toda a autoria acontece via MCP**, contra o servidor do seu ambiente.

Fluxo validado ao vivo contra um ambiente real em 13/08/2026.

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

As demais tools não têm escopo próprio — cavalgam nestes: `spec_context`,
`spec_models`, `spec_connectors` e `spec_tools` em `spec.read`; `spec_revise`
em `spec.write` (é o `required_scope` declarado no registry do servidor; uma
chamada real com a chave de 6 scopes acima autorizou no ambiente de
validação em 14/08/2026). A lista acima já autoriza a superfície inteira.

## Conectando o Claude Code

O endpoint é o **`/mcp`** do SEU ambiente (JSON-RPC sobre TLS). A URL e a chave
são fornecidas pelo admin da plataforma — não há endpoint padrão, e apontar para
o ambiente errado é a primeira coisa que dá 401:

```bash
claude mcp add --transport http agenteos \
  https://<SEU-AMBIENTE>/mcp \
  --header "Authorization: Bearer <SUA_CHAVE>"
```

Para os scripts da skill (`.claude/skills/agentos-builder/scripts/mcp_client.py`):

```bash
export MCP_URL=https://<SEU-AMBIENTE>   # sem /mcp — o client acrescenta
export MCP_KEY=<SUA_CHAVE>
```

## Autorando

Abra o Claude Code **neste repositório** e use a skill:

```
/agentos-builder criar um agente que <o que você quer>
```

A skill conduz o ciclo completo, sempre via MCP:

0. **Descoberta** — o analista responde em linguagem de negócio: o que a
   pessoa faz hoje na mão, o que liga o agente, o que nunca pode acontecer,
   quem autoriza, o que lê e o que escreve. Duas perguntas de triagem decidem
   se é uma rodada ou três. O produto é a **ficha de domínio**, gravada no
   cabeçalho do rascunho desde a primeira linha
   ([`descoberta.md`](.claude/skills/agentos-builder/references/descoberta.md)).
1. **Derivação** — o kit consulta o ambiente (`spec_node_types`, `spec_context`,
   `spec_connectors`, `spec_tools`, `spec_models`, sempre ao vivo) e deriva o
   YAML inteiro da ficha, cada regra citando a seção do `ARMADILHAS.md` que a
   justifica. O analista não vê slug, nó nem `when`
   ([`create.md`](.claude/skills/agentos-builder/references/create.md)).
2. **Proposta** — o agente volta como roteiro, uma linha por passo, em negócio;
   o analista corrige em negócio e fecha com duas perguntas (caminho escolhido,
   alternativa descartada)
   ([`proposta.md`](.claude/skills/agentos-builder/references/proposta.md)).
3. **Prova** — `spec_test_run` no rascunho, trace traduzido para o analista.
   Publicar só com run verde.
4. **Publicação** — `spec_publish`, com guard mecânico que recusa conexão com
   `default`. **A publicação já entra no catálogo do ambiente na hora**.

Faltou recurso no ambiente em qualquer ponto: o kit para, explica em uma frase,
reporta pela tool `spec_feedback` (a mesma do megafone da tela) e deixa o
rascunho retomável
([`gap.md`](.claude/skills/agentos-builder/references/gap.md)).

Para mudar um agente já publicado: `spec_revise` (abre a PRÓXIMA versão em
draft semeada da última published — published é imutável), e daí o ciclo
normal 2→3→4. Não requer escopo extra: `spec.write` cobre.

O rascunho e a publicação **persistem no servidor** (volume durável — sobrevivem
a redeploy). A pasta `drafts/` deste repo é para o seu trabalho local/backup;
a fonte da verdade é o store do ambiente.

Um exemplo mínimo que passou pelo ciclo inteiro está em
[`examples/sbx-hello/v1.yaml`](examples/sbx-hello/v1.yaml).

Um exemplo **completo**, validado ponta a ponta contra um SFTP real em 26/08/2026, está em
[`examples/test-sftp/v4.yaml`](examples/test-sftp/v4.yaml): nó `sftp_op` (put/move/delete/list)
com aprovação humana obrigatória antes de escrever, gate da escrita na decisão do humano
(`aprovar.decision.decision`), `when` por operação e template de resposta. O cabeçalho do
arquivo explica cada decisão de desenho e o que foi medido em runtime — inclusive por que ele
NÃO tem nó `agent`. Os tropeços do caminho estão em [`ARMADILHAS.md`](ARMADILHAS.md).

Para conectar a APIs externas (Google via app da plataforma, Fluig oauth1a, cadastro
por API, o que o botão "Testar" mente), leia [`docs/conexoes.md`](docs/conexoes.md).
As consultas de leitura mínimas que devolvem 200 estão em
[`examples/http-leitura/v1.yaml`](examples/http-leitura/v1.yaml).

## Limitações conhecidas

> 📌 **Leia [`ARMADILHAS.md`](ARMADILHAS.md) antes de publicar o primeiro agente.**
> Cada uma custou tempo de alguém: o veredito do approval está duas camadas
> abaixo do que parece, um approval que gera item sem `action` derruba a fila de
> aprovações inteira, e um publish rejeitado ainda queima o número da versão.

- **Não existe unpublish/delete pelo MCP** (DAI-637): o que você publicar fica
  no catálogo do ambiente. Limpar exige um admin com acesso ao volume — pelo
  caminho de autoria, **o número da versão está queimado**. Valide bem antes do
  `spec_publish`; não conte com desfazer.
- **`spec_publish` não é atômico:** o arquivo é gravado ANTES da validação do
  catálogo. Publish recusado ("nada foi semeado") ainda deixa a versão no disco,
  imutável — some com o número. Detalhe e checklist em `ARMADILHAS.md` §3.
- Cada nó da spec deve ter `id` **e** `key` com o mesmo valor (compatibilidade
  entre as duas camadas de validação em imagens antigas).

## Regra de ouro

**Zero código do core.** Se para autorar você sentir falta de algo da
plataforma, isso é um gap do MCP Server — reporte ao time da plataforma
(Jira DAI), nunca contorne.
