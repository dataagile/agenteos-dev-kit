"""Guard mecânico do publish (spec §9): property `x-ref: connection` com
`default` NUNCA vai para published — conexão vem da ativação. O `default`
só existe em draft de teste porque spec_test_run não recebe config (ARMADILHAS §9).

Uso: python3 scripts/publish_guard.py <arquivo.yaml>  → exit 1 e lista se houver.
Sem PyYAML de propósito: parse por indentação, suficiente para o YAML que o kit escreve.
"""
import re
import sys


def connection_defaults(content: str) -> list[str]:
    """Nomes das properties do config_schema que têm x-ref: connection E default."""
    found: list[str] = []
    prop: str | None = None
    prop_indent = -1
    has_xref = has_default = False
    in_properties = False
    properties_indent = -1

    def close() -> None:
        if prop and has_xref and has_default:
            found.append(prop)

    for raw in content.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        key = line.strip()

        # Check if we're entering/leaving properties section
        if key.startswith("properties:"):
            in_properties = True
            properties_indent = indent
            prop = None
            has_xref = has_default = False
            continue

        # If we were in properties but moved to a sibling/parent key, exit properties
        if in_properties and indent <= properties_indent and not key.startswith("properties:"):
            close()
            in_properties = False
            prop = None
            has_xref = has_default = False

        # Parse property names (only if in properties section)
        if in_properties and indent == properties_indent + 2:
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*$", key)
            if m:
                close()
                prop = m.group(1)
                prop_indent = indent
                has_xref = has_default = False
                continue

        # Track x-ref and default within a property
        if in_properties and prop is not None and indent > prop_indent:
            if re.match(r"^x-ref:\s*connection\b", key):
                has_xref = True
            elif re.match(r"^default:", key):
                has_default = True

    close()
    return found


if __name__ == "__main__":
    text = open(sys.argv[1], encoding="utf-8").read()
    bad = connection_defaults(text)
    if bad:
        print("publish recusado — x-ref: connection com default:", ", ".join(bad))
        sys.exit(1)
    print("publish_guard: ok")
