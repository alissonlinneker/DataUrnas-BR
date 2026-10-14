#!/usr/bin/env python3
"""Consistência dos certificados de urna nos arquivos de assinatura de 2026.

Lê o catálogo da auditoria de integridade (partes em
data/parquet/2026/integridade/parts/secoes-*.parquet, ou secoes.parquet) e os
dados do BU (data/parquet/2026/secoes_2026.parquet) e confere, só com dados
públicos já baixados:

  - distribuição de AC emissora e algoritmo da chave por modelo de urna;
  - unicidade: um certificado (SHA-256 do DER) nunca aparece em urnas
    diferentes; o par (emissora, serial) identifica um único certificado;
    uma urna não aparece com mais de um certificado;
  - o CN do certificado (UEAO + 8 dígitos) corresponde ao número interno da
    urna registrado no BU, e ao usuário que assinou a parte de hardware;
  - modelo do .vsc igual ao modelo do BU; algoritmo coerente com o modelo.

Com --amostra N (rede, poucas requisições) ou --vsc-dir DIR (arquivos locais),
abre os .vsc e confere também: validade do certificado no dia da eleição
(04/10/2026), chave pública não repetida entre urnas, usuário da assinatura
igual ao CN e, com --ac DIR, a assinatura do certificado da urna pela chave
da AC emissora (Ed521 ou ECDSA). Funciona com o catálogo parcial.

Saída: data/parquet/2026/integridade/certificados_resumo.json (pequeno).

Uso:
  python3 scripts/ele2026/analisar_certificados.py
  python3 scripts/ele2026/analisar_certificados.py --amostra 300 --vsc-dir /tmp/vsc
  python3 scripts/ele2026/analisar_certificados.py --vsc-dir /tmp/vsc --ac certs/
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import pandas as pd  # noqa: E402

from dataurnas.parsers import ed521  # noqa: E402
from dataurnas.parsers import signature as S  # noqa: E402

DIR_INTEGRIDADE = ROOT / "data" / "parquet" / "2026" / "integridade"
BU_PADRAO = ROOT / "data" / "parquet" / "2026" / "secoes_2026.parquet"
SAIDA_PADRAO = DIR_INTEGRIDADE / "certificados_resumo.json"
DIA_ELEICAO = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
MAX_EXEMPLOS = 50

# Algoritmo da chave esperado por modelo (observado nos arquivos de 2026:
# UE2009 a UE2015 com ECDSA P-521, UE2020 e UE2022 com Ed521).
ALG_ESPERADO = {
    "UE2009": "ECDSA", "UE2010": "ECDSA", "UE2011": "ECDSA",
    "UE2013": "ECDSA", "UE2015": "ECDSA", "UE2020": "Ed521", "UE2022": "Ed521",
}
RE_CN = re.compile(r"^UEAO(\d{8})$", re.IGNORECASE)
CHAVE = ["uf", "cd_mun", "zona", "secao"]
COLS_CAT = CHAVE + ["status_secao", "assinatura_valida", "assinatura_algoritmo",
                    "cert_subject", "cert_issuer", "cert_serial", "cert_sha256",
                    "modelo_urna", "motivo", "_lote"]


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

def carregar_catalogo(base: Path = DIR_INTEGRIDADE) -> tuple[pd.DataFrame, dict]:
    """Une as partes secoes-*.parquet (só leitura; ignora parte ilegível) ou,
    sem partes, o secoes.parquet consolidado. Uma linha por seção (último lote)."""
    import pyarrow.parquet as pq

    partes = sorted((base / "parts").glob("secoes-*.parquet"))
    fonte = {"partes": len(partes), "partes_ilegiveis": 0}
    frames = []
    for p in partes:
        try:
            t = pq.read_table(p)
            frames.append(t.select([c for c in COLS_CAT if c in t.column_names]).to_pandas())
        except Exception:  # noqa: BLE001 - parte em gravação ou corrompida
            fonte["partes_ilegiveis"] += 1
    if not frames and (base / "secoes.parquet").exists():
        df = pd.read_parquet(base / "secoes.parquet")
        frames = [df[[c for c in COLS_CAT if c in df.columns]]]
        fonte["arquivo"] = "secoes.parquet"
    if not frames:
        return pd.DataFrame(columns=COLS_CAT), fonte
    cat = pd.concat(frames, ignore_index=True)
    if "_lote" in cat.columns:
        cat = cat.sort_values("_lote", kind="stable")
    cat = cat.drop_duplicates(CHAVE, keep="last").reset_index(drop=True)
    return cat, fonte


def carregar_bu(path: Path = BU_PADRAO) -> pd.DataFrame:
    cols = CHAVE + ["numero_interno_urna", "modelo_urna", "tipo_urna"]
    bu = pd.read_parquet(path, columns=cols)
    return bu.rename(columns={"modelo_urna": "modelo_bu", "tipo_urna": "tipo_urna_bu"})


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------

def secao_id(r) -> str:
    return f"{r['uf']}-{r['cd_mun']}-{r['zona']}-{r['secao']}"


def cn_de_subject(subject) -> Optional[str]:
    if not isinstance(subject, str):
        return None
    for parte in subject.split(","):
        k, _, v = parte.partition("=")
        if k.strip().upper() == "CN":
            return v.strip()
    return None


def numero_de_cn(cn) -> Optional[int]:
    m = RE_CN.match(cn or "")
    return int(m.group(1)) if m else None


def familia_alg(alg) -> Optional[str]:
    if not isinstance(alg, str) or not alg:
        return None
    a = alg.upper()
    if a.startswith("ED521") or a == "EDDSA" or a == ed521_oid():
        return "Ed521"
    if a.startswith("ECDSA") or a == "1.2.840.10045.2.1":
        return "ECDSA"
    return alg


def ed521_oid() -> str:
    return S.OID_ED521


def _num(v) -> Optional[int]:
    try:
        if v is None or pd.isna(v):
            return None
        return int(v)
    except (TypeError, ValueError):
        return None


class Anomalias:
    def __init__(self) -> None:
        self.itens: dict[str, list[dict]] = defaultdict(list)

    def add(self, tipo: str, secao: str, detalhe: str) -> None:
        self.itens[tipo].append({"secao_id": secao, "detalhe": detalhe})

    def resumo(self, max_exemplos: int = MAX_EXEMPLOS) -> dict:
        return {t: {"n": len(v), "exemplos": v[:max_exemplos]}
                for t, v in sorted(self.itens.items())}

    def total(self) -> int:
        return sum(len(v) for v in self.itens.values())


# ---------------------------------------------------------------------------
# Checagens no catálogo
# ---------------------------------------------------------------------------

def analisar_catalogo(cat: pd.DataFrame, bu: Optional[pd.DataFrame],
                      anom: Anomalias) -> dict:
    """Checagens que dependem só do catálogo (e do BU, se disponível)."""
    df = cat.copy()
    if bu is not None and len(bu):
        df = df.merge(bu, on=CHAVE, how="left")
    else:
        df["numero_interno_urna"] = None
        df["modelo_bu"] = None
        df["tipo_urna_bu"] = None
    df["sid"] = df.apply(secao_id, axis=1)
    com = df[df["cert_sha256"].notna() & (df["cert_sha256"] != "")].copy()
    com["cn"] = com["cert_subject"].map(cn_de_subject)
    com["num_cn"] = com["cn"].map(numero_de_cn)
    com["num_bu"] = com["numero_interno_urna"].map(_num)
    com["emissor"] = com["cert_issuer"].map(cn_de_subject)
    com["alg"] = com["assinatura_algoritmo"].map(familia_alg)
    com["modelo"] = com["modelo_urna"].fillna(com["modelo_bu"])

    out: dict = {
        "secoes_catalogo": int(len(df)),
        "secoes_com_certificado": int(len(com)),
        "secoes_sem_certificado_por_status": {
            str(k): int(v) for k, v in
            df[~df.index.isin(com.index)]["status_secao"].fillna("?").value_counts().items()},
        "ufs": sorted(df["uf"].dropna().unique().tolist()),
    }

    # 1. emissora e algoritmo por modelo
    dist: dict = {}
    for (mod, em, alg), n in com.groupby(["modelo", "emissor", "alg"], dropna=False).size().items():
        dist.setdefault(str(mod), []).append({"emissor": str(em), "algoritmo": str(alg),
                                             "secoes": int(n)})
    out["emissores_por_modelo"] = dist
    modal = {}
    for mod, g in com.groupby("modelo"):
        em = g["emissor"].value_counts()
        modal[mod] = em.index[0]
    for r in com.itertuples():
        if r.modelo in modal and r.emissor != modal[r.modelo]:
            anom.add("emissor_atipico_para_modelo", r.sid,
                     f"{r.modelo}: emissor {r.emissor}, esperado {modal[r.modelo]}")
        esp = ALG_ESPERADO.get(r.modelo)
        if esp and r.alg and r.alg != esp:
            anom.add("algoritmo_incoerente_com_modelo", r.sid,
                     f"{r.modelo}: {r.alg}, esperado {esp}")
        if isinstance(r.modelo_urna, str) and isinstance(r.modelo_bu, str) \
                and r.modelo_urna != r.modelo_bu:
            anom.add("modelo_vsc_difere_bu", r.sid,
                     f".vsc {r.modelo_urna}, BU {r.modelo_bu}")

    # 2. unicidade do certificado entre urnas
    urnas_por_cert = com.groupby("cert_sha256").agg(
        urnas=("num_cn", lambda s: sorted({int(x) for x in s.dropna()})),
        urnas_bu=("num_bu", lambda s: sorted({int(x) for x in s.dropna()})),
        secoes=("sid", list))
    repetidos = urnas_por_cert[urnas_por_cert["secoes"].map(len) > 1]
    cert_multi_urna = urnas_por_cert[(urnas_por_cert["urnas"].map(len) > 1)
                                     | (urnas_por_cert["urnas_bu"].map(len) > 1)]
    for sha, r in cert_multi_urna.iterrows():
        for s in r["secoes"]:
            anom.add("certificado_em_urnas_diferentes", s,
                     f"cert {sha[:16]}: CN {r['urnas']}, BU {r['urnas_bu']}")
    # mesma urna (CN) com mais de um certificado
    certs_por_urna = com.dropna(subset=["num_cn"]).groupby("num_cn").agg(
        certs=("cert_sha256", lambda s: sorted(set(s))), secoes=("sid", list))
    urna_multi_cert = certs_por_urna[certs_por_urna["certs"].map(len) > 1]
    for num, r in urna_multi_cert.iterrows():
        for s in r["secoes"]:
            anom.add("urna_com_mais_de_um_certificado", s,
                     f"UEAO{int(num):08d}: {len(r['certs'])} certificados")
    # serial por emissora
    ser = com.groupby(["cert_issuer", "cert_serial"]).agg(
        certs=("cert_sha256", lambda s: sorted(set(s))), secoes=("sid", list))
    ser_dup = ser[ser["certs"].map(len) > 1]
    for (em, sr), r in ser_dup.iterrows():
        for s in r["secoes"]:
            anom.add("serial_repetido_na_emissora", s,
                     f"{cn_de_subject(em)} serial {sr}: {len(r['certs'])} certificados")
    out["unicidade"] = {
        "certificados_distintos": int(com["cert_sha256"].nunique()),
        "subjects_distintos": int(com["cert_subject"].nunique()),
        "pares_emissor_serial_distintos": int(len(ser)),
        "certificados_em_mais_de_uma_secao": int(len(repetidos)),
        "secoes_com_certificado_compartilhado": int(repetidos["secoes"].map(len).sum()),
        "certificados_em_urnas_diferentes": int(len(cert_multi_urna)),
        "urnas_com_mais_de_um_certificado": int(len(urna_multi_cert)),
        "seriais_repetidos_na_emissora": int(len(ser_dup)),
        "compartilhado_por_tipo_urna": {
            str(k): int(v) for k, v in com[com["cert_sha256"].isin(repetidos.index)]
            ["tipo_urna_bu"].fillna("?").value_counts().items()},
    }

    # 3. CN x número interno do BU x usuário da assinatura
    sem_cn = com[com["num_cn"].isna()]
    for r in sem_cn.itertuples():
        anom.add("cn_fora_do_padrao", r.sid, f"CN {r.cn!r}")
    tem_bu = com[com["num_cn"].notna() & com["num_bu"].notna()]
    dif = tem_bu[tem_bu["num_cn"] != tem_bu["num_bu"]]
    for r in dif.itertuples():
        anom.add("cn_difere_numero_interno_bu", r.sid,
                 f"CN {r.cn}, BU {int(r.num_bu):08d} ({r.tipo_urna_bu})")
    mot = com["motivo"].fillna("").str.contains("CN do certificado", regex=False)
    for r in com[mot].itertuples():
        anom.add("cn_difere_usuario_assinatura", r.sid, str(r.motivo))
    out["identidade"] = {
        "cn_no_padrao_UEAO": int(com["num_cn"].notna().sum()),
        "cn_fora_do_padrao": int(len(sem_cn)),
        "comparados_com_bu": int(len(tem_bu)),
        "cn_igual_numero_interno_bu": int(len(tem_bu) - len(dif)),
        "cn_difere_numero_interno_bu": int(len(dif)),
        "sem_numero_interno_no_bu": int(com["num_bu"].isna().sum()),
        "cn_difere_usuario_assinatura": int(mot.sum()),
        "cn_minusculo": int(com["cn"].fillna("").str.startswith("ueao").sum()),
    }
    out["assinatura_valida"] = {str(k): int(v) for k, v in
                                com["assinatura_valida"].astype(str).value_counts().items()}
    return out


# ---------------------------------------------------------------------------
# Checagens no .vsc (validade, chave pública, cadeia)
# ---------------------------------------------------------------------------

def _spki_der(der: bytes) -> bytes:
    """SubjectPublicKeyInfo (DER) do certificado."""
    _, i, ln = S._ber_tlv(der, 0)
    _, j, ln_tbs = S._ber_tlv(der, i)  # tbsCertificate
    inicios, k = [], j
    while k < j + ln_tbs:  # início (byte de tag) de cada campo do TBS
        t, v, n = S._ber_tlv(der, k)
        inicios.append((t, k, v + n))
        k = v + n
    if inicios and inicios[0][0] == 0xA0:  # [0] version
        inicios = inicios[1:]
    _, ini, fim = inicios[5]
    return der[ini:fim]


def _aki(c) -> Optional[str]:
    from cryptography import x509
    try:
        e = c.extensions.get_extension_for_class(x509.AuthorityKeyIdentifier)
        return e.value.key_identifier.hex() if e.value.key_identifier else None
    except x509.ExtensionNotFound:
        return None


def _ski(c) -> Optional[str]:
    from cryptography import x509
    try:
        return c.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value.digest.hex()
    except x509.ExtensionNotFound:
        return None


def info_vsc(raw: bytes) -> dict:
    """Campos do certificado e da parte HW de um .vsc."""
    v = S.parse_vsc(raw)
    hw = v["hw"]
    if not hw["certificado"]:
        return {"erro": "sem certificado"}
    i = S.info_certificado(hw["certificado"])
    usuario = hw["usuario"]
    esperado = f"{usuario}{hw['serial']:08d}" if usuario.upper() == "UEAO" else usuario
    return {
        "modelo_cod": v["modelo_cod"], "alg_hw": hw["algoritmo_assinatura"],
        "usuario": esperado, "cn": i["cn"], "subject": i["subject"],
        "issuer": i["issuer"], "serial": i["serial"], "sha256": i["sha256"],
        "nao_antes": i["nao_antes"], "nao_depois": i["nao_depois"],
        "oid_chave": i["oid_chave"], "oid_assinatura": i["oid_assinatura"],
        "chave_sha256": hashlib.sha256(_spki_der(i["_der"])).hexdigest(),
        "aki": _aki(i["_cert"]), "_cert": i["_cert"], "_der": i["_der"],
    }


def carregar_acs(d: Path) -> list:
    """Certificados de AC (PEM ou DER) de um diretório."""
    from cryptography import x509
    acs = []
    for p in sorted(Path(d).iterdir()):
        if not p.is_file():
            continue
        b = p.read_bytes()
        try:
            if b"-----BEGIN CERTIFICATE-----" in b:
                acs.extend(x509.load_pem_x509_certificates(b))
            else:
                acs.append(S._carregar_certificado(b))
        except Exception:  # noqa: BLE001 - arquivo que não é certificado
            continue
    return acs


def assinado_por(cert, ac) -> bool:
    """True se a assinatura do certificado confere com a chave da AC."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization

    if cert.signature_algorithm_oid.dotted_string == S.OID_ED521:
        der_ac = ac.public_bytes(serialization.Encoding.DER)
        chave = S._chave_ed521_do_certificado(der_ac)
        if chave is None:
            return False
        return ed521.verificar(chave, cert.tbs_certificate_bytes, cert.signature)
    try:
        cert.verify_directly_issued_by(ac)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def validar_cadeia(info: dict, acs: list) -> tuple[Optional[bool], str, object]:
    """(True/False/None, descrição, certificado da AC que assinou ou None).
    None: nenhuma AC candidata no diretório. Confere só o elo urna -> AC."""
    c = info["_cert"]
    cand = [a for a in acs if a.subject == c.issuer
            or (info["aki"] and _ski(a) == info["aki"])]
    if not cand:
        return None, "AC emissora ausente", None
    for a in cand:
        if assinado_por(c, a):
            return True, a.subject.rfc4514_string(), a
    return False, "assinatura do certificado não confere com a AC", None


def analisar_vscs(infos: dict[str, dict], cat: pd.DataFrame, anom: Anomalias,
                  acs: Optional[list] = None, dia: datetime = DIA_ELEICAO) -> dict:
    """infos: secao_id -> info_vsc(). Checagens que exigem o certificado inteiro."""
    cat_sha = {}
    if len(cat):
        for r in cat.itertuples():
            cat_sha[f"{r.uf}-{r.cd_mun}-{r.zona}-{r.secao}"] = r.cert_sha256
    validos = {k: v for k, v in infos.items() if "erro" not in v}
    out: dict = {"vsc_analisados": len(infos), "com_certificado": len(validos)}
    validade = Counter()
    janelas: dict[str, list] = defaultdict(list)
    chaves: dict[str, set] = defaultdict(set)
    chave_secoes: dict[str, list] = defaultdict(list)
    alg_por_emissor: dict[str, Counter] = defaultdict(Counter)
    cadeia = Counter()
    for sid, i in sorted(validos.items()):
        ini = datetime.fromisoformat(i["nao_antes"])
        fim = datetime.fromisoformat(i["nao_depois"])
        em = cn_de_subject(i["issuer"]) or i["issuer"]
        janelas[em].append((ini, fim))
        if ini <= dia <= fim:
            validade["cobre_dia_eleicao"] += 1
        else:
            validade["fora_da_validade"] += 1
            anom.add("certificado_fora_da_validade", sid,
                     f"{i['nao_antes']} a {i['nao_depois']}")
        num = numero_de_cn(i["cn"])
        chaves[i["chave_sha256"]].add(num if num is not None else i["sha256"])
        chave_secoes[i["chave_sha256"]].append(sid)
        alg = familia_alg(i["oid_chave"]) or i["oid_chave"]
        alg_por_emissor[em][alg] += 1
        if (i["cn"] or "").upper() != (i["usuario"] or "").upper():
            anom.add("cn_difere_usuario_assinatura", sid,
                     f"CN {i['cn']}, usuário {i['usuario']}")
        hw_alg = familia_alg(i["alg_hw"])
        if hw_alg and alg and hw_alg != alg:
            anom.add("algoritmo_hw_difere_chave", sid, f"HW {i['alg_hw']}, chave {alg}")
        if sid in cat_sha and isinstance(cat_sha[sid], str) and cat_sha[sid] != i["sha256"]:
            anom.add("certificado_difere_catalogo", sid, "SHA-256 do .vsc difere do catálogo")
        if acs is not None:
            ok, desc, ac = validar_cadeia(i, acs)
            cadeia[{True: "valida", False: "invalida", None: "sem_ac"}[ok]] += 1
            if ok is False:
                anom.add("cadeia_invalida", sid, desc)
            if ac is not None:
                nome_ac = cn_de_subject(ac.subject.rfc4514_string())
                ac_ini, ac_fim = ac.not_valid_before_utc, ac.not_valid_after_utc
                if not ac_ini <= dia <= ac_fim:
                    anom.add("ac_emissora_fora_da_validade_no_dia", sid,
                             f"{nome_ac} válida de {ac_ini.date()} a {ac_fim.date()}")
                if not ac_ini <= ini <= ac_fim:
                    anom.add("certificado_emitido_fora_da_validade_da_ac", sid,
                             f"emitido em {ini.date()}; {nome_ac} válida de "
                             f"{ac_ini.date()} a {ac_fim.date()}")
    for k, urnas in chaves.items():
        if len(urnas) > 1:
            for sid in chave_secoes[k]:
                anom.add("chave_publica_em_urnas_diferentes", sid,
                         f"chave {k[:16]} em {len(urnas)} urnas")
    out["validade"] = dict(validade)
    out["validade_por_emissor"] = {
        em: {"n": len(js),
             "nao_antes_min": min(a for a, _ in js).isoformat(),
             "nao_antes_max": max(a for a, _ in js).isoformat(),
             "nao_depois_min": min(b for _, b in js).isoformat(),
             "nao_depois_max": max(b for _, b in js).isoformat()}
        for em, js in sorted(janelas.items())}
    out["chaves_publicas_distintas"] = len(chaves)
    out["chaves_em_urnas_diferentes"] = sum(1 for u in chaves.values() if len(u) > 1)
    out["algoritmo_chave_por_emissor"] = {k: dict(v) for k, v in alg_por_emissor.items()}
    out["aki_por_emissor"] = dict(sorted({
        (cn_de_subject(i["issuer"]) or "?"): i["aki"] for i in validos.values()}.items()))
    if acs is not None:
        out["cadeia"] = {"acs_carregadas": len(acs), **dict(cadeia)}
    return out


def ler_vsc_dir(d: Path) -> dict[str, dict]:
    """Lê vsc_<uf>_m<mun>_z<zona>_s<secao>.bin de um diretório."""
    infos = {}
    pad = re.compile(r"^vsc_([a-z]{2})_m(\d{5})_z(\d{4})_s(\d{4})\.bin$")
    for p in sorted(Path(d).glob("vsc_*.bin")):
        m = pad.match(p.name)
        if not m:
            continue
        sid = "-".join(m.groups())
        try:
            infos[sid] = info_vsc(p.read_bytes())
        except Exception as e:  # noqa: BLE001 - arquivo ilegível vira registro
            infos[sid] = {"erro": str(e)}
    return infos


def escolher_amostra(cat: pd.DataFrame, n: int, seed: int = 2026) -> pd.DataFrame:
    """Amostra estratificada por (modelo, emissor) entre seções com certificado."""
    com = cat[cat["cert_sha256"].notna()].copy()
    if not len(com) or n <= 0:
        return com.iloc[0:0]
    com["_estrato"] = com["modelo_urna"].fillna("?") + "|" + com["cert_issuer"].fillna("?")
    estratos = com.groupby("_estrato")
    por = max(1, n // max(1, estratos.ngroups))
    partes = [g.sample(min(len(g), por), random_state=seed) for _, g in estratos]
    return pd.concat(partes).head(max(n, len(partes)))


async def baixar_amostra(amostra: pd.DataFrame, dest: Path, concorrencia: int = 4) -> int:
    """Baixa o -vota.vsc das seções da amostra para dest (pula os já baixados)."""
    from dataurnas.downloader import ele2026 as E

    dest.mkdir(parents=True, exist_ok=True)
    f = E.HttpFetcher(concurrency=concorrencia, http2=False, rate=float(concorrencia),
                      rate_max=float(concorrencia))
    sem = asyncio.Semaphore(concorrencia)
    n = 0

    async def um(r) -> None:
        nonlocal n
        p = dest / f"vsc_{r.uf}_m{r.cd_mun}_z{r.zona}_s{r.secao}.bin"
        if p.exists():
            return
        async with sem:
            aux = await f.get_json(E.url_aux(r.uf, r.cd_mun, r.zona, r.secao))
            esc = E.escolher_hash(aux) if aux else None
            if not esc:
                return
            nm = esc["arquivos"].get("vota") or next(
                (v for v in esc["arquivos"].values() if v.endswith(".vsc")), None)
            if not nm:
                return
            raw = await f.get(E.url_arquivo(r.uf, r.cd_mun, r.zona, r.secao, esc["hash"], nm))
            if raw:
                p.write_bytes(raw)
                n += 1

    try:
        await asyncio.gather(*[um(r) for r in amostra.itertuples()])
    finally:
        await f.close()
    return n


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def analisar(cat: pd.DataFrame, bu: Optional[pd.DataFrame],
             infos: Optional[dict] = None, acs: Optional[list] = None,
             fonte: Optional[dict] = None) -> dict:
    anom = Anomalias()
    res = {
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "dia_eleicao": DIA_ELEICAO.date().isoformat(),
        "fonte": fonte or {},
        "catalogo": analisar_catalogo(cat, bu, anom),
    }
    if infos is not None:
        res["vsc"] = analisar_vscs(infos, cat, anom, acs)
    res["cadeia_validada"] = bool(acs) and infos is not None
    res["n_anomalias"] = anom.total()
    res["anomalias"] = anom.resumo()
    return res


def imprimir(res: dict) -> None:
    c = res["catalogo"]
    print(f"UFs: {', '.join(c['ufs'])}")
    print(f"seções no catálogo: {c['secoes_catalogo']}; com certificado: "
          f"{c['secoes_com_certificado']}")
    print("emissora e algoritmo por modelo:")
    for mod, linhas in sorted(c["emissores_por_modelo"].items()):
        for x in linhas:
            print(f"  {mod:8s} {x['emissor']:12s} {x['algoritmo']:6s} {x['secoes']:>8d}")
    u, i = c["unicidade"], c["identidade"]
    print(f"certificados distintos: {u['certificados_distintos']}; em urnas diferentes: "
          f"{u['certificados_em_urnas_diferentes']}; urnas com >1 certificado: "
          f"{u['urnas_com_mais_de_um_certificado']}; seriais repetidos: "
          f"{u['seriais_repetidos_na_emissora']}; certificados em >1 seção: "
          f"{u['certificados_em_mais_de_uma_secao']} {u['compartilhado_por_tipo_urna']}")
    print(f"CN = número interno do BU: {i['cn_igual_numero_interno_bu']}/"
          f"{i['comparados_com_bu']}; CN fora do padrão: {i['cn_fora_do_padrao']}; "
          f"CN difere do usuário da assinatura: {i['cn_difere_usuario_assinatura']}")
    if "vsc" in res:
        v = res["vsc"]
        print(f".vsc analisados: {v['vsc_analisados']}; validade: {v['validade']}; "
              f"chaves distintas: {v['chaves_publicas_distintas']}; "
              f"chaves em urnas diferentes: {v['chaves_em_urnas_diferentes']}")
        for em, j in v["validade_por_emissor"].items():
            print(f"  {em}: emitidos de {j['nao_antes_min'][:10]} a {j['nao_antes_max'][:10]}, "
                  f"válidos até {j['nao_depois_min'][:10]} a {j['nao_depois_max'][:10]} "
                  f"(n={j['n']})")
        if "cadeia" in v:
            print(f"cadeia: {v['cadeia']}")
    print(f"anomalias: {res['n_anomalias']}")
    for t, a in res["anomalias"].items():
        ex = ", ".join(e["secao_id"] for e in a["exemplos"][:5])
        print(f"  {t}: {a['n']} (ex.: {ex})")


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--integridade", default=str(DIR_INTEGRIDADE))
    ap.add_argument("--bu", default=str(BU_PADRAO))
    ap.add_argument("--saida", default=str(SAIDA_PADRAO))
    ap.add_argument("--vsc-dir", help="diretório com vsc_<uf>_m<mun>_z<zona>_s<secao>.bin")
    ap.add_argument("--amostra", type=int, default=0,
                    help="baixa o .vsc de N seções (estratificado) para --vsc-dir")
    ap.add_argument("--concorrencia", type=int, default=4)
    ap.add_argument("--ac", help="diretório com certificados das AC (PEM/DER)")
    return ap.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    cat, fonte = carregar_catalogo(Path(args.integridade))
    bu = carregar_bu(Path(args.bu)) if Path(args.bu).exists() else None
    infos = None
    if args.amostra:
        if not args.vsc_dir:
            print("--amostra exige --vsc-dir", file=sys.stderr)
            return 2
        n = asyncio.run(baixar_amostra(escolher_amostra(cat, args.amostra),
                                       Path(args.vsc_dir), args.concorrencia))
        print(f".vsc baixados: {n}")
    if args.vsc_dir:
        infos = ler_vsc_dir(Path(args.vsc_dir))
    acs = carregar_acs(Path(args.ac)) if args.ac else None
    res = analisar(cat, bu, infos, acs, fonte)
    saida = Path(args.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str) + "\n",
                     encoding="utf-8")
    imprimir(res)
    print(f"resumo: {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
