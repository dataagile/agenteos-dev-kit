"""Teste do parse de erro-texto do MCP (`_parse_tool_error`) — stdlib puro.

Rodar: python3 tests/test_mcp_client_error_parse.py (de dentro da pasta da skill).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import mcp_client as m  # noqa: E402

# código do catálogo vira .code, mensagem limpa (caso visto ao vivo no sandbox-tbc)
e = m._parse_tool_error("not_found: Nenhuma versão publicada de sbx-hello para revisar")
assert e.code == "not_found", e.code
assert str(e) == "Nenhuma versão publicada de sbx-hello para revisar", str(e)

# todos os códigos do catálogo são promovidos
for code in m._KNOWN_CODES:
    assert m._parse_tool_error(f"{code}: x").code == code

# prefixo minúsculo FORA do catálogo NÃO vira code nem trunca a mensagem
e = m._parse_tool_error("yaml: line 4: could not find expected ':'")
assert e.code is None, e.code
assert str(e) == "yaml: line 4: could not find expected ':'", str(e)

# texto sem prefixo algum
e = m._parse_tool_error("tool retornou erro")
assert e.code is None and str(e) == "tool retornou erro"

# mensagem multilinha preservada após o código (re.S)
e = m._parse_tool_error("validation_failed: linha1\nlinha2")
assert e.code == "validation_failed" and str(e) == "linha1\nlinha2"

print("test_mcp_client_error_parse: ok")
