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

Com --todas, lê em fluxo o .vsc de TODAS as seções com status ok de
secoes_2026.parquet (sem gravar arquivo bruto em disco), valida cada
certificado contra as AC de data/certificados/ac/ e sobe a cadeia até onde os
certificados disponíveis permitem (nivel_cadeia "intermediaria" ou "raiz").
Concorrência educada (padrão 8, taxa adaptativa em 429), retomável: cada lote
vira uma parte em certificados_partes/ e a próxima execução pula as seções já
feitas. Saída: certificados.parquet (uma linha por seção) e a seção "todas"
de certificados_resumo.json.

Saída: data/parquet/2026/integridade/certificados_resumo.json (pequeno).

Uso:
  python3 scripts/ele2026/analisar_certificados.py
  python3 scripts/ele2026/analisar_certificados.py --amostra 300 --vsc-dir /tmp/vsc
  python3 scripts/ele2026/analisar_certificados.py --vsc-dir /tmp/vsc --ac certs/
  python3 scripts/ele2026/analisar_certificados.py --todas [--uf rr --limite 50]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
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
AC_PADRAO = ROOT / "data" / "certificados" / "ac"
DIA_ELEICAO = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
MAX_EXEMPLOS = 50

# SHA-512 (base64) dos arquivos de certificado de AC publicados pelo TSE no
# resumo digital do sistema HOLOCRON (Eleições Gerais 2026, 02/09/2026),
# pasta D:\Aplic\SEVIN\Holocron\certificados. Serve para conferir, byte a
# byte, os PEM guardados em data/certificados/ac/ (ver o README de lá).
RESUMO_OFICIAL_SHA512 = {
    "acraiz-ue.pem": "O/LBooMqsk+Zx//zxVwXr0lboFIPwvgVj/nILBlZQaC+HZtQ1PuAFEdaWga458oPijiuUl5umAjVO+2bIcgt0g==",
    "acraizuev2.cer": "2a/T+2kuy0njwNLrSgqlAkala9p7FF6PL8x3327/M+xY9RHeQTytbeSSBEqib40aFS0q0Ir9HuL0LVwhRi6ozw==",
    "acurnav2.cer": "OTL7MHgqDbasQvSjBMWk5SkqBf5UTV7V3YjQ/kWqe8ZYZfayRLLJRJAtnS9USj4MIVg5ejiWM5ZGKiAJ1usOgw==",
    "acue2020.cer": "LLveJWbhgUEiPfm/WlQL2b1Y0UtSdzvLlKB+tDAhM60rQ869y7/iEw3yQKSkMKVVN3goJsmB/m21MASvdxKhzg==",
    "acue2022.cer": "nawawQDNRHwS4X5kYuMNZhn+aTv/ZDxzdIhbMP0mQ6rqGZ6Q5YkiTjeRSmhEEUztze7D94pBvHQAkXdI28eYeQ==",
}

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
    cand = _candidatas(c, info["aki"], acs)
    if not cand:
        return None, "AC emissora ausente", None
    for a in cand:
        if assinado_por(c, a):
            return True, a.subject.rfc4514_string(), a
    return False, "assinatura do certificado não confere com a AC", None


def _candidatas(cert, aki: Optional[str], acs: list) -> list:
    """AC que podem ter emitido o certificado (mesmo nome ou SKI = AKI)."""
    return [a for a in acs if a is not cert and (
        a.subject == cert.issuer or (aki and _ski(a) == aki))]


def _cn_cert(c) -> str:
    s = c.subject.rfc4514_string()
    return cn_de_subject(s) or s


def subir_cadeia(ac, acs: list, max_niveis: int = 6) -> tuple[str, list[str]]:
    """Sobe a partir da AC que assinou o certificado da urna, conferindo cada
    assinatura, até uma raiz autoassinada. ("raiz", caminho) quando a raiz
    está entre os certificados e sua autoassinatura confere; senão
    ("intermediaria", caminho até onde foi possível conferir)."""
    atual, caminho = ac, [_cn_cert(ac)]
    for _ in range(max_niveis):
        if atual.issuer == atual.subject:
            return ("raiz" if assinado_por(atual, atual) else "intermediaria"), caminho
        pai = next((a for a in _candidatas(atual, _aki(atual), acs)
                    if assinado_por(atual, a)), None)
        if pai is None:
            return "intermediaria", caminho
        atual = pai
        caminho.append(_cn_cert(pai))
    return "intermediaria", caminho


def conferir_resumo_oficial(raw: bytes) -> Optional[str]:
    """Nome do arquivo do resumo digital do TSE cujo SHA-512 é igual ao do
    arquivo, ou None."""
    import base64
    h = base64.b64encode(hashlib.sha512(raw).digest()).decode()
    return next((n for n, v in RESUMO_OFICIAL_SHA512.items() if v == h), None)


def descrever_acs(d: Path, dia: datetime = DIA_ELEICAO) -> list[dict]:
    """Ficha de cada certificado de AC do diretório (para o resumo)."""
    from cryptography.hazmat.primitives import serialization
    acs = carregar_acs(d)
    arquivos = {}
    for p in sorted(Path(d).iterdir()):
        if p.is_file():
            arquivos[p.name] = p.read_bytes()
    out = []
    for a in acs:
        der = a.public_bytes(serialization.Encoding.DER)
        nome = next((n for n, b in arquivos.items()
                     if der in b or a.public_bytes(serialization.Encoding.PEM) in b), None)
        nivel, caminho = subir_cadeia(a, acs)
        ini, fim = a.not_valid_before_utc, a.not_valid_after_utc
        out.append({
            "arquivo": nome, "cn": _cn_cert(a), "emissor": cn_de_subject(
                a.issuer.rfc4514_string()),
            "serial": format(a.serial_number, "x"),
            "sha256_der": hashlib.sha256(der).hexdigest(),
            "nao_antes": ini.isoformat(), "nao_depois": fim.isoformat(),
            "valida_no_dia_da_eleicao": bool(ini <= dia <= fim),
            "ski": _ski(a), "aki": _aki(a),
            "cadeia_conferida": caminho, "nivel": nivel,
            "confere_resumo_oficial_tse": conferir_resumo_oficial(arquivos[nome])
            if nome else None,
        })
    return out


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
# Modo completo (--todas): todas as seções, em fluxo, sem arquivo bruto
# ---------------------------------------------------------------------------

COLS_TABELA = CHAVE + [
    "modelo", "cn", "cn_confere_usuario", "cert_sha256", "chave_sha256", "emissor",
    "serial", "not_before", "not_after", "valido_na_eleicao", "cadeia_ok",
    "nivel_cadeia", "cadeia_caminho", "ac_valida_na_eleicao", "ac_not_after",
    "origem", "motivo", "coletado_em",
]

# AC carregadas em cada processo de verificação (o Ed521 é Python puro e
# custa cerca de 0,2 s por certificado, por isso a verificação vai para um
# pool de processos).
_ACS_PROC: list = []
_NIVEL_AC: dict[str, tuple[str, list[str]]] = {}


def _init_worker(ac_dir: Optional[str]) -> None:
    _ACS_PROC[:] = carregar_acs(Path(ac_dir)) if ac_dir else []
    _NIVEL_AC.clear()


def _nivel_da_ac(ac) -> tuple[str, list[str]]:
    from cryptography.hazmat.primitives import serialization
    k = hashlib.sha256(ac.public_bytes(serialization.Encoding.DER)).hexdigest()
    if k not in _NIVEL_AC:
        _NIVEL_AC[k] = subir_cadeia(ac, _ACS_PROC)
    return _NIVEL_AC[k]


def avaliar_vsc(raw: bytes, dia_iso: str = DIA_ELEICAO.isoformat()) -> dict:
    """Uma linha da tabela (sem a chave da seção) a partir dos bytes do .vsc.
    Usa as AC de _ACS_PROC (ver _init_worker)."""
    from dataurnas.downloader.ele2026 import MODELOS

    dia = datetime.fromisoformat(dia_iso)
    try:
        i = info_vsc(raw)
    except Exception as e:  # noqa: BLE001 - arquivo ilegível vira linha com motivo
        return {"motivo": f"vsc ilegível: {e}"[:200]}
    if "erro" in i:
        return {"motivo": i["erro"]}
    ini = datetime.fromisoformat(i["nao_antes"])
    fim = datetime.fromisoformat(i["nao_depois"])
    motivos = []
    linha = {
        "modelo": MODELOS.get(i["modelo_cod"], str(i["modelo_cod"])),
        "cn": i["cn"],
        "cn_confere_usuario": (i["cn"] or "").upper() == (i["usuario"] or "").upper(),
        "cert_sha256": i["sha256"], "chave_sha256": i["chave_sha256"],
        "emissor": cn_de_subject(i["issuer"]) or i["issuer"],
        "serial": str(i["serial"]), "not_before": ini, "not_after": fim,
        "valido_na_eleicao": bool(ini <= dia <= fim),
    }
    if not linha["valido_na_eleicao"]:
        motivos.append("certificado fora da validade no dia da eleição")
    if not linha["cn_confere_usuario"]:
        motivos.append(f"CN {i['cn']} difere do usuário da assinatura {i['usuario']}")
    ok, desc, ac = validar_cadeia(i, _ACS_PROC) if _ACS_PROC else (
        None, "AC emissora ausente", None)
    linha["cadeia_ok"] = ok
    if ok is not True:
        motivos.append(desc)
    if ac is not None:
        nivel, caminho = _nivel_da_ac(ac)
        linha["nivel_cadeia"] = nivel
        linha["cadeia_caminho"] = " > ".join([i["cn"] or "?"] + caminho)
        a_ini, a_fim = ac.not_valid_before_utc, ac.not_valid_after_utc
        linha["ac_valida_na_eleicao"] = bool(a_ini <= dia <= a_fim)
        linha["ac_not_after"] = a_fim
        if not linha["ac_valida_na_eleicao"]:
            motivos.append(f"observação: certificado publicado da {caminho[0]} "
                           f"válido até {a_fim.date().isoformat()}")
        if not a_ini <= ini <= a_fim:
            motivos.append(f"observação: emitido em {ini.date().isoformat()}, fora da "
                           f"validade publicada da {caminho[0]}")
    linha["motivo"] = "; ".join(motivos) or None
    return linha


def nome_vsc(uf: str, mun: str, zona: str, secao: str, fase: str = "o",
             pleito: Optional[str] = None) -> str:
    """Nome do -vota.vsc no padrão de 2026 (ex.: o03220ac0100700090001-vota.vsc)."""
    from dataurnas.downloader import ele2026 as E
    p = int(pleito or E.PLEITO)
    return f"{fase}{p:05d}{uf.lower()}{mun}{zona}{secao}-vota.vsc"


async def baixar_vsc(fetcher, r, via_aux: bool = False) -> tuple[Optional[bytes], str]:
    """(bytes, origem). Tenta o caminho direto com o hash já conhecido
    (secoes_2026.parquet) e, se faltar o hash ou vier 404, lê o -aux.json para
    descobrir hash e nome. Bytes None quando o arquivo não existe."""
    from dataurnas.downloader import ele2026 as E

    h = getattr(r, "hash", None)
    fase = {"oficial": "o"}.get(getattr(r, "fase", "oficial") or "oficial")
    if not via_aux and isinstance(h, str) and h and h != "0" and fase:
        raw = await fetcher.get(E.url_arquivo(r.uf, r.cd_mun, r.zona, r.secao, h,
                                              nome_vsc(r.uf, r.cd_mun, r.zona, r.secao, fase)))
        if raw is not None:
            return raw, "direto"
    aux = await fetcher.get_json(E.url_aux(r.uf, r.cd_mun, r.zona, r.secao))
    esc = E.escolher_hash(aux) if aux else None
    if not esc:
        return None, "aux sem hash"
    nm = esc["arquivos"].get("vota") or next(
        (v for v in esc["arquivos"].values() if v.endswith(".vsc")), None)
    if not nm:
        return None, "aux sem .vsc"
    raw = await fetcher.get(E.url_arquivo(r.uf, r.cd_mun, r.zona, r.secao, esc["hash"], nm))
    return raw, ("aux" if raw is not None else "vsc ausente (404)")


def carregar_secoes_ok(path: Path, ufs: Optional[list[str]] = None,
                       limite: Optional[int] = None,
                       fracao: Optional[float] = None) -> tuple[pd.DataFrame, int]:
    """Seções com status ok (ordenadas) e o total nacional de seções ok.

    Com ``fracao`` (0 a 1), mantém uma amostra determinística: a seção entra
    quando o SHA-256 da sua chave cai abaixo do limiar. Como o sorteio é
    uniforme e independente da UF e do modelo, a amostra fica proporcional em
    cada UF e em cada modelo de urna, e é reproduzível em qualquer máquina.
    """
    cols = CHAVE + ["status", "hash", "fase"]
    import pyarrow.parquet as pq
    disp = pq.read_schema(path).names
    df = pd.read_parquet(path, columns=[c for c in cols if c in disp])
    df = df[df["status"] == "ok"]
    total = int(len(df))
    if ufs:
        df = df[df["uf"].isin([u.lower() for u in ufs])]
    if fracao is not None and 0 < fracao < 1:
        import hashlib

        limiar = int(fracao * 2**32)
        chaves = df[CHAVE].astype(str).agg("/".join, axis=1)
        sorteio = chaves.map(lambda k: int.from_bytes(hashlib.sha256(k.encode()).digest()[:4], "big"))
        df = df[sorteio < limiar]
    df = df.sort_values(CHAVE).reset_index(drop=True)
    if limite:
        df = df.head(limite)
    return df, total


def partes_de(tabela: Path) -> Path:
    return tabela.with_name(tabela.stem + "_partes")


def chaves_feitas(partes: Path) -> set[tuple]:
    import pyarrow.parquet as pq
    feitas: set[tuple] = set()
    for p in sorted(partes.glob("parte-*.parquet")):
        try:
            t = pq.read_table(p, columns=CHAVE).to_pandas()
        except Exception:  # noqa: BLE001 - parte truncada por interrupção
            continue
        feitas.update(map(tuple, t[CHAVE].itertuples(index=False, name=None)))
    return feitas


def _gravar_parte(partes: Path, linhas: list[dict]) -> None:
    if not linhas:
        return
    partes.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(linhas).reindex(columns=COLS_TABELA)
    nome = partes / f"parte-{time.time_ns()}.parquet"
    tmp = nome.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(nome)  # parte só aparece completa


def consolidar(tabela: Path) -> pd.DataFrame:
    """Une as partes em certificados.parquet (uma linha por seção)."""
    partes = sorted(partes_de(tabela).glob("parte-*.parquet"))
    frames = []
    for p in partes:
        try:
            frames.append(pd.read_parquet(p))
        except Exception:  # noqa: BLE001
            continue
    if not frames:
        return pd.DataFrame(columns=COLS_TABELA)
    df = pd.concat(frames, ignore_index=True).reindex(columns=COLS_TABELA)
    df = df.drop_duplicates(CHAVE, keep="last").sort_values(CHAVE).reset_index(drop=True)
    tabela.parent.mkdir(parents=True, exist_ok=True)
    tmp = tabela.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(tabela)
    return df


async def coletar_todas(secoes: pd.DataFrame, fetcher, tabela: Path,
                        ac_dir: Optional[Path], processos: int = 0,
                        lote: int = 1000, intervalo: float = 30.0,
                        via_aux: bool = False, tarefas: int = 16, log=print) -> dict:
    """Baixa e avalia o .vsc de cada seção ainda não feita. processos = 0
    avalia no próprio processo (testes); > 0 usa um pool de processos."""
    from concurrent.futures import ProcessPoolExecutor

    partes = partes_de(tabela)
    feitas = chaves_feitas(partes)
    pend = [r for r in secoes.itertuples(index=False)
            if (r.uf, r.cd_mun, r.zona, r.secao) not in feitas]
    st = {"secoes_alvo": int(len(secoes)), "ja_feitas": int(len(secoes) - len(pend)),
          "processadas": 0, "falhas_rede": 0, "origem": Counter(), "inicio": time.time()}
    log(f"seções: {len(secoes)}; já feitas: {st['ja_feitas']}; pendentes: {len(pend)}")
    pool = None
    if processos > 0:
        pool = ProcessPoolExecutor(processos, initializer=_init_worker,
                                   initargs=(str(ac_dir) if ac_dir else None,))
    else:
        _init_worker(str(ac_dir) if ac_dir else None)
    loop = asyncio.get_running_loop()
    buf: list[dict] = []
    fila: asyncio.Queue = asyncio.Queue()
    for r in pend:
        fila.put_nowait(r)

    async def worker() -> None:
        while True:
            try:
                r = fila.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                raw, origem = await baixar_vsc(fetcher, r, via_aux)
            except Exception as e:  # noqa: BLE001 - fica pendente para a próxima
                st["falhas_rede"] += 1
                if st["falhas_rede"] <= 5:
                    log(f"falha de rede em {r.uf}-{r.cd_mun}-{r.zona}-{r.secao}: {e}")
                continue
            st["origem"][origem] += 1
            if raw is None:
                linha = {"motivo": origem}
            elif pool is not None:
                linha = await loop.run_in_executor(pool, avaliar_vsc, raw)
            else:
                linha = avaliar_vsc(raw)
            linha.update(uf=r.uf, cd_mun=r.cd_mun, zona=r.zona, secao=r.secao,
                         origem=origem, coletado_em=datetime.now(timezone.utc))
            buf.append(linha)
            st["processadas"] += 1
            if len(buf) >= lote:
                _gravar_parte(partes, buf[:])
                buf.clear()

    async def progresso() -> None:
        while True:
            await asyncio.sleep(intervalo)
            dt_ = time.time() - st["inicio"]
            v = st["processadas"] / dt_ if dt_ else 0.0
            falta = len(pend) - st["processadas"] - st["falhas_rede"]
            eta = falta / v / 3600 if v else float("nan")
            taxa = fetcher.rate_info() if hasattr(fetcher, "rate_info") else "-"
            log(f"[{dt_ / 60:6.1f} min] {st['processadas']}/{len(pend)} "
                f"({v:.1f} seções/s, {taxa}, http {getattr(fetcher, 'stats', {})}) "
                f"ETA {eta:.1f} h")

    prog = asyncio.create_task(progresso())
    try:
        await asyncio.gather(*[worker() for _ in range(max(1, tarefas))])
    finally:
        prog.cancel()
        _gravar_parte(partes, buf)
        if pool is not None:
            pool.shutdown(wait=True, cancel_futures=True)
    st["segundos"] = round(time.time() - st["inicio"], 1)
    st["secoes_por_segundo"] = round(st["processadas"] / st["segundos"], 2) \
        if st["segundos"] else None
    st["origem"] = dict(st["origem"])
    del st["inicio"]
    return st


def _datas(s: pd.Series) -> tuple[Optional[str], Optional[str]]:
    s = pd.to_datetime(s, utc=True).dropna()
    return (s.min().isoformat(), s.max().isoformat()) if len(s) else (None, None)


def _contagem(s: pd.Series) -> dict:
    def rot(v) -> str:
        return "indeterminado" if v is None or (isinstance(v, float) and pd.isna(v)) \
            else str(v)
    return {k: int(v) for k, v in s.astype(object).map(rot).value_counts().items()}


def resumir_tabela(df: pd.DataFrame, total_ok: int) -> dict:
    """Resumo de certificados.parquet para certificados_resumo.json."""
    com = df[df["cert_sha256"].notna()]
    out: dict = {
        "secoes_ok_no_pais": int(total_ok),
        "secoes_processadas": int(len(df)),
        "cobertura_pct": round(100 * len(df) / total_ok, 2) if total_ok else None,
        "situacao": "concluído" if total_ok and len(df) >= total_ok else "em andamento",
        "ufs": sorted(df["uf"].dropna().unique().tolist()),
        "com_certificado": int(len(com)),
        "sem_certificado_por_motivo": {str(k): int(v) for k, v in
                                       df[df["cert_sha256"].isna()]["motivo"]
                                       .fillna("?").value_counts().items()},
        "valido_na_eleicao": _contagem(com["valido_na_eleicao"]),
        "cadeia_ok": _contagem(com["cadeia_ok"]),
        "nivel_cadeia": _contagem(com["nivel_cadeia"]),
        "cn_confere_usuario": _contagem(com["cn_confere_usuario"]),
        "certificados_distintos": int(com["cert_sha256"].nunique()),
        "certificados_em_mais_de_uma_secao": int(
            (com["cert_sha256"].value_counts() > 1).sum()),
        "chaves_publicas_distintas": int(com["chave_sha256"].nunique()),
        "chaves_em_urnas_diferentes": int(
            (com.groupby("chave_sha256")["cn"].nunique() > 1).sum()),
    }
    por = {}
    for (em, mod), g in com.groupby(["emissor", "modelo"], dropna=False):
        nb, nb2 = _datas(g["not_before"])
        na, na2 = _datas(g["not_after"])
        por.setdefault(str(em), {})[str(mod)] = {
            "secoes": int(len(g)), "nao_antes_min": nb, "nao_antes_max": nb2,
            "nao_depois_min": na, "nao_depois_max": na2,
            "cadeia_ok": _contagem(g["cadeia_ok"]),
            "ac_valida_na_eleicao": _contagem(g["ac_valida_na_eleicao"]),
            "caminhos": {str(k): int(v) for k, v in
                         g["cadeia_caminho"].fillna("?").str.replace(
                             r"^[^>]*> ", "", regex=True).value_counts().items()},
        }
    out["por_emissor_e_modelo"] = por
    ac_ate = pd.to_datetime(com["ac_not_after"], utc=True)
    nb = pd.to_datetime(com["not_before"], utc=True)
    apos = com[ac_ate.notna() & (nb > ac_ate)]
    out["emitidos_apos_validade_publicada_da_ac"] = {
        "n": int(len(apos)),
        "exemplos": [f"{r.uf}-{r.cd_mun}-{r.zona}-{r.secao} ({r.modelo}, "
                     f"{pd.Timestamp(r.not_before).date()})"
                     for r in apos.head(MAX_EXEMPLOS).itertuples()],
    }
    prob = com[(com["cadeia_ok"] != True) | (com["valido_na_eleicao"] != True)  # noqa: E712
               | (com["cn_confere_usuario"] != True)]  # noqa: E712
    out["problemas"] = {
        "n": int(len(prob)),
        "exemplos": [{"secao_id": f"{r.uf}-{r.cd_mun}-{r.zona}-{r.secao}",
                      "motivo": r.motivo} for r in prob.head(MAX_EXEMPLOS).itertuples()],
    }
    return out


def atualizar_resumo(saida: Path, bloco: dict, chave: str = "todas") -> dict:
    """Grava o bloco no resumo existente, preservando o restante."""
    res = {}
    if saida.exists():
        try:
            res = json.loads(saida.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            res = {}
    res[chave] = bloco
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str) + "\n",
                     encoding="utf-8")
    return res


def executar_todas(args) -> int:
    from dataurnas.downloader import ele2026 as E

    ufs = [u.strip() for u in args.uf.split(",")] if args.uf else None
    secoes, total_ok = carregar_secoes_ok(Path(args.bu), ufs, args.limite, args.fracao)
    tabela = Path(args.tabela)
    ac_dir = Path(args.ac) if args.ac else (AC_PADRAO if AC_PADRAO.exists() else None)
    procs = args.processos if args.processos is not None else max(1, (os.cpu_count() or 2) // 2)
    c = args.concorrencia

    async def rodar() -> dict:
        f = E.HttpFetcher(concurrency=c, http2=False, rate=float(args.taxa or 2 * c),
                          rate_max=float(args.taxa_max or 5 * c))
        try:
            return await coletar_todas(secoes, f, tabela, ac_dir, procs,
                                       via_aux=args.via_aux, tarefas=2 * c)
        finally:
            st_http = dict(f.stats)
            await f.close()
            print(f"http: {st_http}")

    st = asyncio.run(rodar())
    df = consolidar(tabela)
    bloco = resumir_tabela(df, total_ok)
    bloco["gerado_em"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    bloco["acs"] = descrever_acs(ac_dir) if ac_dir else []
    bloco["ultima_execucao"] = st
    if args.fracao:
        if bloco["secoes_processadas"] >= len(secoes):
            bloco["situacao"] = f"concluído (amostra de {args.fracao:.0%})"
        bloco["amostra_fracao"] = args.fracao
        bloco["amostra_criterio"] = "SHA-256 da chave uf/cd_mun/zona/secao abaixo do limiar"
    atualizar_resumo(Path(args.saida), bloco)
    print(f"execução: {st}")
    print(f"tabela: {tabela} ({len(df)} seções); situação: {bloco['situacao']} "
          f"({bloco['cobertura_pct']}% das {total_ok} seções ok)")
    print(f"cadeia_ok: {bloco['cadeia_ok']}; nível: {bloco['nivel_cadeia']}; "
          f"válido na eleição: {bloco['valido_na_eleicao']}")
    print(f"resumo: {args.saida}")
    return 0


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
    ap.add_argument("--concorrencia", type=int, default=None,
                    help="requisições simultâneas (padrão 4 na amostra, 8 em --todas)")
    ap.add_argument("--ac", help="diretório com certificados das AC (PEM/DER); "
                    "padrão data/certificados/ac em --todas")
    ap.add_argument("--todas", action="store_true",
                    help="lê em fluxo o .vsc de todas as seções ok (retomável)")
    ap.add_argument("--uf", help="em --todas: só estas UFs (ex.: rr,ac)")
    ap.add_argument("--limite", type=int, help="em --todas: no máximo N seções")
    ap.add_argument("--fracao", type=float,
                    help="em --todas: amostra determinística (ex.: 0.05 para 5%%), "
                         "proporcional por UF e modelo")
    ap.add_argument("--tabela", help="em --todas: parquet de saída "
                    "(padrão <integridade>/certificados.parquet)")
    ap.add_argument("--processos", type=int, default=None,
                    help="em --todas: processos de verificação (padrão metade dos núcleos)")
    ap.add_argument("--taxa", type=float, help="em --todas: req/s inicial (padrão 2x conc.)")
    ap.add_argument("--taxa-max", type=float, help="em --todas: teto de req/s (padrão 5x conc.)")
    ap.add_argument("--via-aux", action="store_true",
                    help="em --todas: sempre lê o -aux.json antes do .vsc")
    args = ap.parse_args(argv)
    if args.concorrencia is None:
        args.concorrencia = 8 if args.todas else 4
    if args.tabela is None:
        args.tabela = str(Path(args.integridade) / "certificados.parquet")
    return args


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    if args.todas:
        return executar_todas(args)
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
    if args.ac:
        res["acs"] = descrever_acs(Path(args.ac))
    saida = Path(args.saida)
    if saida.exists():  # preserva o bloco do modo --todas
        try:
            antigo = json.loads(saida.read_text(encoding="utf-8"))
            if "todas" in antigo:
                res["todas"] = antigo["todas"]
        except json.JSONDecodeError:
            pass
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str) + "\n",
                     encoding="utf-8")
    imprimir(res)
    print(f"resumo: {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
