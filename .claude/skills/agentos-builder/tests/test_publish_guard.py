"""publish_guard.connection_defaults(): acha property x-ref: connection com default. Sem rede.

Rodar: python3 tests/test_publish_guard.py (de dentro da pasta da skill).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
from publish_guard import connection_defaults  # noqa: E402

COM_DEFAULT = """
config_schema:
  type: object
  properties:
    connection_sftp_id:
      type: string
      x-ref: connection
      default: "b744c7bc-3e62-4a58-b85d-492d1bd3190b"   # REMOVER antes de publicar
      title: "Conexão SFTP"
    pasta:
      type: string
      default: "entrada"
      title: "Pasta"
nodes: []
"""
assert connection_defaults(COM_DEFAULT) == ["connection_sftp_id"], connection_defaults(COM_DEFAULT)

SEM_DEFAULT = """
config_schema:
  type: object
  properties:
    connection_sftp_id:
      type: string
      x-ref: connection
      title: "Conexão SFTP"
    pasta:
      type: string
      default: "entrada"
nodes: []
"""
assert connection_defaults(SEM_DEFAULT) == [], connection_defaults(SEM_DEFAULT)

DUAS = """
config_schema:
  properties:
    a:
      x-ref: connection
      default: "x"
    b:
      default: "y"
      x-ref: connection
    c:
      x-ref: connection
"""
assert connection_defaults(DUAS) == ["a", "b"], connection_defaults(DUAS)

assert connection_defaults("nodes: []\n") == []

# Bloco `properties:` aninhado (schema de objeto dentro de outro) não pode
# mascarar um sibling top-level — os dois devem ser reportados (review final,
# Important 1: o parser antigo perdia o sibling depois do bloco aninhado).
NESTED = """
config_schema:
  properties:
    grupo:
      type: object
      properties:
        conn:
          type: string
          x-ref: connection
          default: "abc"
    outra:
      type: string
      x-ref: connection
      default: "zzz"
"""
assert connection_defaults(NESTED) == ["conn", "outra"], connection_defaults(NESTED)

# Indentação de 4 espaços — o parser não pode depender de um passo fixo de 2.
QUATRO_ESPACOS = """
config_schema:
    properties:
        conexao:
            type: string
            x-ref: connection
            default: "abc"
"""
assert connection_defaults(QUATRO_ESPACOS) == ["conexao"], connection_defaults(QUATRO_ESPACOS)

# Ceiling conhecido, não garantia: forma flow numa linha só. `x-ref:`/`default:`
# aqui são pedaços da linha `conn: {...}`, nunca linhas próprias, então o guard
# não os vê — passa em silêncio. O kit nunca escreve flow style; documentado no
# docstring de publish_guard.py.
FLOW = """
config_schema:
  properties:
    conn: {x-ref: connection, default: "x"}
nodes: []
"""
assert connection_defaults(FLOW) == [], connection_defaults(FLOW)

print("test_publish_guard: ok")
