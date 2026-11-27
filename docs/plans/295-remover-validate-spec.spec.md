# 295 — Remover o validate_spec.py e apontar o guia para o spec_validate do MCP

## Intenção

GLPI #295 / OP 2404 (filha da 1161). O `validate_spec.py` do dev-kit recusa toda spec: o tripwire DAI-526 dispara porque o core já tem `NodeSpec.key`. A validação oficial já é a do MCP (`mcp_client.validate` → `spec.validate`), e nenhuma operação da skill usa o script desde a feature 024. **Corrige:** remove o script quebrado e o teste dele, e aponta os dois trechos do guia que ainda o citam para o `mcp_client.validate`. **Inclui (gestor, 27/11):** remover também o `dogfood_check.py` do dev-kit e a cópia do script no Agente_OS (PR próprio). A documentação dos ~12 recursos do core vai em spec à parte (item 8). **Não muda:** o `mcp_client.py`, os outros scripts e testes, o MCP e o código do core.

## Causa (com prova)

- O script aborta em `_check_node_key_tripwire()` se `"key" in NodeSpec.model_fields` (`.claude/skills/agentos-builder/scripts/validate_spec.py:136-153`, chamado em `:658`).
- O core tem `key: str | None = None` dentro de `class NodeSpec`, em `packages/agent-specs/src/agent_specs/schema.py:39`, na `main` (adfc88d6) e na imagem de produção TBC (`cc0fa538`, release 26/11). O campo entrou pelo DAI-626 (Agente_OS #302, commit 9001550a).
- Reprodução, em 27/11, com `examples/sbx-hello/v1.yaml`:
  - com o core no `PYTHONPATH`: `{"ok": false, "errors": [{"layer": 0, ..., "message": "schema.py now defines node 'key' — DAI-526 likely landed; ..."}]}`, exit 2;
  - só com o dev-kit (o caso do dev): `Failed to import 'agent_specs'. Run 'uv sync' at the repo root ...`, exit 2. O script presume o layout do monorepo (`_REPO_ROOT/packages/...`), que este repositório não tem.
- O script não muda desde o commit inicial (509d6e9). O `lifecycle.md:57-59` já registra que a validação passou ao MCP (024/T017) e que o script "is no longer part of any documented skill operation".

## Solução mínima (Ponytail ultra)

Apagar é menor que consertar e acaba com a duplicidade. Consertar exigiria o core instalado no dev-kit, e o `CLAUDE.md` deste repositório proíbe isso ("Zero import/código do core da plataforma"; "Toda operação de spec passa pelo MCP"). O script importa `agent_specs` e `cdm`.

1. Apagar `.claude/skills/agentos-builder/scripts/validate_spec.py`.
2. Apagar `.claude/skills/agentos-builder/tests/test_validate_spec.py`.
3. `references/backup.md:74`: trocar o comando `.venv/bin/python …/validate_spec.py <path>` por `mcp_client.validate(content)` sobre o conteúdo restaurado, mantendo o resto da frase.
4. `references/lifecycle.md:59`: trocar a frase "`scripts/validate_spec.py --list-node-types` still exists (own test suite, …, kept green) but is no longer part of any documented skill operation" por uma frase dizendo que o script local foi removido (GLPI #295) por ter quebrado contra o core (tripwire DAI-526, `NodeSpec.key` do DAI-626). As linhas 55 e 57 contam a história no passado e ficam como estão.
5. `scripts/mcp_client.py:154` (docstring histórica, "replaces … running `validate_spec.py --list-node-types`"): não tocar.
6. Apagar `.claude/skills/agentos-builder/scripts/dogfood_check.py` (decisão do gestor, 27/11). Ele também importa o core (alembic, testcontainers, `packages/`), proibido neste repositório, e nada o cita fora do próprio docstring. A cópia do Agente_OS, onde ele roda no monorepo, fica.
7. Agente_OS (PR próprio, decisão do gestor, 27/11): a cópia da skill no monorepo tem o mesmo script e o mesmo tripwire. Nela, os itens 1 a 4 se repetem; `.claude/context/zero-hardcode.md:30` e `_reversa_forward/` são histórico e ficam.
8. A outra metade do #295, documentar os ~12 recursos do core, sai em spec própria: `docs/plans/295-documentar-recursos-core.spec.md`.

## Critério de aceite

- CA-1: os dois arquivos somem, e `git grep -nE 'validate_spec|list-node-types' -- . ':!docs/'` no branch acha só menções históricas: `lifecycle.md:55`, `:57`, `:59` (a nota de remoção) e `mcp_client.py:154`. Nenhuma delas é instrução de rodar o script: `git grep -nE 'bin/python[^`]*validate_spec|still exists' -- .claude` dá zero. Controle positivo: o mesmo par de greps em `origin/main` acha `backup.md:74` e `lifecycle.md:59`.
- CA-2: os testes que sobram passam (stdlib, sem CI no repositório): `test_gap_redact.py`, `test_mcp_client_error_parse.py`, `test_mcp_client_feedback.py`, `test_publish_guard.py`.
- CA-3 (spec válida conhecida, pedida no chamado): **uma** chamada `mcp_client.validate` sobre `examples/sbx-hello/v1.yaml` no sandbox-os devolve `ok: true`. Sem laço: o gestor avisou do 429 do Cloudflare.

## Teste

Sem lógica nova, então nada de teste novo. Valem o grep do CA-1 (com o controle positivo), os 4 testes do CA-2 e a chamada do CA-3.

## Entrega (27/11)

- dev-kit: commit 4a41134 (script, teste e `dogfood_check.py` removidos; `backup.md:74` e `lifecycle.md:59` atualizados).
- Agente_OS: commit ba403833 na branch `fix/295-remover-validate-spec` (os mesmos itens, menos o `dogfood_check.py`).
- Documentação dos ~12 recursos: `docs/plans/295-documentar-recursos-core.spec.md`.
