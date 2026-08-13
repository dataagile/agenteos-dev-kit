#!/usr/bin/env python3
"""Dogfood check (024/T019) — drives agentos-builder's real mcp_client.py against
a real local MCP server (uvicorn on 127.0.0.1, Postgres testcontainer, an
allowed test tenant). No deployed TLS server required.

Proves two things:

  1. Read-only parity: fetching + validating `fin-pagamentos` through
     `mcp_client` is compared against calling the local validators directly
     (`agent_specs.schema.AgentSpecSchema` + `cdm.agent_spec.validate_agent_spec`).
     `fin-pagamentos/published` is only ever READ here — never written.
  2. Write/publish/cleanup works end-to-end via `mcp_client` on a THROWAWAY
     slug (`zz-dogfood-024-throwaway`) only, which this script deletes again
     before exiting. It never touches any real published spec.

Run: uv run python .claude/skills/agentos-builder/scripts/dogfood_check.py
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import os
import shutil
from collections import Counter
import socket
import sys
import threading
import time
from datetime import timedelta
from pathlib import Path

import sqlalchemy as sa
import uvicorn
import yaml
from alembic import command
from alembic.config import Config
from testcontainers.postgres import PostgresContainer

_REPO_ROOT = Path(__file__).resolve().parents[4]  # .claude/skills/agentos-builder/scripts -> repo root
for _pkg in ("agent-specs", "cdm", "mcp-server", "tenancy", "db"):
    sys.path.insert(0, str(_REPO_ROOT / "packages" / _pkg / "src"))

from agent_specs.schema import AgentSpecSchema  # noqa: E402
from cdm.agent_spec import validate_agent_spec  # noqa: E402
from db import Database  # noqa: E402
from mcp_server.app import create_app  # noqa: E402
from mcp_server.auth import issue_key  # noqa: E402
from mcp_server.settings import Settings  # noqa: E402

# mcp_client.py lives in a hyphenated dir, not import-friendly as a package —
# load it by path, same script this proves works for the real skill.
_client_spec = importlib.util.spec_from_file_location("mcp_client", Path(__file__).parent / "mcp_client.py")
mcp_client = importlib.util.module_from_spec(_client_spec)
assert _client_spec.loader is not None
_client_spec.loader.exec_module(mcp_client)

_TENANT = "33333333-3333-3333-3333-333333333333"
_RUNTIME_ROLE = "agenteos_runtime"
_RUNTIME_PW = "dogfood_runtime_pw"  # noqa: S105 — throwaway local testcontainer password
_ALEMBIC_INI = _REPO_ROOT / "infra" / "migrations" / "alembic.ini"
_THROWAWAY_SLUG = "zz-dogfood-024-throwaway"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _to_psycopg3(url: str) -> str:
    return url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)


@contextlib.asynccontextmanager
async def _lifespan(app, dsn: str):
    database = Database(dsn)
    await database.open()
    app.state.db = database
    try:
        yield
    finally:
        await database.close()


def main() -> int:
    print("=== 1. Postgres testcontainer, migrate to head, seed 1 test tenant ===")
    with PostgresContainer("postgres:16") as pg:
        admin_dsn = _to_psycopg3(pg.get_connection_url())
        os.environ["DATABASE_URL"] = admin_dsn
        command.upgrade(Config(str(_ALEMBIC_INI)), "head")

        engine = sa.create_engine(admin_dsn)
        with engine.begin() as conn:
            conn.execute(sa.text(f"DROP ROLE IF EXISTS {_RUNTIME_ROLE}"))
            conn.execute(sa.text(f"CREATE ROLE {_RUNTIME_ROLE} LOGIN PASSWORD '{_RUNTIME_PW}' NOSUPERUSER NOCREATEDB NOCREATEROLE"))
            conn.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {_RUNTIME_ROLE}"))
            conn.execute(sa.text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {_RUNTIME_ROLE}"))
            conn.execute(sa.text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {_RUNTIME_ROLE}"))
            conn.execute(sa.text("INSERT INTO tenants (id, name, slug) VALUES (:t, 'Dogfood', 'dogfood')"), {"t": _TENANT})
        engine.dispose()

        from sqlalchemy.engine import make_url

        runtime_dsn = make_url(admin_dsn).set(username=_RUNTIME_ROLE, password=_RUNTIME_PW).render_as_string(hide_password=False)

        print("=== 2. Real local uvicorn (no TLS/deployed server needed) ===")
        settings = Settings(
            app_env="development",
            otel_exporter_otlp_endpoint="http://otel-collector:4317",
            database_url=runtime_dsn,
            redis_url="redis://localhost:6379/0",
            secret_key="dogfood-secret",
            otel_traces_enabled=False,
            mcp_enabled=True,
            mcp_allowed_tenant_ids=(_TENANT,),
            _env_file=None,
        )
        app = create_app(settings, lifespan=lambda a: _lifespan(a, runtime_dsn))

        port = _free_port()
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        else:
            raise RuntimeError("uvicorn did not start")

        os.environ["MCP_URL"] = f"http://127.0.0.1:{port}"

        try:
            print("=== 3. Issue a scoped key for the test tenant ===")

            async def _issue():
                db = Database(runtime_dsn)
                await db.open()
                key = await issue_key(db, tenant_id=_TENANT, scope=["spec.read", "spec.write"], ttl=timedelta(hours=1))
                await db.close()
                return key

            os.environ["MCP_KEY"] = asyncio.run(_issue()).secret

            print("=== 4. Read-only parity check: fin-pagamentos (never written to) ===")
            specs = mcp_client.list_specs()
            print(f"  spec.list via MCP: {len(specs)} specs")
            assert any(s["slug"] == "fin-pagamentos" for s in specs), "fin-pagamentos missing from MCP list"

            published_versions = sorted(s["version"] for s in specs if s["slug"] == "fin-pagamentos" and s["state"] == "published")
            version = published_versions[-1]
            read = mcp_client.read_spec("fin-pagamentos", version)
            content = read["content"]
            mcp_verdict = mcp_client.validate(content)

            raw = yaml.safe_load(content)
            try:
                spec = AgentSpecSchema.model_validate(raw)
                local_pydantic_ok = True
            except Exception:
                spec = None
                local_pydantic_ok = False
            local_layer2_errors = validate_agent_spec(raw)

            mcp_pairs = Counter((e["field_path"], e["message"]) for e in mcp_verdict.get("errors", []))
            local_pairs = Counter((e.path, e.message) for e in local_layer2_errors)

            print(f"  MCP spec.validate: ok={mcp_verdict['ok']}, errors={mcp_verdict.get('errors', [])}")
            print(f"  local pydantic ok: {local_pydantic_ok}")
            print(f"  local JSON-Schema (cdm.agent_spec.validate_agent_spec) errors: {len(local_layer2_errors)}")

            assert mcp_verdict["ok"] == local_pydantic_ok, "PARITY BREAK on the layer both validators actually share (pydantic)"
            assert mcp_pairs == local_pairs, f"PARITY BREAK on layer 2: mcp={mcp_pairs} local={local_pairs}"
            print("  -> full parity CONFIRMED (pydantic ok/not-ok + JSON-Schema layer-2 errors, field-for-field)")

            print("=== 4b. Same comparison against a spec that DOES trip layer 2 (read-only) ===")
            read2 = mcp_client.read_spec("analise-estoque", "1")
            content2 = read2["content"]
            mcp_verdict2 = mcp_client.validate(content2)
            raw2 = yaml.safe_load(content2)
            local_layer2_errors2 = validate_agent_spec(raw2)
            mcp_pairs2 = Counter((e["field_path"], e["message"]) for e in mcp_verdict2.get("errors", []))
            local_pairs2 = Counter((e.path, e.message) for e in local_layer2_errors2)
            print(f"  MCP spec.validate(analise-estoque v1): ok={mcp_verdict2['ok']}, {len(mcp_verdict2.get('errors', []))} errors")
            print(f"  local JSON-Schema errors: {len(local_layer2_errors2)} -> {[e.to_dict() for e in local_layer2_errors2]}")
            assert mcp_pairs2 == local_pairs2, f"PARITY BREAK on the known DAI-526/G6 drift: mcp={mcp_pairs2} local={local_pairs2}"
            print(
                f"  -> MCP reproduces the known DAI-526/G6 drift exactly ({sum(local_pairs2.values())} errors, "
                "field-for-field) — the Round 2 gap (mcp_server used agent_specs.lint instead of "
                "cdm.agent_spec.validate_agent_spec) is closed."
            )

            print("=== 4c. Node-type/trigger discovery via MCP (T027, closes gap #3) ===")
            discovered = mcp_client.node_types()
            print(f"  spec.node_types: {len(discovered['node_types'])} types, transform_strategies={discovered.get('transform_strategies')}")
            assert discovered["node_types"], "spec.node_types voltou vazio"
            assert discovered.get("trigger", {}).get("type_enum"), "trigger.type_enum ausente"
            assert discovered.get("transform_strategies"), "transform_strategies ausente"
            print("  -> node-type discovery now comes from the MCP, no direct core-repo read in this script's mcp_client path")

            print("=== 5. Write/publish/cleanup on a THROWAWAY slug only ===")
            throwaway_yaml = (
                f'id: "agt_{_THROWAWAY_SLUG.replace("-", "_")}_v1"\n'
                f'slug: "{_THROWAWAY_SLUG}"\n'
                'name: "Dogfood Throwaway"\n'
                'version: "1.0.0"\n'
                "nodes:\n"
                '  - id: "noop"\n'
                '    type: "tool"\n'
            )
            written = mcp_client.write_draft(_THROWAWAY_SLUG, "1", throwaway_yaml)
            print(f"  write_draft -> {written}")
            assert mcp_client.validate(throwaway_yaml)["ok"]
            published = mcp_client.publish(_THROWAWAY_SLUG, "1")
            print(f"  publish -> {published}")
            assert published["state"] == "published"

            print("=== 6. Cleanup throwaway files ===")
            for state_dir in ("drafts", "published"):
                p = _REPO_ROOT / "packages" / "agent-specs" / state_dir / _THROWAWAY_SLUG
                if p.is_dir():
                    shutil.rmtree(p)
                    print(f"  removed {p}")

            print("\n=== DOGFOOD CHECK: PASS ===")
            return 0
        finally:
            server.should_exit = True
            thread.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
