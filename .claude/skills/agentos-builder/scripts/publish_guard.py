"""Guard mecânico do publish (spec §9): property `x-ref: connection` com
`default` NUNCA vai para published — conexão vem da ativação. O `default`
só existe em draft de teste porque spec_test_run não recebe config (ARMADILHAS §9).

Uso: python3 scripts/publish_guard.py <arquivo.yaml>  → exit 1 e lista se houver.
Sem PyYAML de propósito: parse por indentação, suficiente para o YAML que o kit
escreve. Casa qualquer bloco `properties:` — não só o de `config_schema` — então
um schema de nó com `x-ref: connection` + `default` também é recusado; direção
segura.

Ceiling conhecido, não garantia: forma flow (`conn: {x-ref: connection, default:
x}`) não é reconhecida — `x-ref:`/`default:` só contam como linha própria, e o
kit nunca escreve flow style. Ver `tests/test_publish_guard.py` para o caso.

Ceiling 2: só nomes de property `[A-Za-z_][A-Za-z0-9_-]*` são reconhecidos;
nome entre aspas ou com ponto passa em silêncio (mesma classe do flow-style).
"""
import pathlib
import re
import sys

_PROP_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*$")
_XREF_RE = re.compile(r"^x-ref:\s*connection\b")
_DEFAULT_RE = re.compile(r"^default:")


def connection_defaults(content: str) -> list[str]:
    """Nomes das properties que têm `x-ref: connection` E `default` em algum
    lugar do próprio bloco (linhas com indent maior que o da property, até a
    primeira linha de volta ao nível dela ou menos)."""
    lines: list[tuple[int, str]] = []
    for raw in content.splitlines():
        stripped = raw.split("#", 1)[0].rstrip()
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip())
        lines.append((indent, stripped.strip()))

    found: list[str] = []
    for i, (indent, key) in enumerate(lines):
        if not _XREF_RE.match(key):
            continue

        # Nome da property: a linha anterior mais próxima com indent menor.
        prop = prop_indent = prop_idx = None
        for j in range(i - 1, -1, -1):
            pindent, pkey = lines[j]
            if pindent < indent:
                m = _PROP_RE.match(pkey)
                if m:
                    prop, prop_indent, prop_idx = m.group(1), pindent, j
                break
        if prop is None or prop in found:
            continue

        # Bloco da property inteiro (não só a partir da linha do x-ref):
        # default pode vir antes ou depois do x-ref dentro dele.
        has_default = False
        for pindent, pkey in lines[prop_idx + 1 :]:
            if pindent <= prop_indent:
                break
            if _DEFAULT_RE.match(pkey):
                has_default = True
                break
        if has_default:
            found.append(prop)

    return found


if __name__ == "__main__":
    text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
    bad = connection_defaults(text)
    if bad:
        print("publish recusado — x-ref: connection com default:", ", ".join(bad))
        sys.exit(1)
    print("publish_guard: ok")
