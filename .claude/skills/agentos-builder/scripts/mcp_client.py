#!/usr/bin/env python3
"""Thin MCP client for agentos-builder (T017/T018, feature 024).

Wraps as 11 tools do servidor — `spec.list/read/write/validate/publish/
node_types/context/models/connectors/tools/revise` — over the AgenteOS MCP
server's JSON-RPC endpoint (protocolo MCP nativo, servido em `{MCP_URL}/mcp`
pelo nginx do ambiente): `POST {MCP_URL}/mcp {"jsonrpc": "2.0", "method":
"tools/call", "params": {"name": ..., "arguments": ...}}` + `Authorization:
Bearer <key>`. O servidor é stateless (cada POST é autônomo — validado ao vivo
no sandbox-tbc, 13/08/2026); nomes de tool usam underscore (`spec_write`),
o "." é mapeado aqui.

Auth: reads `MCP_URL` + `MCP_KEY` from env, validated on every call (the
server re-validates too — this client does not cache a verdict). Missing or
rejected either -> raise `McpClientError` and ABORT. This skill has **no
fallback** to direct filesystem access on a raiz deste repositório for spec
content — that would mask MCP gaps and defeat the point of the 024
core/sandbox split (see SKILL.md's Auth section).

Zero hardcode: no agent/slug/ERP name here — pure protocol wrapper, stdlib
only (no new dependency for thin HTTP calls).
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any


class McpClientError(Exception):
    """MCP call failed. `.code` is one of the mcp-tools.md catalog
    (unauthorized/not_found/immutable_published/validation_failed/parse_error)
    when the server rejected the call, or None for a config/transport error
    (missing MCP_URL/MCP_KEY, server unreachable)."""

    def __init__(self, message: str, *, code: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


# Códigos do catálogo (`interfaces/mcp-tools.md`) — o parse de erro-texto só promove
# prefixos DESTA lista a `.code`; qualquer outro prefixo minúsculo (ex.: "yaml: ...")
# fica intacto na mensagem, como a docstring de McpClientError promete.
_KNOWN_CODES = ("unauthorized", "not_found", "immutable_published", "validation_failed", "parse_error")
_CODE_RE = re.compile(rf"^({'|'.join(_KNOWN_CODES)}):\s*(.*)$", re.S)


def _parse_tool_error(text: str) -> McpClientError:
    """Erro de tool vindo como TEXTO pelo /mcp ("codigo: mensagem" — visto ao vivo:
    "not_found: Nenhuma versão publicada..."); sem este parse o `.code` prometido
    nas docstrings vinha sempre None."""
    m = _CODE_RE.match(text)
    if m:
        return McpClientError(m.group(2), code=m.group(1))
    return McpClientError(text)


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise McpClientError(
            f"{name} não configurado. agentos-builder não lê/escreve "
            "a raiz deste repositório diretamente — configure MCP_URL (endpoint do MCP) "
            "e MCP_KEY (chave emitida via mcp_server.auth.issue_key para o seu tenant) "
            "antes de usar este skill. Sem fallback ao filesystem local."
        )
    return value


def _call(tool: str, params: dict[str, Any]) -> dict[str, Any]:
    url = _env("MCP_URL").rstrip("/") + "/mcp"
    key = _env("MCP_KEY")

    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool.replace(".", "_"), "arguments": params},
        }
    ).encode("utf-8")
    req = urllib.request.Request(  # noqa: S310 — MCP_URL is operator config, not user input
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 — MCP_URL is operator config, not user input
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise McpClientError(f"MCP em {url} respondeu HTTP {exc.code}: {exc.read()[:300]!r}", code="unauthorized" if exc.code == 401 else None) from exc
    except urllib.error.URLError as exc:
        raise McpClientError(f"MCP em {url} inacessível: {exc}") from exc

    if "error" in payload:  # erro de protocolo JSON-RPC (tool desconhecida, args inválidos)
        err = payload["error"]
        raise McpClientError(err.get("message", "erro JSON-RPC"), code=err.get("code") and str(err["code"]), details=err.get("data") or {})
    result = payload.get("result") or {}
    if result.get("isError"):
        text = (result.get("content") or [{}])[0].get("text", "tool retornou erro")
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            raise _parse_tool_error(text)
        raise McpClientError(parsed.get("message", text), code=parsed.get("code"), details=parsed.get("details") or {})
    if result.get("structuredContent") is not None:
        return result["structuredContent"]  # type: ignore[no-any-return]
    text = (result.get("content") or [{}])[0].get("text", "{}")
    return json.loads(text)  # type: ignore[no-any-return]


def list_specs(state: str | None = None) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"state": state} if state else {}
    return _call("spec.list", params)["specs"]  # type: ignore[no-any-return]


def read_spec(slug: str, version: str) -> dict[str, Any]:
    """Returns `{"slug", "version", "content"}` — `content` is the raw YAML text."""
    return _call("spec.read", {"slug": slug, "version": version})


def write_draft(slug: str, version: str, content: str, templates: dict[str, str] | None = None) -> dict[str, Any]:
    """Cria/edita um draft. Levanta `McpClientError(code="immutable_published")`
    se a versão já está publicada, ou `code="parse_error"` se o YAML é inválido.

    `templates` (DAI-595): os `.j2` do agente viajam JUNTO da spec, como
    `{nome_do_arquivo: conteúdo em texto}` — ex.: `{"entrega.md.j2": "..."}`.
    Sem isso, agente cuja entrega sai por template não tem como ser autorado."""
    params: dict[str, Any] = {"slug": slug, "version": version, "content": content}
    if templates is not None:
        params["templates"] = templates
    return _call("spec.write", params)


def validate(content: str) -> dict[str, Any]:
    """Returns `{"ok": True}` or `{"ok": False, "errors": [{"field_path", "message"}]}`."""
    return _call("spec.validate", {"content": content})


def node_types() -> dict[str, Any]:
    """Node-type catalog (+ `runtime_ready`) and the `trigger`/`spec_level` shape —
    replaces reading `agent_spec_v1_builder_map.json` and running
    `validate_spec.py --list-node-types` directly (T027, closes gap #3).

    Read `variants` (063/#484), not `required`/`optional`: those two describe only
    the builder-map form and omit `config`, the block that carries the behaviour of
    every deterministic node. `variants` is derived from the schema the validator
    actually enforces, so it cannot drift from it."""
    return _call("spec.node_types", {})


def context() -> dict[str, Any]:
    """What resolves inside `{{ ... }}`, per scope — `node`, `template`, `loop_item`
    (063/#484 G-03). Read this BEFORE writing any `.j2`: the `result` level is
    mandatory in step refs, and the run id is `run.id` in a node but `run.run_id`
    in a template."""
    return _call("spec.context", {})


def models() -> dict[str, Any]:
    """Model aliases of the authenticated tenant, for `model_ref` / `intent_model_ref`
    (063/#484 G-04). `available` says which are usable now."""
    return _call("spec.models", {})


def connectors() -> list[dict[str, Any]]:
    """Connectors (conexões a ERP) do tenant — a fonte para `connector_id` num nó.
    Discovery, não memória: nunca preencha connector_id de cabeça. Escopo: spec.read."""
    return _call("spec.connectors", {})["connectors"]  # type: ignore[no-any-return]


def tools() -> list[dict[str, Any]]:
    """Tools de MCP-servers do tenant — a fonte para `tool_name` num nó `tool`.
    Escopo: spec.read."""
    return _call("spec.tools", {})["tools"]  # type: ignore[no-any-return]


def revise(slug: str) -> dict[str, str]:
    """Abre a PRÓXIMA versão em draft a partir da última published (DAI-591).
    Published é imutável — revisar = novo draft semeado dela, depois o ciclo
    normal write→validate→publish.

    Retorna `{"slug", "version", "state": "draft", "seeded_from"}` — `version`
    é a nova (use-a no `write_draft`/`publish` seguintes) e `seeded_from` a
    published que serviu de semente. Idempotente: se o draft da próxima versão
    já existe, devolve-o sem re-semear (não sobrescreve edições em andamento).

    Escopo: spec.write (cavalga; a chave de autoria do README já autoriza —
    comprovado ao vivo no sandbox-tbc em 14/08: chamada com a chave de 6 scopes
    autorizou e chegou ao handler). `code="not_found"` se o slug não tem
    published."""
    return _call("spec.revise", {"slug": slug})


def publish(slug: str, version: str) -> dict[str, Any]:
    """Levanta `McpClientError(code="validation_failed", details={"errors": [...]})`
    se o draft não passa em `validate` primeiro — o servidor MCP recusa a promoção."""
    return _call("spec.publish", {"slug": slug, "version": version})
