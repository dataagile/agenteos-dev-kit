# Chamado no GLPI aberto pelo kit — Implementation Plan (lado do kit)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Quando o kit trava (gap, MCP falhando, ou o usuário pede), ele monta um rascunho redigido, pergunta, e abre o chamado no GLPI pela tool `spec_feedback` estendida, devolvendo número e link.

**Architecture:** Só o lado do kit. A plataforma (tool `spec_feedback` com destino GLPI, `GlpiClient` em `cdm`, dedup, smoke real) está delegada à sessão do Agente_OS com o spec como contrato; este plano assume o contrato da seção 2 do spec e pode ser executado antes do deploy, porque os testes do kit não tocam rede. Duas peças de código (`feedback()` exigindo reportante; `gap_redact.py`), o resto é texto de referência e documentação.

**Tech Stack:** Markdown; Python 3 stdlib; testes como scripts `assert` rodados com `python3 tests/<arquivo>.py` de dentro de `.claude/skills/agentos-builder/` (sem pytest).

**Spec:** `docs/superpowers/specs/2026-09-22-glpi-chamado-pelo-kit-design.md` (seções 4, 5-kit, 6-kit, 7 linhas 3–4)

## Global Constraints

- Nada abre chamado sem o usuário responder "sim" ao rascunho inteiro (spec §4).
- `mcp_client.feedback(category, message, context)` mantém a assinatura; `context` passa a exigir `reporter_name` e `reporter_email` (`ValueError` local antes da rede); retorno é o dict da tool: `{"status": "ok", "ticket_id": int, "url": str, "deduplicated": bool}`.
- Redação mecânica antes de qualquer envio (spec §4 / `gap.md` §4): sem `default:` de conexão, UUID, payload de conexão, host, usuário, token, conteúdo de run, CPF, PIX, segredo.
- Reportante em `.claude/agentos-builder.local.json` com chaves `reporter_name`, `reporter_email`; arquivo no `.gitignore`. Não é segredo.
- Gatilhos: (1) gap do `gap.md`; (2) `McpClientError` de servidor (`internal`, `upstream_unavailable`, HTTP 5xx, sem código) **duas vezes seguidas no mesmo passo** em `spec_write`/`spec_validate`/`spec_test_run`/`spec_publish`; (3) o usuário pede (`/reportar`, "travou", "bug"). `validation_failed`, `not_found`, `unauthorized` não contam.
- Cabeçalho do rascunho após envio: `# Gap reportado: glpi #<N> — <data>`; sem MCP/gh: `# Gap reportado: texto — <data>`.
- Retorno ao usuário: `Chamado #N aberto: <url>` ou `Já existe o #N para isto: <url>`.
- `spec_feedback` exige só `spec.read` (📏 código): a chave de 6 scopes cobre; a nota "a confirmar no sandbox" do README fecha.
- Zero código do core; sem fallback a filesystem para operação de spec; nenhum arquivo local novo **por agente** (o `.local.json` é por instalação, não por agente).
- Todo commit termina com `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Branch: `feat/glpi-chamado-kit` a partir de `origin/main` (≥ `0124614`). Um PR ao final.

---

## File structure

| Arquivo | Responsabilidade | Task |
|---|---|---|
| `.claude/skills/agentos-builder/scripts/mcp_client.py` | `feedback()` exige `reporter_*` | 1 |
| `.claude/skills/agentos-builder/tests/test_mcp_client_feedback.py` | prova a exigência e o repasse do retorno | 1 |
| `.claude/skills/agentos-builder/scripts/gap_redact.py` | `redact(text) -> str` stdlib | 2 |
| `.claude/skills/agentos-builder/tests/test_gap_redact.py` | prova que UUID, `default:`, CPF, token somem | 2 |
| `.claude/skills/agentos-builder/references/gap.md` | gatilhos, reportante, canal com retorno GLPI, redação via script | 3 |
| `.gitignore` | `.claude/agentos-builder.local.json` | 3 |
| `.claude/skills/agentos-builder/SKILL.md` | `/reportar` no router; regra | 4 |
| `README.md` | fecha a nota de escopo; gap vira chamado | 4 |
| `ARMADILHAS.md` | §20: GLPI responde HTML 200 em manutenção | 4 |
| `docs/guia/glpi-chamado.html` | fragmento `<section id="c15">` para o guia | 5 |

---

### Task 1: `feedback()` exige reportante e repassa o retorno da tool

**Files:**
- Modify: `.claude/skills/agentos-builder/scripts/mcp_client.py` (função `feedback`, linhas ~222–239)
- Test: `.claude/skills/agentos-builder/tests/test_mcp_client_feedback.py`

**Interfaces:**
- Consumes: `_call(tool, params) -> dict` (existente).
- Produces: `feedback(category: str, message: str, context: dict[str, str] | None = None) -> dict[str, Any]` — `ValueError` se `context` não tiver `reporter_name` e `reporter_email` não-vazios; devolve o dict da tool sem transformar. A Task 3 (`gap.md`) chama assim.

- [ ] **Step 1: Write the failing test** — substitua o conteúdo de `tests/test_mcp_client_feedback.py` por:

```python
"""feedback(): valida category/message/reporter localmente e repassa o retorno da tool. Sem rede.

Rodar: python3 tests/test_mcp_client_feedback.py (de dentro da pasta da skill).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import mcp_client as m  # noqa: E402

calls = []
RET = {"status": "ok", "ticket_id": 241, "url": "https://glpi.example/front/ticket.form.php?id=241", "deduplicated": False}
m._call = lambda tool, params: calls.append((tool, params)) or RET
REP = {"reporter_name": "Ana Analista", "reporter_email": "ana@cliente.com.br"}

# chamada mínima válida: reporter obrigatório, retorno repassado inteiro
out = m.feedback("melhoria", "[kit] falta pergunta X", context=REP)
assert out == RET, out
assert calls[-1][0] == "spec.feedback"
assert calls[-1][1]["context"] == REP, calls[-1]

# context inteiro viaja
ctx = {**REP, "slug": "s", "version": "0.1", "tool": "x.y", "kit_version": "0.6.0", "step": "derivacao"}
m.feedback("erro", "[plataforma] tool fora do catálogo", context=ctx)
assert calls[-1][1]["context"] == ctx, calls[-1]

n = len(calls)

# sem context → não chega na rede
try:
    m.feedback("erro", "x")
    raise AssertionError("devia levantar ValueError")
except ValueError as e:
    assert "reporter" in str(e), e
assert len(calls) == n

# reporter vazio → não chega na rede
try:
    m.feedback("erro", "x", context={"reporter_name": " ", "reporter_email": "a@b"})
    raise AssertionError("devia levantar ValueError")
except ValueError:
    pass
assert len(calls) == n

# category inválida
try:
    m.feedback("bug", "x", context=REP)
    raise AssertionError("devia levantar ValueError")
except ValueError:
    pass
assert len(calls) == n

# message vazia
try:
    m.feedback("erro", "   ", context=REP)
    raise AssertionError("devia levantar ValueError")
except ValueError:
    pass
assert len(calls) == n

# message > 4000
try:
    m.feedback("erro", "a" * 4001, context=REP)
    raise AssertionError("devia levantar ValueError")
except ValueError:
    pass
assert len(calls) == n

print("test_mcp_client_feedback: ok")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .claude/skills/agentos-builder && python3 tests/test_mcp_client_feedback.py`
Expected: `AssertionError: devia levantar ValueError` (a chamada sem context hoje passa).

- [ ] **Step 3: Write minimal implementation** — substitua a função `feedback` inteira por:

```python
def feedback(category: str, message: str, context: dict[str, str] | None = None) -> dict[str, Any]:
    """Abre chamado no GLPI pela tool `spec_feedback` (a plataforma abre; o kit não
    tem credencial). `context.reporter_name`/`reporter_email` são obrigatórios —
    é o "Reportado por" do chamado. `message` vai CRUA — passe por
    `gap_redact.redact()` antes (references/gap.md §4). Primeira linha da message
    leva a classe: [ambiente] | [plataforma] | [kit].
    Devolve o dict da tool: {status, ticket_id, url, deduplicated}."""
    if category not in _FEEDBACK_CATEGORIES:
        raise ValueError(f"category deve ser um de {_FEEDBACK_CATEGORIES}, veio {category!r}")
    if not message.strip():
        raise ValueError("message vazia — o servidor recusa (minLength 1) e cairia no fallback à toa")
    if len(message) > 4000:
        raise ValueError(f"message tem {len(message)} chars; máximo 4000")
    ctx = dict(context or {})
    for k in ("reporter_name", "reporter_email"):
        if not str(ctx.get(k, "")).strip():
            raise ValueError(f"context.{k} é obrigatório — o chamado precisa de 'Reportado por' (references/gap.md §5)")
    return _call("spec.feedback", {"category": category, "message": message, "context": ctx})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .claude/skills/agentos-builder && python3 tests/test_mcp_client_feedback.py`
Expected: `test_mcp_client_feedback: ok`

- [ ] **Step 5: Run the other tests**

Run: `cd .claude/skills/agentos-builder && python3 tests/test_mcp_client_error_parse.py && python3 tests/test_publish_guard.py`
Expected: dois `: ok`.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/agentos-builder/scripts/mcp_client.py .claude/skills/agentos-builder/tests/test_mcp_client_feedback.py
git commit -m "feat(mcp_client): feedback() exige reporter_name/email e repassa {ticket_id,url,deduplicated}

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: `gap_redact.py` — redação mecânica antes do envio

**Files:**
- Create: `.claude/skills/agentos-builder/scripts/gap_redact.py`
- Test: `.claude/skills/agentos-builder/tests/test_gap_redact.py`

**Interfaces:**
- Consumes: nada.
- Produces: `redact(text: str) -> str`. Substitui por `<removido>`: UUIDs; o valor de qualquer linha `default:`; CPF (`000.000.000-00` ou 11 dígitos contíguos); o valor após `token`, `secret`, `password`, `senha`, `Bearer`, `user_token`, `App-Token` (`=` ou `:`); chaves PIX no formato e-mail ou telefone `+55…`. Mantém o resto intacto. A Task 3 manda o modelo chamar isto antes do `feedback()`. Ceiling documentado: PIX aleatória (UUID já coberta) e nomes de host não são removidos — host é citado por nome de conexão, não por endereço (gap.md §4).

- [ ] **Step 1: Write the failing test**

```python
"""gap_redact.redact(): o que não pode ir cru ao chamado some. Sem rede.

Rodar: python3 tests/test_gap_redact.py (de dentro da pasta da skill).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
from gap_redact import redact  # noqa: E402

RAW = """[ambiente] conexão SFTP recusa escrita
passo: Escreve — sftp_op criar
conector: "SFTP Protheus TBC — DEV" (id b744c7bc-3e62-4a58-b85d-492d1bd3190b)
      default: "b744c7bc-3e62-4a58-b85d-492d1bd3190b"   # REMOVER antes de publicar
erro: CONNECTOR_ERROR
cliente informou CPF 123.456.789-09 e também 98765432100
token=abc.DEF-123 password: s3nh@ Authorization: Bearer eyJhbGci
pix do fornecedor: fornecedor@empresa.com.br ou +5561999998888
o que destravaria: liberar allowed_ops=read_write na conexão
"""
out = redact(RAW)

# o que precisa sumir
for bad in (
    "b744c7bc-3e62-4a58-b85d-492d1bd3190b",
    "123.456.789-09", "98765432100",
    "abc.DEF-123", "s3nh@", "eyJhbGci",
    "fornecedor@empresa.com.br", "+5561999998888",
):
    assert bad not in out, f"vazou: {bad}\n{out}"

# o que precisa ficar
for keep in (
    "[ambiente] conexão SFTP recusa escrita",
    'conector: "SFTP Protheus TBC — DEV"',
    "erro: CONNECTOR_ERROR",
    "o que destravaria: liberar allowed_ops=read_write na conexão",
    "REMOVER antes de publicar",
):
    assert keep in out, f"removeu demais: {keep}\n{out}"

# a linha default: mantém a chave, troca o valor
assert 'default: <removido>' in out, out
# marcador único
assert out.count("<removido>") >= 8, out.count("<removido>")
# idempotente
assert redact(out) == out

print("test_gap_redact: ok")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .claude/skills/agentos-builder && python3 tests/test_gap_redact.py`
Expected: `ModuleNotFoundError: No module named 'gap_redact'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Redação mecânica do pedido técnico antes de `mcp_client.feedback()` (gap.md §4).

O texto vai cru ao chamado do GLPI. Isto remove o que NUNCA pode ir: UUID
(inclui id de conexão e chave PIX aleatória), valor de `default:`, CPF,
valores de token/secret/password/Bearer, e-mail e telefone (chaves PIX).
Ceiling: nome de host não é removido — cite conexão pelo NOME, não pelo
endereço (gap.md §4). Stdlib puro.

Uso: python3 scripts/gap_redact.py < pedido.txt
"""
import re
import sys

_R = "<removido>"
_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), _R),
    (re.compile(r"^(\s*default:\s*)(?:\"[^\"]*\"|'[^']*'|[^#\n]*?)(\s*(?:#.*)?)$", re.M), rf"\1{_R}\2"),
    (re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), _R),
    (re.compile(r"(?<!\d)\d{11}(?!\d)"), _R),
    (re.compile(r"(?i)\b(bearer)\s+\S+"), rf"\1 {_R}"),
    (re.compile(r"(?i)\b(token|secret|password|senha|user_token|app-token)(\s*[:=]\s*)\S+"), rf"\1\2{_R}"),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), _R),
    (re.compile(r"\+55\s?\d{2}\s?\d{4,5}-?\d{4}\b"), _R),
]


def redact(text: str) -> str:
    for pat, rep in _RULES:
        text = pat.sub(rep, text)
    return text


if __name__ == "__main__":
    sys.stdout.write(redact(sys.stdin.read()))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .claude/skills/agentos-builder && python3 tests/test_gap_redact.py`
Expected: `test_gap_redact: ok`. Se `allowed_ops=read_write` for atingido pela regra de `token|secret|...` (não deve — a chave não está na lista), ajuste a lista, não o teste.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/agentos-builder/scripts/gap_redact.py .claude/skills/agentos-builder/tests/test_gap_redact.py
git commit -m "feat(gap_redact): redação mecânica do pedido técnico — UUID, default:, CPF, token, e-mail, telefone

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: `gap.md` — gatilhos, reportante, chamado no retorno

**Files:**
- Modify: `.claude/skills/agentos-builder/references/gap.md`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `mcp_client.feedback(...)` (Task 1) e `gap_redact.redact()` (Task 2), `python3 scripts/gap_redact.py` via stdin.
- Produces: o procedimento que o modelo segue; os nomes de seção `## 0. Quando o kit sugere`, `## 5. Canal, em ordem` são citados por `SKILL.md` (Task 4).

- [ ] **Step 1: Insert the trigger section** — imediatamente antes de `## 1. Classificar`:

```markdown
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
```

- [ ] **Step 2: Replace §4's first sentence and add the script** — substitua `A `message` vai **crua** ao Sentry. Confira, linha a linha, que **não** há:` por:

```markdown
A `message` vai **crua** ao chamado do GLPI. Passe o pedido técnico por
`python3 scripts/gap_redact.py` (stdin → stdout) ou `gap_redact.redact(texto)`
**antes** de montar o rascunho, e confira o resultado: **não** pode haver:
```

- [ ] **Step 3: Replace §5 entirely** — do `## 5. Canal, em ordem` até a linha `` `# Gap reportado: feedback|issue #N|texto — <data>`. `` inclusive, por:

```markdown
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
```

- [ ] **Step 4: Update the intro sentence and §6** — na linha 3, `Quando a derivação (`create.md`) ou o test run (`proposta.md`) esbarra em algo que o ambiente não tem, o kit **para naquele ponto**.` → `Quando um dos gatilhos do §0 dispara, o kit **para naquele ponto**.` Em §6, `remova `# Pendente:` e `# Gap reportado:`` fica como está (já cobre `glpi #N`).

- [ ] **Step 5: `.gitignore`** — acrescente a linha `.claude/agentos-builder.local.json`.

- [ ] **Step 6: Verify**

Run: `grep -n "^## " .claude/skills/agentos-builder/references/gap.md; grep -n "Sentry" .claude/skills/agentos-builder/references/gap.md; grep -n "agentos-builder.local.json" .gitignore`
Expected: seções `0.`–`6.`; nenhuma linha com "Sentry"; uma linha no `.gitignore`.

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/agentos-builder/references/gap.md .gitignore
git commit -m "docs(gap): três gatilhos, reportante local, canal 1 devolve chamado do GLPI, redação via gap_redact

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: `SKILL.md`, `README.md`, `ARMADILHAS.md`

**Files:**
- Modify: `.claude/skills/agentos-builder/SKILL.md` (router e regra)
- Modify: `README.md` (linhas ~30–31 e ~83)
- Modify: `ARMADILHAS.md` (nova §20 antes de `## Quando algo não for culpa da sua spec`)

- [ ] **Step 1: SKILL.md** — na tabela do router, substitua a linha `| Gap (parar, reportar, retomar) | Live | `references/gap.md` |` por:

```markdown
| Gap (parar, reportar, retomar) | Live | `references/gap.md` |
| Reportar (`/reportar` — chamado no GLPI sob demanda) | Live | `references/gap.md` §0 gatilho 3 |
```

No parágrafo **O humano nunca responde campo de schema.**, substitua `gap.md` — parar, reportar por `spec_feedback`, deixar o rascunho retomável. Nunca contornar.` por `gap.md` — parar, montar o rascunho redigido, perguntar, e só então abrir o chamado no GLPI por `spec_feedback`; deixar o rascunho retomável. Nunca contornar, nunca abrir sem "sim".` Substitua `All 10 operations` por `All 11 operations`. Bump `version: "0.6.0"` → `"0.7.0"`.

- [ ] **Step 2: README.md** — substitua as duas linhas `` `spec_feedback` (usada pelo `gap.md`) — cobertura pelos 6 scopes acima **a\nconfirmar no sandbox**. `` por:

```markdown
`spec_feedback` (usada pelo `gap.md`) exige só `spec.read` (🔍 `required_scope`
no registry, 22/09/2026) — a lista acima já a cobre.
```

Na frase da seção "Autorando" que diz `reporta pela tool `spec_feedback` (a mesma do megafone da tela) e deixa o`, troque `(a mesma do megafone da tela)` por `(que abre o chamado no GLPI pela plataforma, com o seu nome como reportante, sempre depois de você aprovar o rascunho)`.

- [ ] **Step 3: ARMADILHAS.md** — insira antes de `## Quando algo não for culpa da sua spec`:

```markdown
## 20. O GLPI responde HTML com 200 quando o NPM está em manutenção

🔍 Lido no cliente da plataforma (`cdm.glpi`, teste
`test_html_maintenance_page_with_200_is_glpi_error_not_crash`): o proxy na
frente do GLPI devolve uma página HTML **com status 200** durante manutenção.
Quem parseia JSON sem olhar o `content-type` quebra com `ValueError`, não com
"indisponível".

Para quem autora pelo kit isso chega como `McpClientError` com
`code="upstream_unavailable"` no `feedback()` — não é bug da sua spec nem da
chave: o canal está fora. O `gap.md` §5 manda cair no fallback (issue ou
texto) e registrar `# Gap reportado:` do mesmo jeito. Tente o chamado de novo
mais tarde só se o usuário pedir; a plataforma deduplica pelo `external_id`.

---

```

- [ ] **Step 4: Verify**

Run: `grep -n "All 11\|version: \"0.7.0\"\|Reportar" .claude/skills/agentos-builder/SKILL.md; grep -n "a confirmar" README.md; grep -n "^## 20" ARMADILHAS.md; cd .claude/skills/agentos-builder && for t in tests/test_mcp_client_error_parse.py tests/test_mcp_client_feedback.py tests/test_publish_guard.py tests/test_gap_redact.py; do python3 $t || exit 1; done`
Expected: três hits no SKILL.md; nenhum "a confirmar" no README; `## 20` presente; quatro `: ok`.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/agentos-builder/SKILL.md README.md ARMADILHAS.md
git commit -m "docs(skill,readme,armadilhas): /reportar no router, escopo do spec_feedback fechado, §20 GLPI HTML 200

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Capítulo do guia — fragmento HTML

**Files:**
- Create: `docs/guia/glpi-chamado.html`

**Interfaces:**
- Consumes: o markup da seção `c14` de `~/shared/keycloak-glpi-guia.html` (classes `kicker g`, `lede`, `mer`/`mermaid`, `steps`, `callout g`). Não há como validar contra o guia publicado daqui; o fragmento é colado pelo Gianluka depois de `c14`.
- Produces: `<section id="c15" data-track="daos glpi dev">` autocontida.

- [ ] **Step 1: Write the fragment**

```html
<section id="c15" data-track="daos glpi dev">
  <div class="kicker g">Capítulo 15</div>
  <h2>Dev-kit → GLPI: travou na autoria, vira chamado</h2>
  <p class="lede">Quem cria agentes pelo dev-kit (analista ou dev) não precisa de acesso ao GLPI nem de credencial nenhuma: quando a autoria trava, o kit monta o rascunho, pergunta, e a <b>plataforma</b> abre o chamado. O número e o link voltam na conversa.</p>
  <p>Contrato e desenho: <code>agenteos-dev-kit/docs/superpowers/specs/2026-09-22-glpi-chamado-pelo-kit-design.md</code>. Reaproveita o mesmo usuário técnico, o mesmo cliente e o mesmo mapeamento de categorias do capítulo 14.</p>

  <h3>O mapa</h3>
  <div class="mer"><pre class="mermaid">
flowchart LR
  A["Analista / dev&lt;br/&gt;Claude Code + dev-kit"] -->|"1. gap, MCP falhando 2x, ou /reportar"| K["skill agentos-builder&lt;br/&gt;references/gap.md"]
  K -->|"2. rascunho redigido (gap_redact) → pergunta → sim"| M["MCP do AgenteOS&lt;br/&gt;tool spec_feedback"]
  M -->|"3. dedup por external_id"| S["GLPI API v2&lt;br/&gt;GET /Assistance/Ticket?filter="]
  M -->|"4. POST /Assistance/Ticket&lt;br/&gt;grant password, usuário técnico"| T["Chamado&lt;br/&gt;Incidente ou Requisição"]
  M -->|"5. {ticket_id, url, deduplicated}"| K
  K -->|"6. 'Chamado #N aberto: link'"| A
  classDef g fill:#FBF1E1,stroke:#A8681A,color:#101B28
  class S,T g
  </pre></div>

  <h3>O que dispara a sugestão</h3>
  <ol class="steps">
    <li><b>Gap.</b> A derivação ou o test run precisa de conexão, tool, strategy ou modelo que o ambiente não tem. O kit para ali.</li>
    <li><b>MCP falhando duas vezes no mesmo passo.</b> Erro de servidor em <code>spec_write</code>, <code>spec_validate</code>, <code>spec_test_run</code> ou <code>spec_publish</code>, duas vezes seguidas. Erro de validação da spec não conta.</li>
    <li><b>Pedido explícito.</b> "travou", "bug" ou <code>/reportar</code>.</li>
  </ol>
  <div class="callout g"><b class="t">Nunca abre sozinho</b>O kit mostra o rascunho inteiro — uma frase em linguagem de negócio e o pedido técnico, já sem UUID de conexão, CPF, token ou conteúdo de run — e só chama a plataforma depois do "sim".</div>

  <h3>O que chega no GLPI</h3>
  <ul>
    <li>Título <code>[dev-kit] Reportar erro: &lt;primeira linha&gt;</code> (Incidente) ou <code>[dev-kit] Sugestão de melhoria: …</code> (Requisição).</li>
    <li>Corpo: mensagem, depois <b>Reportado por</b> (nome e e-mail que o kit perguntou uma vez), tenant, slug e versão do rascunho, tool e passo, versão do kit, data.</li>
    <li>Requerente: o usuário técnico <code>agenteos-api</code>, como no capítulo 14. A pessoa está no corpo.</li>
    <li>Relato repetido (mesmo tenant, categoria, primeira linha e slug) não abre outro chamado: volta o existente com <em>deduplicated</em> e um followup "reportado de novo por …".</li>
  </ul>

  <h3>Quando o GLPI não responde</h3>
  <p>Página de manutenção do NPM, 5xx ou token recusado viram <code>upstream_unavailable</code> na tool — nunca 500. O kit avisa que o canal está fora e cai no fallback: issue no repositório do kit (se houver <code>gh</code>) ou o texto pronto para repassar ao time TBC. Nada se perde; o rascunho fica marcado no cabeçalho para retomar.</p>

  <h3>Para quem administra</h3>
  <ul>
    <li>O <code>mcp-server</code> do spoke precisa das cinco variáveis <code>glpi_*</code> da API v2 (as mesmas do api-gateway). Sem elas a tool devolve <code>upstream_unavailable</code>.</li>
    <li>Anexos não entram nesta versão: o log vai no corpo. Quando entrarem, a API v1 já está ao alcance do servidor.</li>
  </ul>
</section>
```

- [ ] **Step 2: Verify well-formedness**

Run: `python3 -c "import html.parser,sys; p=html.parser.HTMLParser(); p.feed(open('docs/guia/glpi-chamado.html',encoding='utf-8').read()); print('parse ok')"; grep -c "<section\|</section>" docs/guia/glpi-chamado.html`
Expected: `parse ok`; `2`.

- [ ] **Step 3: Commit and open the PR**

```bash
git add docs/guia/glpi-chamado.html
git commit -m "docs(guia): capítulo 15 — dev-kit abre chamado no GLPI (fragmento para colar no guia)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push -u origin feat/glpi-chamado-kit
gh pr create --title "feat(skill): trava vira chamado no GLPI — gatilhos, consentimento, redação, retorno" --body "Lado do kit do spec docs/superpowers/specs/2026-09-22-glpi-chamado-pelo-kit-design.md (#30). A plataforma (spec_feedback → GLPI) está com a sessão do Agente_OS.

- mcp_client.feedback() exige reporter_name/email e repassa {ticket_id, url, deduplicated}
- scripts/gap_redact.py: redação mecânica (UUID, default:, CPF, token, e-mail, telefone) + teste
- gap.md: §0 três gatilhos (nunca abre sozinho), reportante em .claude/agentos-builder.local.json (gitignored), canal 1 devolve o chamado
- SKILL.md 0.7.0 com /reportar; README fecha a nota de escopo (spec_feedback exige spec.read); ARMADILHAS §20
- docs/guia/glpi-chamado.html: capítulo 15 para o guia Keycloak/GLPI (publicação por scp fica com o Gianluka)

Prova ao vivo (feedback() contra o sandbox devolvendo ticket_id) depende do deploy da plataforma; até lá os testes são sem rede contra o contrato.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

### Task 6: Prova ao vivo (depois do deploy da plataforma)

**Files:** nenhum novo. Só roda quando a sessão do Agente_OS avisar que `spec_feedback` com destino GLPI está no sandbox-os.

- [ ] **Step 1: Chamado de teste pelo cliente do kit**

Run (de `.claude/skills/agentos-builder/`, com `MCP_URL`/`MCP_KEY`):
```bash
python3 -c "
import sys; sys.path.insert(0,'scripts'); import mcp_client as m
r = m.feedback('melhoria', '[kit] TESTE dev-kit — pode fechar. Prova do canal spec_feedback→GLPI.', context={'reporter_name':'Dev-kit smoke','reporter_email':'devkit@tbc.test','slug':'probe-http-body','version':'1','tool':'spec_feedback','kit_version':'0.7.0','step':'smoke'})
print(r)
r2 = m.feedback('melhoria', '[kit] TESTE dev-kit — pode fechar. Prova do canal spec_feedback→GLPI.', context={'reporter_name':'Dev-kit smoke','reporter_email':'devkit@tbc.test','slug':'probe-http-body','version':'1','tool':'spec_feedback','kit_version':'0.7.0','step':'smoke'})
print(r2)
"
```
Expected: primeiro `{"status": "ok", "ticket_id": N, "url": ".../front/ticket.form.php?id=N", "deduplicated": false}`; segundo com o **mesmo** `ticket_id` e `deduplicated: true`.

- [ ] **Step 2: Fechar o chamado de teste no GLPI** (pela tela, ou pedir à sessão do Agente_OS) e anotar o número no corpo do PR do kit como evidência 📏.

- [ ] **Step 3: Se o passo 1 falhar com `upstream_unavailable`** — não é do kit: repassar à sessão do Agente_OS com o `McpClientError` completo. O PR do kit pode entrar antes; a prova entra como comentário depois.

---

## Self-review

**Spec coverage (lado do kit).** §4 gatilhos → Task 3 §0; consentimento → Task 3 §0 + SKILL (Task 4); rascunho duas camadas → já em gap.md §3 (intacto); redação → Task 2 + Task 3 §4; reportante local → Task 3 §5 + `.gitignore`; retorno/cabeçalho → Task 3 §5; cliente `feedback()` → Task 1. §5-kit testes → Tasks 1, 2 (a redação era "a única lógica que precisa de teste"). §6-kit docs → Task 4 (gap.md, SKILL, README, ARMADILHAS §20) e Task 5 (guia). §7 linha 3 → Tasks 1–4; linha 4 → Task 5. Prova ao vivo → Task 6, dependente do deploy.

**Placeholders.** Nenhum "TBD"/"similar to". O `<N>`/`<data>` nos cabeçalhos são o formato que o modelo preenche, não lacunas do plano.

**Type consistency.** `feedback(category, message, context)` igual em Task 1, Task 3 §5 e Task 6. `redact(text) -> str` igual em Task 2 e Task 3 §4. Chaves `reporter_name`/`reporter_email` iguais em Tasks 1, 3, 5, 6. `# Gap reportado: glpi #N — <data>` igual em Task 3 e Task 4 (ARMADILHAS §20 cita só o prefixo). `version` `"0.7.0"` em Task 4 e Task 6.
