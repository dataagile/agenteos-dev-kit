# Armadilhas conhecidas

Cada item aqui **custou tempo de alguém**. Todos foram medidos ao vivo contra um
sandbox real — não são suposições sobre como a plataforma deveria funcionar.

Leia antes de publicar o primeiro agente. As duas primeiras seções são as que
mais queimam tempo.

---

## 1. Aprovação: o veredito está DUAS camadas abaixo

O nó `approval` devolve:

```json
{
  "type": "...", "items": [...], "status": "approved",
  "decision": {"item_id": "...", "decision": "approved", "decided_by": "...", "edited_values": {}},
  "aprovados": [...]
}
```

O `decision` de fora é **o dicionário do item**. O veredito é o `decision` de
dentro:

```yaml
# ✅ certo
expr: "aprovar.decision.decision == 'approved'"

# ❌ compara dict com string — sempre falso
expr: "aprovar.decision == 'approved'"
```

**Por que isso é pior do que parece:** com a comparação errada, o humano aprova,
a condition dá `false` e os nós de escrita são pulados por `condition_jump`. O
run termina **Concluída**, sem erro — e nada foi escrito. Se você tivesse
desenhado fail-*open*, teria escrito sem aprovação.

> Desenhe sempre fail-closed: a condition libera a escrita, nunca a bloqueia.
> Foi o que transformou este erro em "não fez nada" em vez de "fez sem aprovar".

Medido em 26/08/2026 (`test-sftp` v3 → v4).

---

## 2. Nó `approval` sem `headline_template` derruba a `/inbox` INTEIRA

Se a sua spec não declara `config.headline_template` no nó `approval`, o item
nasce com `action` vazio — e a fila de aprovações **não renderiza**, com
`Cannot read properties of undefined (reading 'replace')`.

Não é só o seu card: a página cai por inteiro, levando junto **os itens de todos
os outros agentes do tenant**. A única saída é decidir o item por API
(`POST /api/v1/approval-items/<id>/decide`).

**Sempre declare `headline_template` em nó `approval`.**

O front foi blindado (PR #586 da plataforma: item malformado vira card feio, não
página fora do ar), mas o item continua sem headline — quem consertar o card não
conserta a sua spec.

Medido em 26/08/2026, com repro determinística.

---

## 3. `spec_publish` NÃO é atômico — publish rejeitado ainda queima a versão

O servidor grava `published/<slug>/vN.yaml` **antes** de validar contra o
catálogo. Se o catálogo recusar, a mensagem diz:

> Catálogo rejeitou a spec — **nada foi semeado**

Isso é verdade sobre o catálogo e **mentira sobre o disco**: o arquivo já está
no volume, publicado, imutável — e não existe unpublish (DAI-637). O número
daquela versão está queimado para sempre; você segue para a próxima.

**Antes de `spec_publish`, confira o que o catálogo valida:**

- **`id` é ESTÁVEL entre versões.** Não acompanha o `vN`. Mudar o `id` de uma
  versão para outra dá `Slug já em uso por outro AgentSpec` — e queima a versão.
  Confira com `spec_read` de um agente que já tenha várias versões publicadas.
- Toda property do `config_schema` precisa de `title` e `description` (lint D-02).
- Major novo (`2.0.0` → `3.0.0`) com contrato ativo é recusado sem `allow_major`.

Medido em 26/08/2026: `test-sftp` v2 ficou publicada, fora do catálogo, sem como
limpar.

---

## 4. `config.when` funciona em nó de escrita — e é avaliado DEPOIS da condition

`config.when` vale para `sftp_op` (provado em 26/08: com `operacao: put`, os nós
`mover` e `deletar` vieram com `reason: when_false` enquanto `criar` executou).

Mas atenção à ordem: se um `condition` a montante pular os nós, eles nunca
chegam a avaliar o `when`. Um `when` que "não funcionou" quase sempre é uma
condition anterior que já desviou o fluxo — confira o `reason` de cada nó pulado:
`when_false` (o when barrou) é diferente de `condition_jump` (nem chegou lá).

**Exceção que vale conhecer:** o `when` de um nó `approval` é fail-**open** — um
`when` ilegível PULA a aprovação em vez de barrar. Não use `when` em approval.

---

## 5. Chat só dispara run se a spec declarar `chat_system_prompt`

Se o seu agente conversa mas nunca executa — o concierge responde texto e manda
clicar "Executar" — **não é limitação da plataforma**. A ponte chat→run existe,
e depende de o modelo emitir um marcador na última linha da resposta.

Quem instrui o modelo a emitir o marcador é `metadata.chat_system_prompt`, na
sua spec. Sem esse campo, nada dispara.

Veja um exemplo real: `spec_read('agente-smartview', '4')` → `metadata`.

### O que chega em `run.input`

Quando o run vem pelo marcador, o `run.input` tem **exatamente uma chave**:

```json
{"mensagem": "<o JSON do marcador, re-serializado como STRING>"}
```

Consequências práticas:

- `{{run.input.mensagem}}` funciona. **`{{run.input.op}}` não** — não há parse
  automático; é uma string. Para alcançar os campos, desserialize num nó
  `transform`.
- `mensagem` carrega o **payload do marcador**, não a frase crua do usuário.

### ⚠️ E o guard que barra a escrita

Uma ref a `{{run.input.*}}` dentro de um nó de escrita **mata o run** com
`untrusted_input_in_write` — e `sftp_op` conta como escrita (assim como
`http_request`). O portão é o campo `input_trust_level`, que o chat **não**
define: por padrão, input de chat não é confiável.

**Logo: um path que venha do chat não pode chegar no `sftp_op`.** Desenhe com o
path vindo do `config` (o autor declara), ou use o pedido do usuário apenas para
ESCOLHER entre opções fixas do config — nunca para compor o path.

---

## 6. Conexão: leia o `config` antes de desenhar a escrita

`spec_connectors` devolve o `config` público de cada conexão (sem segredos).
Olhe **antes** de escrever a spec:

- **`allowed_ops`** — uma conexão `read_only` recusa escrita no executor, com
  `error_class: cap`. Isso é comportamento correto, não bug da sua spec. E é a
  forma independente de confirmar que a mudança feita na UI pegou de fato.
- **`base_dir`** — é o jail da conexão. Se for `/`, qualquer path relativo
  alcança tudo o que aquele usuário SFTP enxerga. Informação de segurança que
  muda como você desenha o path.

---

## 7. O ambiente pode não estar com o seu agente ativado

- **Publicar não ativa.** Publicar põe no catálogo; rodar exige **contrato ativo**
  e ativação da instância. Em sandbox isso pode depender de liberação manual da
  TBC (veja com o admin do ambiente).
- **Versão nova não migra sozinha.** Com o contrato em `latest`, a instância
  continua na versão pinada; a UI avisa "reative pelo Marketplace", mas o card
  não tem botão de reativar — vá direto em `/products/<slug>/activate`.
- **`main` não é ambiente.** Um fix mergeado no repositório da plataforma só vale
  para você depois de release + deploy no seu sandbox.

---

## 8. Convenções que a validação não pega

- Cada nó precisa de `id` **e** `key` com o mesmo valor.
- `spec_write` sem o parâmetro `templates` grava `templates: []` — se a spec
  referencia um `.j2`, ela quebra em execução. Mande os templates no mesmo write.
- A chave de versão do store é o **major puro** (`"0"`, `"1"`), não `"0.1"`. O
  semver completo vive no campo `version:` de dentro do YAML.
- `idempotency_key` de escrita é injetada pelo runtime (`<run_id>_<no>_<i>`) —
  o autor **não** declara em `sftp_op`. (Em `http_request`, declara.)

---

## Quando algo não for culpa da sua spec

Estes são defeitos de plataforma conhecidos em 26/08/2026. Se bater neles, não
gaste tempo reescrevendo a spec:

| Sintoma | O que é |
|---|---|
| Nó `agent` falha com `couldn't get a connection after 30.00 sec` ou `Model registry load timed out` | Bug de event loop no agent-runtime: o pool do worker não serve o workflow do Hatchet. **Grafo sem nó `agent` não é afetado** — foi assim que o `test-sftp` rodou ponta a ponta. |
| `/runs/<id>` responde "Not Found" | Rota inexistente no front; abra o trace clicando a linha em `/runs`. |
| Settings → Modelos → "Modelos por subagente" diz "Nenhuma etapa configurada" mesmo com nó `agent` | Bug de UI. |

**Regra de ouro do kit:** falta algo para autorar = gap do MCP Server. Reporte
ao time da plataforma (Jira DAI); não contorne com código do core.
