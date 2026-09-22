"""feedback(): valida category/message localmente e monta a chamada certa. Sem rede.

Rodar: python3 tests/test_mcp_client_feedback.py (de dentro da pasta da skill).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import mcp_client as m  # noqa: E402

calls = []
m._call = lambda tool, params: calls.append((tool, params)) or {"ok": True}

# chamada mínima
out = m.feedback("melhoria", "[kit] falta pergunta X")
assert out == {"ok": True}, out
assert calls[-1] == ("spec.feedback", {"category": "melhoria", "message": "[kit] falta pergunta X"}), calls[-1]

# context viaja inteiro
m.feedback("erro", "[plataforma] tool fora do catálogo", context={"slug": "s", "version": "1", "tool": "x.y"})
assert calls[-1][1]["context"] == {"slug": "s", "version": "1", "tool": "x.y"}, calls[-1]

# category inválida não chega na rede
n = len(calls)
try:
    m.feedback("bug", "x")
    raise AssertionError("devia levantar ValueError")
except ValueError:
    pass
assert len(calls) == n

# message vazia não chega na rede
try:
    m.feedback("erro", "   ")
    raise AssertionError("devia levantar ValueError")
except ValueError:
    pass
assert len(calls) == n

# message > 4000 não chega na rede
try:
    m.feedback("erro", "a" * 4001)
    raise AssertionError("devia levantar ValueError")
except ValueError:
    pass
assert len(calls) == n

print("test_mcp_client_feedback: ok")
