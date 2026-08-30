# Armadilhas conhecidas

Cada item aqui **custou tempo de alguém**. Nada é suposição sobre como a
plataforma deveria funcionar: tudo foi **medido ao vivo num sandbox real ou
verificado no código da plataforma**.

Os dois têm força diferente, e o documento marca qual é qual:

- **📏 medido** — aconteceu, com run/evidência.
- **🔍 código** — lido na fonte da plataforma, mas ainda não exercitado por um
  autor. Encontrou exceção na prática? **Corrija aqui.**

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
>
> **Uma exceção existe e não é sua para consertar:** o `when` de um nó
> `approval` não é fail-closed — ver §4. Por isso a regra lá é não usar `when`
> em approval.
>
> E há um segundo motivo, mais forte, para gatear no VEREDITO e não na presença
> do nó: 📏 um approval pode vir `skipped` **sem decisão humana nenhuma** — por
> `when` fora da gramática ou por contexto vazio (passo anterior falhou). Nos
> dois casos o run segue como aprovado, e `aprovar.decision.decision` é a única
> coisa que não resolve. Ver §4.

**Por que o erro é silencioso:** numa `condition`, um caminho que **não
resolve** é tratado como `None` (🔍 `hatchet_app.py`, docstring de
`_eval_condition`) — não levanta,
não avisa, apenas compara falso e o fluxo segue pelo ramo negativo. Um erro de
digitação no caminho tem exatamente a mesma aparência de "o humano rejeitou".
Ao depurar, confira primeiro se o caminho existe no output do passo anterior.

**Nota para grafo simples:** acima, `items` e `aprovados` aparecem preenchidos —
mas num approval **sem `context_from`** os dois vêm **vazios**, que é o caso de
quem está começando. `status` e `decision.decision` continuam iguais; só a lista
some. O porquê está na §2.

📏 Medido em 26/08/2026 (`test-sftp` v3 → v4).

---

## 2. Approval que gera item SEM `action` derruba a `/inbox` INTEIRA

### O sintoma (📏 medido, repro determinística 3×)

Um item de approval que nasce com `action` vazio faz a fila de aprovações **não
renderizar**: `Cannot read properties of undefined (reading 'replace')`.

Não é só o seu card: a página cai por inteiro, levando junto **os itens de todos
os outros agentes do tenant**. A única saída é decidir o item por API
(`POST /api/v1/approval-items/<id>/decide`) — HITL sem UI.

Repro: `/inbox` normal → roda agente cujo approval gera item sem `action` →
`/inbox` quebra → decide por API → `/inbox` volta.

O front foi blindado (PR #586 da plataforma: item malformado vira card feio, não
página fora do ar). Mas **o item continua sem headline** — quem conserta o card
não conserta a sua spec.

### Como evitar (🔍 código — a cura ainda NÃO foi confirmada por um run)

O `action` é montado a partir de **`config.context_from`**: o runtime só entra no
bloco que monta o card quando `context_from` está declarado **e** aponta para um
passo que existe em `step_results`. Sem isso, o item nasce sem `action` — foi o
caso do `test-sftp`, um approval simples sem passo de lista a montante.

O `headline_template` é **opcional dentro desse bloco** (tem default
`"{count} {noun} — R$ {total:.2f}"`) e só é lido depois que o `context_from`
resolveu. Ou seja: declarar `headline_template` sozinho, sem `context_from`,
provavelmente **não** resolve.

Contra-evidência que sustenta isso: **nenhuma spec publicada declara
`headline_template`**, e mesmo assim os cards da `fin-pagamentos` têm headline —
ela usa `context_from` + `amount_path`/`title_path`/`supplier_name_path`.

### ⚠️ Isto NÃO é caso exótico — é o approval mínimo

Um nó `approval` **sem `context_from`** produz item com `action`, `items` e
`aprovados` **todos vazios**. E um approval sem passo anterior que produza lista
é exatamente o que se escreve num grafo simples — o primeiro agente de quase
todo autor.

Ou seja: **todo mundo que começa cai nisto.** Não é borda, é o caminho comum.

Duas consequências práticas:

- Se a sua `/inbox` quebrou logo no primeiro agente com approval, o problema
  provavelmente é este, e não algo que você escreveu errado.
- Exigir `headline_template` não seria conserto suficiente: o caso mínimo não
  tem `context_from`, e sem ele o `headline_template` nem chega a ser lido.

**Recomendação enquanto não há confirmação:** se o card precisa mostrar conteúdo,
o `approval` precisa de um passo a montante produzindo lista, apontado em
`context_from`. Se o seu grafo não tem esse passo naturalmente, saiba que o item
vai nascer vazio.

> 🔴 **Ao declarar `context_from`, leia a §4 antes.** O gate de alçada só roda
> quando o `context_from` resolve — então seguir esta recomendação é o que ativa
> o caminho onde um `config.when` mal escrito **pula a aprovação humana**. Se
> você declarar `context_from`, não use `when` no mesmo nó.

O experimento que fecharia esta seção (ainda não feito): approval **com**
`context_from` apontando um passo que produza lista **e** `headline_template`
declarado junto — só assim dá para separar o que cada um faz. Se você rodar,
**atualize aqui**; é a única seção deste documento cuja cura não foi exercitada.

---

## 3. `spec_publish` NÃO é atômico — publish rejeitado ainda queima a versão

O servidor grava `published/<slug>/vN.yaml` **antes** de validar contra o
catálogo. Se o catálogo recusar, a mensagem diz:

> Catálogo rejeitou a spec — **nada foi semeado**

Isso é verdade sobre o catálogo e **mentira sobre o disco**: o arquivo já está
no volume, publicado, imutável — e não existe unpublish (DAI-637). O número
daquela versão está queimado para sempre; você segue para a próxima.

> 💡 **A saída para não pagar este preço enquanto experimenta: `spec_test_run`**
> roda o draft sem publicar nada (§9). Publique só quando a dúvida já estiver
> resolvida.

**Antes de `spec_publish`, confira o que o catálogo valida:**

- **`id` é ESTÁVEL entre versões.** Não acompanha o `vN`. Mudar o `id` de uma
  versão para outra dá `Slug já em uso por outro AgentSpec` — e queima a versão.
  Confira com `spec_read` de um agente que já tenha várias versões publicadas.
- Toda property do `config_schema` precisa de `title` e `description` (lint D-02).
- **O gate de major olha o campo `change_class`, NÃO o dígito do semver.** Só
  recusa quando `change_class: "major"` **e** existe contrato `active` com
  `version_pinned` NULL — aí exige `allow_major`. Publicar `3.0.0` e `4.0.0` com
  contrato ativo passa normalmente se a spec declarar `change_class: "minor"`
  (📏 medido: as duas foram semeadas sem `allow_major`).

### ⚠️ O incentivo está invertido: declarar `major` honestamente CUSTA uma versão

Junte as duas coisas acima e o resultado é perverso (🔍 código):

1. `change_class: "major"` num slug com contrato ativo **não pinado** faz o
   catálogo recusar o publish (guard R8, em `agent_specs/seed.py::upsert_spec`).
2. Essa recusa cai no **mesmo** `report.rejeitados` de qualquer outra — e o
   arquivo **já foi gravado** antes: em `mcp_server/tools/spec_publish.py`, a
   chamada a `specs_service.publish_spec()` (promove o arquivo) vem **antes** da
   chamada a `seed_spec()` (valida o catálogo).

Ou seja: **a declaração honesta queima o número da versão permanentemente**, e
declarar `minor` passa liso. O autor que classifica direito é punido; o que
subdeclara, não.

**Enquanto isso não mudar:** se a sua mudança é mesmo major e o slug tem
contrato ativo não pinado, alinhe com o admin do ambiente **antes** de publicar
(`allow_major`, ou pinar o contrato numa versão). Não descubra pelo publish
recusado — o número já terá ido embora.

Consequência para quem lê o histórico: `change_class` de spec publicada **não é
confiável** como registro do tamanho da mudança. Olhe o diff, não o campo.

> **Nota para quem for consertar isto na plataforma:** o caminho do contrato
> hub→spoke (`platform_contract.py::_ingest_material`) já faz na ordem certa —
> valida o schema, roda o lint D-02, chama o `seed_spec` e **só então** escreve
> os templates em disco. É o molde; o `spec_publish` do MCP é que está invertido.
> Verificado em 27/08/2026: `publish_spec` tem **um único** call site antes de
> `seed_spec`, então o conserto é num lugar só.

📏 Medido em 26/08/2026: `test-sftp` v2 ficou publicada, fora do catálogo, sem
como limpar.

---

## 4. `config.when` funciona em nó de escrita — e é avaliado DEPOIS da condition

📏 `config.when` vale para `sftp_op` (medido em 26/08: com `operacao: put`, os nós
`mover` e `deletar` vieram com `reason: when_false` enquanto `criar` executou).

Mas atenção à ordem: se um `condition` a montante pular os nós, eles nunca
chegam a avaliar o `when`. Um `when` que "não funcionou" quase sempre é uma
condition anterior que já desviou o fluxo — confira o `reason` de cada nó pulado:
`when_false` (o when barrou) é diferente de `condition_jump` (nem chegou lá).

### 🔴 Exceção do `approval` — a única do doc onde errar significa escrita sem aprovação

**NÃO use `when` em nó `approval`.** Não é cautela: num dos dois caminhos, uma
expressão fora de três formas exatas **pula o humano em silêncio**.

Existem **dois** campos `when` diferentes num nó approval, com códigos e
comportamentos distintos. Confunda-os e você tira a conclusão errada.

#### `config.when` (dentro do `config`) — 🔴 o perigoso

Avaliado pelo gate de alçada (`hatchet_app.py`, bloco `if node_type ==
"approval"`), via `_evaluate_condition_expr`. Esse avaliador reconhece
**exatamente três formas**:

```
len(<path>) <op> <int>
<path> == 'string'   /  <path> != 'string'
<path> == null       /  <path> != null
```

Qualquer outra coisa loga um warning e devolve `False` — e ali `False` significa
**`_skip_approval = True`**. Executei o avaliador (🔍 + execução isolada):

| `config.when` | avalia | efeito |
|---|---|---|
| `config.alcada_hitl != null` | True | pede aprovação ✅ |
| `config.total > 1000` | False | **pula o humano** 🔴 |
| `config.total >= 1000` | False | **pula o humano** 🔴 |
| `config.exige_aprovacao` (truthiness pura) | False | **pula o humano** 🔴 |
| `config.notificar_resumo_suprimido != true` | False | **pula o humano** 🔴 |
| `config.alcada_hitl != nulo` (typo) | False | **pula o humano** 🔴 |

**Erro de escrita e "dispense a aprovação" são indistinguíveis.**

#### As duas gramáticas se CRUZAM — copiar de outro nó é a armadilha

Não é "o approval aceita menos". Cada gate aceita formas que o outro não aceita:

| forma | nó normal | `approval` |
|---|---|---|
| `config.<key>` (truthiness pura) | ✅ | 🔴 pula o humano |
| `config.<key> != true` / `== true` | ✅ | 🔴 pula o humano |
| `config.<key> == 'string'` / `!=` | ✅ | ✅ |
| `config.<key> == null` / `!= null` | ✅ | ✅ |
| `len(<path>) <op> <int>` | ❌ | ✅ |

As duas primeiras linhas são o risco real, porque **têm precedente vivo para
copiar**: a truthiness pura e o `!= true` são formas documentadas do gate
genérico, e o `!= true` aparece textualmente numa spec publicada
(`config.notificar_resumo_suprimido != true`). O autor não precisa inventar
nada — basta copiar de um nó que viu funcionando, e no approval aquilo vira
"dispense o humano".

> ⚠️ **A §2 leva você para dentro desta região.** O gate de alçada só roda quando
> o `context_from` resolve. Ou seja, quem segue o conselho da §2 (declarar
> `context_from` para não derrubar a `/inbox`) é exatamente quem passa a ser
> afetado por isto. E **sem `context_from` o `config.when` é ignorado por
> inteiro** — a aprovação sempre acontece. Consequência prática: testar no
> approval mínimo dá **falso negativo**; você conclui que o problema não existe.

#### `node.when` (topo do nó) — o menos grave

Avaliado em `executors.py::_execute_approval` (passo 1). O executor espera um
**booleano já avaliado**; recebendo outra coisa, loga warning e cai em
truthiness. Logo, uma **string não-vazia avalia verdadeiro e a aprovação
acontece**. Só um falsy literal devolveria `{"status": "skipped", "reason":
"when_false"}`.

#### Estado hoje

- 🔍 **Não há regressão viva.** As três specs publicadas que usam `when` em
  approval (`fin-pagamentos` v3, `-pix` v1, `-cnab` v1) usam todas
  `config.alcada_hitl != null` — forma reconhecida. É **sorte histórica**, não
  proteção: conferir em produção e ver funcionando não desmente nada.
- 🔍 **Não há defesa em autoria.** O lint que roda antes da promoção valida o
  `config_schema`; não olha `when` nem `approval`. Uma spec com `when` inválido
  **publica limpa**.

#### 📏 Medido — dois runs, com braço de controle

| braço | `config.when` | run_id | resultado |
|---|---|---|---|
| controle | `config.alcada_hitl == null` (forma reconhecida) | `5d8ec509-43bb-44ea-bd30-0953766e9f95` | `awaiting_approval` — **card nasceu** |
| teste | `config.total > 1000` (forma inválida) | `235c25e7-a961-432a-a0ed-3d0ed73876f2` | `aprovar` **skipped**, `reason: alcada_below_threshold`, run **completed** |

Mesmo draft, mesma config, só a linha do `when` mudou. Feito com `spec_test_run`
num draft descartável e grafo só de leitura — sem publicar nada, sem nó de
escrita, custo zero de catálogo (ver §9).

---

### 🔴 O outro jeito de pular o humano — e este não exige que você erre nada

📏 Medido no mesmo ciclo (run `26b5c8b6-6477-4f9d-b599-e5b459c8aa3c`): o nó de
listagem **falhou** (erro de infra), o `transform` a jusante devolveu `[]`, e o
`approval` veio `skipped` com `reason: empty_context` — run **completed**.

**Um passo anterior falhando esvazia o `context_from`, e a aprovação humana é
pulada em silêncio.** O caso do `when` exige um typo do autor; este dispara
sozinho quando o ERP ou o SFTP está fora do ar.

O mecanismo comum aos dois está em `_APPROVED_STATUSES`, que inclui
`"skipped"` — o halt-check depois do approval deixa passar, por desenho (uma
aprovação legitimamente dispensada não deve virar run failed).

> ⚠️ Some isto ao aviso da §2: declarar `context_from` é o que ativa **os dois**
> caminhos. Sem `context_from`, o bloco nem roda e a aprovação sempre acontece.

### ✅ A defesa que cobre os dois

**Gateie a escrita no VEREDITO, nunca na simples presença do nó de approval:**

```yaml
expr: "aprovar.decision.decision == 'approved'"
```

É o mesmo caminho da §1, e agora com o segundo motivo para existir: sem decisão
humana, `decision.decision` **não resolve**, vale `None`, compara falso e a
condition cai no ramo negativo. Nos dois cenários acima — `when` fora da
gramática e contexto vazio — o run segue como se estivesse aprovado, e **só o
gate no veredito segura a escrita**.

> Achado do PR monitor (o caminho do `when`) e da sessão de autoria (o
> `empty_context`), medido por ela. Esta seção **contradiz de propósito** a
> regra de fail-closed da §1: aqui o mecanismo não protege sozinho — a proteção
> é não usar `when` em approval **e** gatear no veredito.

---

## 5. Chat só dispara run se a spec declarar `chat_system_prompt`

> **🔍 Seção lida no código da plataforma**, ainda não exercitada por um autor.
> O que foi 📏 medido aqui: o concierge responde texto e manda clicar
> "Executar", e o POST desse botão manda `input: {conversation_id}` — **sem**
> campo de mensagem. O resto abaixo (marcador, shape do `run.input`, guard)
> vem da fonte. Provou na prática? Corrija aqui.

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

- **`allowed_ops`** — 📏 o campo aparece no `spec_connectors` e é a forma
  independente de confirmar que a mudança feita na UI pegou de fato (antes, só
  dava para confiar na tela). 🔍 Uma conexão `read_only` recusa escrita **no
  executor** com `error_class: cap` — comportamento correto, não bug da sua
  spec.
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
- 🔍 `spec_write` sem o parâmetro `templates` grava `templates: []` — se a spec
  referencia um `.j2`, ela quebra em execução. Mande os templates no mesmo write.
- A chave de versão do store é o **major puro** (`"0"`, `"1"`), não `"0.1"`. O
  semver completo vive no campo `version:` de dentro do YAML.
- 📏 `idempotency_key` de escrita é injetada pelo runtime — o autor **não**
  declara em `sftp_op`. (Em `http_request`, declara.) Visto num run real:
  `<run_id>_criar_0`.

---

## 9. `spec_test_run`: teste o draft SEM queimar uma versão

📏 A §3 diz que publicar errado queima o número da versão para sempre. A saída é
**não publicar para testar**: `spec_test_run` executa um **draft**, sem promover
nada e sem tocar o catálogo. Foi assim que a §4 saiu de 🔍 para 📏 — dois runs
com braço de controle, num draft descartável, custo zero.

**Use isto sempre que a dúvida for "o que este grafo faz de verdade".** É a
única forma de medir sem pagar o preço da §3.

Duas coisas que só se descobrem usando (📏):

- **Não faz merge da config do tenant, MAS aplica os defaults do
  `config_schema`.** Property com `default` resolve; property **sem** default
  chega ao executor como **template cru** (`{{config.x}}` literal). Foi o que
  fez um `sftp_op` de teste responder 500 — o `connection_id` chegou literal.
  Se o seu draft depende de conexão, declare `default` no `config_schema` ou
  espere o erro.
- **Grafo só de leitura é o que torna o teste barato.** Sem nó de escrita, não
  há efeito colateral em ERP, SFTP ou ledger — dá para repetir à vontade e
  variar uma linha por vez, que é o que transforma observação em medição.

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
