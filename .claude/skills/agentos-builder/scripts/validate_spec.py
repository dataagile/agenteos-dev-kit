#!/usr/bin/env python3
"""AgentSpec validator CLI for the agentos-builder skill.

Two-layer validation of a published AgentSpec YAML:

  Layer 1 (pydantic): ``agent_specs.schema.AgentSpecSchema`` — the seed-time
    MVP schema (id, slug, name, version, nodes, ...).
  Layer 2 (JSON Schema): ``cdm.agent_spec.validate_agent_spec`` — the frozen
    AgentSpec v1.0 contract (packages/cdm/schemas/agent_spec_v1.json), which
    additionally requires ``trigger`` and validates node shapes per type plus
    the closed condition-expression grammar.

Zero hardcode: no agent/client/ERP name and no node-type list is literal in
this file. Node types come from the builder map
(packages/cdm/schemas/agent_spec_v1_builder_map.json) and runtime-readiness
is derived by parsing ExecutorFactory.execute's dispatch branches in
apps/agent-runtime/src/agent_runtime/executors.py at runtime (D-04 graceful
degradation if that parse fails).

``--write-to`` is THE only sanctioned write path for this skill: it validates
the source YAML, then structurally confines the destination to
{drafts,published}/ under the repo root. Direct LLM-side
Write of AgentSpec YAMLs is deprecated in favor of this path — the boundary
check here is a hard structural refusal (exit 3), not advisory guidance an
LLM caller could talk itself past.

Usage:
    validate_spec.py <path-to-yaml>
    validate_spec.py <path-to-yaml> --write-to <dest-path>
    validate_spec.py --list-node-types
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup — repo layout discovery (zero hardcode: no agent/tenant/ERP
# names below, only structural package paths that are part of the monorepo
# layout itself).
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[3]  # .claude/skills/agentos-builder/scripts -> repo root

_BUILDER_MAP_PATH = (
    _REPO_ROOT / "packages" / "cdm" / "schemas" / "agent_spec_v1_builder_map.json"
)
_EXECUTORS_PATH = (
    _REPO_ROOT
    / "apps"
    / "agent-runtime"
    / "src"
    / "agent_runtime"
    / "executors.py"
)


def _fallback_sys_path() -> None:
    """Add workspace package src/ dirs to sys.path as a last resort.

    Only used when the normal editable-install imports fail (e.g. `uv sync`
    was never run). Graceful degradation per D-04 — loud, not silent: the
    caller still reports layer-0 errors if imports keep failing afterwards.
    """
    candidates = [
        _REPO_ROOT / "packages" / "agent-specs" / "src",
        _REPO_ROOT / "packages" / "cdm" / "src",
    ]
    for c in candidates:
        if c.is_dir():
            sys.path.insert(0, str(c))


def _emit_layer0_error(message: str) -> None:
    payload = {
        "ok": False,
        "errors": [{"layer": 0, "path": "", "message": message}],
    }
    print(json.dumps(payload))
    sys.exit(2)


try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    _fallback_sys_path()
    try:
        import yaml  # type: ignore[import-untyped]  # noqa: F811
    except ImportError:
        _emit_layer0_error(
            "Failed to import 'yaml'. Run 'uv sync' at the repo root and "
            "invoke this script with .venv/bin/python."
        )

try:
    from agent_specs.schema import AgentSpecSchema, NodeSpec
except ImportError:
    _fallback_sys_path()
    try:
        from agent_specs.schema import AgentSpecSchema, NodeSpec  # noqa: F811
    except ImportError:
        _emit_layer0_error(
            "Failed to import 'agent_specs'. Run 'uv sync' at the repo root "
            "and invoke this script with .venv/bin/python."
        )

try:
    from cdm.agent_spec import validate_agent_spec
except ImportError:
    _fallback_sys_path()
    try:
        from cdm.agent_spec import validate_agent_spec  # noqa: F811
    except ImportError:
        _emit_layer0_error(
            "Failed to import 'cdm'. Run 'uv sync' at the repo root and "
            "invoke this script with .venv/bin/python."
        )

try:
    from pydantic import ValidationError as PydanticValidationError
except ImportError:
    _emit_layer0_error(
        "Failed to import 'pydantic'. Run 'uv sync' at the repo root and "
        "invoke this script with .venv/bin/python."
    )


def _check_node_key_tripwire() -> None:
    """DAI-526 tripwire: abort loudly if pydantic NodeSpec ever gains a `key` field.

    This skill's whole dual id/key posture (layer 1 requires node `id`, layer
    2 requires node `key`, --write-to's known_drift classification, the
    gate-severity downgrade for that specific mismatch) is built on the
    current fact that agent_specs.schema.NodeSpec has NO `key` field. If
    DAI-526 (or any other change) adds one, that fact silently stops being
    true and every piece of guidance/logic built on it becomes stale —
    loud failure here forces a human to re-derive it instead of the script
    quietly giving wrong answers.
    """
    if "key" in NodeSpec.model_fields:
        _emit_layer0_error(
            "schema.py now defines node 'key' — DAI-526 likely landed; "
            "agentos-builder's dual id/key guidance and gate downgrade must "
            "be revisited before use."
        )


# ---------------------------------------------------------------------------
# Layer 1 + Layer 2 validation
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    doc = yaml.safe_load(raw)
    if not isinstance(doc, dict):
        raise ValueError(f"Top-level YAML content must be a mapping, got {type(doc).__name__}")
    return doc


def _pydantic_errors_to_dicts(exc: PydanticValidationError) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for err in exc.errors():
        loc = err.get("loc", ())
        path = "/" + "/".join(str(p) for p in loc) if loc else ""
        errors.append({"layer": 1, "path": path, "message": err.get("msg", "invalid")})
    return errors


# Root-level MVP-only fields that trip layer 2's `additionalProperties: false`
# on the top-level object — the known id/key + MVP-field schema drift
# (see validate_spec_file's module-docstring cross-reference and the T002/T003
# handoff report). Listed once here so both the drift-detection regex message
# and any future consumer stay in sync with the actual field set.
_KNOWN_DRIFT_ROOT_FIELDS = ("category", "change_class", "config_schema", "io", "requires_erp")

_NODE_INDEX_PATH_RE = re.compile(r"^/nodes/\d+$")


def _is_known_drift(layer: int, path: str, message: str, doc: dict[str, Any] | None = None) -> bool:
    """Classify a layer-2 error as the known, pre-existing id/key + MVP-field drift.

    True iff:
      (a) path == "/" and message is the additionalProperties complaint that
          names any of the known MVP-only root fields, OR
      (b) path matches ^/nodes/\\d+$, message is either "'key' is a required
          property" or the oneOf "is not valid under any of the given
          schemas" complaint, AND the actual node object at that index does
          NOT already have a `key` field (D-15).

    A `/nodes/N` oneOf/key-required failure on a node that DOES have `key`
    is never the known drift — something else about that node's shape is
    genuinely wrong (novel), regardless of message text. ``doc`` is the
    parsed spec document; when it is not supplied (or the node can't be
    resolved), (b) falls back to the pre-D-15 message-only heuristic so
    existing call sites that don't thread the doc through keep working.

    Everything else (condition.expr grammar violations, bad slug pattern,
    missing trigger, etc.) is a novel/real error — always False.
    """
    if layer != 2:
        return False
    if path == "/" and "Additional properties are not allowed" in message:
        return any(field in message for field in _KNOWN_DRIFT_ROOT_FIELDS)
    if _NODE_INDEX_PATH_RE.match(path):
        if "'key' is a required property" in message or "is not valid under any of the given schemas" in message:
            node = _resolve_node_at_path(doc, path)
            if node is not None:
                return "key" not in node
            return True
    return False


def _resolve_node_at_path(doc: dict[str, Any] | None, path: str) -> dict[str, Any] | None:
    """Resolve the node dict referenced by a ``/nodes/N`` JSON Pointer path.

    Returns None if *doc* is absent, `nodes` is missing/not a list, the
    index is out of range, or the entry isn't a dict — callers treat None
    as "can't verify, fall back to message-only classification".
    """
    if not doc:
        return None
    match = _NODE_INDEX_PATH_RE.match(path)
    if not match:
        return None
    index = int(path.rsplit("/", 1)[-1])
    nodes = doc.get("nodes")
    if not isinstance(nodes, list) or index >= len(nodes):
        return None
    node = nodes[index]
    return node if isinstance(node, dict) else None


def validate_spec_file(path: Path) -> dict[str, Any]:
    """Run layer 1 (pydantic) then layer 2 (JSON Schema) validation.

    Returns the result payload dict:
      {"ok": bool,
       "errors": [{"layer", "path", "message", "known_drift"}, ...],
       "summary": {"layer1_errors": n, "layer2_known_drift": n, "layer2_novel": n}}

    `ok` reflects only the blocking layers: it is True iff there are zero
    layer-0 (operational) and zero layer-1 (pydantic MVP schema) errors.
    Layer-2 (frozen JSON Schema) errors — known_drift or novel — are
    reported but do not flip `ok` to False (D-14): the frozen contract is
    advisory/diagnostic today, not a publish gate.
    `known_drift` is purely informational — it lets a caller distinguish the
    pre-existing systemic id/key schema mismatch (see T002/T003 handoff) from
    a real, novel validation failure in the spec under test.
    """
    try:
        doc = _load_yaml(path)
    except FileNotFoundError:
        return {
            "ok": False,
            "errors": [{"layer": 0, "path": "", "message": f"File not found: {path}", "known_drift": False}],
            "summary": {"layer1_errors": 0, "layer2_known_drift": 0, "layer2_novel": 0},
        }
    except Exception as exc:  # noqa: BLE001 — surface any parse error as layer-0
        return {
            "ok": False,
            "errors": [{"layer": 0, "path": "", "message": f"Failed to load YAML: {exc}", "known_drift": False}],
            "summary": {"layer1_errors": 0, "layer2_known_drift": 0, "layer2_novel": 0},
        }

    errors: list[dict[str, Any]] = []

    # Layer 1 — pydantic MVP schema.
    try:
        AgentSpecSchema.model_validate(doc)
    except PydanticValidationError as exc:
        for e in _pydantic_errors_to_dicts(exc):
            e["known_drift"] = False
            errors.append(e)

    # Layer 2 — frozen JSON Schema contract, independent of layer 1 outcome
    # so callers see the full picture in one pass.
    layer2_errors = validate_agent_spec(doc)
    for err in layer2_errors:
        errors.append(
            {
                "layer": 2,
                "path": err.path,
                "message": err.message,
                "known_drift": _is_known_drift(2, err.path, err.message, doc),
            }
        )

    layer1_count = sum(1 for e in errors if e["layer"] == 1)
    layer2_known = sum(1 for e in errors if e["layer"] == 2 and e["known_drift"])
    layer2_novel = sum(1 for e in errors if e["layer"] == 2 and not e["known_drift"])

    return {
        "ok": not any(e["layer"] in (0, 1) for e in errors),
        "errors": errors,
        "summary": {
            "layer1_errors": layer1_count,
            "layer2_known_drift": layer2_known,
            "layer2_novel": layer2_novel,
        },
    }


# ---------------------------------------------------------------------------
# --list-node-types
# ---------------------------------------------------------------------------


def _load_builder_map() -> dict[str, Any]:
    raw = _BUILDER_MAP_PATH.read_text(encoding="utf-8")
    return json.loads(raw)  # type: ignore[no-any-return]


def _extract_frozenset_str_literals(node: ast.AST) -> set[str] | None:
    """Extract string literals from an `frozenset({...})` call AST node.

    Returns None if *node* is not a recognizable frozenset-of-strings call.
    """
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    is_frozenset_call = isinstance(func, ast.Name) and func.id == "frozenset"
    if not is_frozenset_call:
        return None
    if not node.args:
        return set()
    arg = node.args[0]
    elements: list[ast.expr] = []
    if isinstance(arg, (ast.Set, ast.List, ast.Tuple)):
        elements = list(arg.elts)
    else:
        return None
    values: set[str] = set()
    for el in elements:
        if isinstance(el, ast.Constant) and isinstance(el.value, str):
            values.add(el.value)
        else:
            # Non-literal element — bail out, caller treats as unparseable.
            return None
    return values


def _extract_string_constant(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _find_execute_method(tree: ast.Module) -> ast.AsyncFunctionDef | None:
    """Locate ExecutorFactory.execute — the single real dispatch point.

    Node-type routing tables exist in two files (interpreter.py routes to a
    target *category*; executors.py's ExecutorFactory.execute is what
    actually runs a node). This function reads executors.py because that is
    where "does an executor exist" is decided — interpreter.py's routing
    describes intent, not implementation (e.g. it comments that
    'delegate_to_agent' is handled by 'ExecutorFactory._execute_delegate_to_agent',
    but no such method exists in executors.py today).
    """
    for stmt in tree.body:
        if isinstance(stmt, ast.ClassDef) and stmt.name == "ExecutorFactory":
            for member in stmt.body:
                if isinstance(member, ast.AsyncFunctionDef) and member.name == "execute":
                    return member
    return None


def _collect_module_frozensets(tree: ast.Module) -> dict[str, set[str] | None]:
    """Map module-level frozenset/set variable names to their string contents.

    A value of None means the assignment exists but could not be parsed as a
    literal collection of strings (unparseable — triggers partial=True).
    """
    tables: dict[str, set[str] | None] = {}
    for stmt in tree.body:
        if not isinstance(stmt, ast.Assign):
            continue
        targets = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
        if not targets:
            continue
        value = stmt.value
        literal: set[str] | None
        if isinstance(value, (ast.Set, ast.List, ast.Tuple)):
            literal = set()
            for el in value.elts:
                s = _extract_string_constant(el)
                if s is None:
                    literal = None
                    break
                literal.add(s)
        else:
            literal = _extract_frozenset_str_literals(value)
        for name in targets:
            tables[name] = literal
    return tables


def _parse_executor_dispatch(executors_path: Path | None = None) -> dict[str, Any]:
    """Parse executors.py via ast to find which node types have a real executor.

    ``executors_path`` defaults to the real repo file; overridable for tests
    that need to exercise the empty-dispatch / unparseable-table paths
    against a synthetic stand-in file without touching the real source.

    Criterion for "runtime_ready": a node type is runtime_ready iff
    ``ExecutorFactory.execute`` contains an executable dispatch branch for it
    that actually calls an executor method — i.e. the type is a member of one
    of the module-level frozenset/set dispatch tables referenced inside
    ``execute`` (``_LLM_TYPES``, ``_TOOL_GATEWAY_TYPES``, ``_ERP_QUERY_TYPES``,
    ``_TRANSFORM_TYPES``, ``_RENDER_TYPES``, or any future table following the
    same pattern) OR the type is checked via an explicit
    ``if node_type == "<literal>":`` branch inside ``execute`` whose body does
    NOT raise (e.g. ``channel_send``, ``audit_append``, ``approval``, ``tool``).

    A type is explicitly NOT runtime_ready when its ``execute`` branch raises
    (e.g. ``team`` → ``PlatformError``/``NotImplementedError``) — this is
    detected by checking whether the branch body contains a ``raise``
    statement as its (first) effect.

    Types with no dispatch table membership and no explicit branch (e.g.
    ``delegate_to_agent``, which interpreter.py routes but executors.py never
    names) fall through to ``execute``'s bare fallback — NOT runtime_ready,
    because there is no real executor selected for them; the fallback exists
    as a generic safety net, not a routing decision for that type.

    This function hardcodes no *type names* — it reads whichever tables and
    literal-type branches actually exist in executors.py, so new dispatch
    entries are picked up automatically without a change here.

    Returns {"ready_types": set[str], "not_ready_types": set[str],
    "partial": bool, "warning": str | None}.
    """
    target = executors_path if executors_path is not None else _EXECUTORS_PATH
    try:
        source = target.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(target))
    except Exception as exc:  # noqa: BLE001
        return {
            "ready_types": set(),
            "not_ready_types": set(),
            "partial": True,
            "warning": f"Failed to parse executors.py: {exc}",
        }

    frozensets = _collect_module_frozensets(tree)
    execute_fn = _find_execute_method(tree)
    if execute_fn is None:
        return {
            "ready_types": set(),
            "not_ready_types": set(),
            "partial": True,
            "warning": "Could not locate ExecutorFactory.execute in executors.py",
        }

    ready: set[str] = set()
    not_ready: set[str] = set()
    unparseable_tables: list[str] = []

    def _body_raises(body: list[ast.stmt]) -> bool:
        return any(isinstance(s, ast.Raise) for s in body)

    for stmt in ast.walk(execute_fn):
        if not isinstance(stmt, ast.If):
            continue
        test = stmt.test
        # Pattern: `if node_type in <TABLE_NAME>:`
        if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.In):
            comparator = test.comparators[0]
            if isinstance(comparator, ast.Name) and comparator.id in frozensets:
                values = frozensets[comparator.id]
                if values is None:
                    unparseable_tables.append(comparator.id)
                    continue
                if _body_raises(stmt.body):
                    not_ready |= values
                else:
                    ready |= values
                continue
        # Pattern: `if node_type == "<literal>":` (possibly `and`-combined,
        # e.g. `if node_type == "loop" and node.get(...):` — still counts as
        # a real dispatch branch for that literal type).
        eq_targets: list[ast.Compare] = []
        if isinstance(test, ast.Compare):
            eq_targets = [test]
        elif isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
            eq_targets = [v for v in test.values if isinstance(v, ast.Compare)]
        for cmp_node in eq_targets:
            if len(cmp_node.ops) != 1 or not isinstance(cmp_node.ops[0], ast.Eq):
                continue
            left_is_node_type = isinstance(cmp_node.left, ast.Name) and cmp_node.left.id == "node_type"
            if not left_is_node_type:
                continue
            literal = _extract_string_constant(cmp_node.comparators[0])
            if literal is None:
                continue
            if _body_raises(stmt.body):
                not_ready.add(literal)
            else:
                ready.add(literal)

    # A type appearing in both ready and not_ready (e.g. raise-then-fallback
    # in nested branches) is treated conservatively as not ready.
    ready -= not_ready

    partial = bool(unparseable_tables)
    warning = (
        f"Could not parse dispatch table(s) as literal string collections: {unparseable_tables}"
        if unparseable_tables
        else None
    )

    # A real executors.py always dispatches at least SOME node types — zero
    # decisions found (both sets empty) means the parser's structural
    # assumptions (ast.If shapes it recognizes) stopped matching the file,
    # not that the repo genuinely has no runtime-ready types. Treat that as
    # partial/unreliable rather than silently reporting an empty catalog as
    # if it were ground truth.
    if not ready and not not_ready:
        partial = True
        empty_warning = "Parsed executors.py but found zero dispatch decisions (ready+not_ready both empty) — parser likely out of sync with ExecutorFactory.execute's structure."
        warning = f"{warning}; {empty_warning}" if warning else empty_warning

    return {
        "ready_types": ready,
        "not_ready_types": not_ready,
        "partial": partial,
        "warning": warning,
    }


def list_node_types(executors_path: Path | None = None) -> dict[str, Any]:
    """Build the --list-node-types payload.

    Source of truth for the type catalog + required/optional fields: the
    builder map's ``properties.node_types`` object. Source of truth for
    ``runtime_ready``: executors.py's ``ExecutorFactory.execute`` dispatch
    (see ``_parse_executor_dispatch`` docstring for the exact criterion).

    Caveat: this reflects only *top-level* dispatch in ``execute()``. A type
    like ``condition`` has separate, narrower handling when nested inside a
    ``loop`` node's ``body`` (``_execute_loop``) — that nested-only support
    does not make it runtime_ready as a top-level node here, since a
    top-level ``condition`` node still falls through to the generic
    fallback.

    ``executors_path`` is a test-only override — see ``_parse_executor_dispatch``.
    """
    try:
        builder_map = _load_builder_map()
    except Exception as exc:  # noqa: BLE001
        return {
            "node_types": [],
            "partial": True,
            "warning": f"Failed to load builder map: {exc}",
        }

    node_types_obj = builder_map.get("properties", {}).get("node_types", {})

    dispatch = _parse_executor_dispatch(executors_path)
    ready_types: set[str] = dispatch["ready_types"]
    partial = dispatch["partial"]
    warning = dispatch.get("warning")

    entries: list[dict[str, Any]] = []
    for type_name, spec in node_types_obj.items():
        entries.append(
            {
                "type": type_name,
                "runtime_ready": type_name in ready_types,
                "required": spec.get("required", []),
                "optional": spec.get("optional", []),
            }
        )

    # Empty node_types catalog is the second empty-discovery cause (devil #4/#8):
    # a real builder map always defines node types, so an empty resolution
    # means the map moved/changed shape, not that the repo has none.
    if not node_types_obj:
        partial = True
        empty_map_warning = "Builder map's properties.node_types resolved empty — map likely moved or changed shape."
        warning = f"{warning}; {empty_map_warning}" if warning else empty_map_warning

    result: dict[str, Any] = {"node_types": entries, "partial": partial}
    if warning:
        result["warning"] = warning
    return result


# ---------------------------------------------------------------------------
# --write-to structural boundary
# ---------------------------------------------------------------------------

# The only two directories agentos-builder is allowed to write AgentSpec
# YAMLs into. Structural, not advisory: enforced via realpath containment,
# not a string-prefix check an LLM caller could route around with `..` or
# symlinks.
_ALLOWED_WRITE_ROOTS = (
    _REPO_ROOT / "packages" / "agent-specs" / "drafts",
    _REPO_ROOT / "packages" / "agent-specs" / "published",
)


def _resolve_write_destination(dest: str) -> Path | None:
    """Return the realpath of *dest* if it falls under an allowed write root, else None.

    Uses ``os.path.realpath``-equivalent resolution (``Path.resolve()``,
    which does not require the path to exist) so `..` segments and symlinks
    cannot be used to escape the allowed roots.
    """
    resolved = Path(dest).resolve()
    for root in _ALLOWED_WRITE_ROOTS:
        allowed_root = root.resolve()
        if resolved == allowed_root or allowed_root in resolved.parents:
            return resolved
    return None


def write_spec(src: Path, dest: str) -> dict[str, Any]:
    """Validate *src*, then copy it to *dest* iff layer 1 is clean and *dest* is in-bounds.

    Returns a payload combining the validation result with either
    ``{"written": "<dest>"}`` on success or an operational error.
    """
    result = validate_spec_file(src)

    resolved_dest = _resolve_write_destination(dest)
    if resolved_dest is None:
        return {
            **result,
            "written": None,
            "error": "path outside a raiz deste repositório — refused (boundary is structural, not advisory)",
        }

    layer1_errors = [e for e in result["errors"] if e.get("layer") == 1]
    layer0_errors = [e for e in result["errors"] if e.get("layer") == 0]
    if layer0_errors or layer1_errors:
        return {**result, "written": None}

    resolved_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, resolved_dest)
    return {**result, "written": str(resolved_dest)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    _check_node_key_tripwire()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("yaml_path", nargs="?", help="Path to an AgentSpec YAML file to validate.")
    parser.add_argument(
        "--list-node-types",
        action="store_true",
        help="List all known node types with runtime_ready status and field maps.",
    )
    parser.add_argument(
        "--write-to",
        metavar="DEST",
        help=(
            "Validate yaml_path, then copy it to DEST — the only sanctioned write path "
            "for this skill. DEST must resolve under a raiz deste repo: drafts/ or "
            "a raiz deste repo: published/."
        ),
    )
    args = parser.parse_args(argv)

    if args.list_node_types:
        result = list_node_types()
        print(json.dumps(result))
        return 0

    if not args.yaml_path:
        parser.error("yaml_path is required unless --list-node-types is given")

    if args.write_to:
        result = write_spec(Path(args.yaml_path), args.write_to)
        print(json.dumps(result))
        if result.get("written"):
            return 0
        if result.get("error"):
            return 3
        # layer 0 = operational failure — exit 2. layer 1/2 = validation errors — exit 1.
        if any(e.get("layer") == 0 for e in result["errors"]):
            return 2
        return 1

    result = validate_spec_file(Path(args.yaml_path))
    print(json.dumps(result))
    if result["ok"]:
        return 0
    # layer 0 = operational failure (file missing, unparseable YAML) — exit 2.
    # layer 1/2 = real validation errors — exit 1.
    if any(e.get("layer") == 0 for e in result["errors"]):
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
