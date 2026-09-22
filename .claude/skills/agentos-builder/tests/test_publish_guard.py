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

print("test_publish_guard: ok")
