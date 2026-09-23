# Conexões de ponta a ponta

O que foi levantado construindo o Arquiteto TOTVS (11 a 15/09/2026) e que nenhuma
tela avisa. Tudo 📏 medido, salvo onde marcado 🔍.

Depois de criar a conexão, confira com `spec_connectors` que ela aparece e leia
o `config` público (`ARMADILHAS.md` §6). O `connection_id` da spec vem de lá.
Consultas de leitura mínimas que devolvem 200 estão em
[`examples/http-leitura/v1.yaml`](../examples/http-leitura/v1.yaml).

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
