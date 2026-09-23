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

# C1: JSON, access_token/client_secret/api_key e Basic também somem
for raw, secret in (
    ('{"token": "abc123", "password": "p4ss"}', "abc123"),
    ("access_token: ghp_abcdefghijklmnop", "ghp_abcdefghijklmnop"),
    ("client_secret=shhh-123", "shhh-123"),
    ("Authorization: Basic YWRtaW46c2VuaGE=", "YWRtaW46c2VuaGE="),
    ("X-Api-Key: sk-123", "sk-123"),
):
    out_c1 = redact(raw)
    assert secret not in out_c1, f"vazou: {secret}\n{out_c1}"
    assert "<removido>" in out_c1, out_c1

# allowed_ops=read_write não é confundido com secret/token/password
assert "allowed_ops=read_write" in redact("allowed_ops=read_write")

# idempotente no caso JSON
out_json = redact('{"token": "abc123", "password": "p4ss"}')
assert redact(out_json) == out_json

# observações do review do #31: telefone sem +55, CNPJ (PIX), senha com espaço
for bad in ("61 99999-8888", "(61) 3333-4444", "12.345.678/0001-90", "12345678000190"):
    out2 = redact(f"contato {bad} fim")
    assert bad not in out2, f"vazou: {bad}\n{out2}"
assert "minha senha longa" not in redact("senha: minha senha longa\npassword = outra com espaco\n")
assert "contato <removido> fim" in redact("contato 61 99999-8888 fim")
assert redact("erro 2026-09-22 às 14:30 code=E1234") == "erro 2026-09-22 às 14:30 code=E1234"

# token do GitHub solto no texto (sem "token=" na frente)
for pat in ("ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", "github_pat_11AAAAAAA0abcdefghijklmnopqrstuvwxyz"):
    out3 = redact(f"usei o PAT {pat} no header")
    assert pat not in out3 and "<removido>" in out3, out3

# token com 11+ dígitos seguidos: a regra do PAT roda antes da de CPF, sem sobrar fragmento
tok = "ghp_abc12345678901234xyzABCDEFGHIJK"
out4 = redact(f"PAT {tok} fim")
assert out4 == "PAT <removido> fim", out4

print("test_gap_redact: ok")
