# 295 (2ª metade): documentar no kit os 12 recursos do core que o PR #53 listou

## Intenção

GLPI #295 / OP 2404, a pedido do gestor (27/11). O PR #53 listou 12 recursos do core sem menção no kit. Sem doc, o autor de agente não os descobre, ou cai nas armadilhas deles. Este PR **inclui** `docs/recursos-do-core.md`: uma seção por recurso, com o formato, um exemplo que passou no `spec.validate` do sandbox-os, as armadilhas e a origem no código. Ele também **corrige** dois exemplos do kit: o `sbx-hello` usava `model_ref: default`, que não é alias do tenant, e o `gmail-pdf-senha` usava `config.max_iterations`, que o runtime ignora. **Exclui** qualquer mudança no core e as decisões de produto listadas no fim. **Inclui também** a §24 do `ARMADILHAS.md`, com as armadilhas novas que o validador não pega (regra do `CLAUDE.md` do repositório). **Não muda** scripts nem testes.

## Fonte e marcação

- Cada afirmação é 🔍: lida no código do Agente_OS, em `origin/main` 2e3a045b. Os 12 recursos são iguais na produção TBC (cc0fa538), conferido por `git diff cc0fa538 origin/main` nos caminhos envolvidos.
- Nenhum recurso foi executado (📏): isso exigiria subir a daos-local.
- Cada exemplo de YAML passa no `spec.validate` do MCP do sandbox-os, uma chamada por exemplo, em 27/11.
- Os dois recursos que são tools MCP (9 `config_override` e 10 arquivar/restaurar) têm exemplo de chamada, não de YAML.

## Solução mínima

1. `docs/recursos-do-core.md`:
   - um índice;
   - 12 seções, cada uma com: o que faz, onde vai, o exemplo, as armadilhas e a origem (arquivo:linha do Agente_OS e o PR).
2. `README.md`: uma linha ao lado do link de `docs/conexoes.md` apontando para `docs/recursos-do-core.md`.
3. `examples/sbx-hello/v1.yaml`: `model_ref: Anthropic-claude-haiku-4-5-20251001`, com o comentário "model_ref é alias do tenant: consulte spec_models e escolha um ativo". A mesma regra vale nos exemplos da doc.
4. `ARMADILHAS.md` §24, "Recursos do core: o que o validador NÃO pega". Uma linha por armadilha, cada uma com link para a seção da doc:
   - `filter_by_field` sem `operator`;
   - `enrich` sem `join_on` ou com `on:`;
   - o loop com falha parcial segue;
   - `tool_name`/`params` de `document.*` e a `strategy` não conferidos;
   - escrita HTTP em dry-run no `spec_test_run`;
   - o `extrato_pdf` lê todos os PDFs da conversa;
   - chave inventada no `config` do approval;
   - com `on_reject: continue`, a guarda da escrita tem que ser exatamente `aprovar.status == 'approved'` (E-APPROVAL-ON-REJECT-CONTINUE-WRITE), diferente da regra geral da §1 (`decision.decision`).
5. `examples/gmail-pdf-senha/v1.yaml:56`: `max_iterations: 20` passa a `limit: 20`. Prova: o `_execute_loop` lê `config.limit` (executors.py:3703-3900), e `max_iterations` não aparece no agent-runtime.

## Critério de aceite

- CA-1: as 12 seções existem, e cada uma tem origem com arquivo:linha.
- CA-2: cada um dos 10 exemplos de YAML (os da doc e o `sbx-hello`) devolve `{"ok":true}` no `spec.validate` do sandbox-os, uma chamada cada.
- CA-3: o link no README abre o arquivo.

## Decisões de produto (só listadas, para o gestor e o Gianluka)

1. O `config` do approval aceita chave inventada sem aviso (`additionalProperties: true`).
2. Um rascunho arquivado ainda roda pelo `spec_test_run` com `spec_source: draft` (runs.py:671-693).
3. O anexo do chat ou do canal não vira artefato do run, então `document.*`, `content_from_artifact` e `body_from_artifact` não o leem. Só o `extrato_pdf` consome anexo.
4. O loop com falha parcial segue por padrão (o run fica `completed`), decisão do PR #130. Fica documentado; só vira pergunta se o Gianluka quiser mudar.

## Incoerências do core (para OP à parte, se o gestor quiser)

- `filter_by_field` sem `operator` passa no validador e no run devolve só os itens sem o campo. O builder map diz "default eq".
- O builder map diz que, no `enrich` sem par, o campo "NÃO é gravado". Desde o #1246, o código grava `None`.
- A entrada `loop` do builder map ainda descreve a forma legada e não tem `as`.
- O validador não confere `tool_name` e `params` das tools `document.*`, nem a `strategy` do transform.
- O `protocol.py` diz que `erp_company_id` é "opcional", mas ele é obrigatório com `config_override`.
