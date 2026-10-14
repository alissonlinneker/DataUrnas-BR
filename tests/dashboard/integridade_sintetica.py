"""Conjunto sintético no formato da auditoria de integridade de 2026.

Segue o contrato de ``data/parquet/2026/integridade`` para desenvolver e testar
o painel e o relatório antes de existirem dados reais. Os hashes são calculados
de conteúdos fictícios, então ``sha512 == sha512_assinado`` é verdadeiro de fato.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

TIPOS = [("bu", "bu.dat"), ("rdv", "rdv.dat"), ("log", "log.jez"), ("vota", "vota.vsc"),
         ("busa", "busa.dat"), ("imgbu", "imgbu.dat")]


def _arquivos_secao(uf: str, cd_mun: str, zona: str, secao: str, divergir: bool = False) -> list[dict]:
    linhas = []
    for tipo, sufixo in TIPOS:
        conteudo = f"{uf}-{cd_mun}-{zona}-{secao}-{tipo}".encode()
        sha512 = hashlib.sha512(conteudo).hexdigest()
        assinado = sha512 if tipo in ("bu", "rdv", "log") else None
        if divergir and tipo == "bu":
            assinado = hashlib.sha512(b"outro conteudo").hexdigest()
        linhas.append({
            "uf": uf, "cd_mun": cd_mun, "zona": zona, "secao": secao, "tipo": tipo,
            "nome": f"o00407-{cd_mun}{zona}{secao}-{sufixo}", "tamanho": len(conteudo),
            "md5": hashlib.md5(conteudo).hexdigest(),  # noqa: S324 (catálogo, não segurança)
            "sha256": hashlib.sha256(conteudo).hexdigest(), "sha512": sha512,
            "sha512_assinado": assinado,
            "hash_confere": None if assinado is None else assinado == sha512,
            "token_tse": "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVowMTIzNDU", "data_hora_tse": "04/10/2026 18:05:00",
        })
    return linhas


def _secao(uf, cd_mun, zona, secao, status="ok", arquivos=None, assinatura=True, votos=True):
    arquivos = arquivos or []
    return {
        "uf": uf, "cd_mun": cd_mun, "zona": zona, "secao": secao, "status_secao": status,
        "n_arquivos": len(arquivos),
        "n_hash_confere": sum(a["hash_confere"] is True for a in arquivos),
        "n_hash_diverge": sum(a["hash_confere"] is False for a in arquivos),
        "n_sem_hash": sum(a["hash_confere"] is None for a in arquivos),
        "assinatura_valida": assinatura if status == "ok" else None,
        "assinatura_algoritmo": "ecdsa-with-SHA512" if status == "ok" else None,
        "cert_subject": "CN=Urna 2079451" if status == "ok" else None,
        "cert_issuer": "CN=AC Urna Eletrônica" if status == "ok" else None,
        "cert_serial": "0A1B2C" if status == "ok" else None,
        "cert_sha256": "ab" * 32 if status == "ok" else None,
        "modelo_urna": "UE2020" if status == "ok" else None,
        "motivo": None if status == "ok" else status.replace("_", " "),
        "votos_conferem": votos if status == "ok" else None,
    }


def gerar(pasta: Path, divergente: bool = True, com_secoes: bool = True, arquivo_corrompido: bool = True) -> Path:
    """Grava o conjunto em ``pasta`` (o diretório ``integridade``) e devolve a pasta."""
    pasta.mkdir(parents=True, exist_ok=True)
    plano = [
        ("ac", "01007", "0009", "0001", False),
        ("ac", "01007", "0009", "0002", divergente),
        ("ac", "01120", "0004", "0010", False),
        ("sp", "71072", "0001", "0001", False),
        ("sp", "71072", "0001", "0002", False),
        ("zz", "29998", "0001", "0001", False),
    ]
    por_uf: dict[str, list[dict]] = {}
    secoes = []
    for uf, mun, zona, sec, div in plano:
        arqs = _arquivos_secao(uf, mun, zona, sec, div)
        por_uf.setdefault(uf, []).append(arqs)
        secoes.append(_secao(uf, mun, zona, sec, arquivos=arqs))
    secoes.append(_secao("ac", "01007", "0009", "0003", status="agregada"))
    secoes.append(_secao("zz", "29998", "0001", "0002", status="nao_instalada"))

    pd.DataFrame([a for lista in por_uf["ac"] for a in lista]).to_parquet(pasta / "arquivos_ac.parquet")
    pd.DataFrame([a for lista in por_uf["zz"] for a in lista]).to_parquet(pasta / "arquivos_zz.parquet")
    # SP dividido em partes
    pd.DataFrame(por_uf["sp"][0]).to_parquet(pasta / "arquivos_sp_1.parquet")
    pd.DataFrame(por_uf["sp"][1]).to_parquet(pasta / "arquivos_sp_2.parquet")
    if arquivo_corrompido:
        (pasta / "arquivos_rr.parquet").write_bytes(b"PAR1 em gravacao")
    if com_secoes:
        pd.DataFrame(secoes).to_parquet(pasta / "secoes.parquet")
    (pasta / "resumo.json").write_text(json.dumps({
        "totais": {"secoes": len(secoes)},
        "inicio": "2026-10-13T08:00:00", "atualizado_em": "2026-10-13T10:30:00",
        "divergencias": [],
    }), encoding="utf-8")
    return pasta


def res_uf_sintetico() -> pd.DataFrame:
    """Seções instaladas por UF (forma de ``resultado_uf.parquet``)."""
    return pd.DataFrame({"uf": ["ac", "sp", "zz", "rr"], "secoes_total": [4, 4, 2, 1],
                         "secoes_instaladas": [3, 4, 1, 1]})
