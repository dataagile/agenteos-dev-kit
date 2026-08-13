"""Tests for the agentos-builder skill's validate_spec.py CLI.

Invokes the script as a subprocess (same interpreter as the test run, via
``sys.executable``) so the tests exercise the exact CLI contract a skill
caller would use — not internal functions directly.

Synthetic specs are built by loading a real published spec and mutating it
in memory, then writing to ``tmp_path`` — never handwritten from scratch, so
they stay structurally close to production data.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPT = _REPO_ROOT / ".claude" / "skills" / "agentos-builder" / "scripts" / "validate_spec.py"
_PUBLISHED_DIR = _REPO_ROOT / "packages" / "agent-specs" / "published"


def _run_cli(*args: str) -> tuple[int, dict[str, Any]]:
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        timeout=60,
    )
    assert proc.stdout.strip(), f"empty stdout; stderr={proc.stderr}"
    payload = json.loads(proc.stdout)
    return proc.returncode, payload


def _real_spec_paths() -> list[Path]:
    return sorted(_PUBLISHED_DIR.glob("*/*.yaml"))


def _load_real_spec() -> dict[str, Any]:
    """Load the fin-pagamentos published spec as a base for mutation."""
    path = _PUBLISHED_DIR / "fin-pagamentos" / "v1.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return raw


def _write_yaml(tmp_path: Path, name: str, doc: dict[str, Any]) -> Path:
    out = tmp_path / name
    out.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Case 1 — real published specs
# ---------------------------------------------------------------------------
#
# HISTORICAL NOTE (was a known repo bug, now resolved for `ok` purposes):
# every spec under a raiz deste repo: published/*/*.yaml used the node key
# `id` and legacy per-type config shapes (e.g. `config.expr`,
# `config.primitive`) inherited from the pydantic MVP schema
# (agent_specs.schema.NodeSpec), while the frozen JSON Schema contract
# (packages/cdm/schemas/agent_spec_v1.json) required `key` plus type-specific
# top-level fields (`expression`, `branches`, `tool_name`, ...). Some
# published specs may still carry residual layer-2 known_drift/novel
# findings (missing `trigger`, id/key mismatches not yet migrated), but per
# D-14 `ok` reflects only layers 0/1 — a real published spec with zero
# layer-0/1 errors now reports ok=true regardless of layer-2 state. This test
# was previously asserting ok=false for this exact scenario; per the D-14
# review comment (Gianluka) that contradicted the "layer 2 does not block"
# doctrine, so it was updated to assert ok=true instead of being silently
# loosened to hide a real regression — the underlying layer-2 findings (if
# any) are still fully reported in `errors`/`summary`, just not gating `ok`.


@pytest.mark.parametrize(
    "spec_path", _real_spec_paths(), ids=[p.parent.name for p in _real_spec_paths()]
)
def test_real_published_specs_pass_ok_despite_layer2_known_drift(spec_path: Path) -> None:
    returncode, payload = _run_cli(str(spec_path))

    assert payload["summary"]["layer1_errors"] == 0, (
        f"precondition broken: expected zero layer-1 errors for a real published spec, got: {payload['summary']}"
    )
    assert payload["ok"] is True, (
        f"D-14: ok should be True with zero layer-0/1 errors, got ok=False: {payload['errors']}"
    )
    assert returncode == 0


# ---------------------------------------------------------------------------
# Case 2 — missing trigger
# ---------------------------------------------------------------------------


def test_missing_trigger_fails_layer2(tmp_path: Path) -> None:
    doc = _load_real_spec()
    assert "trigger" in doc
    del doc["trigger"]

    spec_path = _write_yaml(tmp_path, "missing_trigger.yaml", doc)
    returncode, payload = _run_cli(str(spec_path))

    # Missing `trigger` is a layer-2-only (frozen JSON Schema) violation —
    # layer 1 (pydantic MVP schema) does not require it. Per D-14, `ok`
    # reflects only layers 0/1, so this stays ok=true; the error is still
    # fully reported below.
    assert payload["summary"]["layer1_errors"] == 0
    assert payload["ok"] is True
    assert returncode == 0
    layer2_errors = [e for e in payload["errors"] if e["layer"] == 2]
    assert any("trigger" in e["message"] or "trigger" in e["path"] for e in layer2_errors), (
        f"expected an error mentioning 'trigger', got: {layer2_errors}"
    )


# ---------------------------------------------------------------------------
# Case 3 — condition node with unsupported expression grammar
# ---------------------------------------------------------------------------


def test_unsupported_condition_expression_fails_with_nodes_pointer(tmp_path: Path) -> None:
    doc = _load_real_spec()
    doc["nodes"] = [
        {
            "key": "check_something",
            "type": "condition",
            "config": {"expr": "foo > bar or baz"},
        }
    ]

    spec_path = _write_yaml(tmp_path, "bad_condition.yaml", doc)
    returncode, payload = _run_cli(str(spec_path))

    assert payload["ok"] is False
    assert returncode == 1
    errors = payload["errors"]
    assert any(e["path"].startswith("/nodes") for e in errors), (
        f"expected a JSON Pointer error rooted at /nodes, got: {errors}"
    )
    condition_errors = [
        e for e in errors if "condition.expr" in e["message"] or "not supported" in e["message"].lower()
    ]
    assert condition_errors, f"expected a condition-expression grammar error, got: {errors}"
    assert all(not e["known_drift"] for e in condition_errors), (
        f"a condition-expression grammar violation is a novel error, not the known id/key drift: {condition_errors}"
    )
    assert payload["summary"]["layer2_novel"] >= 1


# ---------------------------------------------------------------------------
# Case 3b — _is_known_drift must distinguish "key present, something else
# missing" (novel) from "key genuinely absent" (known_drift) — D-15 / PR #174
# review comment from rodrigopg.
#
# Both cases produce the SAME generic oneOf failure message at /nodes/N
# ("... is not valid under any of the given schemas") because the frozen
# node_condition definition (as of this run) requires key+type+expression+
# branches, and neither case supplies expression/branches. The only
# structural difference is whether `key` itself is present on the node. If
# T007-T009 (running in parallel) patch node_condition to add a config.expr-
# based oneOf branch, the exact "something else missing" field may change,
# but the shape of the bug under test (key present + oneOf failure at
# /nodes/N) is unaffected — this test only needs a node that has `key` and
# still fails the oneOf for a real, unrelated reason.
# ---------------------------------------------------------------------------


def test_condition_node_with_key_but_missing_required_field_is_novel_not_known_drift(
    tmp_path: Path,
) -> None:
    """A condition node that already HAS `key` but is missing its type's own
    required field (here: `expression`/`branches`) must be classified as a
    real, actionable (`novel`) error — not hidden behind known_drift=True.

    THIS TEST IS EXPECTED TO CURRENTLY FAIL: the unfixed `_is_known_drift`
    pattern-matches on the oneOf message text alone (path matches
    `^/nodes/\\d+$` and message contains "is not valid under any of the given
    schemas") without checking whether `key` is actually present on the node
    in the validated document — so it currently misclassifies this case as
    known_drift=True too. The fix (T014b) must inspect the actual node object,
    not just the error message.
    """
    doc = _load_real_spec()
    doc["nodes"] = [
        {
            # `key` IS present — this must NOT be classified known_drift.
            "key": "check_something",
            "type": "condition",
            "config": {"expr": "foo == bar"},
            # Deliberately omitting `expression` / `branches`, the fields
            # node_condition currently requires beyond key+type. Also missing
            # under any config.expr-based oneOf branch T007-T009 might add,
            # since this node's `config` has no `on_true`/`on_false`.
        }
    ]

    spec_path = _write_yaml(tmp_path, "condition_key_present_missing_fields.yaml", doc)
    _returncode, payload = _run_cli(str(spec_path))

    node_oneof_errors = [
        e
        for e in payload["errors"]
        if e["layer"] == 2
        and e["path"].startswith("/nodes/0")
        and (
            "is not valid under any of the given schemas" in e["message"]
            or "condition.expr" in e["message"]
        )
    ]
    assert node_oneof_errors, (
        f"expected a oneOf failure at /nodes/0 for a condition node missing "
        f"expression/branches, got: {payload['errors']}"
    )
    assert all(not e["known_drift"] for e in node_oneof_errors), (
        "a condition node that already has `key` but is missing a real "
        "required field of its own type must be classified as novel "
        f"(known_drift=False), not known_drift=True; got: {node_oneof_errors}"
    )


def test_condition_node_without_key_still_classified_known_drift(tmp_path: Path) -> None:
    """Companion case: a condition node genuinely missing `key` (the
    pre-existing, systemic id/key drift) must still be classified
    known_drift=True — confirming the D-15 fix narrows the classifier without
    breaking the legitimate known-drift case. This case is expected to PASS
    against the current (unfixed) classifier already."""
    doc = _load_real_spec()
    doc["nodes"] = [
        {
            # No `key` at all — only the legacy `id` field, mirroring every
            # real published spec's shape.
            "id": "check_something",
            "type": "condition",
            "config": {"expr": "foo == bar"},
        }
    ]

    spec_path = _write_yaml(tmp_path, "condition_no_key.yaml", doc)
    _returncode, payload = _run_cli(str(spec_path))

    layer2_errors = [e for e in payload["errors"] if e["layer"] == 2 and e["path"] == "/nodes/0"]
    assert any("'key' is a required property" in e["message"] for e in layer2_errors), (
        f"expected a missing-key error at /nodes/0, got: {layer2_errors}"
    )
    assert all(e["known_drift"] for e in layer2_errors), (
        f"a condition node genuinely missing `key` must still be known_drift=True, got: {layer2_errors}"
    )


# ---------------------------------------------------------------------------
# Case 4 — invalid slug
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_slug", ["Has Uppercase And Spaces", "UPPER_SLUG", "-leading-dash"])
def test_invalid_slug_fails_layer2_only(tmp_path: Path, bad_slug: str) -> None:
    doc = _load_real_spec()
    doc["slug"] = bad_slug

    spec_path = _write_yaml(tmp_path, "bad_slug.yaml", doc)
    returncode, payload = _run_cli(str(spec_path))

    # pydantic's `slug: str` field has no pattern constraint — an invalid
    # slug only trips the frozen JSON Schema's regex (layer 2). Per D-14,
    # `ok` reflects only layers 0/1, so this stays ok=true; the layer-2
    # error is still fully reported below.
    assert payload["summary"]["layer1_errors"] == 0
    assert payload["ok"] is True
    assert returncode == 0
    assert payload["errors"], "expected at least one error for an invalid slug"


# ---------------------------------------------------------------------------
# Case 5 — --list-node-types
# ---------------------------------------------------------------------------


def test_list_node_types_shape() -> None:
    returncode, payload = _run_cli("--list-node-types")

    assert returncode == 0
    assert "node_types" in payload
    assert "partial" in payload

    node_types = payload["node_types"]
    assert len(node_types) >= 14, f"expected at least 14 node types, got {len(node_types)}"

    by_type = {}
    for entry in node_types:
        assert "type" in entry
        assert "runtime_ready" in entry
        assert isinstance(entry["runtime_ready"], bool)
        assert "required" in entry
        assert "optional" in entry
        by_type[entry["type"]] = entry

    assert "tool" in by_type
    assert by_type["tool"]["runtime_ready"] is True


def test_list_node_types_not_partial_on_clean_repo() -> None:
    """Sanity check: with the repo's current executors.py, parsing should
    succeed cleanly (partial=False, no warning) — a regression here signals
    someone changed the dispatch-table style in a way the parser can't read,
    which would silently degrade --list-node-types accuracy."""
    _returncode, payload = _run_cli("--list-node-types")
    assert payload["partial"] is False
    assert "warning" not in payload


# ---------------------------------------------------------------------------
# Operational failure paths
# ---------------------------------------------------------------------------


def test_missing_file_exits_2(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.yaml"
    returncode, payload = _run_cli(str(missing))

    assert returncode == 2
    assert payload["ok"] is False
    assert payload["errors"][0]["layer"] == 0


def test_valid_synthetic_spec_passes_both_layers(tmp_path: Path) -> None:
    """Construct a spec that satisfies BOTH layers — proves the validator
    itself is not the source of the id/key drift documented in case 1 (the
    drift is real, in the published data, not an artifact of this script).

    This requires threading the needle between the two schemas' actual
    constraints, discovered empirically:
      * layer 1 (pydantic NodeSpec) requires `id` on every node.
      * layer 2 (JSON Schema) requires `key` on every node, but node objects
        allow additionalProperties — so a node may carry BOTH `id` and `key`.
      * layer 2's root schema has `additionalProperties: false` and does not
        list the MVP-only root fields (`category`, `change_class`,
        `config_schema`, `io`, `requires_erp`) that the pydantic root model
        defines (with defaults) — so a spec passing both layers must OMIT
        those MVP-only fields from the document entirely.
    """
    doc = _load_real_spec()
    doc["nodes"] = [
        {
            "id": "start",
            "key": "start",
            "type": "trigger",
        },
        {
            "id": "notify",
            "key": "notify",
            "type": "channel_send",
            "channel": "whatsapp",
            "message_template": "hello",
        },
    ]
    for mvp_only_field in ("category", "change_class", "config_schema", "io", "requires_erp"):
        doc.pop(mvp_only_field, None)

    spec_path = _write_yaml(tmp_path, "valid_synthetic.yaml", doc)
    returncode, payload = _run_cli(str(spec_path))

    assert payload["ok"] is True, f"expected ok=true, got errors: {payload['errors']}"
    assert returncode == 0
    assert payload["errors"] == []
    assert payload["summary"] == {"layer1_errors": 0, "layer2_known_drift": 0, "layer2_novel": 0}


# ---------------------------------------------------------------------------
# --write-to
# ---------------------------------------------------------------------------


def test_write_to_happy_path_into_drafts() -> None:
    """Layer 1 clean + destination in-bounds under drafts/ -> file is written,
    even though layer 2 still reports the known id/key drift (write only
    gates on layer 1 + path, per spec)."""
    src = _PUBLISHED_DIR / "analise-estoque" / "v1.yaml"
    dest_dir = _PUBLISHED_DIR.parent / "drafts" / "__test-write-to-happy"
    dest = dest_dir / "v1.yaml"
    assert not dest_dir.exists(), "leftover disposable test dir from a prior failed run"

    try:
        returncode, payload = _run_cli(str(src), "--write-to", str(dest))

        assert returncode == 0
        assert payload["written"] == str(dest.resolve())
        assert dest.is_file()
        assert dest.read_text(encoding="utf-8") == src.read_text(encoding="utf-8")
        # Layer 1 is clean (write gate passed) even though layer 2 still has
        # the known drift — write does not require full `ok`.
        assert payload["summary"]["layer1_errors"] == 0
    finally:
        if dest_dir.exists():
            import shutil as _shutil

            _shutil.rmtree(dest_dir)


@pytest.mark.parametrize(
    "bad_dest_fn",
    [
        lambda tmp_path: "/tmp/x-agentos-builder-escape.yaml",
        lambda tmp_path: str(_PUBLISHED_DIR / ".." / ".." / ".." / "tmp" / "y-agentos-builder-escape.yaml"),
    ],
    ids=["absolute-outside", "dotdot-escape"],
)
def test_write_to_path_escape_refused(tmp_path: Path, bad_dest_fn) -> None:
    src = _PUBLISHED_DIR / "analise-estoque" / "v1.yaml"
    bad_dest = bad_dest_fn(tmp_path)

    returncode, payload = _run_cli(str(src), "--write-to", bad_dest)

    assert returncode == 3
    assert payload["written"] is None
    assert "outside a raiz deste repositório" in payload["error"]
    assert not Path(bad_dest).resolve().exists(), "escape attempt must not create the file"


def test_write_to_symlink_escape_refused(tmp_path: Path) -> None:
    """A symlink placed inside drafts/ that points outside the repo must not
    be usable to smuggle a write past the boundary check — the guard resolves
    symlinks (Path.resolve()) before the containment check, not just strings."""
    src = _PUBLISHED_DIR / "analise-estoque" / "v1.yaml"
    outside_dir = tmp_path / "outside-repo"
    outside_dir.mkdir()

    symlink_path = _PUBLISHED_DIR.parent / "drafts" / "__test-symlink-escape"
    assert not symlink_path.exists(), "leftover disposable symlink from a prior failed run"

    try:
        symlink_path.symlink_to(outside_dir, target_is_directory=True)
        bad_dest = symlink_path / "spec.yaml"

        returncode, payload = _run_cli(str(src), "--write-to", str(bad_dest))

        assert returncode == 3
        assert payload["written"] is None
        assert "outside a raiz deste repositório" in payload["error"]
        assert not (outside_dir / "spec.yaml").exists(), "escape via symlink must not create the file"
    finally:
        if symlink_path.is_symlink() or symlink_path.exists():
            symlink_path.unlink()


def test_write_to_refuses_when_layer1_dirty(tmp_path: Path) -> None:
    doc = _load_real_spec()
    del doc["slug"]  # layer-1 required field

    spec_path = _write_yaml(tmp_path, "no_slug.yaml", doc)
    dest_dir = _PUBLISHED_DIR.parent / "drafts" / "__test-write-to-dirty"
    dest = dest_dir / "v1.yaml"
    assert not dest_dir.exists()

    try:
        returncode, payload = _run_cli(str(spec_path), "--write-to", str(dest))

        assert returncode == 1
        assert payload["written"] is None
        assert not dest.exists()
        assert payload["summary"]["layer1_errors"] >= 1
    finally:
        if dest_dir.exists():
            import shutil as _shutil

            _shutil.rmtree(dest_dir)


# ---------------------------------------------------------------------------
# --list-node-types: empty-discovery forces partial=True
# ---------------------------------------------------------------------------
#
# These exercise validate_spec's internal functions directly (not via
# subprocess) using the executors_path override hook, since simulating a
# "zero dispatch decisions found" repo state isn't reachable through the CLI
# without mutating the real executors.py.

import importlib.util as _importlib_util  # noqa: E402


def _load_validate_spec_module():
    spec = _importlib_util.spec_from_file_location("validate_spec", _SCRIPT)
    module = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_list_node_types_partial_when_executors_dispatch_is_empty(tmp_path: Path) -> None:
    module = _load_validate_spec_module()
    fake_executors = tmp_path / "fake_executors.py"
    fake_executors.write_text(
        "class ExecutorFactory:\n"
        "    async def execute(self, node):\n"
        "        return None\n",
        encoding="utf-8",
    )

    result = module.list_node_types(executors_path=fake_executors)

    assert result["partial"] is True
    assert "warning" in result
    assert "zero dispatch decisions" in result["warning"]


def test_parse_executor_dispatch_partial_on_unparseable_table(tmp_path: Path) -> None:
    module = _load_validate_spec_module()
    fake_executors = tmp_path / "fake_executors.py"
    fake_executors.write_text(
        "_LLM_TYPES = frozenset(SOME_DYNAMIC_EXPR)\n"
        "class ExecutorFactory:\n"
        "    async def execute(self, node):\n"
        "        node_type = node.get('type')\n"
        "        if node_type in _LLM_TYPES:\n"
        "            return 1\n",
        encoding="utf-8",
    )

    result = module._parse_executor_dispatch(fake_executors)

    assert result["partial"] is True
    assert "warning" in result or result.get("warning") is not None


# ---------------------------------------------------------------------------
# DAI-526 NodeSpec-key tripwire
# ---------------------------------------------------------------------------


def test_node_key_tripwire_fires_when_nodespec_gains_key_field(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_validate_spec_module()
    monkeypatch.setitem(module.NodeSpec.model_fields, "key", object())

    with pytest.raises(SystemExit) as exc_info:
        module._check_node_key_tripwire()

    assert exc_info.value.code == 2


def test_node_key_tripwire_silent_when_nodespec_has_no_key_field() -> None:
    module = _load_validate_spec_module()
    assert "key" not in module.NodeSpec.model_fields
    module._check_node_key_tripwire()  # must not raise/exit


def test_node_key_tripwire_fires_via_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end: the tripwire actually gates `main()`, not just a helper
    nobody calls."""
    module = _load_validate_spec_module()
    monkeypatch.setitem(module.NodeSpec.model_fields, "key", object())

    with pytest.raises(SystemExit) as exc_info:
        module.main([str(_PUBLISHED_DIR / "analise-estoque" / "v1.yaml")])

    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# D-14 — `ok` reflects only blocking layers (0/1), not layer-2 warnings
# ---------------------------------------------------------------------------
#
# T005 (017-standardize-agentspec-schema): target behavior once T014a lands.
# `ok` today is `len(errors) == 0` — ANY error, including non-blocking
# layer-2 (frozen JSON Schema) warnings, flips it False. That is a footgun
# (PR #174 review, Gianluka): a spec with zero layer-0/1 errors and only
# layer-2 known_drift/novel warnings should report ok=True.
#
# The three tests below prove the target semantics. The first one FAILS
# against the current (unfixed) script by design — it documents the exact
# behavior T014a must produce. See this module's docstring block above (case
# 1) plus test_missing_trigger_fails_layer2 / test_unsupported_condition_
# expression_fails_with_nodes_pointer / test_invalid_slug_fails for the
# EXISTING tests whose expected `ok` value T014a must flip to True (all four
# are layer-2-only scenarios today).


def test_layer2_only_errors_yield_ok_true(tmp_path: Path) -> None:
    """Zero layer-0/1 errors + some layer-2 errors (known_drift AND novel
    mixed) -> ok must be True (D-14). This is the real fin-pagamentos shape:
    19 known_drift (id/key + MVP-field drift) + a deliberately injected novel
    error (bad slug), zero layer-1 errors. EXPECTED TO FAIL until T014a
    changes `ok` from `len(errors) == 0` to
    `len([e for e in errors if e["layer"] in (0, 1)]) == 0`.
    """
    doc = _load_real_spec()
    doc["slug"] = "UPPER_SLUG"  # forces a novel layer-2 error alongside known_drift
    # After the T007-T009 schema patches + T013's key: additions, the real
    # published spec (fin-pagamentos) now has ZERO layer-2 errors of its own —
    # so known_drift must be forced independently here (a node missing `key`)
    # to keep this test's "known_drift AND novel mixed" precondition true.
    doc["nodes"][0].pop("key", None)

    spec_path = _write_yaml(tmp_path, "layer2_only.yaml", doc)
    _returncode, payload = _run_cli(str(spec_path))

    assert payload["summary"]["layer1_errors"] == 0, (
        f"precondition broken: expected zero layer-1 errors, got {payload['summary']}"
    )
    assert payload["summary"]["layer2_known_drift"] > 0
    assert payload["summary"]["layer2_novel"] > 0
    assert payload["ok"] is True, (
        "D-14: ok should be True when only layer-2 errors are present "
        f"(zero layer-0/1) — got ok=False with errors: {payload['errors']}"
    )


def test_layer1_error_still_yields_ok_false_regardless_of_layer2(tmp_path: Path) -> None:
    """A real layer-1 (pydantic) error must keep ok=False regardless of
    layer-2 state — layer 1 is blocking. This should ALREADY pass today
    (layer-1 errors already flip ok False under both old and new logic) and
    must keep passing after T014a.
    """
    doc = _load_real_spec()
    del doc["slug"]  # layer-1 required field on AgentSpecSchema

    spec_path = _write_yaml(tmp_path, "layer1_error.yaml", doc)
    _returncode, payload = _run_cli(str(spec_path))

    assert payload["summary"]["layer1_errors"] >= 1, (
        f"precondition broken: expected a layer-1 error, got {payload['summary']}"
    )
    assert payload["ok"] is False


def test_layer0_error_yields_ok_false(tmp_path: Path) -> None:
    """A layer-0 (operational) error — e.g. file not found — must keep
    ok=False. Layer 0 is blocking per D-14 (only layers 0/1 gate `ok`).
    Covers the same missing-file path as test_missing_file_exits_2 but
    asserts explicitly under the D-14 framing (layer-0 is blocking, same as
    layer-1) rather than as a generic operational-failure check.
    """
    missing = tmp_path / "does_not_exist.yaml"
    returncode, payload = _run_cli(str(missing))

    assert returncode == 2
    assert payload["errors"][0]["layer"] == 0
    assert payload["ok"] is False


# ─────────────────────────────────────────────────────────────────────────────
# oneOf disjointness — every config-shaped variant must be mutually exclusive
# with its legacy sibling (review PR #183 HIGH: condition/loop lacked the
# `not:` guard, so a legacy-shaped node carrying an incidental `config` object
# matched two oneOf branches and FAILED validation where it used to pass).
# ─────────────────────────────────────────────────────────────────────────────

_AMBIGUOUS_NODES = [
    (
        "condition_legacy_with_incidental_config",
        {
            "key": "a",
            "type": "condition",
            "expression": "{{ steps.a.output }}",
            "branches": {"true": "b"},
            "config": {"expr": "x > 0"},
        },
    ),
    (
        "loop_legacy_with_incidental_config",
        {
            "key": "b",
            "type": "loop",
            "over": "{{ steps.a.output }}",
            "body": ["x"],
            "config": {
                "over": "a.result",
                "body": [
                    {"key": "c", "type": "tool", "config": {"primitive": "read", "connector_id": "x", "entity": "Y"}}
                ],
            },
        },
    ),
    (
        "tool_legacy_with_incidental_config",
        {
            "key": "c",
            "type": "tool",
            "tool_name": "cdm.read",
            "config": {"primitive": "read", "connector_id": "x", "entity": "Y"},
        },
    ),
]


@pytest.mark.parametrize("label,node", _AMBIGUOUS_NODES, ids=[n[0] for n in _AMBIGUOUS_NODES])
def test_legacy_node_with_incidental_config_matches_exactly_one_branch(label: str, node: dict) -> None:
    """A legacy-shaped node with an incidental `config` key must validate —
    i.e. match exactly ONE oneOf branch, never two ("is valid under each of"
    is the ambiguity failure this guards against).
    """
    import jsonschema

    schema = json.loads((_REPO_ROOT / "packages" / "cdm" / "schemas" / "agent_spec_v1.json").read_text())
    node_schema = {"$defs": schema["$defs"], "$ref": "#/$defs/node"}
    jsonschema.validate(node, node_schema)  # raises on ambiguity or mismatch


def test_all_config_variants_have_not_guard() -> None:
    """Structural tripwire: every *_config/_primitive oneOf variant must carry
    a `not:` disjointness clause against its legacy sibling. A new variant
    added without one reintroduces the PR #183 ambiguity class.
    """
    schema = json.loads((_REPO_ROOT / "packages" / "cdm" / "schemas" / "agent_spec_v1.json").read_text())
    variants = [
        "node_condition_config",
        "node_loop_config",
        "node_tool_primitive",
        "node_channel_send_config",
        "node_audit_append_config",
    ]
    for name in variants:
        parts = schema["$defs"][name]["allOf"]
        assert any(isinstance(p, dict) and "not" in p for p in parts), f"{name} sem not:-guard de disjunção"
