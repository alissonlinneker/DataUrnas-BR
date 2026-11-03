#!/usr/bin/env python3
"""Certificados e assinaturas das urnas no 2º turno de 2026 (pleito 3221).

Lê só arquivos já baixados: as partes versoes-*.parquet do versionamento do
2º turno (colunas uf, cd_mun, zona, secao, tipo, hash, nome, sha512, conteudo),
em um ou mais diretórios. Para cada seção com BU e arquivo de assinatura
(.vsc, tipo "vota" ou "sa"), confere:

  1. SHA-512 do bu.dat (e de outro arquivo guardado que esteja na lista do
     .vsc) igual ao valor assinado dentro do .vsc, nas partes de hardware e
     de software; SHA-512 do próprio conteúdo assinado igual ao hash
     autoassinado;
  2. assinatura de hardware (chave do certificado da urna) sobre o conteúdo
     assinado e sobre o bu.dat; com --todas-fracao, também sobre cada um dos
     arquivos listados, numa amostra determinística (ou em todas as seções);
  3. cadeia do certificado da urna até a AC emissora e acima, com os
     certificados de AC em data/certificados/ac/; validade em 25/10/2026,
     algoritmo, emissor, período, número de série e extensões;
  4. padrões: certificado emitido depois da carga ou perto da eleição, mesmo
     certificado em mais de uma seção, mesmo número interno com certificados
     diferentes entre os turnos, CN diferente do número interno do BU,
     emissor e algoritmo nas seções que fecharam depois de 17:30 (Brasília)
     contra as demais e contra o 1º turno, e a AC URNA com certificado
     publicado vencido em 18/07/2026.

Subcomandos (retomáveis; cada parte de entrada vira uma parte de saída):

  extrair    partes versoes-*.parquet -> <saida>/_partes/extrato/ (leve)
  verificar  extrato -> <saida>/_partes/verif/ (pesado: Ed521 em Python puro;
             pode rodar em outra máquina só com o extrato e as AC)
  analisar   consolida, compara com o 1º turno e com o encerramento e grava
             <saida>/secoes.parquet, <saida>/resumo.json e o relatório
  tudo       os três em sequência

Uso:
  python3 scripts/ele2026/certificados_t2.py tudo --processos 3
  python3 scripts/ele2026/certificados_t2.py extrair --versoes t2=data/versoes/2026/t2/bus/parts
  python3 scripts/ele2026/certificados_t2.py verificar --processos 80 --todas-fracao 1
  python3 scripts/ele2026/certificados_t2.py analisar --relatorio docs/certificados-2turno-2026.md
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import pandas as pd  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from dataurnas.parsers import signature as S  # noqa: E402


def _modulo_certificados():
    p = Path(__file__).resolve().parent / "analisar_certificados.py"
    spec = importlib.util.spec_from_file_location("_analisar_certificados_t2", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AC = _modulo_certificados()

PARQUET = ROOT / "data" / "parquet" / "2026"
VERSOES_PADRAO = [ROOT / "data" / "versoes" / "2026" / "t2" / "bus" / "parts",
                  ROOT / "data" / "versoes" / "2026" / "t2-sseco" / "bus" / "parts"]
SAIDA_PADRAO = PARQUET / "t2" / "certificados"
ENC_PADRAO = PARQUET / "t2" / "encerramento" / "secoes_encerramento.parquet"
T1_CATALOGO = PARQUET / "integridade" / "secoes.parquet"
T1_BU = PARQUET / "secoes_2026.parquet"
T1_AMOSTRA = PARQUET / "integridade" / "certificados.parquet"
AC_PADRAO = ROOT / "data" / "certificados" / "ac"
RELATORIO_PADRAO = ROOT / "docs" / "certificados-2turno-2026.md"

DIA_T2 = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
DIA_T1 = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
BSB = timezone(timedelta(hours=-3))
LIMITE_TARDE_MIN = 30  # minutos depois das 17h de Brasília
CHAVE = ["uf", "cd_mun", "zona", "secao"]
TIPOS_VSC = ("vota", "sa")
TIPOS_BU = ("bu", "busa")
MAX_LISTA = 200

# Extensões esperadas num certificado de urna (as demais são registradas
# como incomuns).
EXT_PADRAO = {
    "2.5.29.19": "basicConstraints", "2.5.29.15": "keyUsage",
    "2.5.29.14": "subjectKeyIdentifier", "2.5.29.35": "authorityKeyIdentifier",
    "2.5.29.31": "cRLDistributionPoints", "2.5.29.32": "certificatePolicies",
}

SCHEMA_VSC = pa.schema([
    ("uf", pa.string()), ("cd_mun", pa.string()), ("zona", pa.string()),
    ("secao", pa.string()), ("hash", pa.string()), ("tipo", pa.string()),
    ("nome", pa.string()), ("coletado_em", pa.string()), ("origem", pa.string()),
    ("parte", pa.string()), ("tamanho", pa.int64()), ("sha512_vsc", pa.string()),
    ("sha512_coleta_confere", pa.bool_()), ("erro", pa.string()),
    ("modelo_cod", pa.int64()), ("modelo", pa.string()),
    ("hw_alg", pa.string()), ("hw_alg_hash", pa.string()), ("hw_data_hora", pa.string()),
    ("hw_usuario", pa.string()), ("hw_conjunto_chave", pa.string()),
    ("sw_alg", pa.string()), ("sw_data_hora", pa.string()), ("sw_usuario", pa.string()),
    ("sw_serial", pa.int64()), ("sw_conjunto_chave", pa.string()),
    ("hw_conteudo_ok", pa.bool_()), ("sw_conteudo_ok", pa.bool_()),
    ("n_arquivos_hw", pa.int64()), ("n_arquivos_sw", pa.int64()),
    ("sw_hw_hashes_iguais", pa.bool_()), ("arquivos_divergentes_sw_hw", pa.string()),
    ("bu_nome_vsc", pa.string()), ("bu_hash_hw", pa.string()), ("bu_hash_sw", pa.string()),
    ("cert_sha256", pa.string()), ("cert_subject", pa.string()), ("cn", pa.string()),
    ("cert_issuer", pa.string()), ("emissor", pa.string()), ("serial", pa.string()),
    ("versao_cert", pa.string()), ("not_before", pa.timestamp("us", tz="UTC")),
    ("not_after", pa.timestamp("us", tz="UTC")), ("oid_chave", pa.string()),
    ("alg_chave", pa.string()), ("curva", pa.string()), ("oid_assinatura_cert", pa.string()),
    ("chave_sha256", pa.string()), ("ski", pa.string()), ("aki", pa.string()),
    ("extensoes", pa.string()), ("extensoes_incomuns", pa.string()),
    ("ext_criticas", pa.string()), ("basic_ca", pa.bool_()), ("key_usage", pa.string()),
    ("cn_confere_usuario", pa.bool_()),
    # carga útil da verificação (lida só por "verificar")
    ("cert_der", pa.binary()), ("hw_hash", pa.binary()), ("hw_assinatura", pa.binary()),
    ("arq_nomes", pa.list_(pa.string())), ("arq_hashes", pa.list_(pa.binary())),
    ("arq_assinaturas", pa.list_(pa.binary())),
])
PAYLOAD = ["cert_der", "hw_hash", "hw_assinatura", "arq_nomes", "arq_hashes",
           "arq_assinaturas"]

SCHEMA_BU = pa.schema([
    ("uf", pa.string()), ("cd_mun", pa.string()), ("zona", pa.string()),
    ("secao", pa.string()), ("hash", pa.string()), ("tipo", pa.string()),
    ("nome", pa.string()), ("coletado_em", pa.string()), ("origem", pa.string()),
    ("parte", pa.string()), ("tamanho", pa.int64()), ("sha512_bu", pa.string()),
    ("sha512_coleta_confere", pa.bool_()), ("erro_bu", pa.string()),
    ("numero_interno", pa.int64()), ("tipo_urna", pa.string()),
    ("data_hora_carga", pa.string()), ("codigo_carga", pa.string()),
    ("gerador_midia", pa.string()), ("data_hora_emissao", pa.string()),
    ("encerramento_bu", pa.string()),
])

SCHEMA_VERIF = pa.schema([
    ("uf", pa.string()), ("cd_mun", pa.string()), ("zona", pa.string()),
    ("secao", pa.string()), ("hash", pa.string()), ("sha512_vsc", pa.string()),
    ("assinatura_algoritmo", pa.string()), ("assinatura_conteudo_ok", pa.bool_()),
    ("assinatura_bu_ok", pa.bool_()), ("todas_verificadas", pa.bool_()),
    ("n_assinaturas_ok", pa.int64()), ("n_assinaturas_falha", pa.int64()),
    ("arquivos_assinatura_invalida", pa.string()), ("cadeia_ok", pa.bool_()),
    ("cadeia_desc", pa.string()), ("ac_cn", pa.string()), ("ac_sha256", pa.string()),
    ("ac_not_before", pa.timestamp("us", tz="UTC")),
    ("ac_not_after", pa.timestamp("us", tz="UTC")), ("nivel_cadeia", pa.string()),
    ("cadeia_caminho", pa.string()), ("erro_verif", pa.string()),
])


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

def sorteio(uf: str, mun: str, zona: str, secao: str) -> float:
    """Número em [0, 1) determinístico pela chave da seção (mesmo critério do
    --fracao de analisar_certificados.py)."""
    k = "/".join((uf, mun, zona, secao)).encode()
    return int.from_bytes(hashlib.sha256(k).digest()[:4], "big") / 2**32


def data_je(s) -> Optional[datetime]:
    """'YYYYMMDDThhmmss' (hora local da urna) -> datetime ingênuo, ou None."""
    if not isinstance(s, str) or len(s) < 15:
        return None
    try:
        return datetime.strptime(s[:15], "%Y%m%dT%H%M%S")
    except ValueError:
        return None


def _bool(cond: pd.Series, indeterminado: pd.Series) -> pd.Series:
    """Série boolean com NA onde a comparação não se aplica."""
    out = cond.fillna(False).astype("boolean")
    out[indeterminado.fillna(True).astype(bool)] = pd.NA
    return out


def _unwrap(v):
    while isinstance(v, tuple) and len(v) == 2:
        v = v[1]
    return v


def _tabela(linhas: list[dict], schema: pa.Schema) -> pa.Table:
    cols = {f.name: [r.get(f.name) for r in linhas] for f in schema}
    return pa.table(cols, schema=schema)


def _gravar(t: pa.Table, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".tmp")
    pq.write_table(t, tmp)
    tmp.replace(destino)  # parte só aparece completa


def _atual(destino: Path, fonte: Path) -> bool:
    return destino.exists() and destino.stat().st_mtime >= fonte.stat().st_mtime


# ---------------------------------------------------------------------------
# extrair
# ---------------------------------------------------------------------------

def listar_partes(dirs: list[tuple[str, Path]]) -> list[tuple[str, Path]]:
    """(rótulo, parte) de cada versoes-*.parquet que tem a coluna conteudo
    (as partes de votos, com outro esquema, ficam de fora)."""
    out = []
    for rot, d in dirs:
        for p in sorted(Path(d).glob("versoes-*.parquet")):
            try:
                if "conteudo" in pq.read_schema(p).names:
                    out.append((rot, p))
            except Exception:  # noqa: BLE001 - parte em gravação
                continue
    return out


def linha_bu(r: dict) -> dict:
    from dataurnas.models import SpecVersion
    from dataurnas.parsers.asn1_helper import decode_envelope

    raw = r["conteudo"]
    sha = hashlib.sha512(raw).hexdigest()
    col = (r.get("sha512") or "").lower()
    out = {"sha512_bu": sha, "sha512_coleta_confere": (col == sha) if col else None}
    try:
        try:
            _, bu = decode_envelope(raw, "EntidadeBoletimUrna", SpecVersion.V2)
        except Exception:  # noqa: BLE001
            _, bu = decode_envelope(raw, "EntidadeBoletimUrna", SpecVersion.V1)
        urna = bu.get("urna") or {}
        carga = ((urna.get("correspondenciaResultado") or {}).get("carga")) or {}
        ger = carga.get("identificadorGeradorMidia") or {}
        tu = urna.get("tipoUrna")
        if isinstance(tu, tuple):
            tu = tu[0] if isinstance(tu[0], str) else str(tu[1])
        sa = _unwrap(bu.get("dadosSecaoSA"))
        out.update({
            "numero_interno": carga.get("numeroInternoUrna"),
            "tipo_urna": str(tu) if tu is not None else None,
            "data_hora_carga": carga.get("dataHoraCarga"),
            "codigo_carga": str(carga["codigoCarga"]) if carga.get("codigoCarga") else None,
            "gerador_midia": ger.get("nome") if isinstance(ger, dict) else None,
            "data_hora_emissao": bu.get("dataHoraEmissao"),
            "encerramento_bu": sa.get("dataHoraEncerramento") if isinstance(sa, dict) else None,
        })
    except Exception as e:  # noqa: BLE001 - BU ilegível vira linha com erro
        out["erro_bu"] = f"BU ilegível: {e}"[:200]
    return out


def _extensoes(c) -> dict:
    from cryptography import x509
    nomes, incomuns, criticas = [], [], []
    basic_ca, ku = None, None
    for e in c.extensions:
        oid = e.oid.dotted_string
        nome = EXT_PADRAO.get(oid) or getattr(e.oid, "_name", None) or oid
        nomes.append(nome)
        if oid not in EXT_PADRAO:
            incomuns.append(f"{nome} ({oid})")
        if e.critical:
            criticas.append(nome)
        if isinstance(e.value, x509.BasicConstraints):
            basic_ca = bool(e.value.ca)
        if isinstance(e.value, x509.KeyUsage):
            v = e.value
            usos = [n for n in ("digital_signature", "content_commitment", "key_encipherment",
                                "data_encipherment", "key_agreement", "key_cert_sign",
                                "crl_sign") if getattr(v, n)]
            ku = ",".join(usos)
    return {"extensoes": ",".join(sorted(nomes)), "extensoes_incomuns": ";".join(incomuns) or None,
            "ext_criticas": ",".join(sorted(criticas)) or None, "basic_ca": basic_ca,
            "key_usage": ku}


def linha_vsc(r: dict) -> dict:
    from dataurnas.downloader.ele2026 import MODELOS

    raw = r["conteudo"]
    sha = hashlib.sha512(raw).hexdigest()
    col = (r.get("sha512") or "").lower()
    out: dict = {"sha512_vsc": sha, "sha512_coleta_confere": (col == sha) if col else None}
    try:
        v = S.parse_vsc(raw)
    except Exception as e:  # noqa: BLE001
        out["erro"] = f"vsc ilegível: {e}"[:200]
        return out
    sw, hw = v["sw"], v["hw"]
    hs_hw = {a["nome"]: a["hash"] for a in hw["arquivos"]}
    hs_sw = {a["nome"]: a["hash"] for a in sw["arquivos"]}
    div = sorted(n for n in set(hs_sw) & set(hs_hw) if hs_sw[n] != hs_hw[n])
    so_um = sorted(set(hs_sw) ^ set(hs_hw))
    bu_nome = next((n for n in hs_hw if n.endswith(("-bu.dat", "-busa.dat"))), None) or \
        next((n for n in hs_sw if n.endswith(("-bu.dat", "-busa.dat"))), None)
    usuario = f"{hw['usuario']}{hw['serial']:08d}" if hw["usuario"].upper() == "UEAO" \
        else hw["usuario"]
    out.update({
        "modelo_cod": v["modelo_cod"],
        "modelo": MODELOS.get(v["modelo_cod"], str(v["modelo_cod"])),
        "hw_alg": hw["algoritmo_assinatura"], "hw_alg_hash": hw["algoritmo_hash"],
        "hw_data_hora": hw["data_hora"], "hw_usuario": usuario,
        "hw_conjunto_chave": hw["conjunto_chave"],
        "sw_alg": sw["algoritmo_assinatura"], "sw_data_hora": sw["data_hora"],
        "sw_usuario": sw["usuario"], "sw_serial": sw["serial"],
        "sw_conjunto_chave": sw["conjunto_chave"],
        "hw_conteudo_ok": hashlib.sha512(hw["conteudo"]).digest() == hw["hash"],
        "sw_conteudo_ok": hashlib.sha512(sw["conteudo"]).digest() == sw["hash"],
        "n_arquivos_hw": len(hw["arquivos"]), "n_arquivos_sw": len(sw["arquivos"]),
        "sw_hw_hashes_iguais": not div and not so_um,
        "arquivos_divergentes_sw_hw": ";".join(div + [f"só numa parte: {n}" for n in so_um])
        or None,
        "bu_nome_vsc": bu_nome,
        "bu_hash_hw": hs_hw[bu_nome].hex() if bu_nome in hs_hw else None,
        "bu_hash_sw": hs_sw[bu_nome].hex() if bu_nome in hs_sw else None,
        "hw_hash": hw["hash"], "hw_assinatura": hw["assinatura"],
        "arq_nomes": [a["nome"] for a in hw["arquivos"]],
        "arq_hashes": [a["hash"] for a in hw["arquivos"]],
        "arq_assinaturas": [a["assinatura"] for a in hw["arquivos"]],
    })
    if not hw["certificado"]:
        out["erro"] = "sem certificado na parte de hardware"
        return out
    try:
        i = S.info_certificado(hw["certificado"])
    except Exception as e:  # noqa: BLE001
        out["erro"] = f"certificado ilegível: {e}"[:200]
        return out
    c = i["_cert"]
    curva = None
    alg = AC.familia_alg(i["oid_chave"])
    if alg == "Ed521":
        curva = "E-521"
    elif alg == "ECDSA":
        try:
            curva = c.public_key().curve.name
        except Exception:  # noqa: BLE001
            curva = "?"
    out.update({
        "cert_sha256": i["sha256"], "cert_subject": i["subject"], "cn": i["cn"],
        "cert_issuer": i["issuer"], "emissor": AC.cn_de_subject(i["issuer"]) or i["issuer"],
        "serial": i["serial"], "versao_cert": c.version.name,
        "not_before": c.not_valid_before_utc, "not_after": c.not_valid_after_utc,
        "oid_chave": i["oid_chave"], "alg_chave": alg, "curva": curva,
        "oid_assinatura_cert": i["oid_assinatura"],
        "chave_sha256": hashlib.sha256(AC._spki_der(i["_der"])).hexdigest(),
        "ski": AC._ski(c), "aki": AC._aki(c),
        "cn_confere_usuario": (i["cn"] or "").upper() == usuario.upper(),
        "cert_der": i["_der"], **_extensoes(c),
    })
    return out


def extrair_parte(rotulo: str, caminho: str) -> tuple[list[dict], list[dict]]:
    """(linhas .vsc, linhas BU) de uma parte versoes-*.parquet."""
    cols = CHAVE + ["tipo", "hash", "nome", "sha512", "tamanho", "conteudo", "coletado_em"]
    t = pq.read_table(caminho, columns=cols,
                      filters=[("tipo", "in", list(TIPOS_VSC + TIPOS_BU))])
    vscs, bus = [], []
    parte = Path(caminho).name
    for r in t.to_pylist():
        if r["conteudo"] is None:
            continue
        base = {k: r[k] for k in CHAVE + ["hash", "tipo", "nome", "coletado_em"]}
        base.update(origem=rotulo, parte=parte, tamanho=r["tamanho"])
        if r["tipo"] in TIPOS_VSC:
            vscs.append({**base, **linha_vsc(r)})
        else:
            bus.append({**base, **linha_bu(r)})
    return vscs, bus


def _nome_extrato(rotulo: str, parte: Path) -> str:
    return f"{rotulo}__{parte.stem}"


def _job_extrair(rotulo: str, caminho: str, destino: str) -> tuple[int, int]:
    vscs, bus = extrair_parte(rotulo, caminho)
    d = Path(destino)
    _gravar(_tabela(bus, SCHEMA_BU), d.with_name(d.name + ".bu.parquet"))
    _gravar(_tabela(vscs, SCHEMA_VSC), d.with_name(d.name + ".vsc.parquet"))
    return len(vscs), len(bus)


def _pool(processos: int):
    from concurrent.futures import ProcessPoolExecutor
    return ProcessPoolExecutor(processos, initializer=_baixar_prioridade)


def _baixar_prioridade() -> None:
    try:
        os.nice(20 - os.nice(0))
    except OSError:
        pass


def _executar(jobs: list[tuple], func, processos: int, rotulo: str, log=print) -> list:
    """Roda func(*job) em sequência (processos <= 0) ou num pool."""
    res, t0 = [], time.time()
    if processos <= 0:
        for j in jobs:
            res.append(func(*j))
        return res
    from concurrent.futures import as_completed
    with _pool(processos) as ex:
        fut = {ex.submit(func, *j): j for j in jobs}
        for n, f in enumerate(as_completed(fut), 1):
            try:
                res.append(f.result())
            except Exception as e:  # noqa: BLE001 - parte com falha fica para a próxima
                log(f"{rotulo}: falha em {fut[f][1]}: {e}")
            if n % 10 == 0 or n == len(jobs):
                log(f"{rotulo}: {n}/{len(jobs)} partes ({time.time() - t0:.0f} s)")
    return res


def extrair(dirs: list[tuple[str, Path]], saida: Path, processos: int = 0, log=print) -> dict:
    destino = saida / "_partes" / "extrato"
    partes = listar_partes(dirs)
    jobs = []
    for rot, p in partes:
        d = destino / _nome_extrato(rot, p)
        if _atual(d.with_name(d.name + ".vsc.parquet"), p) and \
                _atual(d.with_name(d.name + ".bu.parquet"), p):
            continue
        jobs.append((rot, str(p), str(d)))
    log(f"extrair: {len(partes)} partes com conteúdo; pendentes: {len(jobs)}")
    res = _executar(jobs, _job_extrair, processos, "extrair", log)
    return {"partes": len(partes), "processadas": len(res),
            "vsc": sum(a for a, _ in res), "bu": sum(b for _, b in res)}


# ---------------------------------------------------------------------------
# verificar
# ---------------------------------------------------------------------------

_ACS: list = []
_NIVEL: dict = {}


def _init_acs(ac_dir: Optional[str]) -> None:
    if not _ACS and ac_dir and Path(ac_dir).exists():
        _ACS[:] = AC.carregar_acs(Path(ac_dir))


def verificar_linha(r: dict, todas_fracao: float = 0.0) -> dict:
    """Assinaturas (conteúdo, bu.dat e, na amostra, todos os arquivos) e cadeia."""
    from cryptography.hazmat.primitives import serialization

    out = {k: r[k] for k in CHAVE + ["hash", "sha512_vsc"]}
    if not r.get("cert_der"):
        out["erro_verif"] = r.get("erro") or "sem certificado"
        return out
    try:
        info = S.info_certificado(r["cert_der"])
    except Exception as e:  # noqa: BLE001
        out["erro_verif"] = f"certificado ilegível: {e}"[:200]
        return out
    verif, alg = S._verificador_hw(info, r["hw_alg"])
    out["assinatura_algoritmo"] = alg
    if verif is None:
        out["erro_verif"] = alg
    else:
        out["assinatura_conteudo_ok"] = bool(verif(r["hw_hash"], r["hw_assinatura"]))
        nomes = r["arq_nomes"] or []
        bu = r.get("bu_nome_vsc")
        todas = todas_fracao >= 1 or (todas_fracao > 0 and sorteio(
            r["uf"], r["cd_mun"], r["zona"], r["secao"]) < todas_fracao)
        ok = falha = 0
        invalidas = []
        for n, h, s in zip(nomes, r["arq_hashes"], r["arq_assinaturas"], strict=True):
            if not todas and n != bu:
                continue
            v = bool(verif(h, s))
            ok, falha = ok + v, falha + (not v)
            if not v:
                invalidas.append(n)
            if n == bu:
                out["assinatura_bu_ok"] = v
        out.update(todas_verificadas=todas, n_assinaturas_ok=ok, n_assinaturas_falha=falha,
                   arquivos_assinatura_invalida=";".join(invalidas) or None)
    c = info["_cert"]
    if not _ACS:
        out.update(cadeia_ok=None, cadeia_desc="AC emissora ausente")
        return out
    ok, desc, ac = AC.validar_cadeia({"_cert": c, "aki": AC._aki(c)}, _ACS)
    out.update(cadeia_ok=ok, cadeia_desc=desc)
    if ac is not None:
        k = hashlib.sha256(ac.public_bytes(serialization.Encoding.DER)).hexdigest()
        if k not in _NIVEL:
            _NIVEL[k] = AC.subir_cadeia(ac, _ACS)
        nivel, caminho = _NIVEL[k]
        out.update(ac_cn=caminho[0], ac_sha256=k, ac_not_before=ac.not_valid_before_utc,
                   ac_not_after=ac.not_valid_after_utc, nivel_cadeia=nivel,
                   cadeia_caminho=" > ".join([info["cn"] or "?"] + caminho))
    return out


def _job_verificar(caminho: str, destino: str, ac_dir: Optional[str],
                   todas_fracao: float) -> int:
    _init_acs(ac_dir)
    cols = CHAVE + ["hash", "sha512_vsc", "erro", "hw_alg", "bu_nome_vsc"] + PAYLOAD
    linhas = [verificar_linha(r, todas_fracao)
              for r in pq.read_table(caminho, columns=cols).to_pylist()]
    _gravar(_tabela(linhas, SCHEMA_VERIF), Path(destino))
    return len(linhas)


def verificar(saida: Path, ac_dir: Optional[Path], processos: int = 0,
              todas_fracao: float = 0.0, log=print) -> dict:
    ext = saida / "_partes" / "extrato"
    dest = saida / "_partes" / "verif"
    jobs = []
    entradas = sorted(ext.glob("*.vsc.parquet"))
    for p in entradas:
        d = dest / p.name.replace(".vsc.parquet", ".verif.parquet")
        if not _atual(d, p):
            jobs.append((str(p), str(d), str(ac_dir) if ac_dir else None, todas_fracao))
    log(f"verificar: {len(entradas)} extratos; pendentes: {len(jobs)}")
    if processos <= 0:
        _init_acs(str(ac_dir) if ac_dir else None)
    res = _executar(jobs, _job_verificar, processos, "verificar", log)
    return {"extratos": len(entradas), "processados": len(res), "linhas": sum(res)}


# ---------------------------------------------------------------------------
# analisar
# ---------------------------------------------------------------------------

def _ler(glob_dir: Path, padrao: str, colunas: Optional[list[str]] = None,
         schema: Optional[pa.Schema] = None) -> pd.DataFrame:
    frames = []
    for p in sorted(glob_dir.glob(padrao)):
        try:
            frames.append(pq.read_table(p, columns=colunas).to_pandas())
        except Exception:  # noqa: BLE001 - parte em gravação
            continue
    if not frames:
        nomes = colunas or [f.name for f in (schema or [])]
        return pd.DataFrame(columns=nomes)
    return pd.concat(frames, ignore_index=True)


def _ultima(df: pd.DataFrame, chave: list[str]) -> pd.DataFrame:
    return df.sort_values("coletado_em", kind="stable").drop_duplicates(chave, keep="last")


def sid(df: pd.DataFrame) -> pd.Series:
    return df["uf"].str.upper() + "/" + df["cd_mun"] + "/" + df["zona"] + "/" + df["secao"]


def carregar_t1(catalogo: Path = T1_CATALOGO, bu: Path = T1_BU) -> pd.DataFrame:
    """Uma linha por seção do 1º turno: certificado (catálogo da integridade)
    e número interno da carga (secoes_2026.parquet)."""
    if not catalogo.exists():
        return pd.DataFrame(columns=CHAVE)
    cols = CHAVE + ["cert_sha256", "cert_subject", "cert_issuer", "cert_serial",
                    "assinatura_valida", "assinatura_algoritmo", "modelo_urna"]
    t1 = pd.read_parquet(catalogo, columns=cols)
    t1 = t1[t1["cert_sha256"].notna() & (t1["cert_sha256"] != "")].copy()
    t1["t1_cn"] = t1["cert_subject"].map(AC.cn_de_subject)
    t1["t1_emissor"] = t1["cert_issuer"].map(AC.cn_de_subject)
    t1["t1_alg"] = t1["assinatura_algoritmo"].map(AC.familia_alg)
    t1 = t1.rename(columns={"cert_sha256": "t1_cert_sha256", "cert_serial": "t1_serial",
                            "modelo_urna": "t1_modelo", "assinatura_valida": "t1_assinatura_valida"})
    t1 = t1.drop(columns=["cert_subject", "cert_issuer", "assinatura_algoritmo"])
    if bu.exists():
        b = pd.read_parquet(bu, columns=CHAVE + ["numero_interno_urna"])
        t1 = t1.merge(b.rename(columns={"numero_interno_urna": "t1_numero_interno"}),
                      on=CHAVE, how="left")
    return t1.drop_duplicates(CHAVE)


def carregar_encerramento(path: Path = ENC_PADRAO) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=CHAVE + ["minutos_apos_17h_bsb", "encerramento_bsb"])
    e = pd.read_parquet(path, columns=CHAVE + ["minutos_apos_17h_bsb", "encerramento_bsb",
                                               "faixa"])
    return e.drop_duplicates(CHAVE, keep="last")


def consolidar(saida: Path, t1: Optional[pd.DataFrame] = None,
               enc: Optional[pd.DataFrame] = None, dia: datetime = DIA_T2) -> pd.DataFrame:
    """Uma linha por seção: o par (BU, .vsc) de mesmo hash mais recente."""
    ext = saida / "_partes" / "extrato"
    cols_vsc = [f.name for f in SCHEMA_VSC if f.name not in PAYLOAD]
    vsc = _ler(ext, "*.vsc.parquet", cols_vsc, SCHEMA_VSC)
    bu = _ler(ext, "*.bu.parquet", None, SCHEMA_BU)
    ver = _ler(saida / "_partes" / "verif", "*.verif.parquet", None, SCHEMA_VERIF)
    # versões repetidas entre coletas/diretórios: o mesmo arquivo conta uma vez
    conflito_bu = bu.groupby(CHAVE + ["hash"])["sha512_bu"].nunique()
    conflito_vsc = vsc.groupby(CHAVE + ["hash"])["sha512_vsc"].nunique()
    bu = _ultima(bu, CHAVE + ["hash"]).merge(
        conflito_bu.rename("n_conteudos_bu").reset_index(), on=CHAVE + ["hash"], how="left")
    vsc = _ultima(vsc, CHAVE + ["hash"]).merge(
        conflito_vsc.rename("n_conteudos_vsc").reset_index(), on=CHAVE + ["hash"], how="left")
    ver = ver.drop_duplicates(CHAVE + ["hash", "sha512_vsc"], keep="last")
    vsc = vsc.merge(ver, on=CHAVE + ["hash", "sha512_vsc"], how="left")
    bu = bu.rename(columns={c: f"bu_{c}" for c in ["tipo", "nome", "coletado_em", "origem",
                                                   "parte", "tamanho", "sha512_coleta_confere"]})
    vsc = vsc.rename(columns={"tipo": "vsc_tipo", "nome": "vsc_nome",
                              "coletado_em": "vsc_coletado_em", "origem": "vsc_origem",
                              "parte": "vsc_parte", "tamanho": "vsc_tamanho",
                              "sha512_coleta_confere": "vsc_sha512_coleta_confere"})
    par = bu.merge(vsc, on=CHAVE + ["hash"], how="outer", indicator=True)
    par["tem_bu"] = par["_merge"].isin(["both", "left_only"])
    par["tem_vsc"] = par["_merge"].isin(["both", "right_only"])
    par["par_completo"] = par["_merge"] == "both"
    par["_ord"] = par["par_completo"].astype(int)
    par["_quando"] = par["vsc_coletado_em"].fillna(par["bu_coletado_em"])
    n_hash = par.groupby(CHAVE)["hash"].nunique().rename("n_hashes")
    df = par.sort_values(["_ord", "_quando"], kind="stable").drop_duplicates(CHAVE, keep="last")
    df = df.drop(columns=["_merge", "_ord", "_quando"]).merge(n_hash.reset_index(), on=CHAVE)
    df = df.reset_index(drop=True)
    df["secao_id"] = sid(df)

    # 1. hash do bu.dat x valor assinado
    df["bu_hash_confere"] = pd.Series(pd.NA, index=df.index, dtype="boolean")
    m = df["par_completo"] & df["bu_hash_hw"].notna()
    df.loc[m, "bu_hash_confere"] = (df.loc[m, "sha512_bu"] == df.loc[m, "bu_hash_hw"]) & (
        df.loc[m, "bu_hash_sw"].isna() | (df.loc[m, "sha512_bu"] == df.loc[m, "bu_hash_sw"]))
    df["bu_nome_confere"] = pd.Series(pd.NA, index=df.index, dtype="boolean")
    m = df["par_completo"]
    df.loc[m, "bu_nome_confere"] = df.loc[m, "bu_nome"] == df.loc[m, "bu_nome_vsc"]

    # 3. validade e datas
    df["valido_no_dia"] = _bool((df["not_before"] <= dia) & (df["not_after"] >= dia),
                                df["not_before"].isna())
    df["ac_valida_no_dia"] = _bool((df["ac_not_before"] <= dia) & (df["ac_not_after"] >= dia),
                                   df["ac_not_after"].isna())
    df["emitido_na_validade_da_ac"] = _bool(
        (df["not_before"] >= df["ac_not_before"]) & (df["not_before"] <= df["ac_not_after"]),
        df["ac_not_after"].isna() | df["not_before"].isna())
    carga = df["data_hora_carga"].map(data_je)
    df["carga_utc"] = pd.to_datetime(carga.map(
        lambda d: d.replace(tzinfo=BSB) if d else None), utc=True)
    df["emitido_apos_carga"] = _bool(df["not_before"] > df["carga_utc"],
                                     df["carga_utc"].isna() | df["not_before"].isna())
    df["dias_emissao_ate_eleicao"] = (dia - df["not_before"]).dt.total_seconds() / 86400
    assin = df["hw_data_hora"].map(data_je)
    df["assinatura_utc"] = pd.to_datetime(assin.map(
        lambda d: d.replace(tzinfo=BSB) if d else None), utc=True)
    # tolerância de 3 h: a hora gravada é a local da urna (UTC-2 a UTC-5)
    df["cert_valido_na_assinatura"] = _bool(
        (df["not_before"] <= df["assinatura_utc"] + pd.Timedelta(hours=3))
        & (df["not_after"] >= df["assinatura_utc"] - pd.Timedelta(hours=3)),
        df["assinatura_utc"].isna() | df["not_before"].isna())

    # 4. identidade
    df["cn_num"] = df["cn"].map(lambda v: AC.numero_de_cn(v) if isinstance(v, str) else None)
    df["cn_igual_numero_interno"] = pd.Series(pd.NA, index=df.index, dtype="boolean")
    m = df["cn_num"].notna() & df["numero_interno"].notna()
    df.loc[m, "cn_igual_numero_interno"] = df.loc[m, "cn_num"].astype("int64") == \
        df.loc[m, "numero_interno"].astype("int64")

    if enc is not None and len(enc):
        df = df.merge(enc, on=CHAVE, how="left")
        df["fechou_tarde"] = _bool(df["minutos_apos_17h_bsb"] > LIMITE_TARDE_MIN,
                                   df["minutos_apos_17h_bsb"].isna())
    else:
        df["minutos_apos_17h_bsb"] = pd.NA
        df["fechou_tarde"] = pd.NA
    if t1 is not None and len(t1):
        df = df.merge(t1, on=CHAVE, how="left")
        tem = df["t1_cert_sha256"].notna() & df["cert_sha256"].notna()
        df["mesmo_cert_t1"] = pd.Series(pd.NA, index=df.index, dtype="boolean")
        df.loc[tem, "mesmo_cert_t1"] = df.loc[tem, "cert_sha256"] == df.loc[tem, "t1_cert_sha256"]
        df["mesmo_cn_t1"] = pd.Series(pd.NA, index=df.index, dtype="boolean")
        df.loc[tem, "mesmo_cn_t1"] = df.loc[tem, "cn"].str.upper() == \
            df.loc[tem, "t1_cn"].str.upper()
    return df


def falhas(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Seções com divergência de hash, assinatura inválida ou cadeia quebrada."""
    def f(col):
        return df[df[col].astype("boolean").fillna(True).eq(False)] if col in df else df.iloc[0:0]
    out = {
        "bu_hash_diverge": f("bu_hash_confere"),
        "bu_nome_diverge": f("bu_nome_confere"),
        "conteudo_hw_hash_diverge": f("hw_conteudo_ok"),
        "conteudo_sw_hash_diverge": f("sw_conteudo_ok"),
        "hashes_sw_hw_divergem": f("sw_hw_hashes_iguais"),
        "assinatura_conteudo_invalida": f("assinatura_conteudo_ok"),
        "assinatura_bu_invalida": f("assinatura_bu_ok"),
        "assinatura_arquivo_invalida": df[df["n_assinaturas_falha"].fillna(0) > 0],
        "cadeia_invalida": f("cadeia_ok"),
        "vsc_ilegivel": df[df["tem_vsc"] & df["erro"].notna()],
        "bu_ilegivel": df[df["tem_bu"] & df["erro_bu"].notna()],
        "sha512_coleta_diverge": df[df["bu_sha512_coleta_confere"].astype("boolean")
                                    .fillna(True).eq(False)
                                    | df["vsc_sha512_coleta_confere"].astype("boolean")
                                    .fillna(True).eq(False)],
    }
    return out


def _cont(s: pd.Series) -> dict:
    def rot(v):
        return "indeterminado" if v is None or v is pd.NA or (
            isinstance(v, float) and pd.isna(v)) else str(v)
    return {k: int(v) for k, v in s.astype(object).map(rot).value_counts().items()}


def _lista(df: pd.DataFrame, cols: list[str], n: int = MAX_LISTA) -> list[dict]:
    cols = [c for c in cols if c in df.columns]
    out = []
    for r in df.head(n)[cols].to_dict("records"):
        out.append({k: (None if v is pd.NA or (isinstance(v, float) and pd.isna(v))
                        else (v.isoformat() if hasattr(v, "isoformat") else v))
                    for k, v in r.items()})
    return out


def distribuicao(df: pd.DataFrame, em: str = "emissor", alg: str = "alg_chave",
                 mod: str = "modelo") -> list[dict]:
    g = df.groupby([mod, em, alg], dropna=False).size().reset_index(name="secoes")
    tot = max(1, int(g["secoes"].sum()))
    return [{"modelo": str(r[mod]), "emissor": str(r[em]), "algoritmo": str(r[alg]),
             "secoes": int(r["secoes"]), "pct": round(100 * r["secoes"] / tot, 2)}
            for r in g.sort_values([mod, em]).to_dict("records")]


def _pct(s: pd.Series) -> dict:
    vc = s.fillna("?").value_counts()
    tot = max(1, int(vc.sum()))
    return {str(k): {"n": int(v), "pct": round(100 * v / tot, 2)} for k, v in vc.items()}


def comparar_tarde(df: pd.DataFrame, t1: Optional[pd.DataFrame]) -> dict:
    """Emissor e algoritmo: seções que fecharam tarde x demais x 1º turno, com
    o esperado pela composição de UF das seções tardias."""
    com = df[df["cert_sha256"].notna()]
    tarde = com[com["fechou_tarde"].astype("boolean").fillna(False)]
    demais = com[com["fechou_tarde"].astype("boolean").fillna(True).eq(False)]
    sem_info = com[com["fechou_tarde"].isna()]
    out = {
        "limite_minutos_apos_17h": LIMITE_TARDE_MIN,
        "secoes_tarde": int(len(tarde)), "secoes_demais": int(len(demais)),
        "secoes_sem_horario": int(len(sem_info)),
        "emissor": {"tarde": _pct(tarde["emissor"]), "demais": _pct(demais["emissor"])},
        "algoritmo": {"tarde": _pct(tarde["alg_chave"]), "demais": _pct(demais["alg_chave"])},
        "modelo": {"tarde": _pct(tarde["modelo"]), "demais": _pct(demais["modelo"])},
    }
    # esperado: para cada UF, a proporção de emissores entre as demais seções
    # da mesma UF, ponderada pelo número de seções tardias da UF
    if len(tarde) and len(demais):
        prop = demais.groupby("uf")["emissor"].value_counts(normalize=True)
        n_uf = tarde["uf"].value_counts()
        esp = Counter()
        for uf, n in n_uf.items():
            if uf in prop.index.get_level_values(0):
                for e, p in prop.loc[uf].items():
                    esp[e] += n * p
        tot = sum(esp.values()) or 1
        out["emissor"]["tarde_esperado_pela_uf"] = {
            k: {"n": round(v, 1), "pct": round(100 * v / tot, 2)} for k, v in esp.most_common()}
        out["tarde_por_uf"] = {str(k): int(v) for k, v in n_uf.items()}
    if t1 is not None and len(t1):
        out["emissor"]["t1"] = _pct(t1["t1_emissor"])
        out["algoritmo"]["t1"] = _pct(t1["t1_alg"])
        out["modelo"]["t1"] = _pct(t1["t1_modelo"])
        t1t = t1.merge(tarde[CHAVE], on=CHAVE)
        out["emissor"]["t1_mesmas_secoes_tarde"] = _pct(t1t["t1_emissor"])
    # taxa de seções tardias por UF e modelo (UFs com 5 ou mais tardias)
    if len(tarde):
        ufs = tarde["uf"].value_counts()
        base = com[com["uf"].isin(ufs[ufs >= 5].index) & com["fechou_tarde"].notna()]
        tx = base.groupby(["uf", "modelo"])["fechou_tarde"].agg(["sum", "count"])
        out["taxa_tarde_por_uf_modelo"] = {
            str(u): {str(m): {"tardias": int(r["sum"]), "secoes": int(r["count"]),
                              "pct": round(100 * r["sum"] / r["count"], 2)}
                     for (_, m), r in g.iterrows()}
            for u, g in tx.groupby(level=0)}
    # outras características nas tardias x demais
    for col in ("valido_no_dia", "cadeia_ok", "assinatura_conteudo_ok", "assinatura_bu_ok",
                "bu_hash_confere", "cn_igual_numero_interno", "mesmo_cert_t1",
                "emitido_apos_carga"):
        if col in com:
            out.setdefault("indicadores", {})[col] = {
                "tarde": _cont(tarde[col]), "demais": _cont(demais[col])}
    for nome, g in (("tarde", tarde), ("demais", demais)):
        nb = pd.to_datetime(g["not_before"], utc=True)
        out.setdefault("emissao_certificado", {})[nome] = {
            "mediana": nb.median().isoformat() if len(nb.dropna()) else None,
            "apos_1o_turno": int((nb > DIA_T1).sum()),
            "ultimos_30_dias": int((nb > DIA_T2 - timedelta(days=30)).sum()),
        }
    return out


def comparar_turnos(df: pd.DataFrame, t1: Optional[pd.DataFrame]) -> dict:
    if t1 is None or not len(t1):
        return {"disponivel": False}
    com = df[df["cert_sha256"].notna()].copy()
    tem = com[com["t1_cert_sha256"].notna()]
    out: dict = {"disponivel": True, "secoes_t1_com_certificado": int(len(t1)),
                 "secoes_t2_com_certificado": int(len(com)),
                 "secoes_comparadas": int(len(tem)),
                 "mesmo_certificado": int(tem["mesmo_cert_t1"].astype(bool).sum())}
    dif = tem[~tem["mesmo_cert_t1"].astype(bool)]
    mesmo_cn = dif[dif["mesmo_cn_t1"].astype(bool)]
    out["certificado_diferente"] = int(len(dif))
    out["certificado_diferente_mesmo_cn"] = int(len(mesmo_cn))
    out["certificado_diferente_outra_urna"] = int(len(dif) - len(mesmo_cn))
    # por número interno (CN), em qualquer seção
    t1_por_cn = t1.dropna(subset=["t1_cn"]).assign(_cn=lambda x: x["t1_cn"].str.upper())
    pares = set(zip(t1_por_cn["_cn"], t1_por_cn["t1_cert_sha256"], strict=True))
    t1_por_cn = t1_por_cn.drop_duplicates(["_cn", "t1_cert_sha256"]).groupby("_cn")[
        "t1_cert_sha256"].agg(list)
    com["_cn"] = com["cn"].str.upper()
    com["_t1_certs"] = com["_cn"].map(t1_por_cn)
    achou = com[com["_t1_certs"].notna()]
    troca = achou[[(n, c) not in pares for n, c in zip(achou["_cn"], achou["cert_sha256"],
                                                      strict=True)]]
    out["cn_presente_no_t1"] = int(len(achou))
    out["cn_novo_no_t2"] = int(len(com) - len(achou))
    out["mesmo_cn_certificado_diferente_entre_turnos"] = int(len(troca))
    out["lista_mesmo_cn_certificado_diferente"] = _lista(
        troca.assign(t1_certs=troca["_t1_certs"].map(lambda v: ",".join(x[:16] for x in v))),
        ["secao_id", "cn", "cert_sha256", "not_before", "emissor", "t1_certs", "t1_cn"])
    t1_cert_secao = t1.set_index("t1_cert_sha256")[CHAVE].astype(str).agg("/".join, axis=1)
    t1_cert_secao = t1_cert_secao[~t1_cert_secao.index.duplicated()]
    com["_secao_t1_do_cert"] = com["cert_sha256"].map(t1_cert_secao)
    chave = com[CHAVE].astype(str).agg("/".join, axis=1)
    movida = com[com["_secao_t1_do_cert"].notna() & (com["_secao_t1_do_cert"] != chave)]
    out["certificado_do_t1_em_outra_secao"] = int(len(movida))
    out["lista_certificado_do_t1_em_outra_secao"] = _lista(
        movida.assign(secao_t1=movida["_secao_t1_do_cert"]),
        ["secao_id", "cn", "secao_t1", "tipo_urna"])
    novos = com[com["_secao_t1_do_cert"].isna()]
    nb = pd.to_datetime(novos["not_before"], utc=True)
    out["certificado_nao_visto_no_t1"] = int(len(novos))
    out["certificado_nao_visto_no_t1_emitido_apos_t1"] = int((nb > DIA_T1).sum())
    out["lista_emitido_apos_t1"] = _lista(
        novos[nb > DIA_T1], ["secao_id", "cn", "emissor", "not_before", "modelo", "tipo_urna"])
    out["outra_urna_por_tipo_urna"] = _cont(dif[~dif["mesmo_cn_t1"].astype(bool)]["tipo_urna"])
    out["lista_outra_urna"] = _lista(
        dif[~dif["mesmo_cn_t1"].astype(bool)],
        ["secao_id", "t1_cn", "cn", "tipo_urna", "fechou_tarde"])
    # distribuições do 1º turno (todas as seções com certificado)
    out["distribuicao_t1"] = distribuicao(t1, "t1_emissor", "t1_alg", "t1_modelo")
    return out


def resumir(df: pd.DataFrame, t1: Optional[pd.DataFrame], acs: list[dict],
            fontes: dict, dia: datetime = DIA_T2) -> dict:
    com = df[df["cert_sha256"].notna()]
    par = df[df["par_completo"]]
    fl = falhas(df)
    out: dict = {
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "turno": 2, "pleito": "3221", "dia_eleicao": dia.date().isoformat(),
        "fontes": fontes,
        "cobertura": {
            "secoes": int(len(df)), "com_bu": int(df["tem_bu"].sum()),
            "com_vsc": int(df["tem_vsc"].sum()), "par_bu_vsc": int(len(par)),
            "bu_sem_vsc": int((df["tem_bu"] & ~df["tem_vsc"]).sum()),
            "vsc_sem_bu": int((df["tem_vsc"] & ~df["tem_bu"]).sum()),
            "com_certificado": int(len(com)),
            "verificadas": int(df["assinatura_conteudo_ok"].notna().sum()),
            "todas_assinaturas_verificadas": int(df["todas_verificadas"].astype("boolean")
                                                 .fillna(False).sum()),
            "secoes_com_mais_de_um_hash": int((df["n_hashes"] > 1).sum()),
            "ufs": sorted(df["uf"].dropna().unique().tolist()),
            "por_uf": {u: {"com_bu": int(g["tem_bu"].sum()), "com_vsc": int(g["tem_vsc"].sum()),
                           "par": int(g["par_completo"].sum())}
                       for u, g in df.groupby("uf")},
            "tipo_vsc": _cont(df["vsc_tipo"]),
        },
        "verificacoes": {
            "bu_hash_confere": _cont(par["bu_hash_confere"]),
            "bu_nome_confere": _cont(par["bu_nome_confere"]),
            "sha512_coleta_bu_confere": _cont(df[df["tem_bu"]]["bu_sha512_coleta_confere"]),
            "sha512_coleta_vsc_confere": _cont(df[df["tem_vsc"]]["vsc_sha512_coleta_confere"]),
            "hw_conteudo_ok": _cont(df[df["tem_vsc"]]["hw_conteudo_ok"]),
            "sw_conteudo_ok": _cont(df[df["tem_vsc"]]["sw_conteudo_ok"]),
            "sw_hw_hashes_iguais": _cont(df[df["tem_vsc"]]["sw_hw_hashes_iguais"]),
            "assinatura_conteudo_ok": _cont(com["assinatura_conteudo_ok"]),
            "assinatura_bu_ok": _cont(com["assinatura_bu_ok"]),
            "assinaturas_arquivos": {
                "secoes": int(com["todas_verificadas"].astype("boolean").fillna(False).sum()),
                "ok": int(com["n_assinaturas_ok"].fillna(0)[
                    com["todas_verificadas"].astype("boolean").fillna(False)].sum()),
                "falha": int(com["n_assinaturas_falha"].fillna(0).sum())},
            "assinatura_algoritmo": _cont(com["assinatura_algoritmo"]),
            "cadeia_ok": _cont(com["cadeia_ok"]),
            "nivel_cadeia": _cont(com["nivel_cadeia"]),
            "valido_no_dia": _cont(com["valido_no_dia"]),
            "ac_valida_no_dia": _cont(com["ac_valida_no_dia"]),
            "cert_valido_na_assinatura": _cont(com["cert_valido_na_assinatura"]),
            "emitido_na_validade_da_ac": _cont(com["emitido_na_validade_da_ac"]),
            "cn_confere_usuario": _cont(com["cn_confere_usuario"]),
            "cn_igual_numero_interno": _cont(com["cn_igual_numero_interno"]),
            "erro_vsc": _cont(df[df["tem_vsc"]]["erro"].dropna()),
            "erro_bu": _cont(df[df["tem_bu"]]["erro_bu"].dropna()),
        },
        "falhas": {k: {"n": int(len(v)), "secoes": _lista(v, [
            "secao_id", "hash", "bu_nome", "bu_nome_vsc", "sha512_bu", "bu_hash_hw",
            "bu_hash_sw", "arquivos_divergentes_sw_hw", "arquivos_assinatura_invalida",
            "cadeia_desc", "erro", "erro_bu", "erro_verif"], 1000)} for k, v in fl.items()},
        "certificados": {
            "distribuicao": distribuicao(com),
            "curvas": _cont(com["curva"]),
            "oid_assinatura_cert": _cont(com["oid_assinatura_cert"]),
            "versao": _cont(com["versao_cert"]),
            "extensoes": _cont(com["extensoes"]),
            "extensoes_incomuns": _cont(com["extensoes_incomuns"].dropna()),
            "extensoes_criticas": _cont(com["ext_criticas"].fillna("nenhuma")),
            "basic_ca": _cont(com["basic_ca"]),
            "key_usage": _cont(com["key_usage"]),
            "hw_alg_hash": _cont(com["hw_alg_hash"]),
            "sw_alg": _cont(com["sw_alg"]),
            "sw_usuario": _cont(com["sw_usuario"]),
            "sw_conjunto_chave": _cont(com["sw_conjunto_chave"]),
            "cadeia_caminho": _cont(com["cadeia_caminho"].fillna("?").str.replace(
                r"^[^>]*> ", "", regex=True)),
            "certificados_distintos": int(com["cert_sha256"].nunique()),
            "chaves_distintas": int(com["chave_sha256"].nunique()),
            "pares_emissor_serial": int(com.groupby(["emissor", "serial"]).ngroups),
        },
    }
    # períodos de validade por emissor e modelo
    por = []
    for (em, mod), g in com.groupby(["emissor", "modelo"], dropna=False):
        nb, na = pd.to_datetime(g["not_before"], utc=True), pd.to_datetime(g["not_after"], utc=True)
        dur = (na - nb).dt.days
        por.append({"emissor": str(em), "modelo": str(mod), "secoes": int(len(g)),
                    "nao_antes_min": nb.min().isoformat(), "nao_antes_max": nb.max().isoformat(),
                    "nao_depois_min": na.min().isoformat(), "nao_depois_max": na.max().isoformat(),
                    "duracao_dias": _cont(dur),
                    "ac_not_after": _cont(g["ac_not_after"].map(
                        lambda v: v.date().isoformat() if pd.notna(v) else None))})
    out["certificados"]["por_emissor_modelo"] = por
    nb = pd.to_datetime(com["not_before"], utc=True)
    out["certificados"]["emissao_por_ano"] = {str(k): int(v) for k, v in
                                              nb.dt.year.value_counts().sort_index().items()}
    ult = com[nb >= pd.Timestamp("2026-06-01", tz="UTC")]
    out["certificados"]["emissao_2026_por_mes"] = {
        str(k): int(v) for k, v in pd.to_datetime(ult["not_before"], utc=True)
        .dt.strftime("%Y-%m").value_counts().sort_index().items()}
    # padrões
    pad: dict = {}
    rep = com[com.groupby("cert_sha256")["cert_sha256"].transform("size") > 1]
    pad["certificado_em_mais_de_uma_secao"] = {
        "certificados": int(rep["cert_sha256"].nunique()), "secoes": int(len(rep)),
        "por_tipo_urna": _cont(rep["tipo_urna"]), "por_tipo_vsc": _cont(rep["vsc_tipo"]),
        "lista": _lista(rep.sort_values("cert_sha256"),
                        ["secao_id", "cn", "cert_sha256", "tipo_urna", "vsc_tipo"])}
    multi = com.dropna(subset=["cn"]).assign(_cn=lambda x: x["cn"].str.upper())
    multi = multi[multi.groupby("_cn")["cert_sha256"].transform("nunique") > 1]
    pad["mesmo_cn_com_certificados_diferentes_no_t2"] = {
        "cns": int(multi["cn"].str.upper().nunique()), "secoes": int(len(multi)),
        "lista": _lista(multi, ["secao_id", "cn", "cert_sha256", "not_before"])}
    chave_multi = com.assign(_cn=com["cn"].str.upper())
    chave_multi = chave_multi[chave_multi.groupby("chave_sha256")["_cn"].transform("nunique") > 1]
    pad["chave_publica_em_urnas_diferentes"] = {"secoes": int(len(chave_multi)),
                                                "lista": _lista(chave_multi, ["secao_id", "cn"])}
    difcn = com[com["cn_igual_numero_interno"].astype("boolean").fillna(True).eq(False)]
    pad["cn_difere_numero_interno"] = {
        "n": int(len(difcn)),
        "lista": _lista(difcn, ["secao_id", "cn", "numero_interno", "tipo_urna", "modelo",
                                "t1_cn", "t1_numero_interno", "fechou_tarde"], 1000)}
    pad["cn_minusculo"] = int(com["cn"].fillna("").str.startswith("ueao").sum())
    dia_carga = df["data_hora_carga"].str[:8]
    pad["carga"] = {
        "com_data": int(dia_carga.notna().sum()),
        "ate_1o_turno": int((dia_carga <= "20261004").sum()),
        "entre_turnos": int((dia_carga > "20261004").sum()),
        "entre_turnos_por_tipo_urna": _cont(df[dia_carga > "20261004"]["tipo_urna"]),
        "primeira": dia_carga.min() if dia_carga.notna().any() else None,
        "ultima": dia_carga.max() if dia_carga.notna().any() else None,
    }
    pos = com[com["emitido_apos_carga"].astype("boolean").fillna(False)]
    pad["emitido_apos_carga"] = {
        "n": int(len(pos)),
        "lista": _lista(pos, ["secao_id", "cn", "not_before", "data_hora_carga", "emissor",
                              "modelo", "tipo_urna"])}
    perto = com[nb > dia - timedelta(days=60)]
    pad["emitido_nos_60_dias_antes"] = {
        "n": int(len(perto)), "apos_1o_turno": int((nb > DIA_T1).sum()),
        "por_emissor": _cont(perto["emissor"]),
        "lista": _lista(perto.sort_values("not_before"),
                        ["secao_id", "cn", "not_before", "emissor", "modelo", "tipo_urna"])}
    ac_urna = com[com["emissor"] == "AC URNA"]
    ac_nb = pd.to_datetime(ac_urna["not_before"], utc=True)
    venc = pd.Timestamp("2026-07-18", tz="UTC")
    pad["ac_urna"] = {
        "secoes": int(len(ac_urna)),
        "ac_valida_no_dia": _cont(ac_urna["ac_valida_no_dia"]),
        "cadeia_ok": _cont(ac_urna["cadeia_ok"]),
        "emitidos_apos_vencimento_publicado": int((ac_nb > venc).sum()),
        "lista_emitidos_apos_vencimento": _lista(
            ac_urna[ac_nb > venc].sort_values("not_before"),
            ["secao_id", "cn", "not_before", "modelo", "cadeia_ok"]),
        "not_after_certificados": _cont(ac_urna["not_after"].map(
            lambda v: v.date().isoformat() if pd.notna(v) else None)),
    }
    ninv = com[com["cert_valido_na_assinatura"].astype("boolean").fillna(True).eq(False)]
    pad["certificado_fora_da_validade_na_assinatura"] = {
        "n": int(len(ninv)), "lista": _lista(ninv, ["secao_id", "cn", "not_before",
                                                    "hw_data_hora"])}
    pad["tarde_x_demais"] = comparar_tarde(df, t1)
    pad["turnos"] = comparar_turnos(df, t1)
    out["padroes"] = pad
    out["acs"] = acs
    return out


def descrever_acs(ac_dir: Optional[Path], dia: datetime) -> list[dict]:
    if not ac_dir or not Path(ac_dir).exists():
        return []
    return AC.descrever_acs(Path(ac_dir), dia)


COLS_SAIDA_EXCLUIR = {"carga_utc", "assinatura_utc"}


def analisar(saida: Path, enc_path: Path = ENC_PADRAO, t1_catalogo: Path = T1_CATALOGO,
             t1_bu: Path = T1_BU, ac_dir: Optional[Path] = AC_PADRAO,
             relatorio: Optional[Path] = None, fontes: Optional[dict] = None,
             log=print) -> dict:
    t1 = carregar_t1(t1_catalogo, t1_bu)
    enc = carregar_encerramento(enc_path)
    df = consolidar(saida, t1, enc)
    res = resumir(df, t1, descrever_acs(ac_dir, DIA_T2), fontes or {})
    res["fontes"].update({"encerramento": str(enc_path), "t1_catalogo": str(t1_catalogo),
                          "t1_bu": str(t1_bu)})
    tab = df.drop(columns=[c for c in COLS_SAIDA_EXCLUIR if c in df.columns])
    for c in tab.columns:  # colunas com tipos mistos (pd.NA e bool) viram boolean
        if tab[c].dtype == object and tab[c].map(lambda v: isinstance(v, bool) or v is pd.NA
                                                 or v is None).all():
            tab[c] = tab[c].astype("boolean")
    saida.mkdir(parents=True, exist_ok=True)
    tmp = saida / "secoes.tmp"
    tab.to_parquet(tmp, index=False)
    tmp.replace(saida / "secoes.parquet")
    (saida / "resumo.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    if relatorio:
        Path(relatorio).write_text(gerar_relatorio(res), encoding="utf-8")
        log(f"relatório: {relatorio}")
    c, v = res["cobertura"], res["verificacoes"]
    log(f"seções: {c['secoes']}; par BU+vsc: {c['par_bu_vsc']}; verificadas: {c['verificadas']}")
    log(f"bu_hash_confere {v['bu_hash_confere']}; assinatura_conteudo {v['assinatura_conteudo_ok']}"
        f"; assinatura_bu {v['assinatura_bu_ok']}; cadeia {v['cadeia_ok']}")
    log(f"falhas: { {k: x['n'] for k, x in res['falhas'].items() if x['n']} }")
    log(f"saída: {saida}")
    return res


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------

def _n(v) -> str:
    try:
        return f"{int(v):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(v)


def _p(v) -> str:
    return f"{v:.2f}".replace(".", ",") + "%"


def _sim(d: dict, chave: str = "True") -> str:
    tot = sum(d.values())
    return f"{_n(d.get(chave, 0))} de {_n(tot)}"


def _rot_cont(d: dict) -> str:
    nomes = {"True": "sim", "False": "não", "indeterminado": "indeterminado"}
    return "; ".join(f"{nomes.get(k, k)}: {_n(v)}" for k, v in d.items()) or "nenhum"


def _data(s) -> str:
    if not s:
        return "?"
    d = str(s)[:10].split("-")
    return f"{d[2]}/{d[1]}/{d[0]}" if len(d) == 3 else str(s)


def _data_je(s) -> str:
    return f"{s[6:8]}/{s[4:6]}/{s[:4]}" if isinstance(s, str) and len(s) >= 8 else "?"


def _secao_md(s: str) -> str:
    return f"`{s}`"


def gerar_relatorio(res: dict) -> str:
    c, v, f, ce, pad = (res["cobertura"], res["verificacoes"], res["falhas"],
                        res["certificados"], res["padroes"])
    L: list[str] = []
    a = L.append
    a("# Certificados e assinaturas das urnas: 2º turno de 2026")
    a("")
    a(f"Auditoria independente dos arquivos públicos do 2º turno das Eleições Gerais de 2026 "
      f"(25/10/2026, pleito 3221, eleição 6258). Gerado em {res['gerado_em']} por "
      "`scripts/ele2026/certificados_t2.py`, só com arquivos já baixados (nenhum download "
      "novo do TSE). Tabela por seção: `data/parquet/2026/t2/certificados/secoes.parquet`; "
      "números completos: `data/parquet/2026/t2/certificados/resumo.json`.")
    a("")
    graves = {k: x for k, x in f.items() if x["n"] and k != "sha512_coleta_diverge"}
    a("## Resultado")
    a("")
    if graves:
        a("> **Atenção: foram encontradas falhas.** As seções estão listadas abaixo.")
        a("")
        for k, x in graves.items():
            a(f"### {k.replace('_', ' ')}: {_n(x['n'])} seção(ões)")
            a("")
            a("| Seção | Detalhe |")
            a("|---|---|")
            for s in x["secoes"]:
                det = "; ".join(f"{kk}={vv}" for kk, vv in s.items()
                                if kk != "secao_id" and vv not in (None, ""))
                a(f"| {_secao_md(s['secao_id'])} | {det[:300]} |")
            a("")
    else:
        a(f"Nenhuma divergência de hash, nenhuma assinatura inválida e nenhuma cadeia quebrada "
          f"nas {_n(c['verificadas'])} seções verificadas.")
        a("")
    a("| Verificação | Resultado |")
    a("|---|---|")
    a(f"| SHA-512 do bu.dat igual ao valor assinado no .vsc (partes HW e SW) | "
      f"{_rot_cont(v['bu_hash_confere'])} |")
    a(f"| Nome do bu.dat igual ao listado no .vsc | {_rot_cont(v['bu_nome_confere'])} |")
    a(f"| SHA-512 do conteúdo assinado igual ao hash autoassinado, parte de hardware | "
      f"{_rot_cont(v['hw_conteudo_ok'])} |")
    a(f"| Idem, parte de software | {_rot_cont(v['sw_conteudo_ok'])} |")
    a(f"| Lista de hashes igual nas partes de software e de hardware | "
      f"{_rot_cont(v['sw_hw_hashes_iguais'])} |")
    a(f"| Assinatura de hardware do conteúdo assinado (chave do certificado da urna) | "
      f"{_rot_cont(v['assinatura_conteudo_ok'])} |")
    a(f"| Assinatura de hardware do bu.dat | {_rot_cont(v['assinatura_bu_ok'])} |")
    aa = v["assinaturas_arquivos"]
    a(f"| Assinatura de hardware de cada arquivo listado no .vsc | "
      f"{_n(aa['secoes'])} seções; assinaturas válidas: {_n(aa['ok'])}; inválidas: "
      f"{_n(aa['falha'])} |")
    a(f"| Certificado da urna assinado pela AC emissora | {_rot_cont(v['cadeia_ok'])} |")
    a(f"| Certificado da urna válido em 25/10/2026 | {_rot_cont(v['valido_no_dia'])} |")
    a(f"| Certificado válido no momento da assinatura (hora da urna, tolerância de 3 h) | "
      f"{_rot_cont(v['cert_valido_na_assinatura'])} |")
    a(f"| CN do certificado igual ao usuário da assinatura de hardware | "
      f"{_rot_cont(v['cn_confere_usuario'])} |")
    a(f"| CN do certificado igual ao número interno da urna na carga do BU | "
      f"{_rot_cont(v['cn_igual_numero_interno'])} |")
    a(f"| SHA-512 do arquivo guardado igual ao registrado na coleta (BU / .vsc) | "
      f"{_rot_cont(v['sha512_coleta_bu_confere'])} / {_rot_cont(v['sha512_coleta_vsc_confere'])} |")
    a("")
    a("## Cobertura")
    a("")
    a("Os arquivos do 2º turno ainda estão sendo coletados; os números abaixo são os dos "
      "arquivos disponíveis no momento da geração e mudam quando o script é executado de novo.")
    a("")
    a("| Item | Seções |")
    a("|---|---:|")
    a(f"| Seções com algum arquivo guardado | {_n(c['secoes'])} |")
    a(f"| Com BU | {_n(c['com_bu'])} |")
    a(f"| Com .vsc | {_n(c['com_vsc'])} |")
    a(f"| Com BU e .vsc da mesma versão (verificáveis) | {_n(c['par_bu_vsc'])} |")
    a(f"| BU sem .vsc (assinatura ainda não buscada) | {_n(c['bu_sem_vsc'])} |")
    a(f"| .vsc sem BU | {_n(c['vsc_sem_bu'])} |")
    a(f"| Com certificado e assinatura verificada | {_n(c['verificadas'])} |")
    a(f"| Com todas as assinaturas de arquivo verificadas | "
      f"{_n(c['todas_assinaturas_verificadas'])} |")
    a(f"| Com mais de uma versão (hash) publicada | {_n(c['secoes_com_mais_de_um_hash'])} |")
    a("")
    a(f"UFs presentes: {', '.join(u.upper() for u in c['ufs'])}.")
    a("")
    a("| UF | Com BU | Com .vsc | Par completo |")
    a("|---|---:|---:|---:|")
    for u, x in c["por_uf"].items():
        a(f"| {u.upper()} | {_n(x['com_bu'])} | {_n(x['com_vsc'])} | {_n(x['par'])} |")
    a("")
    a("## Como cada verificação foi feita")
    a("")
    a("1. **Hash do BU.** O SHA-512 do `bu.dat` guardado é recalculado a partir dos bytes e "
      "comparado com o hash que o `.vsc` traz para o mesmo nome de arquivo, tanto na parte de "
      "hardware quanto na de software. Também se confere o SHA-512 do conteúdo assinado (a "
      "lista de arquivos e hashes) contra o hash autoassinado de cada parte. Dos arquivos "
      "listados no `.vsc`, só o `bu.dat` está guardado no versionamento; os demais (RDV, log, "
      "imagens) não foram baixados nesta coleta.")
    a("2. **Assinatura.** A assinatura de hardware do conteúdo assinado é conferida com a chave "
      "pública do certificado que acompanha o `.vsc` (Ed521 nas UE2020 e UE2022, ECDSA P-521 "
      "com SHA-512 nas UE2013 e UE2015). Como o conteúdo assinado contém o hash de todos os "
      "arquivos, essa assinatura já autentica a lista inteira. Além dela, a assinatura "
      "individual do `bu.dat` é conferida em todas as seções, e a de cada um dos arquivos "
      "listados, na amostra indicada na cobertura.")
    a("3. **Cadeia.** A assinatura do certificado da urna é conferida com a chave pública da AC "
      "emissora (certificados em `data/certificados/ac/`), e a da AC com a da AC acima dela "
      "quando esse certificado está disponível.")
    a("4. **Padrões.** Cruzamento com o número interno da carga gravado no BU, com o horário "
      "de encerramento (`data/parquet/2026/t2/encerramento/secoes_encerramento.parquet`) e com "
      "o catálogo do 1º turno (`data/parquet/2026/integridade/secoes.parquet`, 499.207 seções "
      "com certificado, e `data/parquet/2026/secoes_2026.parquet`).")
    a("")
    a("## Certificados das urnas")
    a("")
    a("| Modelo | AC emissora | Algoritmo da chave | Seções | % |")
    a("|---|---|---|---:|---:|")
    for x in ce["distribuicao"]:
        a(f"| {x['modelo']} | {x['emissor']} | {x['algoritmo']} | {_n(x['secoes'])} | "
          f"{_p(x['pct'])} |")
    a("")
    a(f"Curvas: {_rot_cont(ce['curvas'])}. Algoritmo da assinatura dos certificados (OID): "
      f"{_rot_cont(ce['oid_assinatura_cert'])}. Versão X.509: {_rot_cont(ce['versao'])}. "
      f"Hash da assinatura de hardware: {_rot_cont(ce['hw_alg_hash'])}.")
    a("")
    a(f"Certificados distintos: {_n(ce['certificados_distintos'])}; chaves públicas distintas: "
      f"{_n(ce['chaves_distintas'])}; pares emissor e número de série distintos: "
      f"{_n(ce['pares_emissor_serial'])}.")
    a("")
    a("| AC emissora | Modelo | Seções | Emitidos entre | Vencem entre | Duração (dias) | "
      "Validade publicada da AC até |")
    a("|---|---|---:|---|---|---|---|")
    for x in ce["por_emissor_modelo"]:
        dur = ", ".join(f"{k}: {_n(n)}" for k, n in list(x["duracao_dias"].items())[:4])
        acn = ", ".join(_data(k) if k != "indeterminado" else k for k in x["ac_not_after"])
        a(f"| {x['emissor']} | {x['modelo']} | {_n(x['secoes'])} | "
          f"{_data(x['nao_antes_min'])} a {_data(x['nao_antes_max'])} | "
          f"{_data(x['nao_depois_min'])} a {_data(x['nao_depois_max'])} | {dur} | {acn} |")
    a("")
    a("**Extensões.** Conjuntos encontrados: " + "; ".join(
        f"`{k}` ({_n(n)})" for k, n in ce["extensoes"].items()) + ". Extensões fora do "
      "conjunto esperado (basicConstraints, keyUsage, subjectKeyIdentifier, "
      "authorityKeyIdentifier, cRLDistributionPoints, certificatePolicies): "
      f"{_rot_cont(ce['extensoes_incomuns'])}. Extensões marcadas como críticas: "
      f"{_rot_cont(ce['extensoes_criticas'])}. basicConstraints com CA: "
      f"{_rot_cont(ce['basic_ca'])}. keyUsage: {_rot_cont(ce['key_usage'])}.")
    a("")
    a("**Emissão por ano:** " + ", ".join(f"{k}: {_n(n)}" for k, n in
                                         ce["emissao_por_ano"].items()) + ".")
    if ce["emissao_2026_por_mes"]:
        a("")
        a("**Emissão a partir de junho de 2026, por mês:** " + ", ".join(
            f"{k}: {_n(n)}" for k, n in ce["emissao_2026_por_mes"].items()) + ".")
    a("")
    a("**Assinatura de software.** Algoritmo: " + _rot_cont(ce["sw_alg"]) + "; usuário: " +
      _rot_cont(ce["sw_usuario"]) + "; conjunto de chaves: " +
      _rot_cont(ce["sw_conjunto_chave"]) + ". O algoritmo CEPESC é de governo e não é "
      "publicado, por isso essa assinatura não pode ser conferida; só o hash do conteúdo da "
      "parte de software é conferido.")
    a("")
    a("### Autoridades certificadoras")
    a("")
    a("| AC | Emitida por | Validade | Válida em 25/10/2026 | Cadeia conferida | "
      "Confere com o resumo digital do TSE |")
    a("|---|---|---|---|---|---|")
    for x in res.get("acs", []):
        a(f"| {x['cn']} | {x['emissor']} | {_data(x['nao_antes'])} a {_data(x['nao_depois'])} | "
          f"{'sim' if x['valida_no_dia_da_eleicao'] else 'não'} | "
          f"{' > '.join(x['cadeia_conferida'])} "
          f"({ {'intermediaria': 'intermediária'}.get(x['nivel'], x['nivel'])}) | "
          f"{x['confere_resumo_oficial_tse'] or 'não consta'} |")
    a("")
    a(f"Caminhos de cadeia nas seções: {_rot_cont(ce['cadeia_caminho'])}.")
    a("")
    a("## Padrões e incoerências")
    a("")
    au = pad["ac_urna"]
    a("### AC URNA com certificado publicado vencido")
    a("")
    a(f"Seções com certificado emitido pela AC URNA: {_n(au['secoes'])}. Cadeia conferida: "
      f"{_rot_cont(au['cadeia_ok'])}. AC válida em 25/10/2026 pelo certificado publicado: "
      f"{_rot_cont(au['ac_valida_no_dia'])}. Certificados de urna emitidos depois de "
      f"18/07/2026 (vencimento do certificado publicado da AC URNA) e conferidos por ela: "
      f"{_n(au['emitidos_apos_vencimento_publicado'])}.")
    if au["lista_emitidos_apos_vencimento"]:
        a("")
        a("| Seção | CN | Emitido em | Modelo | Cadeia |")
        a("|---|---|---|---|---|")
        for s in au["lista_emitidos_apos_vencimento"]:
            a(f"| {_secao_md(s['secao_id'])} | {s['cn']} | {_data(s['not_before'])} | "
              f"{s['modelo']} | {s['cadeia_ok']} |")
    a("")
    a("A situação é a mesma do 1º turno: a assinatura confere com a chave do certificado "
      "publicado da AC URNA, que venceu em 18/07/2026. A explicação mais provável continua "
      "sendo um certificado renovado da AC URNA, com a mesma chave, que não foi publicado "
      "(ver a seção 4 de [ocorrências para o TSE](relatorio-tse-ocorrencias-2026.md)).")
    a("")
    dc = pad["cn_difere_numero_interno"]
    a("### CN do certificado diferente do número interno da carga")
    a("")
    a(f"{_n(dc['n'])} seção(ões) no 2º turno (no 1º turno foram 14 em 499.207).")
    if dc["lista"]:
        a("")
        a("| Seção | CN | Número interno no BU | Tipo de urna | Modelo | CN no 1º turno | "
          "Número interno no 1º turno | Fechou depois de 17:30 |")
        a("|---|---|---|---|---|---|---|---|")
        for s in dc["lista"]:
            ni = s.get("numero_interno")
            t1n = s.get("t1_numero_interno")
            a(f"| {_secao_md(s['secao_id'])} | {s['cn']} | "
              f"{int(ni):08d} | {s.get('tipo_urna')} | {s.get('modelo')} | "
              f"{s.get('t1_cn') or '?'} | {f'{int(t1n):08d}' if t1n else '?'} | "
              f"{s.get('fechou_tarde')} |")
    a("")
    cg = pad.get("carga", {})
    rep = pad["certificado_em_mais_de_uma_secao"]
    a("### Mesmo certificado em mais de uma seção")
    a("")
    a(f"{_n(rep['certificados'])} certificado(s), em {_n(rep['secoes'])} seções. Por tipo de "
      f"urna: {_rot_cont(rep['por_tipo_urna'])}; por tipo de arquivo de assinatura: "
      f"{_rot_cont(rep['por_tipo_vsc'])}.")
    if rep["secoes"] and set(rep["por_tipo_vsc"]) == {"sa"}:
        a("")
        a("Todas essas seções têm arquivo de assinatura do sistema de apuração (`.vsc` do tipo "
          "`sa`), emitido por uma mesma urna de apuração para várias seções (votação por cédula); "
          "por isso o mesmo certificado aparece em mais de uma seção. No 1º turno ocorreu o mesmo "
          "(1 certificado em 29 seções do exterior).")
    if rep["lista"]:
        a("")
        a("| Seção | CN | Certificado (SHA-256, início) | Tipo de urna |")
        a("|---|---|---|---|")
        for s in rep["lista"][:60]:
            a(f"| {_secao_md(s['secao_id'])} | {s['cn']} | `{s['cert_sha256'][:16]}` | "
              f"{s.get('tipo_urna')} |")
    a("")
    mc = pad["mesmo_cn_com_certificados_diferentes_no_t2"]
    a(f"Mesmo CN com certificados diferentes dentro do 2º turno: {_n(mc['cns'])} CN, "
      f"{_n(mc['secoes'])} seções. Mesma chave pública em urnas diferentes: "
      f"{_n(pad['chave_publica_em_urnas_diferentes']['secoes'])} seções. CN em minúsculas "
      f"(`ueao...`): {_n(pad['cn_minusculo'])} (todas as urnas da AC URNA, como no 1º turno).")
    a("")
    a("### Datas de emissão")
    a("")
    ap = pad["emitido_apos_carga"]
    pe = pad["emitido_nos_60_dias_antes"]
    a(f"Certificados emitidos depois da carga da urna (data e hora da carga gravadas no BU, "
      f"hora local tomada como UTC-3): {_n(ap['n'])}. Emitidos nos 60 dias anteriores ao "
      f"2º turno: {_n(pe['n'])} ({_rot_cont(pe['por_emissor'])}); depois do 1º turno "
      f"(04/10/2026): {_n(pe['apos_1o_turno'])}. Certificado fora da validade no momento da "
      f"assinatura: {_n(pad['certificado_fora_da_validade_na_assinatura']['n'])}.")
    if cg:
        a("")
        a(f"Data da carga gravada no BU: {_n(cg['com_data'])} seções com data, de "
          f"{_data_je(cg['primeira'])} a {_data_je(cg['ultima'])}; até o dia do 1º turno: "
          f"{_n(cg['ate_1o_turno'])}; entre os turnos (recarga): {_n(cg['entre_turnos'])} "
          f"({_rot_cont(cg['entre_turnos_por_tipo_urna'])}).")
    if ap["lista"]:
        a("")
        a("| Seção | CN | Emitido em | Carga em | AC | Modelo |")
        a("|---|---|---|---|---|---|")
        for s in ap["lista"][:60]:
            a(f"| {_secao_md(s['secao_id'])} | {s['cn']} | {str(s['not_before'])[:19]} | "
              f"{s['data_hora_carga']} | {s['emissor']} | {s['modelo']} |")
    if pe["lista"]:
        a("")
        a("| Seção | CN | Emitido em | AC | Modelo | Tipo de urna |")
        a("|---|---|---|---|---|---|")
        for s in pe["lista"][-60:]:
            a(f"| {_secao_md(s['secao_id'])} | {s['cn']} | {str(s['not_before'])[:19]} | "
              f"{s['emissor']} | {s['modelo']} | {s.get('tipo_urna')} |")
    a("")
    tt = pad["tarde_x_demais"]
    a("### Seções que fecharam depois de 17:30 (Brasília) x demais x 1º turno")
    a("")
    a(f"Seções com certificado e horário de encerramento: {_n(tt['secoes_tarde'])} tardias "
      f"(mais de {tt['limite_minutos_apos_17h']} minutos depois das 17h de Brasília) e "
      f"{_n(tt['secoes_demais'])} demais; sem horário: {_n(tt['secoes_sem_horario'])}.")
    a("")
    em = tt["emissor"]
    cols = [k for k in ("tarde", "tarde_esperado_pela_uf", "demais", "t1_mesmas_secoes_tarde",
                        "t1") if k in em]
    nomes = {"tarde": "Tardias (2º turno)", "tarde_esperado_pela_uf": "Esperado pela UF",
             "demais": "Demais (2º turno)", "t1_mesmas_secoes_tarde": "Mesmas seções no 1º turno",
             "t1": "1º turno, todas"}
    emissores = sorted({e for k in cols for e in em[k]})
    a("| AC emissora | " + " | ".join(nomes[k] for k in cols) + " |")
    a("|---|" + "---:|" * len(cols))
    for e in emissores:
        cel = []
        for k in cols:
            x = em[k].get(e)
            cel.append(f"{_n(x['n'])} ({_p(x['pct'])})" if x else "0")
        a(f"| {e} | " + " | ".join(cel) + " |")
    a("")
    alg = tt["algoritmo"]
    a("| Algoritmo | " + " | ".join(nomes[k] for k in ("tarde", "demais", "t1") if k in alg)
      + " |")
    a("|---|" + "---:|" * len([k for k in ("tarde", "demais", "t1") if k in alg]))
    for e in sorted({e for k in alg for e in alg[k]}):
        cel = [f"{_n(alg[k][e]['n'])} ({_p(alg[k][e]['pct'])})" if e in alg[k] else "0"
               for k in ("tarde", "demais", "t1") if k in alg]
        a(f"| {e} | " + " | ".join(cel) + " |")
    a("")
    if "tarde_por_uf" in tt:
        a("Seções tardias por UF: " + ", ".join(f"{k.upper()}: {_n(v)}" for k, v in
                                               tt["tarde_por_uf"].items()) + ".")
        a("")
    a("A coluna \"Esperado pela UF\" aplica, a cada seção tardia, a proporção de emissores das "
      "demais seções da mesma UF. Diferença entre as tardias e o esperado indica que, dentro das "
      "mesmas UFs, as seções que fecharam tarde usam outros modelos de urna; isso não é falha de "
      "assinatura nem de certificado (emissor e algoritmo são consequência do modelo).")
    a("")
    if "tarde_esperado_pela_uf" in em:
        exc = {e: em["tarde"].get(e, {"pct": 0})["pct"] - x["pct"]
               for e, x in em["tarde_esperado_pela_uf"].items()}
        e_max = max(exc, key=exc.get)
        if exc[e_max] > 5:
            a(f"**Padrão encontrado:** a {e_max} aparece em {_p(em['tarde'][e_max]['pct'])} das "
              f"seções tardias, contra {_p(em['tarde_esperado_pela_uf'][e_max]['pct'])} "
              "esperados pela composição de UF. A AC emissora acompanha o modelo da urna, então o "
              "padrão é de modelo de hardware (urnas mais antigas fecharam mais tarde), e não de "
              "certificado: nessas seções a cadeia, a validade e as assinaturas conferem como nas "
              "demais (tabela de indicadores abaixo).")
            a("")
    txm = tt.get("taxa_tarde_por_uf_modelo", {})
    if txm:
        mods = sorted({m for g in txm.values() for m in g})
        a("Proporção de seções tardias por UF e modelo (UFs com 5 ou mais seções tardias):")
        a("")
        a("| UF | " + " | ".join(mods) + " |")
        a("|---|" + "---:|" * len(mods))
        for u, g in sorted(txm.items(), key=lambda kv: -sum(x["tardias"] for x in kv[1].values())):
            cel = [f"{_p(g[m]['pct'])} ({_n(g[m]['tardias'])}/{_n(g[m]['secoes'])})" if m in g
                   else "" for m in mods]
            a(f"| {u.upper()} | " + " | ".join(cel) + " |")
        a("")
    ind = tt.get("indicadores", {})
    if ind:
        a("| Indicador | Tardias | Demais |")
        a("|---|---|---|")
        for k, x in ind.items():
            a(f"| {k} | {_rot_cont(x['tarde'])} | {_rot_cont(x['demais'])} |")
        a("")
    ec = tt.get("emissao_certificado", {})
    if ec:
        a("| Emissão do certificado | Tardias | Demais |")
        a("|---|---|---|")
        a(f"| Mediana | {_data(ec['tarde']['mediana'])} | {_data(ec['demais']['mediana'])} |")
        a(f"| Emitidos depois do 1º turno | {_n(ec['tarde']['apos_1o_turno'])} | "
          f"{_n(ec['demais']['apos_1o_turno'])} |")
        a(f"| Emitidos nos 30 dias anteriores | {_n(ec['tarde']['ultimos_30_dias'])} | "
          f"{_n(ec['demais']['ultimos_30_dias'])} |")
        a("")
    tu = pad["turnos"]
    a("### 1º turno x 2º turno")
    a("")
    if tu.get("disponivel"):
        a("| Comparação | Seções |")
        a("|---|---:|")
        a(f"| Seções do 2º turno com certificado e com certificado no 1º turno | "
          f"{_n(tu['secoes_comparadas'])} |")
        a(f"| Mesmo certificado nos dois turnos | {_n(tu['mesmo_certificado'])} |")
        a(f"| Certificado diferente, outra urna (CN diferente) | "
          f"{_n(tu['certificado_diferente_outra_urna'])} |")
        a(f"| Certificado diferente com o mesmo CN na mesma seção | "
          f"{_n(tu['certificado_diferente_mesmo_cn'])} |")
        a(f"| CN do 2º turno presente no 1º turno (qualquer seção) | {_n(tu['cn_presente_no_t1'])} |")
        a(f"| Mesmo CN com certificado diferente entre os turnos | "
          f"{_n(tu['mesmo_cn_certificado_diferente_entre_turnos'])} |")
        a(f"| Certificado do 1º turno usado em outra seção no 2º | "
          f"{_n(tu['certificado_do_t1_em_outra_secao'])} |")
        a(f"| Certificado não visto no 1º turno | {_n(tu['certificado_nao_visto_no_t1'])} |")
        a(f"| Idem, emitido depois do 1º turno | "
          f"{_n(tu['certificado_nao_visto_no_t1_emitido_apos_t1'])} |")
        a("")
        a(f"Urna diferente da do 1º turno, por tipo de urna no BU do 2º turno: "
          f"{_rot_cont(tu['outra_urna_por_tipo_urna'])}. A maior parte é urna de reserva "
          "(`reservaSecao`), isto é, urna substituída; todas essas seções têm hash, assinatura "
          "e cadeia conferidos como as demais.")
        a("")
        if tu["lista_certificado_do_t1_em_outra_secao"]:
            a("**Urnas que votaram em outra seção no 1º turno** (mesmo certificado):")
            a("")
            a("| Seção (2º turno) | CN | Seção no 1º turno | Tipo de urna |")
            a("|---|---|---|---|")
            for s in tu["lista_certificado_do_t1_em_outra_secao"]:
                a(f"| {_secao_md(s['secao_id'])} | {s['cn']} | `{s['secao_t1'].upper()}` | "
                  f"{s.get('tipo_urna')} |")
            a("")
        if tu["lista_mesmo_cn_certificado_diferente"]:
            a("**Mesmo número interno com certificado diferente entre os turnos:**")
            a("")
            a("| Seção (2º turno) | CN | Emitido em | AC | Certificados do 1º turno |")
            a("|---|---|---|---|---|")
            for s in tu["lista_mesmo_cn_certificado_diferente"]:
                a(f"| {_secao_md(s['secao_id'])} | {s['cn']} | {str(s['not_before'])[:10]} | "
                  f"{s['emissor']} | `{s['t1_certs']}` |")
            a("")
        if tu["lista_emitido_apos_t1"]:
            a("**Certificados emitidos depois do 1º turno:**")
            a("")
            a("| Seção | CN | AC | Emitido em | Modelo | Tipo de urna |")
            a("|---|---|---|---|---|---|")
            for s in tu["lista_emitido_apos_t1"]:
                a(f"| {_secao_md(s['secao_id'])} | {s['cn']} | {s['emissor']} | "
                  f"{str(s['not_before'])[:19]} | {s['modelo']} | {s.get('tipo_urna')} |")
            a("")
        a("Distribuição no 1º turno (todas as seções com certificado):")
        a("")
        a("| Modelo | AC emissora | Algoritmo | Seções | % |")
        a("|---|---|---|---:|---:|")
        for x in tu["distribuicao_t1"]:
            a(f"| {x['modelo']} | {x['emissor']} | {x['algoritmo']} | {_n(x['secoes'])} | "
              f"{_p(x['pct'])} |")
        a("")
    else:
        a("Catálogo do 1º turno indisponível.")
        a("")
    a("## O que não pode ser verificado com dados públicos")
    a("")
    a("- **Raízes e AC URNA v2.** Os certificados da AC RAIZ UE, da AC RAIZ UE v2 e da AC URNA v2 "
      "não estão publicados para download; só o SHA-512 deles consta do resumo digital do TSE. "
      "A cadeia termina na AC intermediária (AC URNA, AC UE2020, AC UE2022). O script sobe até "
      "a raiz assim que os arquivos forem colocados em `data/certificados/ac/`.")
    a("- **AC URNA renovada.** O certificado publicado da AC URNA venceu em 18/07/2026. Não há "
      "como confirmar, com dados públicos, a existência de um certificado renovado com a mesma "
      "chave.")
    a("- **Revogação.** Os certificados apontam para listas de revogação (cRLDistributionPoints) "
      "que não são públicas na internet; não foi possível conferir se algum certificado foi "
      "revogado.")
    a("- **Assinatura de software (CEPESC).** Algoritmo de governo não publicado.")
    a("- **Arquivos não guardados.** Só o `bu.dat` e o `.vsc` estão no versionamento; o hash "
      "dos demais arquivos listados no `.vsc` (RDV, log, imagens do BU) não foi comparado com "
      "os arquivos, apenas a assinatura sobre a lista de hashes.")
    a("- **Hora da urna.** A data e a hora da assinatura e da carga são as do relógio da urna, "
      "em hora local; a comparação com a validade do certificado usa tolerância de 3 horas.")
    a("- **Cobertura parcial.** Parte das seções ainda não tem `.vsc` guardado; ver a tabela de "
      "cobertura.")
    a("")
    a("## Reproduzir")
    a("")
    a("```sh")
    a("nice -n 20 .venv/bin/python scripts/ele2026/certificados_t2.py tudo --processos 3 \\")
    a("    --relatorio docs/certificados-2turno-2026.md")
    a("# outra cópia dos arquivos (por exemplo, a de Londres):")
    a("#   --versoes t2=data/versoes/2026/t2/bus/parts --versoes londres=/caminho/parts")
    a("```")
    a("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def _dirs(valores: Optional[list[str]]) -> list[tuple[str, Path]]:
    if not valores:
        return [(p.parent.parent.name, p) for p in VERSOES_PADRAO if p.exists()]
    out, vistos = [], Counter()
    for v in valores:
        rot, _, cam = v.partition("=") if "=" in v else ("", "", v)
        p = Path(cam)
        rot = rot or p.parent.parent.name or p.name
        vistos[rot] += 1
        if vistos[rot] > 1:
            rot = f"{rot}{vistos[rot]}"
        out.append((rot, p))
    return out


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("comando", choices=("extrair", "verificar", "analisar", "tudo"))
    ap.add_argument("--versoes", action="append",
                    help="diretório de partes versoes-*.parquet, opcionalmente rótulo=caminho "
                         "(repetível; padrão: data/versoes/2026/t2[-sseco]/bus/parts)")
    ap.add_argument("--saida", default=str(SAIDA_PADRAO))
    ap.add_argument("--ac", default=str(AC_PADRAO), help="certificados das AC (PEM/DER)")
    ap.add_argument("--encerramento", default=str(ENC_PADRAO))
    ap.add_argument("--t1-catalogo", default=str(T1_CATALOGO))
    ap.add_argument("--t1-bu", default=str(T1_BU))
    ap.add_argument("--processos", type=int, default=3,
                    help="processos (0 = no próprio processo); padrão 3")
    ap.add_argument("--todas-fracao", type=float, default=0.02,
                    help="fração das seções em que a assinatura de TODOS os arquivos listados "
                         "é conferida (1 = todas); padrão 0,02")
    ap.add_argument("--relatorio", default=None,
                    help=f"grava o relatório em markdown (ex.: {RELATORIO_PADRAO.relative_to(ROOT)})")
    return ap.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    a = parse_args(argv)
    saida = Path(a.saida)
    ac_dir = Path(a.ac) if a.ac else None
    dirs = _dirs(a.versoes)
    fontes = {"versoes": {r: str(p) for r, p in dirs}, "ac": str(ac_dir),
              "todas_fracao": a.todas_fracao}
    if a.comando in ("extrair", "tudo"):
        print(f"extrair: {extrair(dirs, saida, a.processos)}")
    if a.comando in ("verificar", "tudo"):
        print(f"verificar: {verificar(saida, ac_dir, a.processos, a.todas_fracao)}")
    if a.comando in ("analisar", "tudo"):
        analisar(saida, Path(a.encerramento), Path(a.t1_catalogo), Path(a.t1_bu), ac_dir,
                 Path(a.relatorio) if a.relatorio else None, fontes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
