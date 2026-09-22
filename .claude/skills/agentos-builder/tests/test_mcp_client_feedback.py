"""feedback(): valida category/message/reporter localmente e repassa o retorno da tool. Sem rede.

Rodar: python3 tests/test_mcp_client_feedback.py (de dentro da pasta da skill).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import mcp_client as m  # noqa: E402

calls = []
RET = {"status": "ok", "ticket_id": 241, "url": "https://glpi.example/front/ticket.form.php?id=241", "deduplicated": False}
m._call = lambda tool, params: calls.append((tool, params)) or RET
REP = {"reporter_name": "Ana Analista", "reporter_email": "ana@cliente.com.br"}

# chamada mínima válida: reporter obrigatório, retorno repassado inteiro
out = m.feedback("melhoria", "[kit] falta pergunta X", context=REP)
assert out == RET, out
assert calls[-1][0] == "spec.feedback"
assert calls[-1][1]["context"] == REP, calls[-1]

# context inteiro viaja
ctx = {**REP, "slug": "s", "version": "0.1", "tool": "x.y", "kit_version": "0.6.0", "step": "derivacao"}
m.feedback("erro", "[plataforma] tool fora do catálogo", context=ctx)
assert calls[-1][1]["context"] == ctx, calls[-1]

n = len(calls)

# sem context → não chega na rede
try:
    m.feedback("erro", "x")
    raise AssertionError("devia levantar ValueError")
except ValueError as e:
    assert "reporter" in str(e), e
assert len(calls) == n

# reporter vazio → não chega na rede
try:
    m.feedback("erro", "x", context={"reporter_name": " ", "reporter_email": "a@b"})
    raise AssertionError("devia levantar ValueError")
except ValueError:
    pass
assert len(calls) == n

# category inválida
try:
    m.feedback("bug", "x", context=REP)
    raise AssertionError("devia levantar ValueError")
except ValueError:
    pass
assert len(calls) == n

# message vazia
try:
    m.feedback("erro", "   ", context=REP)
    raise AssertionError("devia levantar ValueError")
except ValueError:
    pass
assert len(calls) == n

# message > 4000
try:
    m.feedback("erro", "a" * 4001, context=REP)
    raise AssertionError("devia levantar ValueError")
except ValueError:
    pass
assert len(calls) == n

print("test_mcp_client_feedback: ok")
