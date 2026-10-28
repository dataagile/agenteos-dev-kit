# Conexões de ponta a ponta

O que foi levantado construindo o Arquiteto TOTVS (11 a 15/09/2026) e que nenhuma
tela avisa. Tudo 📏 medido, salvo onde marcado 🔍.

Depois de criar a conexão, confira com `spec_connectors` que ela aparece e leia
o `config` público (`ARMADILHAS.md` §6). O `connection_id` da spec vem de lá.
Consultas de leitura mínimas que devolvem 200 estão em
[`examples/http-leitura/v1.yaml`](../examples/http-leitura/v1.yaml).

## Conexão que não está em `connectors()` — criar pelo MCP (🔍 GLPI #245)

🔍 Lido no código da plataforma (Agente_OS#900, `spec_connections.py`), não
medido por run daqui. A plataforma tem `spec.connection_create`,
`spec.connection_update` e `spec.connection_test`. Elas só aparecem para a chave
MCP com o escopo **`connection.write`**, que é dado de propósito (age como
admin do tenant). Sem esse escopo, `connectors()` mostra só o que já existe.
Daí o falso "não há como cadastrar".

Antes de classificar como gap `[ambiente]`:

1. **Ambiente de teste.** Conexão nova para teste aponta para o **laboratório**,
   nunca para a produção do cliente. Usar a conexão de produção "porque é a
   única que existe" grava dados reais (o GED do caso #245).
2. **Quem digita o segredo.** `connection_create` recebe as credenciais no
   `config`, e o que passa pela sessão do Claude passa pelo modelo. Com a chave
   em mãos e o escopo, o autor cria:
   `mcp_client._call("spec.connection_create", {"name": ..., "connector_type":
   "http_generic", "erp_company_id": <UUID>, "config": {...}})`, e depois
   `mcp_client._call("spec.connection_test", {"connection_id": <UUID>})`.
   O teste pode levar até 90 s no gateway, e o `_call` desiste em 30 s. Se der
   timeout, confira o resultado em `connectors()` antes de repetir.
   Se as chaves foram entregues ao admin por canal privado, o caminho é o admin
   cadastrar na tela. O pedido leva só os campos públicos abaixo, nunca o segredo.
3. Criada a conexão, confira com `connectors()` e siga a derivação.

Campos públicos do pedido (Fluig de lab, `http_generic` + `oauth1a`):

| campo | valor |
|---|---|
| nome | ex.: `Fluig Lab <servidor> — GED` |
| `base_url` | URL do Fluig do laboratório |
| `auth_mode` | `oauth1a` |
| `test_method` / `test_path` | `GET` `/api/public/2.0/users/getCurrent` (responde o login do usuário de integração) |
| credenciais | `consumer_key`, `consumer_secret`, `token`, `token_secret`: pelo canal privado, nunca no chamado |

## Google (Drive / Agenda / Gmail) — `http_generic` com `oauth2`

O caminho oficial é o **app OAuth da plataforma** (interno na organização, sem
verificação do Google, refresh token sem expiração) + botão **"Autorizar com
Google"** na conexão, no sandbox-os (Agente_OS#793, #865, #868).

Pré-requisitos, na ordem em que faltam:

1. **Conta Google Workspace da organização.** Conta `@gmail.com` pessoal NÃO
   consegue autorizar um app interno.
2. No projeto Google Cloud do app: a **API do Drive (ou Calendar/Gmail)
   habilitada** E os escopos em "Acesso a dados". Sem a API habilitada o
   consentimento passa e a chamada real dá **403**.
3. `OAUTH_APP_GOOGLE_CLIENT_ID` / `OAUTH_APP_GOOGLE_CLIENT_SECRET` no ambiente
   do spoke (o compose enumera as vars; Agente_OS#865). Isso é do admin.

Fluxo:

1. Conexões → nova → tipo `http_generic`, auth `oauth2`, `base_url`
   `https://www.googleapis.com`.
2. "Autorizar com Google" → consentimento → volta para a conexão.
3. **Tudo no mesmo navegador, logado no sandbox-os.** O `state` do OAuth vive
   num cookie `__Host-`; iniciar por `curl` e consentir no navegador (ou
   vice-versa) dá `state_invalid`.

📏 27/10/2026 (sandbox-tbc, GLPI #284): cada clique em "Autorizar com Google"
no card Google de Configurações → Conexões cria **duas** conexões (Gmail;
Drive + Agenda). Dá para ligar várias contas; os nomes ainda não trazem o
e-mail da conta.

### Anexo do Gmail como arquivo do run (Agente_OS #1119)

📏 28/10/2026 (instância local, Gmail real, runs `ada28a98` e `18a25ed9`).
A API do Gmail devolve o anexo **dentro do JSON** (`{size, data: <base64url>}`),
não como bytes. `response_as: binary` sozinho guardaria o JSON; com
`binary_from_json` o campo é decodificado e vira artefato do run, legível
pelas tools `document.*`:

```yaml
- id: baixar
  key: baixar
  type: http_request
  connection: "{{config.conexao_gmail}}"
  method: GET
  path: "/gmail/v1/users/me/messages/{{listar.result.body.messages.0.id}}/attachments/{{item.body.attachmentId}}"
  response_as: binary
  binary_from_json:
    field: data            # caminho do campo no JSON
    encoding: base64url    # o Gmail usa base64url; base64 comum também é aceito
    content_type: "{{item.mimeType}}"
  filename: "{{item.filename}}"
  config:
    when: "item.body.attachmentId != null"   # partes de texto/HTML não têm anexo
```

Saída: `{{baixar.result.storage_key}}`. As partes do e-mail ficam em
`ler.result.body.payload.parts` (`GET /gmail/v1/users/me/messages/{id}`) — é
sobre elas que o `loop` itera. Spec completa:
[`examples/gmail-pdf-senha/v1.yaml`](../examples/gmail-pdf-senha/v1.yaml).

## PDF com senha — conexão `file_password` + `document.unlock` (Agente_OS #1120)

📏 28/10/2026 (instância local; runs `7ce1f452`, `de633b23`, `6ce5f9cc`).
A senha do arquivo é uma **conexão** do tipo "Senha de arquivo"
(`file_password`, um único campo `password`, guardado no cofre). A tool
`document.unlock` manda o PDF ao data-plane, que abre com a senha e devolve
uma cópia sem proteção; a senha nunca chega à spec, ao run nem aos logs.

```yaml
- id: abrir
  key: abrir
  type: tool
  tool_name: document.unlock
  params:
    storage_key: "{{baixar.result.storage_key}}"
    connection: "{{config.conexao_senha}}"   # x-ref: connection no config_schema
    filename: "{{item.filename}}"
```

| Caso | Resultado medido |
|---|---|
| PDF protegido, senha certa | `unlocked: true`; `{{abrir.data.storage_key}}` é o PDF novo, sem senha |
| PDF sem senha | `unlocked: false`, devolve o mesmo `storage_key` (não usa a conexão) |
| Senha errada | falha com `wrong_password`; conta 1 tentativa |

🔍 Limite de **10 senhas erradas por hora por conexão**: na 11ª a tool responde
`too_many_attempts` por até 1 h — **inclusive para a senha certa**. Não teste
senha por tentativa e erro numa conexão que o agente de produção usa.

A saída do nó `tool` é `{{abrir.data.*}}`, não `.result` (`ARMADILHAS.md` §22),
e o passo seguinte precisa da guarda `when: "abrir.success == true"`
(`ARMADILHAS.md` §23).

## Fluig — `http_generic` com `oauth1a`

Fluig só fala **OAuth 1.0a (HMAC-SHA1)**: modo `oauth1a` do `http_generic`
(Agente_OS#774). Quatro campos:

| campo | onde pegar no Fluig |
|---|---|
| `consumer_key` | Painel de Controle → OAuth application |
| `consumer_secret` | OAuth application → **Editar** (não aparece na tela "Usuário Aplicativo") |
| `token` | Usuário Aplicativo |
| `token_secret` | Usuário Aplicativo |

## GitHub — `http_generic` com Bearer PAT (📏 arquiteto-totvs 0.9, 22/09/2026)

Enquanto não existe preset `github` na plataforma (issue #29), preencha à mão:

| campo | valor |
|---|---|
| `base_url` | `https://api.github.com` |
| auth | Bearer, com um **PAT fine-grained só-leitura** (Contents: read; Metadata: read) restrito aos repositórios necessários |
| headers | `Accept: application/vnd.github+json` e `X-GitHub-Api-Version: 2022-11-28` |
| `test_path` | `/user` (`GET`, 200 com o login do dono do token) |

Leitura que funciona: `GET /search/code?q=<termo>+org:<org>` (§18 do ARMADILHAS
vale aqui também: falha do `http_request` não aborta o run).

**Segurança, antes de sair do sandbox:** PAT fine-grained é de **uma pessoa** —
expira, some quando ela sai da org, e aparece no audit como ela. Para produção
use um **machine user** da org do cliente com o PAT, ou uma **GitHub App**
instalada na org; nunca o PAT de um dev. Não cole o PAT em spec, `default:` ou
chamado (o `gap_redact` remove `token=` mas não um PAT solto).

## Cadastro via API (sem a tela)

Funciona, com três detalhes que custam tempo:

```
POST /api/v1/auth/login            → devolve access_token (Bearer), NÃO cookie
GET  /api/v1/companies             → pegue o erp_company_id (obrigatório abaixo)
POST /api/v1/connections           → body com type, auth_mode, base_url, credenciais, erp_company_id
POST /api/v1/connections/{id}/test → resposta é SSE (text/event-stream), NÃO JSON
```

O `test` por API tem a mesma limitação do botão "Testar" abaixo.

## Erros que parecem outra coisa

| Sintoma | O que é de verdade |
|---|---|
| Botão "Testar" da conexão `oauth2` devolve **401** | Funciona mesmo assim. O gateway do Testar **não faz refresh** do token; a chamada real roda no data-plane, que faz. Prove com um `spec_test_run` de leitura. |
| `403` numa chamada Google depois de consentir | API não habilitada no projeto Google Cloud (item 2 acima). |
| `state_invalid` ao voltar do consentimento | Início e consentimento em contextos diferentes (curl + navegador, ou navegador deslogado). Refaça tudo no navegador logado. |
| `502 CONNECTOR_ERROR` com corpo do destino dentro | Autenticou; a **consulta** está errada (`ARMADILHAS.md` §18). |
| Conta pessoal não consegue autorizar | App interno exige conta da organização (item 1). |
| "Autorizar com Google" não faz nada (no celular) | O botão fica **desabilitado** quando o ambiente não tem o app OAuth (item 3) ou a `OAUTH_CALLBACK_BASE_URL`; o motivo só aparece como dica ao passar o mouse. É do admin (GLPI #284). |
| Tool `document.*` falha com `storage_key fora do run corrente` e o valor é `'{{...}}'` | Referência sem resolver — saída de nó `tool` é `.data`, não `.result` (`ARMADILHAS.md` §22). |
