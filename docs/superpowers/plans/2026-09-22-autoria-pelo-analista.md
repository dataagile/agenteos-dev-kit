# Autoria pelo analista — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O analista de negócio cria um agente ponta a ponta pelo kit sem ver campo de schema: a descoberta conduz, o kit deriva o YAML, apresenta como roteiro, prova com test run e reporta gap pela tool `spec_feedback`.

**Architecture:** A skill `agentos-builder` é prompt em Markdown (`SKILL.md` + `references/*.md`) com um cliente MCP em Python (`scripts/mcp_client.py`). Quase tudo aqui é texto de referência que o modelo segue; só duas peças são código: a função `feedback()` no cliente e o guard mecânico de publish que recusa `default` em property `x-ref: connection`. Nada grava arquivo local novo: a ficha vive no cabeçalho do YAML no MCP.

**Tech Stack:** Markdown; Python 3 stdlib (testes são scripts `assert`, rodados com `python3 tests/<arquivo>.py` de dentro de `.claude/skills/agentos-builder/`; não há pytest instalado).

**Spec:** `docs/superpowers/specs/2026-09-17-autoria-pelo-analista-design.md`

## Global Constraints

- Toda operação de spec passa pelo MCP; sem fallback a filesystem quando o MCP falhar (CLAUDE.md).
- Zero import/código do core da plataforma.
- Sem terceira exceção ao MCP-only: nenhum arquivo local novo por agente (spec §7).
- `SKILL.md` `metadata.version`: `"0.5.0"` → `"0.6.0"`.
- Tool de gap: `spec_feedback(category: erro|melhoria|feedback, message ≤ 4000, context: {slug, version, run_id, tool})`; `message` vai crua ao Sentry — nunca `default:` de conexão, payload, conteúdo de run, CPF, PIX, segredo (spec §6).
- Classe do gap por prefixo fixo na primeira linha da `message`: `[ambiente]`, `[plataforma]`, `[kit]`.
- Ficha de domínio: os onze rótulos de `references/descoberta.md` (Trabalho, Começa quando, Termos, Nunca pode, Autoriza, Lê, Escreve, Fora do grafo, Termina bem, Descartado) mais a linha `Pendente:` para gap (Task 6).
- Todo commit termina com `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Branch de trabalho: `feat/autoria-pelo-analista`, a partir de `origin/main` (`806711e` ou posterior). Um PR ao final.

---

## File structure

| Arquivo | Responsabilidade | Task |
|---|---|---|
| `.claude/skills/agentos-builder/scripts/mcp_client.py` | ganha `feedback()` | 1 |
| `.claude/skills/agentos-builder/tests/test_mcp_client_feedback.py` | prova o shape da chamada sem rede | 1 |
| `.claude/skills/agentos-builder/scripts/publish_guard.py` | recusa `x-ref: connection` com `default` | 2 |
| `.claude/skills/agentos-builder/tests/test_publish_guard.py` | prova aceita/recusa | 2 |
| `.claude/skills/agentos-builder/references/descoberta.md` | triagem no topo; ficha gravada no rascunho por linha | 3 |
| `.claude/skills/agentos-builder/references/create.md` | de entrevista a derivação | 4 |
| `.claude/skills/agentos-builder/references/proposta.md` | roteiro de negócio; tradução do trace | 5 |
| `.claude/skills/agentos-builder/references/gap.md` | duas camadas, classes, canal | 6 |
| `.claude/skills/agentos-builder/references/publish.md` | chama o guard antes do publish | 2 |
| `.claude/skills/agentos-builder/SKILL.md` | router, regra nova, versão | 7 |
| `README.md`, `CLAUDE.md` | cinco momentos; caminho concreto do gap | 7 |

---

### Task 1: `feedback()` no cliente MCP

**Files:**
- Modify: `.claude/skills/agentos-builder/scripts/mcp_client.py` (após `publish()`, linha ~219)
- Test: `.claude/skills/agentos-builder/tests/test_mcp_client_feedback.py`

**Interfaces:**
- Consumes: `_call(tool: str, params: dict) -> dict` (já existe; troca `.` por `_` no nome da tool).
- Produces: `feedback(category: str, message: str, context: dict[str, str] | None = None) -> dict[str, Any]`. Levanta `ValueError` se `category` não está em `{"erro", "melhoria", "feedback"}` ou `len(message) > 4000`. Task 6 chama esta função.

- [ ] **Step 1: Write the failing test**

```python
"""feedback(): valida category/message localmente e monta a chamada certa. Sem rede.

Rodar: python3 tests/test_mcp_client_feedback.py (de dentro da pasta da skill).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import mcp_client as m  # noqa: E402

calls = []
m._call = lambda tool, params: calls.append((tool, params)) or {"ok": True}

# chamada mínima
out = m.feedback("melhoria", "[kit] falta pergunta X")
assert out == {"ok": True}, out
assert calls[-1] == ("spec.feedback", {"category": "melhoria", "message": "[kit] falta pergunta X"}), calls[-1]

# context viaja inteiro
m.feedback("erro", "[plataforma] tool fora do catálogo", context={"slug": "s", "version": "1", "tool": "x.y"})
assert calls[-1][1]["context"] == {"slug": "s", "version": "1", "tool": "x.y"}, calls[-1]

# category inválida não chega na rede
n = len(calls)
try:
    m.feedback("bug", "x")
    raise AssertionError("devia levantar ValueError")
except ValueError:
    pass
assert len(calls) == n

# message > 4000 não chega na rede
try:
    m.feedback("erro", "a" * 4001)
    raise AssertionError("devia levantar ValueError")
except ValueError:
    pass
assert len(calls) == n

print("test_mcp_client_feedback: ok")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .claude/skills/agentos-builder && python3 tests/test_mcp_client_feedback.py`
Expected: `AttributeError: module 'mcp_client' has no attribute 'feedback'`

- [ ] **Step 3: Write minimal implementation**

Append after `publish()` in `scripts/mcp_client.py`:

```python
_FEEDBACK_CATEGORIES = ("erro", "melhoria", "feedback")


def feedback(category: str, message: str, context: dict[str, str] | None = None) -> dict[str, Any]:
    """Reporta gap de autoria pela tool `spec_feedback` (mesmo megafone da tela;
    vai ao Sentry com source=mcp). `message` vai CRUA — nunca inclua `default:`
    de conexão, payload, conteúdo de run, CPF, PIX ou segredo (references/gap.md).
    Primeira linha da message leva a classe: [ambiente] | [plataforma] | [kit]."""
    if category not in _FEEDBACK_CATEGORIES:
        raise ValueError(f"category deve ser um de {_FEEDBACK_CATEGORIES}, veio {category!r}")
    if len(message) > 4000:
        raise ValueError(f"message tem {len(message)} chars; máximo 4000")
    params: dict[str, Any] = {"category": category, "message": message}
    if context:
        params["context"] = context
    return _call("spec.feedback", params)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .claude/skills/agentos-builder && python3 tests/test_mcp_client_feedback.py`
Expected: `test_mcp_client_feedback: ok`

- [ ] **Step 5: Run the existing tests to confirm nothing broke**

Run: `cd .claude/skills/agentos-builder && python3 tests/test_mcp_client_error_parse.py`
Expected: `test_mcp_client_error_parse: ok`

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/agentos-builder/scripts/mcp_client.py .claude/skills/agentos-builder/tests/test_mcp_client_feedback.py
git commit -m "feat(mcp_client): feedback() — gap de autoria pela tool spec_feedback

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: guard mecânico de publish — `x-ref: connection` com `default` é recusado

**Files:**
- Create: `.claude/skills/agentos-builder/scripts/publish_guard.py`
- Test: `.claude/skills/agentos-builder/tests/test_publish_guard.py`
- Modify: `.claude/skills/agentos-builder/references/publish.md` (seção "Steps", entre o passo 1 e o passo 2)

**Interfaces:**
- Consumes: nada do cliente MCP; recebe o YAML como string.
- Produces: `connection_defaults(content: str) -> list[str]` — nomes das properties do `config_schema` com `x-ref: connection` **e** `default`. Lista vazia = pode publicar. Sem dependência de PyYAML: parse por regex de indentação, suficiente para o formato que o kit escreve (uma property por bloco, `x-ref:` e `default:` como chaves diretas da property).

- [ ] **Step 1: Write the failing test**

```python
"""publish_guard.connection_defaults(): acha property x-ref: connection com default. Sem rede.

Rodar: python3 tests/test_publish_guard.py (de dentro da pasta da skill).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
from publish_guard import connection_defaults  # noqa: E402

COM_DEFAULT = """
config_schema:
  type: object
  properties:
    connection_sftp_id:
      type: string
      x-ref: connection
      default: "b744c7bc-3e62-4a58-b85d-492d1bd3190b"   # REMOVER antes de publicar
      title: "Conexão SFTP"
    pasta:
      type: string
      default: "entrada"
      title: "Pasta"
nodes: []
"""
assert connection_defaults(COM_DEFAULT) == ["connection_sftp_id"], connection_defaults(COM_DEFAULT)

SEM_DEFAULT = """
config_schema:
  type: object
  properties:
    connection_sftp_id:
      type: string
      x-ref: connection
      title: "Conexão SFTP"
    pasta:
      type: string
      default: "entrada"
nodes: []
"""
assert connection_defaults(SEM_DEFAULT) == [], connection_defaults(SEM_DEFAULT)

DUAS = """
config_schema:
  properties:
    a:
      x-ref: connection
      default: "x"
    b:
      default: "y"
      x-ref: connection
    c:
      x-ref: connection
"""
assert connection_defaults(DUAS) == ["a", "b"], connection_defaults(DUAS)

assert connection_defaults("nodes: []\n") == []

print("test_publish_guard: ok")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .claude/skills/agentos-builder && python3 tests/test_publish_guard.py`
Expected: `ModuleNotFoundError: No module named 'publish_guard'`

- [ ] **Step 3: Write minimal implementation**

`scripts/publish_guard.py`:

```python
"""Guard mecânico do publish (spec §9): property `x-ref: connection` com
`default` NUNCA vai para published — conexão vem da ativação. O `default`
só existe em draft de teste porque spec_test_run não recebe config (ARMADILHAS §9).

Uso: python3 scripts/publish_guard.py <arquivo.yaml>  → exit 1 e lista se houver.
Sem PyYAML de propósito: parse por indentação, suficiente para o YAML que o kit escreve.
"""
import re
import sys


def connection_defaults(content: str) -> list[str]:
    """Nomes das properties do config_schema que têm x-ref: connection E default."""
    found: list[str] = []
    prop: str | None = None
    prop_indent = -1
    has_xref = has_default = False

    def close() -> None:
        if prop and has_xref and has_default:
            found.append(prop)

    for raw in content.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        key = line.strip()
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*$", key)
        if m and (prop is None or indent <= prop_indent):
            close()
            prop, prop_indent = m.group(1), indent
            has_xref = has_default = False
            continue
        if prop is not None and indent > prop_indent:
            if re.match(r"^x-ref:\s*connection\b", key):
                has_xref = True
            elif re.match(r"^default:", key):
                has_default = True
    close()
    return found


if __name__ == "__main__":
    text = open(sys.argv[1], encoding="utf-8").read()
    bad = connection_defaults(text)
    if bad:
        print("publish recusado — x-ref: connection com default:", ", ".join(bad))
        sys.exit(1)
    print("publish_guard: ok")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .claude/skills/agentos-builder && python3 tests/test_publish_guard.py`
Expected: `test_publish_guard: ok`

- [ ] **Step 5: Wire the guard into `publish.md`**

In `references/publish.md`, section "Steps (in order — do not skip or reorder)", insert a new step between the current step 1 (re-validate) and step 2 (collision check), and renumber the following steps 2→3, 3→4, 4→5, 5→6, 6→7:

```markdown
2. **Guard de conexão (mecânico, não confiança).** Rode
   `python3 scripts/publish_guard.py <draft.yaml>` sobre o conteúdo fresco
   (ou chame `publish_guard.connection_defaults(content)`). Qualquer property
   do `config_schema` com `x-ref: connection` **e** `default` → **recuse o
   publish** e diga quais. Conexão vem da ativação; o `default` só existe em
   draft de teste porque `spec_test_run` não recebe config (ARMADILHAS §9).
   Remova o `default` (mantendo a property), regrave o draft e volte ao passo 1.
```

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/agentos-builder/scripts/publish_guard.py .claude/skills/agentos-builder/tests/test_publish_guard.py .claude/skills/agentos-builder/references/publish.md
git commit -m "feat(publish): guard mecânico — x-ref: connection com default não publica (spec §9)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: `descoberta.md` — triagem no topo e ficha persistida no rascunho

**Files:**
- Modify: `.claude/skills/agentos-builder/references/descoberta.md`

**Interfaces:**
- Produces: a ficha de domínio com os rótulos exatos que a Task 4 consome, mais a regra "gravar a cada linha". Nomes de seção que outras tasks citam: `## Triagem`, `## Produto: a ficha de domínio`, `## Onde a ficha vive`.

- [ ] **Step 1: Insert the triage section**

Insert immediately after the "## Regras da conversa (não negociáveis)" list (before "## Rodada 1 — Propósito e gatilho"):

```markdown
## Triagem — duas perguntas antes de tudo

1. Esse agente **escreve** em algum sistema (cria, muda, apaga, envia) ou só
   consulta e informa?
2. O processo tem **regra que muda por caso** (valor, cliente, dia, tipo)?

| Resposta | Rota | Ficha |
|---|---|---|
| Não escreve **e** não tem regra por caso | **curta**: uma rodada só (a Rodada 1) | Trabalho, Começa quando, Lê, Termina bem, Descartado |
| Qualquer outra | **completa**: Rodadas 1, 2 e 3 | todas as linhas |

A triagem existe porque descoberta em agente simples vira overhead, e a maior
parte dos agentes do AgenteOS é automação, não domínio de cliente. **A triagem
é entrada, não veredito:** se a derivação (`create.md`) encontrar escrita ou
regra condicional numa ficha curta, reabra a Rodada 2 antes de seguir.
```

- [ ] **Step 2: Add the persistence section**

Insert immediately before "## Quando pular esta fase":

```markdown
## Onde a ficha vive: no rascunho, desde a primeira linha

Nada em arquivo local. A memória é o rascunho no MCP.

1. Assim que a linha **Trabalho** é confirmada: proponha `name`, derive o `slug`
   (kebab-case do nome), **cheque colisão** com `mcp_client.list_specs()` e
   grave um rascunho mínimo válido com `mcp_client.write_draft(slug, "0.1",
   content)` — `description`, `trigger`, um nó `render_template` com um `.j2`
   de uma linha — com a ficha parcial como cabeçalho (linhas ainda não
   respondidas ficam com `<pendente>`).
2. A cada linha da ficha confirmada: `write_draft` de novo, mesma versão, só o
   cabeçalho muda. O YAML cresce junto na fase de derivação.
3. Sessão que cai no meio: `mcp_client.read_spec(slug, "0.1")`, leia o
   cabeçalho, retome da primeira linha `<pendente>`.
4. Reabrir uma decisão é regravar o rascunho com a ficha alterada. Publicado é
   `spec_revise`, como qualquer mudança.

O slug nasce validado porque a primeira gravação já passa pelo MCP — não existe
pasta local a criar antes de o slug ser confirmado.
```

- [ ] **Step 3: Update the intro and the fecho to match**

Replace, in the intro paragraph: `são três rodadas curtas e uma decisão` → `são uma triagem, até três rodadas curtas e uma decisão`.

In "## Produto: a ficha de domínio", replace the sentence `Ela **vira o cabeçalho do YAML** (o `create.md` já exige um bloco de comentário) e alimenta a entrevista de campos sem precisar perguntar de novo.` with:

```markdown
Ela **é o cabeçalho do YAML** — já está gravada no rascunho linha a linha (ver
"Onde a ficha vive") — e é a única entrada do `create.md`: a derivação lê a
ficha, não pergunta nada ao humano.
```

- [ ] **Step 4: Verify the labels are exactly the ones Task 4 will reference**

Run: `grep -c "^# \(Trabalho\|Começa quando\|Termos\|Nunca pode\|Autoriza\|Lê\|Escreve\|Fora do grafo\|Termina bem\|Descartado\):" .claude/skills/agentos-builder/references/descoberta.md`
Expected: `10`

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/agentos-builder/references/descoberta.md
git commit -m "docs(descoberta): triagem curta/completa e ficha gravada no rascunho desde a primeira linha

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: `create.md` — de entrevista a derivação

**Files:**
- Modify: `.claude/skills/agentos-builder/references/create.md`

**Interfaces:**
- Consumes: ficha de domínio (rótulos da Task 3); `mcp_client.node_types()/context()/connectors()/tools()/models()/validate()/write_draft()`.
- Produces: YAML derivado, validado, gravado em `drafts/<slug>/v0.1`; a Task 5 lê esse YAML para montar o roteiro. Regra de saída para a Task 6: qualquer linha da tabela de derivação que não encontre o recurso no ambiente **para** e chama `gap.md`.

- [ ] **Step 1: Replace the intro blockquote and the "Guided interview" sentence**

Replace the leading blockquote (`> **Fase 0 — descoberta primeiro.** ... no fim daquele arquivo.`) and the sentence `Guided interview that builds a brand-new AgentSpec YAML from scratch and writes it to ... don't front-load the whole interview in a wall of text.` with:

```markdown
> **Este arquivo não pergunta nada ao humano.** A entrada é a ficha de domínio
> gravada no cabeçalho do rascunho por `references/descoberta.md`. O humano que
> autora é analista de negócio: ele nunca vê slug, nó, `when` ou
> `config_schema`. Se a ficha tem linha `<pendente>`, volte para a descoberta.

Procedimento interno que **deriva** o AgentSpec YAML a partir da ficha, valida
pelo MCP e regrava o rascunho `drafts/<slug>/v0.1` que a descoberta já criou.
O que o humano vê depois disto é o roteiro de `references/proposta.md`.
```

Keep the four paragraphs that follow (node_types fresh, variants, context before `.j2`, models for `model_ref`) unchanged.

- [ ] **Step 2: Replace "## Interview flow" (sections a–e) with "## Derivação"**

Delete everything from `## Interview flow` through the end of item 6 of section e (the approval bullet ending `See ARMADILHAS.md §4.`). Insert:

```markdown
## Derivação — da ficha ao YAML

Cada linha da ficha decide algo. Cada decisão cita a seção do
[`ARMADILHAS.md`](../../../../ARMADILHAS.md) que a justifica. Aplique na
ordem; se uma linha exigir um recurso que o ambiente não tem (conector, tool,
strategy, modelo), **pare aqui** e siga `references/gap.md` — nunca continue
com o nó faltando.

| Linha da ficha | Deriva | Regra |
|---|---|---|
| Trabalho | `name`, `slug` (já validado na descoberta), `description`, `id = agt_<slug_com_underscores>_v<major>` | `id` estável entre versões (§3) |
| Começa quando | `trigger.type` e campos do tipo | enum de `node_types().trigger`; `schedule` exige cron; `chat` implica a regra da linha "Começa quando = chat" |
| Termos | `id`/`key` dos nós (snake_case do termo do usuário); `title`/`description` das properties | mesmo valor em `id` e `key` (§8); property sempre com `title` e `description` (lint D-02) |
| Lê | `io.reads`; um nó de leitura por fonte (`tool` / `http_request` / `sftp_op` / `erp_query`) | `connector_id` só de `connectors()`; `tool_name` só de `tools().platform_tools`; ler `allowed_ops`/`base_dir` antes de compor path (§6) |
| Escreve | `io.writes`; nó de escrita **sempre precedido** de `approval` e de um `condition` que **autoriza** | condition `expr: "<approval>.decision.decision == 'approved'"`, `on_false` → nó terminal de aviso (§1, §4) |
| Autoriza | `approval` com `context_from` apontando o passo que produz a lista; alçada em `config.when` **só** na gramática de condition (`len()`, `== 'str'`, `== null` e negações) | §2 (item sem `action` derruba a inbox), §4; sem alçada = sem `when` |
| Começa quando = chat | nenhum `{{run.input.*}}` alcança nó de escrita; o pedido do usuário só ESCOLHE entre opções do `config` | §5 |
| Nunca pode | um `condition` ou `approval` que a proteja; se não houver onde encaixar, a ficha está errada — volte à Rodada 2 | descoberta.md |
| Fora do grafo | não vira nó; se exigir operation no serviço, é gap `[plataforma]` | §19 |
| Termina bem | último nó `render_template` com o resumo; `.j2` só com o que `context()` resolve, enviado no mesmo `write_draft` | §8 |
| Descartado | linha do cabeçalho; não deriva nó | — |

Regras transversais, aplicadas sem perguntar:

- Todo passo externo que pode falhar ganha um `condition` no `status` antes do
  consumidor (`expr: "<passo>.status == 'ok'"`), porque `http_request` que
  falha **não** aborta o run (§18).
- Nó `agent` só com campos dentro de `config` (§16); o prompt instrui o modelo
  a nunca emitir `{{}}` (§17); a saída é string — parse fica no serviço (§19).
- `http_request`: `body` é objeto só em resposta JSON; fora disso é string sem
  `body_raw` — teste `is string` no template antes de navegar (§11).
- `version: "0.1.0"`, `change_class: "minor"`. Major é conversa com o admin (§3).
- `config_schema`: o que o cliente escolhe na ativação (conexões, pastas,
  limites). O que é fixo fica literal no YAML. Property `x-ref: connection`
  **sem `default`** — exceto no draft de teste, com `# REMOVER antes de publicar`
  (§9); o guard do `publish.md` recusa se sobrar.
- `condition`: leia `semantics.condition` de `node_types()` antes de escrever
  qualquer `expr`; `top_level` e `loop_body` não aceitam as mesmas formas.
- `transform`: só strategies de `node_types().transform_strategies`; lista
  vazia = gap `[plataforma]`.
- Nó com `runtime_ready: false` que não é estrutural (trigger/condition): gap
  `[plataforma]`, não "draft-only".

O analista nunca vê esta tabela. Ela é o contrato entre a ficha e o YAML.
```

- [ ] **Step 3: Rewrite "## File conventions" header bullet**

Replace the bullet starting `- **Cabeçalho = a ficha de domínio** da fase 0, colada como bloco de comentário ...` (through the end of that bullet) with:

```markdown
- **Cabeçalho = a ficha de domínio**, já gravada pela descoberta. A derivação
  acrescenta abaixo dela, ainda como comentário: `# Derivado em <data> a partir
  da ficha acima; regras em references/create.md`. Nada de "draft-only": nó que
  não roda é gap, não nota de rodapé.
```

- [ ] **Step 4: Adjust "## Write sequence" step 1 and step 4**

Replace step 1 `Assemble the full YAML from the interview answers, in memory ...` with:

```markdown
1. Derive o YAML completo a partir da ficha (tabela acima), em memória. Leia o
   rascunho atual com `mcp_client.read_spec(slug, "0.1")` para preservar o
   cabeçalho.
```

Replace in step 4: `→ `mcp_client.write_draft(slug, "0.1", content)`. This both re-validates` with `→ `mcp_client.write_draft(slug, "0.1", content, templates)` — sempre com os `.j2` no mesmo write (§8). This both re-validates`.

- [ ] **Step 5: Replace "## Boundary reminders during the interview"**

Replace that section entirely with:

```markdown
## Quando a derivação não fecha

Tipo de nó, conector, tool, strategy ou modelo que a ficha exige e o ambiente
não tem: **não é** "peça para o dev", nem `/w1`. É gap. Pare na linha da tabela
que travou, grave o rascunho com `# Pendente: <linha> — <o que falta>` no
cabeçalho e siga `references/gap.md`. A regra de ouro do kit continua: zero
código do core, zero contorno.
```

- [ ] **Step 6: Verify no interview language remains**

Run: `grep -n -i "ask\b\|pergunt\|interview" .claude/skills/agentos-builder/references/create.md`
Expected: zero matches for "Ask ", "interview"; the only allowed hit is the intro sentence "não pergunta nada ao humano".

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/agentos-builder/references/create.md
git commit -m "docs(create): de entrevista a derivação — a ficha decide, o humano não responde campo de schema

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: `proposta.md` — roteiro de negócio e tradução do test run

**Files:**
- Create: `.claude/skills/agentos-builder/references/proposta.md`

**Interfaces:**
- Consumes: o YAML derivado (Task 4) via `mcp_client.read_spec(slug, "0.1")`; `spec_test_run` e `spec_run_status` (tools MCP `spec_test_run(slug, version)` → `{run_id}`; `spec_run_status(run_id)` → `{status, steps[], output}`; não estão no `mcp_client.py`, chame pela tool MCP diretamente).
- Produces: o texto que o analista lê; as duas perguntas de decisão; a oferta de publicar só após run verde.

- [ ] **Step 1: Write the file**

```markdown
# Proposta — o que o analista vê

Depois da derivação (`create.md`), o humano recebe **um roteiro**, nunca o YAML.
Uma linha por nó, em linguagem de negócio, usando os termos da ficha (linha
"Termos"). Slug, nó, `when` e `config_schema` não aparecem.

## 1. Montar o roteiro

Leia o rascunho (`mcp_client.read_spec(slug, "0.1")`) e traduza nó a nó, na
ordem do grafo, com a tabela de `descoberta.md` ("Falando com quem decide"):

| Nó | Como falar |
|---|---|
| trigger `schedule` | "Liga <cadência em palavras: toda segunda às 7h / todo dia 5>." |
| trigger `chat` | "Liga quando alguém pede no chat." |
| trigger `event`/`webhook`/`email` | "Liga quando <evento da ficha> acontece." |
| nó de leitura | "Busca <o que a ficha diz que lê> em <sistema>." |
| `condition` de status | "Se não conseguir buscar, avisa e para." |
| `transform` | "Separa/organiza <o que a strategy faz, em palavras>." |
| `approval` | "**Para e pede o ok de <quem autoriza>**<, só acima de <alçada>>." |
| `condition` no veredito | (não vira linha — está implícito na anterior) |
| nó de escrita | "Só depois do ok, <o que escreve> em <onde>." |
| nó de aviso (`on_false`) | "Se não for aprovado, avisa e não faz nada." |
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

Chame a tool MCP `spec_test_run(slug, "0.1")` → `run_id`; depois
`spec_run_status(run_id)` até `status` sair de `received`/`running`.
Traduza o trace para o analista, um passo por linha:

| `steps[].status` / `status` do run | Como falar |
|---|---|
| passo `completed`/`ok` | "<nome do passo em negócio>: rodou." (+ um número se houver: "buscou 12 títulos") |
| passo `skipped` com `reason: condition_jump` | "<passo>: não precisou rodar." |
| passo `skipped` com `reason: when_false` | "<passo>: pulado pela regra <alçada em palavras>." |
| passo `skipped` com `reason: empty_context` | "**Atenção:** a lista veio vazia e a aprovação foi pulada. Confira o passo anterior." (§4) |
| run `awaiting_approval` | "Parou no ponto de aprovação, como esperado. Em teste não dá para aprovar (§13); a prova da escrita vem depois da ativação." |
| passo `failed` / run `failed` | "<passo>: falhou — <mensagem do erro em uma frase>." Depois: `gap.md` se for recurso do ambiente; senão corrija a ficha e re-derive. |
| run `completed` sem escrita | "Rodou até o fim." |

**Só ofereça publicar depois de run verde** (`completed`, ou `awaiting_approval`
quando há aprovação). Antes de `publish.md`, remova todo `default:` de property
`x-ref: connection` que a fase de teste tenha colocado — o guard do publish
recusa se sobrar. Publicar continua sendo decisão explícita do humano; a §3
diz o que custa publicar errado.
```

- [ ] **Step 2: Verify every node type named in the table exists in the current catalog**

Run: `python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(sorted(n['type'] for n in d['node_types']))" <um dump recente de spec_node_types>` — or call the MCP tool `spec_node_types` and list `node_types[].type`.
Expected: contém `trigger`, `condition`, `transform`, `approval`, `render_template`, `agent`, `http_request`, `sftp_op`, `tool`. Se algum faltar, remova a linha da tabela.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/agentos-builder/references/proposta.md
git commit -m "docs(proposta): roteiro de negócio nó a nó e tradução do test run para o analista

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: `gap.md` — parar, explicar, reportar, retomar

**Files:**
- Create: `.claude/skills/agentos-builder/references/gap.md`

**Interfaces:**
- Consumes: `mcp_client.feedback(category, message, context)` (Task 1); `mcp_client.write_draft` para gravar `# Pendente:`; `gh issue create` como fallback.
- Produces: o item na esteira (Sentry via `spec_feedback`) ou a issue `gap`, e o rascunho retomável.

- [ ] **Step 1: Write the file**

```markdown
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
   `context={"slug": slug, "version": "0.1", "tool": "<tool/nó que travou>"}`.
   Cai na esteira do time interno sem passar por ninguém.
2. Se o MCP estiver **indisponível** (`McpClientError` sem `code`, ou HTTP ≠
   401): `gh issue create --label gap --title "<classe> <uma linha>" --body
   "<pedido técnico>"` no repositório do kit.
3. Se nem `gh` houver: entregue o pedido técnico pronto para o analista
   repassar, e diga a quem.

Registre no cabeçalho do rascunho qual canal foi usado:
`# Gap reportado: feedback|issue #N|texto — <data>`.

## 6. Retomar

Quando o gap fechar: `read_spec`, remova `# Pendente:` e `# Gap reportado:`,
volte à linha da tabela de derivação que travou, siga até o roteiro.
```

- [ ] **Step 2: Verify cross-references resolve**

Run: `grep -o "§[0-9]*" .claude/skills/agentos-builder/references/gap.md | sort -u` and confirm each section exists in `ARMADILHAS.md` (`grep -n "^## <n>\." ARMADILHAS.md`).
Expected: every § listed has a heading.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/agentos-builder/references/gap.md
git commit -m "docs(gap): duas camadas, classes, redação mecânica e canal spec_feedback → issue → texto

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: `SKILL.md`, `README.md`, `CLAUDE.md`

**Files:**
- Modify: `.claude/skills/agentos-builder/SKILL.md`
- Modify: `README.md` (seção "Autorando", itens 0–4)
- Modify: `CLAUDE.md` (bullet "Zero import/código do core")

- [ ] **Step 1: SKILL.md — version, router, rule**

Replace `  version: "0.5.0"` with `  version: "0.6.0"`.

In the "## Operations router" table, replace the row `| Descoberta (fase 0 do Create) | Live | `references/descoberta.md` |` and the row `| Create | Live | `references/create.md` |` with:

```markdown
| Descoberta (conversa com o analista) | Live | `references/descoberta.md` |
| Create (derivação — interna, sem perguntas) | Live | `references/create.md` |
| Proposta (roteiro + test run traduzido) | Live | `references/proposta.md` |
| Gap (parar, reportar, retomar) | Live | `references/gap.md` |
```

Replace the paragraph starting `**Create começa pela descoberta.** Quando o pedido for "criar um agente que faz X"` (through `sem ninguém perceber.`) with:

```markdown
**O humano nunca responde campo de schema.** Quem autora é analista de negócio.
Pedido "criar um agente que faz X" segue esta ordem, sem pular:
`descoberta.md` (triagem + rodadas + ficha, gravada no rascunho desde a
primeira linha) → `create.md` (deriva o YAML da ficha; não pergunta) →
`proposta.md` (roteiro em negócio, decisão, test run traduzido) → `publish.md`
(só após run verde, com o guard de conexão). Faltou recurso no ambiente em
qualquer ponto: `gap.md` — parar, reportar por `spec_feedback`, deixar o
rascunho retomável. Nunca contornar.
```

Replace `All 7 operations share the rules above` with `All 9 operations share the rules above`.

- [ ] **Step 2: README.md — the five moments**

Replace items `0.` through `4.` of the "Autorando" list (from `0. **Descoberta**` through the item `4. `spec_publish` — publicar. ...` inclusive) with:

```markdown
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
```

- [ ] **Step 3: CLAUDE.md — the golden rule gets its path**

Replace the bullet:

```markdown
- **Zero import/código do core da plataforma.** Falta algo para autorar =
  gap do MCP Server — reportar ao time da plataforma, não contornar.
```

with:

```markdown
- **Zero import/código do core da plataforma.** Falta algo para autorar =
  gap — reportar, não contornar. O caminho é `references/gap.md`: parar,
  gravar `# Pendente:` no rascunho, reportar pela tool `spec_feedback`
  (fallback: issue `gap` neste repo), retomar quando fechar.
```

- [ ] **Step 4: Run all skill tests**

Run: `cd .claude/skills/agentos-builder && for t in tests/test_mcp_client_error_parse.py tests/test_mcp_client_feedback.py tests/test_publish_guard.py; do python3 $t || exit 1; done`
Expected: three `: ok` lines.

- [ ] **Step 5: Verify every reference file named in SKILL.md exists**

Run: `cd .claude/skills/agentos-builder && grep -o 'references/[a-z-]*\.md' SKILL.md | sort -u | while read f; do test -f "$f" && echo "ok $f" || echo "MISSING $f"; done`
Expected: no `MISSING`.

- [ ] **Step 6: Commit and open the PR**

```bash
git add .claude/skills/agentos-builder/SKILL.md README.md CLAUDE.md
git commit -m "docs(skill): router com proposta e gap, regra 'o humano nunca responde campo de schema', v0.6.0

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push -u origin feat/autoria-pelo-analista
gh pr create --title "feat(skill): autoria pelo analista — descoberta conduz, o kit deriva, gap vira feedback" --body "Implementa docs/superpowers/specs/2026-09-17-autoria-pelo-analista-design.md (#27).

- descoberta.md: triagem curta/completa; ficha gravada no rascunho desde a primeira linha
- create.md: de entrevista a derivação (tabela ficha→YAML citando ARMADILHAS)
- proposta.md (novo): roteiro de negócio nó a nó; test run traduzido
- gap.md (novo): classes, duas camadas, redação mecânica, canal spec_feedback → issue → texto
- mcp_client.feedback(); publish_guard.py recusa x-ref: connection com default
- SKILL.md 0.6.0; README com os cinco momentos; CLAUDE.md com o caminho do gap

Prova (spec §8) fica para depois do merge: três sessões no sandbox (curta, completa, gap forçado) e uma sessão com uma pessoa não-dev.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

## Self-review

**Spec coverage.** §3.1 triagem → Task 3. §3.2 descoberta → Task 3 (conteúdo das rodadas intacto). §3.3 proposta → Task 5 §1–2. §3.4 decisão → Task 5 §3. §3.5 prova → Task 5 §4. §4 ficha no rascunho → Task 3 "Onde a ficha vive". §5 derivação → Task 4. §6 gap → Task 6 + Task 1. §7 arquivos → Tasks 2–7 (publish.md em Task 2; SKILL/README/CLAUDE em Task 7). §9 guard de `default` → Task 2. §9 reabrir descoberta completa → Task 3 ("triagem é entrada, não veredito") e Task 4 linha "Nunca pode". §8 (provas no sandbox) é pós-merge por desenho, dito no corpo do PR.

**Placeholders.** Nenhum "TBD"/"similar to". O Step 2 da Task 5 depende de um dump de `spec_node_types`; a alternativa (chamar a tool) está no próprio step.

**Type consistency.** `feedback(category, message, context)` igual em Task 1 e Task 6. `connection_defaults(content) -> list[str]` igual em Task 2 (código, teste, publish.md). Rótulos da ficha iguais em Tasks 3, 4 e 6 (`# Pendente:` definido na Task 4 e usado na Task 6). Versão do rascunho `"0.1"` em todas as chamadas.
