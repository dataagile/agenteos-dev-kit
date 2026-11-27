# Recursos do core

🔍 Tudo neste guia foi lido no código do Agente_OS (main `2e3a045b`, com o mesmo comportamento na produção TBC `cc0fa538`).
📏 Nenhum dos recursos foi medido em run.
A spec registra que cada exemplo YAML passou no `spec_validate` do sandbox-os em 27/11/2026.

## Índice

- [1. Política de erro por nó](#1-política-de-erro-por-nó)
- [2. Saída final do run](#2-saída-final-do-run)
- [3. Loop aninhado com alias](#3-loop-aninhado-com-alias)
- [4. Operações com PDF](#4-operações-com-pdf)
- [5. Filtro e projeção de campos](#5-filtro-e-projeção-de-campos)
- [6. Enriquecimento por chave composta](#6-enriquecimento-por-chave-composta)
- [7. Envio HTTP de artefato](#7-envio-http-de-artefato)
- [8. Rótulos e edição no card de aprovação](#8-rótulos-e-edição-no-card-de-aprovação)
- [9. Configuração temporária no teste](#9-configuração-temporária-no-teste)
- [10. Arquivamento e restauração de rascunho](#10-arquivamento-e-restauração-de-rascunho)
- [11. Conectores TOTVS RM e extrato em PDF](#11-conectores-totvs-rm-e-extrato-em-pdf)
- [12. Anexos do run](#12-anexos-do-run)

## 1. Política de erro por nó

**O que faz.** Define se uma falha aborta o run ou permite que ele siga. Com `continue`, o passo entra em `output.steps_failed`.

**Onde vai.** `on_error: fail | continue` no topo do nó. O padrão é `fail` em nós comuns e `continue` em loops com falha parcial. `channel_send`, `audit_append` e `render_template` usam `continue` quando `config.best_effort: true`.

**Exemplo.**

```yaml
id: "agt_exemplo_on_error_v1"
slug: "exemplo-on-error"
name: "Exemplo: on_error por nó"
version: "0.1.0"
category: "testes"
description: "Passo opcional que pode falhar sem derrubar o run; loop que aborta se um item falhar."
config_schema:
  type: object
  required: [conexao_api]
  properties:
    conexao_api:
      type: string
      x-ref: connection
      title: "Conexão HTTP"
      description: "Conexão HTTP genérica da API de origem"
trigger:
  type: chat
nodes:
  - id: status_opcional
    key: status_opcional
    type: http_request
    connection: "{{config.conexao_api}}"
    method: GET
    path: "/status"
    output: status
    on_error: continue          # falhou: passo failed, run segue, entra em output.steps_failed
  - id: listar
    key: listar
    type: http_request
    connection: "{{config.conexao_api}}"
    method: GET
    path: "/itens"
    output: itens               # sem on_error: nó de topo comum falha o run (default fail)
  - id: detalhar
    key: detalhar
    type: loop
    on_error: fail              # loop com falha parcial SEGUE por default; fail = aborta e compensa
    config:
      over: "listar.result.body"
      limit: 20
      body:
        - id: detalhe
          key: detalhe
          type: http_request
          connection: "{{config.conexao_api}}"
          method: GET
          path: "/itens/{{item.id}}"
          output: detalhe
```

**Armadilhas.** O loop com falha parcial segue por padrão e o run fica `completed`. Use `on_error: fail` no loop para abortar. Valor fora do enum dá erro de schema. Escrita retida no ledger sempre falha. O validador avisa sobre `config.on_error` (`W-CONFIG-ON-ERROR-IGNORED`), `on_error` em filho de loop (`W-ON-ERROR-EM-FILHO-DE-LOOP-IGNORADO`), escrita de topo com `continue` (`W-WRITE-ON-ERROR-CONTINUE`) e loop com escrita e `continue` (`W-LOOP-WRITE-ON-ERROR-CONTINUE`).

**Origem.** `agent_spec_v1.json:177-181`, `agent_spec.py:1608-1647, 1749-1799`, `hatchet_app.py:234-265, 2421-2437`. PR #921 (`56db400c`).

## 2. Saída final do run

**O que faz.** Escolhe a saída final exibida em `get_run` e `spec_run_status`. Usa `result` quando a saída selecionada tem esse campo.

**Onde vai.** `output_from` no topo da spec, com a chave de um nó de topo no padrão `^[a-z0-9_]{1,64}$`. Se omitido, vale o último nó executado.

**Exemplo.**

```yaml
id: "agt_exemplo_output_from_v1"
slug: "exemplo-output-from"
name: "Exemplo: output_from"
version: "0.1.0"
category: "testes"
description: "A saída final do run é a do nó projetar, não a do último nó."
config_schema:
  type: object
  required: [conexao_api]
  properties:
    conexao_api:
      type: string
      x-ref: connection
      title: "Conexão HTTP"
      description: "Conexão HTTP genérica da API de origem"
trigger:
  type: chat
output_from: "projetar"         # chave de nó de TOPO; sem isto = último nó executado
nodes:
  - id: listar
    key: listar
    type: http_request
    connection: "{{config.conexao_api}}"
    method: GET
    path: "/itens"
    output: itens
  - id: projetar
    key: projetar
    type: transform
    config:
      strategy: map_fields
      source: "listar.result.body"
      fields:
        codigo: id
        nome: descricao
  - id: registrar
    key: registrar
    type: audit_append
    entity_type: "Exemplo"
    action: "listado"
```

**Armadilhas.** Nó inexistente dá erro. Para um nó interno de loop, aponte para o próprio loop. Se o nó escolhido for pulado, a saída é `null`. Acima de 64 KiB, retorna `{from, truncated: true, bytes}`.

**Origem.** `agent_spec_v1.json:70-74`, `agent_spec.py:1802-1855`, `hatchet_app.py:4577-4636`, `published/fin-pagamentos/v3.yaml:46`. PR #931 (`4ec23cca`).

## 3. Loop aninhado com alias

**O que faz.** Dá um nome ao item do loop para referenciá-lo no corpo e em loops internos, inclusive em `when` e `condition`. `item` sempre aponta para o item do loop mais interno.

**Onde vai.** No `config` do nó `loop`, use `as` para declarar o alias, `over` para apontar para a lista e `body` para definir o corpo. O alias é opcional e segue `^[a-z_][a-z0-9_]{0,31}$`. Um loop interno pode usar `over: "{{pedido.linhas}}"`. O teto padrão de `config.limit` é 50.

**Exemplo.**

```yaml
id: "agt_exemplo_loop_as_v1"
slug: "exemplo-loop-as"
name: "Exemplo: loop aninhado com config.as"
version: "0.1.0"
category: "testes"
description: "Loop externo por pedido (alias pedido), interno pelas linhas do pedido."
config_schema:
  type: object
  required: [conexao_api]
  properties:
    conexao_api:
      type: string
      x-ref: connection
      title: "Conexão HTTP"
      description: "Conexão HTTP genérica da API de origem"
trigger:
  type: chat
nodes:
  - id: listar_pedidos
    key: listar_pedidos
    type: http_request
    connection: "{{config.conexao_api}}"
    method: GET
    path: "/pedidos"
    output: pedidos
  - id: por_pedido
    key: por_pedido
    type: loop
    config:
      over: "listar_pedidos.result.body"
      as: pedido                    # alias do item externo, visível aqui e nos loops internos
      body:
        - id: por_linha
          key: por_linha
          type: loop
          config:
            over: "{{pedido.linhas}}"   # lista dentro do item externo (whole-value)
            body:
              - id: consultar_linha
                key: consultar_linha
                type: http_request
                connection: "{{config.conexao_api}}"
                method: GET
                path: "/pedidos/{{pedido.id}}/linhas/{{item.seq}}"   # item = linha (o loop mais interno)
                output: linha
                config:
                  when: "pedido.status == 'aberto'"
```

**Armadilhas.** `item`, `config`, `run`, `steps` e `tenant` são reservados. O validador também recusa alias repetido na cadeia ou igual à chave de um nó. Se `over` não resolver ou apontar para outro tipo, o loop roda zero vezes e só registra aviso no log. O builder map ainda descreve a forma legada e omite `as`.

**Origem.** `agent_spec_v1.json:724-728`, `agent_spec.py:438-439, 598-665`, `executors.py:3703-3900`. PRs #920 (`828f29db`) e #939.

## 4. Operações com PDF

**O que faz.** `document.metadata` lê metadados, `document.split` recorta páginas, `document.merge` junta PDFs e `document.ocr` extrai texto. Recorte e junção gravam um novo PDF como artefato.

**Onde vai.** Em nó `type: tool`, coloque `tool_name` e `params` no topo. O passo seguinte lê `{{passo.data.campo}}`.

- `document.metadata` recebe `storage_key` e `max_bytes` opcional (50 MB). Retorna `pages`, `size_bytes`, `encrypted` e, quando disponível, `title`.
- `document.split` recebe `storage_key` e `pages` (por exemplo, `"1-3,7"` ou `[1,2]`). `filename`, `max_bytes` e `max_pages` são opcionais. O limite de páginas é 500.
- `document.merge` recebe pelo menos duas `storage_keys` e aceita os mesmos opcionais do recorte. Ambos devolvem `storage_key`, `filename`, `pages`, `size_bytes` e `artifacts`.
- `document.ocr` recebe `storage_key`. Os opcionais são `pages` (todas), `lang` (`por`), `scale` (2, máximo 6) e `page_timeout_s` (60). Retorna `pages` com `page`, `text` e `chars`, além de `total_chars`.

**Exemplo.**

```yaml
id: "agt_exemplo_document_v1"
slug: "exemplo-document-tools"
name: "Exemplo: document.metadata/split/merge/ocr"
version: "0.1.0"
category: "testes"
description: "Baixa um PDF, lê metadados, recorta a página 1, junta com o original e faz OCR do recorte."
config_schema:
  type: object
  required: [conexao_api]
  properties:
    conexao_api:
      type: string
      x-ref: connection
      title: "Conexão HTTP"
      description: "Conexão HTTP genérica da API de origem"
trigger:
  type: chat
nodes:
  - id: baixar
    key: baixar
    type: http_request
    connection: "{{config.conexao_api}}"
    method: GET
    path: "/arquivos/nota.pdf"
    response_as: binary
    filename: "nota.pdf"
    output: pdf
  - id: meta
    key: meta
    type: tool
    tool_name: document.metadata
    params:
      storage_key: "{{baixar.result.storage_key}}"
  - id: recorte
    key: recorte
    type: tool
    tool_name: document.split
    params:
      storage_key: "{{baixar.result.storage_key}}"
      pages: "1"
      filename: "pagina-1.pdf"
  - id: juntar
    key: juntar
    type: tool
    tool_name: document.merge
    params:
      storage_keys:
        - "{{recorte.data.storage_key}}"
        - "{{baixar.result.storage_key}}"
      filename: "capa-mais-original.pdf"
  - id: ocr
    key: ocr
    type: tool
    tool_name: document.ocr
    on_error: continue              # sem tesseract no worker = ocr_unavailable; não derruba o run
    params:
      storage_key: "{{recorte.data.storage_key}}"
      lang: "por"
```

**Armadilhas.** O validador não confere `tool_name` nem `params`. Os PDFs precisam ser artefatos do run corrente. No run, confira `error_code`: `invalid_params`, `artifact_outside_run`, `artifact_not_found`, `storage_unavailable`, `invalid_pdf`, `encrypted_pdf`, `pages_out_of_range`, `too_many_pages`, `artifact_too_large` ou `ocr_unavailable`. Para PDF criptografado, use `document.unlock` antes.

**Origem.** `packages/tools/src/tools/document.py:95-112, 130-187, 410-803`, `tool_catalog.json:17-41`. PR #915 (`0b09eba3`).

## 5. Filtro e projeção de campos

**O que faz.** `filter_by_field` retém itens por valor ou por chave. `map_fields` monta objetos com os campos escolhidos.

**Onde vai.** No `config` do nó `transform`, defina `strategy` e `source` com o caminho da lista.

- `filter_by_field` usa `field`, `operator` e `value`. Operadores: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `contains`, `not_contains`, `starts_with`, `in`, `not_in`, `is_null`, `not_null`. Use lista em `value` para `in` e `not_in`. Omita `value` para `is_null` e `not_null`. Nos demais casos, ele é obrigatório. As chaves legadas são `equals` e `not_equals`. `keys_from` e `key_field` fazem a interseção por chave, com `key_field: source_id` por padrão.
- `map_fields` usa `fields`, um mapa não vazio de nome novo para caminho de origem. Caminho ausente vira `None`. Itens que não são objetos entram na contagem de `dropped`.

**Exemplo.**

```yaml
id: "agt_exemplo_filter_map_v1"
slug: "exemplo-filter-map"
name: "Exemplo: filter_by_field + map_fields"
version: "0.1.0"
category: "testes"
description: "Filtra os títulos em aberto acima de 100 e projeta só os campos usados."
config_schema:
  type: object
  required: [conexao_api]
  properties:
    conexao_api:
      type: string
      x-ref: connection
      title: "Conexão HTTP"
      description: "Conexão HTTP genérica da API de origem"
trigger:
  type: chat
nodes:
  - id: listar
    key: listar
    type: http_request
    connection: "{{config.conexao_api}}"
    method: GET
    path: "/titulos"
    output: titulos
  - id: abertos
    key: abertos
    type: transform
    config:
      strategy: filter_by_field
      source: "listar.result.body"
      field: "situacao"
      operator: in
      value: ["aberto", "vencido"]
  - id: relevantes
    key: relevantes
    type: transform
    config:
      strategy: filter_by_field
      source: "abertos.result"
      field: "valor"
      operator: gt
      value: 100
  - id: resumo
    key: resumo
    type: transform
    config:
      strategy: map_fields
      source: "relevantes.result"
      fields:
        titulo: numero
        cliente: cliente.nome
        valor: valor
```

**Armadilhas.** Só com `field`, sem operador nem `equals`, o filtro passa na validação e devolve apenas itens sem o campo. Declare o operador também para igualdade. Estratégia desconhecida passa e dá `unknown_strategy` no run. O validador recusa operador inválido, `operator` junto de `equals`, tipo errado de `value` e `fields` vazio. O runtime usa o prefixo `transform_invalid_config:` para configuração inválida.

**Origem.** `agent_spec_v1.json:483-503`, `agent_spec.py:668-800`, `executors.py:5108-5342` (filtro sem operador em `5277-5279`). PR #924 (`98e827e1`) e PR #1226 (`starts_with`).

## 6. Enriquecimento por chave composta

**O que faz.** Copia campos de uma lista de consulta para cada registro da lista principal, casando por uma ou mais chaves. Retorna `status`, `result` com cópias na ordem original, `unresolved` e `ambiguous`.

**Onde vai.** No `config` do nó `transform`, use `strategy: enrich`, `source` e `lookup` com os caminhos das listas, `join_on` com o mapa de caminhos da origem para a consulta, e `set` com o mapa de campo de destino para campo da consulta. Sem par, grava `None` em destino ausente e mantém valor que já existe.

**Exemplo.**

```yaml
id: "agt_exemplo_enrich_v1"
slug: "exemplo-enrich"
name: "Exemplo: transform enrich"
version: "0.1.0"
category: "testes"
description: "Grava o CNPJ do fornecedor em cada movimento, casando por código+loja."
config_schema:
  type: object
  required: [conexao_api]
  properties:
    conexao_api:
      type: string
      x-ref: connection
      title: "Conexão HTTP"
      description: "Conexão HTTP genérica da API de origem"
trigger:
  type: chat
nodes:
  - id: movimentos
    key: movimentos
    type: http_request
    connection: "{{config.conexao_api}}"
    method: GET
    path: "/movimentos"
    output: movimentos
  - id: fornecedores
    key: fornecedores
    type: http_request
    connection: "{{config.conexao_api}}"
    method: GET
    path: "/fornecedores"
    output: fornecedores
  - id: com_cnpj
    key: com_cnpj
    type: transform
    config:
      strategy: enrich
      source: "movimentos.result.body"
      lookup: "fornecedores.result.body"
      join_on:                          # NUNCA `on:` (YAML 1.1 lê como true)
        fornecedor.codigo: codigo
        fornecedor.loja: loja
      set:
        fornecedor.cnpj: cnpj
```

**Armadilhas.** Sem `join_on`, ou com `on:` (que o YAML lê como booleano), passa na validação e falha no run. A comparação usa `str().strip()`. Chave vazia fica sem par. Chave que se repete na consulta é ambígua e fica sem enriquecimento.

**Origem.** `executors.py:5744-5900`. PR #914 (`edcea7e0`) e PRs #1040 e #1246.

## 7. Envio HTTP de artefato

**O que faz.** Envia um arquivo que já é artefato do run, como um download com `response_as: binary`. Aceita multipart ou corpo binário.

**Onde vai.** No topo do nó `http_request`, use `multipart` com `metadata` obrigatório (objeto), exatamente um de `content_base64` e `content_from_artifact`, e `content_type` opcional. Para corpo binário, use `body_from_artifact` com a chave de armazenamento e `body_content_type` (padrão `application/octet-stream`). Só `http_generic` aceita corpo binário.

**Exemplo.**

```yaml
id: "agt_copiar_arquivo_v1"
slug: "copiar-arquivo"
name: "Copiar arquivo entre APIs"
version: "0.1.0"
category: "testes"
description: "Baixa um arquivo como artefato do run e o envia a outra API, em multipart e em corpo cru."
config_schema:
  type: object
  required: [conexao_origem, conexao_drive, conexao_destino]
  properties:
    conexao_origem: {type: string, x-ref: connection, title: "Origem do arquivo"}
    conexao_drive:  {type: string, x-ref: connection, title: "Google Drive"}
    conexao_destino: {type: string, x-ref: connection, title: "API que aceita octet-stream"}
trigger:
  type: chat
nodes:
  - id: baixar
    key: baixar
    type: http_request
    connection: "{{config.conexao_origem}}"
    method: GET
    path: "/arquivos/relatorio.pdf"
    response_as: binary
    max_bytes: 10485760
    filename: "relatorio.pdf"
    output: arquivo
  - id: subir_drive
    key: subir_drive
    type: http_request
    connection: "{{config.conexao_drive}}"
    method: POST
    path: "/upload/drive/v3/files"
    params: {uploadType: multipart}
    multipart:
      metadata: {name: "relatorio.pdf"}
      content_from_artifact: "{{baixar.result.storage_key}}"
      content_type: "application/pdf"
    idempotency_key: "drive-{{run.id}}"
    output: arquivo_drive
  - id: subir_cru
    key: subir_cru
    type: http_request
    connection: "{{config.conexao_destino}}"
    method: POST
    path: "/api/upload"
    body_from_artifact: "{{baixar.result.storage_key}}"
    body_content_type: "application/pdf"
    idempotency_key: "cru-{{run.id}}"
    output: arquivo_cru
```

**Armadilhas.** Escrita HTTP em `spec_test_run` (sandbox ou shadow) é dry-run. O upload só sai em um run que execute a escrita. O validador recusa `body` com `multipart`, `body_from_artifact` com `body` ou `multipart` (mensagem ilegível), corpo de artefato com GET e escrita sem `idempotency_key`. Pode emitir `W-HTTP-WRITE-SEM-APPROVAL`. No run, confira `unresolved_content_from_artifact`, `unresolved_body_from_artifact`, `artifact_outside_tenant` (chave fora de `run-artifacts/{tenant}/{run}/`) e `artifact_download_failed`.

**Origem.** `agent_spec_v1.json:921-935, 1043-1074`, `executors.py:2894-2996` (dry-run em `2962`). PRs #913 e #1112.

## 8. Rótulos e edição no card de aprovação

**O que faz.** Personaliza os rótulos do card e permite aprovar itens com valores editados e observação.

**Onde vai.** No `config` do nó `approval`. Os campos são opcionais. Sem eles, vale o card antigo.

- `item_noun: {one, many}` e `supplier_label` aceitam até 40 caracteres. `headline_template` aceita `{count}`, `{noun}`, `{total}`, `{unit}` e `{total_brl}` (por exemplo, `1.234,56`).
- `decision_set` aceita `aprovar_lote` (padrão) ou `aprovar_itens`. `amount_unit` define a unidade. `editable_amount` e `approve_notes` usam booleanos literais. `on_reject` aceita `continue` ou `halt` (padrão).
- O resultado expõe `{{aprovar.aprovados}}`, `{{aprovar.status}}`, `{{aprovar.decision.justification}}` e `{{aprovar.edited_values.items}}`. Cada item editado traz `titulo`, `valor_original` e `valor`.

**Exemplo.**

```yaml
id: "agt_revisar_horas_v1"
slug: "revisar-horas"
name: "Revisar horas estimadas"
version: "0.1.0"
category: "testes"
description: "Lista estimativas de uma API, pede aprovação com horas editáveis e comenta a decisão."
config_schema:
  type: object
  required: [conexao_api]
  properties:
    conexao_api: {type: string, x-ref: connection, title: "API das estimativas"}
trigger:
  type: chat
nodes:
  - id: listar
    key: listar
    type: http_request
    connection: "{{config.conexao_api}}"
    method: GET
    path: "/estimativas"
    output: estimativas
  - id: itens
    key: itens
    type: transform
    config:
      strategy: map_fields
      source: "listar.result.body"
      fields: {titulo: codigo, horas: horas, cliente: cliente}
  - id: aprovar
    key: aprovar
    type: approval
    config:
      context_from: itens
      title_path: titulo
      amount_path: horas
      supplier_path: cliente
      decision_set: aprovar_itens
      amount_unit: "h"
      item_noun: {one: "estimativa", many: "estimativas"}
      supplier_label: "Cliente"
      headline_template: "{count} {noun} — {total:g} {unit}"
      editable_amount: true
      approve_notes: true
      on_reject: continue
      timeout_hours: 24
  - id: foi_rejeitado
    key: foi_rejeitado
    type: condition
    config:
      expr: "aprovar.status == 'rejected'"
      on_false: foi_aprovado
  - id: comentar_rejeicao
    key: comentar_rejeicao
    type: http_request
    connection: "{{config.conexao_api}}"
    method: POST
    path: "/estimativas/comentarios"
    body:
      motivo: "{{aprovar.decision.justification}}"
    idempotency_key: "rejeicao-{{run.id}}"
    output: comentario
  - id: foi_aprovado
    key: foi_aprovado
    type: condition
    config:
      expr: "aprovar.status == 'approved'"
      on_false: fim
  - id: gravar
    key: gravar
    type: http_request
    connection: "{{config.conexao_api}}"
    method: POST
    path: "/estimativas/aprovadas"
    body:
      aprovados: "{{aprovar.aprovados}}"
      editados: "{{aprovar.edited_values.items}}"
      observacoes: "{{aprovar.decision.justification}}"
    idempotency_key: "aprov-{{run.id}}"
    output: gravacao
  - id: fim
    key: fim
    type: audit_append
    entity_type: revisao_horas
    action: concluida
    details: {status: "{{aprovar.status}}"}
```

**Armadilhas.** Chave inventada em `config` passa sem aviso (`additionalProperties: true`). O card `aprovar_itens` só aparece na web. Sem edição ou observação, as referências correspondentes viram `null`. Com `on_reject: continue`, o validador exige a guarda de escrita `aprovar.status == 'approved'` (`E-APPROVAL-ON-REJECT-CONTINUE-WRITE`). Essa guarda difere de `aprovar.decision.decision`, da §1 do ARMADILHAS. O validador também emite `E-APPROVAL-ROTULOS` e `E-APPROVAL-EDITAVEL` para rótulos e edição inválidos, como booleano em string ou edição fora de `aprovar_itens` ou junto com `batch_cap`. A região rejeitada só permite `audit_append`, `channel_send`, `http_request` e `transform` (`E-APPROVAL-ON-REJECT-REGIAO-REJEITADO` e, no run, `rejected_region_blocked`).

**Origem.** `agent_spec.py:1293-1309, 1462, 1505`, `hatchet_app.py:1328, 2484, 616`, `builder_map:122-133`. PRs #1091, #1073 e #1071.

## 9. Configuração temporária no teste

**O que faz.** Sobrepõe a configuração efetiva de um rascunho em um test run. O gateway valida a sobreposição em dry-run, sem gravar a instância.

**Onde vai.** `config_override` é um objeto opcional nos argumentos de `spec_test_run`. Se presente, `erp_company_id` é obrigatório. Sem override, vale a configuração efetiva. `spec_run_status` devolve `config_override_keys`.

**Exemplo.**

```json
{"slug":"revisar-horas","version":"0.1.0","erp_company_id":"<uuid>","input":{"mensagem":"teste"},"config_override":{"conexao_api":"<uuid-da-conexão>"}}
```

**Armadilhas.** A mescla é rasa. Um objeto aninhado é substituído inteiro. `validation_failed` cobre override que não é objeto, presença de `company_overrides` ou `execution_mode`, falta de `erp_company_id`, violação do `config_schema`, conexão de outra empresa e spec publicada.

**Origem.** `mcp_server tools/spec_test_run.py:47, 89-134`, `agent-runtime routers/runs.py:507-552`. PR #985.

## 10. Arquivamento e restauração de rascunho

**O que faz.** Arquiva ou restaura um rascunho que nunca foi publicado. Runs, aprovações e versões ficam disponíveis.

**Onde vai.** Passe `slug` nos argumentos de `spec_archive_draft` ou `spec_restore_draft`. A chave precisa do escopo `spec.archive`. O painel também tem botão e aba Arquivados.

**Exemplo.**

```json
{"slug": "teste-op1748"}
```

**Armadilhas.** Arquivamento de agente publicado ou com agenda, canal ou caixa de e-mail ligados dá `conflict`. Os vínculos aparecem em `details.blockers`. Slug inexistente dá `not_found`. Um arquivado ainda roda com `spec_test_run` e `spec_source: draft`, com a configuração crua do YAML.

**Origem.** `tools/spec_archive_draft.py:20-67`, `api-gateway services/agent_archive.py:35-104`, `runs.py:671-693`. PR #1077.

## 11. Conectores TOTVS RM e extrato em PDF

**O que faz.** `totvs_rm` consulta títulos, vincula documentos e chama operações da API do RM. `extrato_pdf` lê lançamentos de um extrato Itaú em PDF.

**Onde vai.** Em nó `type: tool`, use `config.primitive: read | write`, `config.connector_id` com referência a campo `x-ref: connection` e `config.entity`. Em `config`, passe `params` para leitura ou `payload` e `idempotency_key` para escrita.

- `Payable` lê por consulta SQL cadastrada, com igualdade e parâmetros na ordem do mapa. `DocumentLink` escreve com `payload.id` obrigatório e `codcoligada` opcional.
- `ApiOperation` lê com `params: {path, path_params?, query?}`, com caminho relativo ao `basePath` do Swagger. Na escrita, use `payload: {method, path, path_params?, query?, body?}` e declare `config.money_write`. Se for `true`, precisa de aprovação prévia.
- `extrato_pdf` aceita só `BankStatementEntry`, com o filtro `params.anexos: '{{run.input.attachments}}'`. O limite é de 50 páginas.
- Crie a conexão com `spec.connection_create` (escopo `connection.write`). Use `connector_type: totvs_rm` com `base_url`, `username`, `password` e `default_coligada`. `connector_type: extrato_pdf` dispensa campos de configuração.

**Exemplo.**

```yaml
id: "agt_rm_e_extrato_v1"
slug: "rm-e-extrato"
name: "Títulos do RM e extrato em PDF"
version: "0.1.0"
category: "testes"
description: "Lê títulos a pagar do TOTVS RM, consulta um endpoint do Swagger do RM e lê o extrato em PDF anexado ao run."
requires_erp: true
config_schema:
  type: object
  required: [conexao_rm, conexao_extrato]
  properties:
    conexao_rm:      {type: string, x-ref: connection, title: "TOTVS RM"}
    conexao_extrato: {type: string, x-ref: connection, title: "Extrato em PDF"}
trigger:
  type: chat
nodes:
  - id: titulos
    key: titulos
    type: tool
    config:
      primitive: read
      connector_id: "{{config.conexao_rm}}"
      entity: Payable
      params: {}
  - id: coligadas
    key: coligadas
    type: tool
    config:
      primitive: read
      connector_id: "{{config.conexao_rm}}"
      entity: ApiOperation
      params:
        path: "/framework/v1/Branches"
        query: {"query.pageSize": 1}
  - id: aprovar
    key: aprovar
    type: approval
    config:
      context_from: titulos
      title_path: source_id
      amount_path: fields.valor
      timeout_hours: 24
  - id: vincular_doc
    key: vincular_doc
    type: tool
    config:
      primitive: write
      connector_id: "{{config.conexao_rm}}"
      entity: DocumentLink
      payload:
        id: "{{titulos.result.0.fields.proximo_id}}"
        codcoligada: "1"
      idempotency_key: "doclink-{{run.id}}"
  - id: criar_conta
    key: criar_conta
    type: tool
    config:
      primitive: write
      connector_id: "{{config.conexao_rm}}"
      entity: ApiOperation
      money_write: false
      payload:
        method: POST
        path: "/financial/v1/cashaccounts"
        body: {descricao: "Caixa teste"}
      idempotency_key: "conta-{{run.id}}"
  - id: tem_anexo
    key: tem_anexo
    type: condition
    config:
      expr: "len(run.input.attachments) > 0"
      on_false: fim
  - id: extrato
    key: extrato
    type: tool
    config:
      primitive: read
      connector_id: "{{config.conexao_extrato}}"
      entity: BankStatementEntry
      params:
        anexos: "{{run.input.attachments}}"
  - id: fim
    key: fim
    type: audit_append
    entity_type: leitura_rm
    action: concluida
    details: {titulos: "{{titulos.result}}"}
```

**Armadilhas.** `extrato_pdf` lê todos os PDFs da conversa. Um comprovante junto do extrato derruba a leitura com erro. `DocumentLink` sem aprovação passa sem aviso. Escrita fora de `allowed_write_paths` dá `CAPABILITY_DENIED`. Lista vazia bloqueia toda escrita. Na validação de `ApiOperation`, confira `E-APIOP-MONEY-WRITE-NAO-DECLARADA`, `E-APIOP-MONEY-WRITE-SEM-APPROVAL` e `W-APIOP-WRITE-SEM-APPROVAL`.

**Origem.** `connectors/totvs_rm/connector.py:284-366, 490-660`, `connectors/extrato_pdf/connector.py:118-230`, `agent_spec_v1.json:737-790`. PRs #951 e #889.

## 12. Anexos do run

**O que faz.** Expõe os metadados dos anexos recebidos no run. Chat, painel e `agent.run` fornecem `id`, `filename`, `mime` e `url_interna`. Canal fornece `filename`, `content_type`, `storage_key` e `size_bytes`.

**Onde vai.** O servidor injeta `run.input.attachments`. Use `len(run.input.attachments) > 0` em `condition.config.expr` ou `'{{run.input.attachments}}'` para preservar a lista inteira. Pelo MCP, passe `files: [{filename, mime, data_b64}]` nos argumentos de `agent_run` (escopo `agent.converse`). Limites de 5 arquivos, 10 MB por arquivo e 25 MB no total.

**Exemplo.**

```yaml
id: "agt_ler_anexos_v1"
slug: "ler-anexos"
name: "Ler anexos do run"
version: "0.1.0"
category: "testes"
description: "Mostra os anexos recebidos pelo run e resume a lista com um LLM."
trigger:
  type: chat
nodes:
  - id: tem_anexo
    key: tem_anexo
    type: condition
    config:
      expr: "len(run.input.attachments) > 0"
      on_false: sem_anexo
  - id: resumir
    key: resumir
    type: llm_step
    prompt: "Liste nome e tipo de cada anexo recebido: {{run.input.attachments}}"
    model_ref: Anthropic-claude-haiku-4-5-20251001  # model_ref é alias do tenant: consulte spec_models e escolha um ativo
  - id: pular_aviso
    key: pular_aviso
    type: condition
    config:
      expr: "len(run.input.attachments) > 0"
      on_true: fim
  - id: sem_anexo
    key: sem_anexo
    type: llm_step
    prompt: "Diga ao usuário que nenhum arquivo foi anexado."
    model_ref: Anthropic-claude-haiku-4-5-20251001  # model_ref é alias do tenant: consulte spec_models e escolha um ativo
  - id: fim
    key: fim
    type: audit_append
    entity_type: leitura_anexos
    action: concluida
    details: {qtd: "{{run.input.attachments}}"}
```

**Armadilhas.** `{{input.attachments}}` não resolve. Run por agenda não tem anexo. `spec_test_run` recusa anexos em `input` com “input não pode conter: attachments”. Anexo de chat ou canal não vira artefato do run. Só `extrato_pdf` consome anexo. `document.*`, `content_from_artifact` e `body_from_artifact` exigem artefatos do run.

**Origem.** `api-gateway routers/agents.py:1997-2004`, `channels/routers/webhooks.py:300-307`, `routers/internal_mcp_run.py:92-190`, `mcp_server tools/spec_test_run.py:48, 63-67`. A pesquisa não identifica um PR para este recurso.

## Pontos em aberto no core

**Decisões de produto**

- O `config` do approval aceita chaves inventadas sem aviso (`additionalProperties: true`).
- Rascunho arquivado ainda roda com `spec_test_run` e `spec_source: draft` (`runs.py:671-693`).
- Anexo de chat ou canal não vira artefato do run e só `extrato_pdf` o consome. `document.*`, `content_from_artifact` e `body_from_artifact` ficam sem acesso ao anexo.
- Loop com falha parcial segue por padrão e o run fica `completed` (PR #130).

**Incoerências**

- `filter_by_field` sem `operator` passa no validador e devolve só itens sem o campo. O builder map diz “default eq”.
- O builder map diz que `enrich` sem par deixa o campo sem gravação. Desde o PR #1246, o código grava `None` se o campo ainda não existe.
- O builder map ainda descreve a forma legada de `loop` e omite `as`.
- O validador não confere `tool_name` nem `params` de `document.*`, nem a `strategy` do transform.
- O `protocol.py` marca `erp_company_id` como opcional. Com `config_override`, ele é obrigatório.
