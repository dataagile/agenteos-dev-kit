"""gap_redact.redact(): o que não pode ir cru ao chamado some. Sem rede.

Rodar: python3 tests/test_gap_redact.py (de dentro da pasta da skill).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
from gap_redact import redact  # noqa: E402

RAW = """[ambiente] conexão SFTP recusa escrita
passo: Escreve — sftp_op criar
conector: "SFTP Protheus TBC — DEV" (id b744c7bc-3e62-4a58-b85d-492d1bd3190b)
      default: "b744c7bc-3e62-4a58-b85d-492d1bd3190b"   # REMOVER antes de publicar
erro: CONNECTOR_ERROR
cliente informou CPF 123.456.789-09 e também 98765432100
token=abc.DEF-123 password: s3nh@ Authorization: Bearer eyJhbGci
pix do fornecedor: fornecedor@empresa.com.br ou +5561999998888
o que destravaria: liberar allowed_ops=read_write na conexão
"""
out = redact(RAW)

# o que precisa sumir
for bad in (
    "b744c7bc-3e62-4a58-b85d-492d1bd3190b",
    "123.456.789-09", "98765432100",
    "abc.DEF-123", "s3nh@", "eyJhbGci",
    "fornecedor@empresa.com.br", "+5561999998888",
):
    assert bad not in out, f"vazou: {bad}\n{out}"

# o que precisa ficar
for keep in (
    "[ambiente] conexão SFTP recusa escrita",
    'conector: "SFTP Protheus TBC — DEV"',
    "erro: CONNECTOR_ERROR",
    "o que destravaria: liberar allowed_ops=read_write na conexão",
    "REMOVER antes de publicar",
):
    assert keep in out, f"removeu demais: {keep}\n{out}"

# a linha default: mantém a chave, troca o valor
assert 'default: <removido>' in out, out
# marcador único
assert out.count("<removido>") >= 8, out.count("<removido>")
# idempotente
assert redact(out) == out

# ceiling documentado: 11 dígitos nus somem mesmo não sendo CPF; com pontuação ficam
assert "<removido>" in redact("pedido número 20260922001 ficou pendente")
assert "2026-0922-001" in redact("pedido nº 2026-0922-001 ficou pendente")

print("test_gap_redact: ok")
