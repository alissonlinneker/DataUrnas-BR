"""Metadados de construção do banco (tabela ``metadados``, chave/valor).

Registra fatos sobre como o banco foi gerado que não podem ser deduzidos dos
dados com segurança. O principal é ``verify_hashes``: a ausência de issues C01
só significa "nenhum hash inválido" quando a verificação SHA-512 foi de fato
executada; sem ela, a integridade dos arquivos não foi avaliada.
"""

from __future__ import annotations

from datetime import datetime, timezone

TABELA = "metadados"
CHAVE_VERIFY_HASHES = "verify_hashes"
CHAVE_ATUALIZADO_EM = "atualizado_em"
CHAVE_ORIGEM = "origem"

DDL = f"CREATE TABLE IF NOT EXISTS {TABELA} (chave VARCHAR PRIMARY KEY, valor VARCHAR)"


def bool_para_texto(valor: bool) -> str:
    return "true" if valor else "false"


def texto_para_bool(valor) -> bool | None:
    """Converte o valor gravado em bool; None se ausente ou irreconhecível."""
    if valor is None:
        return None
    texto = str(valor).strip().lower()
    if texto in ("true", "1", "sim", "yes"):
        return True
    if texto in ("false", "0", "nao", "não", "no"):
        return False
    return None


def tabela_existe(conn) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?", [TABELA]
    ).fetchone()
    return bool(row and row[0])


def ler_metadados(conn) -> dict[str, str]:
    """Lê todos os metadados (dicionário vazio se a tabela não existe)."""
    if not tabela_existe(conn):
        return {}
    return {str(k): v for k, v in conn.execute(f"SELECT chave, valor FROM {TABELA}").fetchall()}


def gravar_metadados(conn, valores: dict[str, str]) -> None:
    """Grava (upsert) pares chave/valor, criando a tabela se preciso."""
    conn.execute(DDL)
    for chave, valor in valores.items():
        conn.execute(
            f"INSERT INTO {TABELA} (chave, valor) VALUES (?, ?) "
            "ON CONFLICT (chave) DO UPDATE SET valor = excluded.valor",
            [chave, None if valor is None else str(valor)],
        )


def gravar_verificacao_hashes(conn, verificado: bool, origem: str) -> None:
    """Registra se a verificação de hashes SHA-512 foi executada na construção."""
    gravar_metadados(conn, {
        CHAVE_VERIFY_HASHES: bool_para_texto(verificado),
        CHAVE_ORIGEM: origem,
        CHAVE_ATUALIZADO_EM: datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
