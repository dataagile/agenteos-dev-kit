"""Redação mecânica do pedido técnico antes de `mcp_client.feedback()` (gap.md §4).

O texto vai cru ao chamado do GLPI. Isto remove o que NUNCA pode ir: UUID
(inclui id de conexão e chave PIX aleatória), valor de `default:`, CPF,
valores de token/secret/password/senha/api_key/Bearer/Basic (inclusive em
JSON, qualquer chave cujo nome contenha token/secret/password/senha), e-mail
e telefone (chaves PIX).
Ceiling: nome de host não é removido — cite conexão pelo NOME, não pelo
endereço (gap.md §4).
Ceiling 2: qualquer número de 11 dígitos contíguos é tratado como CPF e removido — cite pedido/chamado/nota com prefixo ou pontuação (ex.: "pedido nº 2026-0922-001"), nunca como 11 dígitos nus.
Stdlib puro.

Uso: python3 scripts/gap_redact.py < pedido.txt
"""
import re
import sys

_R = "<removido>"
_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), _R),
    (re.compile(r"^(\s*default:\s*)(?:\"[^\"]*\"|'[^']*'|[^#\n]*?)(\s*(?:#.*)?)$", re.M), rf"\1{_R}\2"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b"), _R),  # antes de CPF/CNPJ: token com 11+ dígitos seguidos
    (re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), _R),
    (re.compile(r"(?<!\d)\d{11}(?!\d)"), _R),
    (re.compile(r"(?i)\b(bearer|basic)\s+\S+"), rf"\1 {_R}"),
    (re.compile(r"(?i)(\b[\w-]*(?:token|secret|password|senha|api[-_]?key)[\w-]*\"?\s*[:=]\s*\"?)[^\"\s,;}\]]+"), rf"\1{_R}"),
    (re.compile(r"(?im)^(\s*(?:senha|password)\s*[:=]\s*)(?!\").+$"), rf"\1{_R}"),
    (re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"), _R),
    (re.compile(r"(?<!\d)\d{14}(?!\d)"), _R),
    (re.compile(r"(?<![\w+])\(?\d{2}\)?\s?9?\d{4}-\d{4}\b"), _R),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), _R),
    (re.compile(r"\+55\s?\d{2}\s?\d{4,5}-?\d{4}\b"), _R),
]


def redact(text: str) -> str:
    for pat, rep in _RULES:
        text = pat.sub(rep, text)
    return text


if __name__ == "__main__":
    sys.stdout.write(redact(sys.stdin.read()))
