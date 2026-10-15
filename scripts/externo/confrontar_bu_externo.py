#!/usr/bin/env python3
"""Confronta boletins de urna lidos do papel (QR Code) com os BUs publicados pelo TSE.

O QR Code impresso no boletim de urna (BU) afixado na porta da seção traz os
votos da seção, um hash SHA-512 encadeado e uma assinatura digital feita pela
própria urna. Quem fotografa ou escaneia o QR Code na seção obtém uma cópia
que não passou pela transmissão nem pela totalização do TSE. Este script:

1. lê o texto dos QR Codes (arquivo .txt com um QR Code por linha, ou o JSON
   público da Totalização Paralela do CMInd, que traz o campo ``qr_raw``);
2. recalcula a cadeia de hashes SHA-512 de todos os QR Codes do boletim;
3. verifica a assinatura:
   - formato 2026 (VRQR 6.x): assinatura da própria urna, com o certificado
     X.509 impresso nos QR Codes ``QRCE`` (Ed521 nas UE2020/UE2022, ECDSA
     P-521 com SHA-512 nas UE2013/UE2015); confere também se o certificado foi
     emitido por uma AC do TSE (AC UE2020, AC UE2022 ou AC URNA, em
     ``data/certificados/ac``);
   - formato até 2024 (VRQR 1.x a 5.x): Ed25519 com a chave pública da UF
     publicada pelo TSE (``--chave-ed25519`` ou ``--dir-chaves``);
4. compara, seção a seção, os votos para Presidente, brancos, nulos,
   comparecimento, eleitores aptos, número de série da urna e código de carga
   com ``data/parquet/2026/secoes_2026.parquet`` e
   ``votos_presidente_2026.parquet``.

Uso típico (na raiz do repositório, com o ambiente do projeto):

    # QR Codes que você mesmo leu (um por linha, em qualquer ordem)
    .venv/bin/python -I scripts/externo/confrontar_bu_externo.py --qr minha_secao.txt

    # baixa os BUs públicos da Totalização Paralela para um diretório novo
    .venv/bin/python -I scripts/externo/confrontar_bu_externo.py \\
        --baixar-cmind /caminho/novo/diretorio --saida-csv confronto.csv

    # autoteste sem rede
    .venv/bin/python -I scripts/externo/confrontar_bu_externo.py --autoteste

Código de saída: 0 sem divergência, 1 se algum BU autêntico diverge do TSE,
2 em erro de uso ou de leitura.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

PARQUET_SECOES = RAIZ / "data/parquet/2026/secoes_2026.parquet"
PARQUET_VOTOS = RAIZ / "data/parquet/2026/votos_presidente_2026.parquet"
DIR_AC = RAIZ / "data/certificados/ac"

CMIND_API = "https://totalizacaoparalela.com.br/api/public-bu"
USER_AGENT = "dataurnas-confronto-bu/1.0 (auditoria independente; pesquisa)"

CARGO_PRESIDENTE = 1
OID_ED521 = "1.3.6.1.4.1.44588.2.1"

# Escopo padrão: 1º turno de 2026 (pleito 3220, 04/10/2026), que é o que os
# parquets do projeto contêm. BUs de outro pleito ou turno são marcados como
# "fora_escopo" e não são comparados.
ESCOPO_PADRAO = {"DTPL": "20261004", "TURN": "1"}


# ---------------------------------------------------------------------------
# Leitura e validação do QR Code
# ---------------------------------------------------------------------------

@dataclass
class BoletimQR:
    origem: str
    blocos_bu: dict = field(default_factory=dict)   # índice -> texto do QR
    blocos_ce: dict = field(default_factory=dict)   # índice -> texto do QRCE
    total_bu: int = 0
    total_ce: int = 0
    conteudo: str = ""          # seção de conteúdo remontada (sem HASH)
    hash_final: str = ""
    assinatura: str = ""
    cabecalho: dict = field(default_factory=dict)
    presidente: Optional[dict] = None
    erros: list = field(default_factory=list)
    hash_ok: Optional[bool] = None
    assinatura_ok: Optional[bool] = None
    algoritmo: str = ""
    certificado: dict = field(default_factory=dict)
    vrqr: str = ""


def normalizar_texto(texto: str) -> str:
    """Desfaz codificação de URL que alguns leitores de QR aplicam."""
    t = texto.strip()
    if re.search(r"%[0-9A-Fa-f]{2}", t):
        t = urllib.parse.unquote(t)
    return t


def separar_blocos(texto: str) -> list[str]:
    """Separa o texto em QR Codes individuais (cada um começa em QRBU: ou QRCE:)."""
    t = normalizar_texto(texto)
    partes = re.split(r"(?=\bQR(?:BU|CE):\d+:\d+\b)", t)
    return [" ".join(p.split()) for p in partes if p.strip().startswith(("QRBU:", "QRCE:"))]


def montar_boletim(texto: str, origem: str) -> BoletimQR:
    bol = BoletimQR(origem=origem)
    for bloco in separar_blocos(texto):
        m = re.match(r"(QRBU|QRCE):(\d+):(\d+)\b", bloco)
        tipo, i, n = m.group(1), int(m.group(2)), int(m.group(3))
        destino = bol.blocos_bu if tipo == "QRBU" else bol.blocos_ce
        if i in destino and destino[i] != bloco:
            bol.erros.append(f"{tipo} {i}:{n} lido duas vezes com conteúdos diferentes")
        destino[i] = bloco
        if tipo == "QRBU":
            bol.total_bu = max(bol.total_bu, n)
        else:
            bol.total_ce = max(bol.total_ce, n)
    if not bol.blocos_bu:
        bol.erros.append("nenhum QR Code de boletim (QRBU) encontrado")
        return bol
    faltam = [i for i in range(1, bol.total_bu + 1) if i not in bol.blocos_bu]
    if faltam:
        bol.erros.append(f"faltam QR Codes do boletim: {faltam} de {bol.total_bu}")
    faltam_ce = [i for i in range(1, bol.total_ce + 1) if i not in bol.blocos_ce]
    if faltam_ce:
        bol.erros.append(f"faltam QR Codes do certificado: {faltam_ce} de {bol.total_ce}")
    verificar_cadeia_hash(bol)
    interpretar_conteudo(bol)
    return bol


def _dividir_bloco(bloco: str) -> tuple[dict, str, str, str]:
    """(cabeçalho, dados, hash, resto) de um QR Code QRBU."""
    toks = bloco.split(" ")
    cab = {}
    i = 0
    while i < len(toks) and toks[i].split(":", 1)[0] in ("QRBU", "VRQR", "VRCH"):
        k, _, v = toks[i].partition(":")
        cab[k] = v
        i += 1
    resto = " ".join(toks[i:])
    m = re.search(r"(?:^| )HASH:([0-9A-Fa-f]{128})(?= |$)", resto)
    if not m:
        return cab, resto, "", ""
    return cab, resto[:m.start()], m.group(1), resto[m.end():].strip()


def verificar_cadeia_hash(bol: BoletimQR) -> None:
    """Manual do QR Code no BU (TSE): HASH do QR i = SHA-512 de
    [conteúdo(i-1)] + espaço + [dados i], com conteúdo(i) = conteúdo(i-1) +
    espaço + [dados i] + " HASH:" + hash i. O cabeçalho (QRBU, VRQR, VRCH)
    fica fora do cálculo."""
    acumulado = ""
    dados_total = []
    ok = True
    for i in range(1, bol.total_bu + 1):
        bloco = bol.blocos_bu.get(i)
        if bloco is None:
            ok = False
            break
        cab, dados, h, resto = _dividir_bloco(bloco)
        bol.vrqr = bol.vrqr or cab.get("VRQR", "")
        if "VRCH" in cab:
            bol.cabecalho.setdefault("VRCH", cab["VRCH"])
        if not h:
            bol.erros.append(f"QR {i}: campo HASH ausente ou malformado")
            ok = False
            break
        mensagem = f"{acumulado} {dados}" if acumulado else dados
        calculado = hashlib.sha512(mensagem.encode("ascii", "strict")).hexdigest()
        if calculado.upper() != h.upper():
            bol.erros.append(f"QR {i}: hash não confere (conteúdo alterado ou lido com erro)")
            ok = False
        acumulado = f"{mensagem} HASH:{h}"
        dados_total.append(dados)
        bol.hash_final = h
        m = re.search(r"(?:^| )ASSI:([0-9A-Fa-f]+)", resto)
        if m:
            bol.assinatura = m.group(1)
    bol.conteudo = " ".join(dados_total)
    bol.hash_ok = ok and len(dados_total) == bol.total_bu


def interpretar_conteudo(bol: BoletimQR) -> None:
    cab = bol.cabecalho
    cargo = None
    pres = None
    em_eleicao = False
    for tok in bol.conteudo.split():
        k, _, v = tok.partition(":")
        if k == "IDEL":
            em_eleicao = True
            cargo = None
            continue
        if k == "CARG":
            cargo = int(v) if v.isdigit() else None
            if cargo == CARGO_PRESIDENTE and pres is None:
                pres = {"candidatos": {}, "APTA": None, "NOMI": None,
                        "BRAN": 0, "NULO": 0, "TOTC": None}
            continue
        if not em_eleicao:
            cab.setdefault(k, v)
            continue
        if cargo == CARGO_PRESIDENTE and pres is not None:
            if k.isdigit():
                pres["candidatos"][int(k)] = pres["candidatos"].get(int(k), 0) + int(v)
            elif k in ("APTA", "NOMI", "BRAN", "NULO", "TOTC"):
                pres[k] = int(v)
    bol.presidente = pres
    if pres:
        soma = sum(pres["candidatos"].values())
        if pres["NOMI"] is not None and soma != pres["NOMI"]:
            bol.erros.append(f"soma dos candidatos ({soma}) diferente de NOMI ({pres['NOMI']})")
        if pres["TOTC"] is not None and soma + pres["BRAN"] + pres["NULO"] != pres["TOTC"]:
            bol.erros.append("nominais + brancos + nulos diferente de TOTC (Presidente)")


# ---------------------------------------------------------------------------
# Assinatura
# ---------------------------------------------------------------------------

def _certificado_do_qr(bol: BoletimQR) -> Optional[bytes]:
    hexa = []
    for i in range(1, bol.total_ce + 1):
        bloco = bol.blocos_ce.get(i)
        if bloco is None:
            return None
        for tok in bloco.split():
            k, _, v = tok.partition(":")
            if k == "CERT":
                hexa.append(v)
            elif k == "IDUE":
                bol.certificado.setdefault("IDUE", v)
            elif k == "MDUE":
                bol.certificado.setdefault("MDUE", v)
    try:
        return bytes.fromhex("".join(hexa)) if hexa else None
    except ValueError:
        return None


def _carregar_acs(d: Path) -> list:
    from cryptography import x509
    acs = []
    if not d or not Path(d).is_dir():
        return acs
    for p in sorted(Path(d).iterdir()):
        try:
            b = p.read_bytes()
            if b"-----BEGIN CERTIFICATE-----" in b:
                acs.extend(x509.load_pem_x509_certificates(b))
            else:
                acs.append(x509.load_der_x509_certificate(b))
        except Exception:  # noqa: BLE001 - arquivo que não é certificado
            continue
    return acs


def _emitido_por(cert, ac) -> bool:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from dataurnas.parsers import ed521, signature

    if cert.issuer != ac.subject:
        return False
    if cert.signature_algorithm_oid.dotted_string == OID_ED521:
        chave = signature._chave_ed521_do_certificado(
            ac.public_bytes(serialization.Encoding.DER))
        return bool(chave) and ed521.verificar(chave, cert.tbs_certificate_bytes, cert.signature)
    try:
        cert.verify_directly_issued_by(ac)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def verificar_assinatura(bol: BoletimQR, chaves25519: dict, dir_ac: Optional[Path]) -> None:
    if not bol.assinatura or not bol.hash_final:
        bol.assinatura_ok = None
        bol.algoritmo = "assinatura ausente"
        return
    try:
        sig = bytes.fromhex(bol.assinatura)
        digest = bytes.fromhex(bol.hash_final)
    except ValueError:
        bol.assinatura_ok = False
        bol.algoritmo = "assinatura malformada"
        return

    if bol.blocos_ce or len(sig) == 132:
        # Formato 2026 (VRQR 6.x): a urna assina com a própria chave e imprime o
        # certificado nos QR Codes QRCE. A mensagem é o hash final em bytes:
        # - UE2020/UE2022: Ed521 sobre SHA-512(hash final), AC UE2020/UE2022;
        # - UE2013/UE2015: ECDSA P-521 com SHA-512 sobre o hash final, AC URNA.
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from dataurnas.parsers import ed521, signature

        cert = _certificado_do_qr(bol)
        if cert is None:
            bol.assinatura_ok = None
            bol.algoritmo = "certificado da urna ausente"
            bol.erros.append("certificado da urna (QRCE) ausente ou incompleto")
            return
        try:
            info = signature.info_certificado(cert)
        except Exception as e:  # noqa: BLE001
            bol.assinatura_ok = False
            bol.erros.append(f"certificado QRCE ilegível: {e}")
            return
        bol.certificado.update({k: info[k] for k in ("cn", "issuer", "serial", "sha256",
                                                      "nao_antes", "nao_depois")})
        if info["oid_chave"] == OID_ED521:
            bol.algoritmo = "Ed521 (certificado da urna, QRCE)"
            chave = signature._chave_ed521_do_certificado(info["_der"])
            bol.assinatura_ok = bool(chave) and ed521.verificar(
                chave, hashlib.sha512(digest).digest(), sig)
        else:
            pk = info["_cert"].public_key()
            if not isinstance(pk, ec.EllipticCurvePublicKey):
                bol.assinatura_ok = None
                bol.algoritmo = f"chave não suportada ({info['oid_chave']})"
                return
            bol.algoritmo = f"ECDSA {pk.curve.name} SHA-512 (certificado da urna, QRCE)"
            try:
                pk.verify(sig, digest, ec.ECDSA(hashes.SHA512()))
                bol.assinatura_ok = True
            except InvalidSignature:
                bol.assinatura_ok = False
        # vínculo certificado <-> urna do boletim
        idue = bol.cabecalho.get("IDUE")
        cn_num = re.sub(r"\D", "", info.get("cn") or "")
        idue_ce = bol.certificado.get("IDUE")
        if idue and idue_ce and int(idue_ce) != int(idue):
            bol.erros.append(f"QRCE é da urna {idue_ce}, boletim diz IDUE {idue}")
            bol.assinatura_ok = False
        if idue and cn_num and int(cn_num) != int(idue):
            bol.erros.append(f"certificado é da urna {cn_num}, boletim diz IDUE {idue}")
            bol.assinatura_ok = False
        acs = _carregar_acs(dir_ac) if dir_ac else []
        if acs:
            emissora = next((a for a in acs if _emitido_por(info["_cert"], a)), None)
            bol.certificado["cadeia"] = (
                emissora.subject.rfc4514_string() if emissora else "NÃO emitido por AC conhecida")
            if emissora is None:
                bol.assinatura_ok = False
                bol.erros.append("certificado da urna não foi emitido pelas AC do TSE disponíveis")
        else:
            bol.certificado["cadeia"] = "não verificada (sem certificados de AC)"
        return

    if len(sig) == 64:
        # Formato até 2024: Ed25519 com chave da UF, sobre o hash final em bytes.
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        bol.algoritmo = "Ed25519 (chave pública da UF)"
        uf = (bol.cabecalho.get("UNFE") or "").lower()
        fase = (bol.cabecalho.get("FASE") or "O").lower()
        chave = chaves25519.get(f"{fase}{uf}") or chaves25519.get("*")
        if chave is None:
            bol.assinatura_ok = None
            bol.erros.append(f"sem chave Ed25519 para {fase}{uf}qrcode.pub (use --dir-chaves)")
            return
        try:
            Ed25519PublicKey.from_public_bytes(chave).verify(sig, digest)
            bol.assinatura_ok = True
        except InvalidSignature:
            bol.assinatura_ok = False
        return

    bol.assinatura_ok = False
    bol.algoritmo = f"assinatura de {len(sig)} bytes (formato desconhecido)"


def carregar_chaves25519(chave: Optional[str], dir_chaves: Optional[Path],
                         lista_hashes: Optional[Path]) -> dict:
    """Chaves Ed25519 por '<fase><uf>' (ex.: 'oac'). '*' = chave única."""
    chaves = {}
    esperado = {}
    if lista_hashes:
        for linha in Path(lista_hashes).read_text(encoding="ascii", errors="replace").splitlines():
            p = linha.split()
            if len(p) == 2:
                esperado[p[1].lower()] = p[0].lower()
    if chave:
        p = Path(chave)
        chaves["*"] = p.read_bytes() if p.is_file() else bytes.fromhex(chave)
    if dir_chaves:
        for p in Path(dir_chaves).glob("*qrcode.pub"):
            b = p.read_bytes()
            if len(b) != 32:
                continue
            if esperado and esperado.get(p.name.lower()) != hashlib.sha512(b).hexdigest():
                print(f"AVISO: {p.name} não confere com a lista de hashes do TSE; ignorada",
                      file=sys.stderr)
                continue
            chaves[p.name[:-len("qrcode.pub")].lower()] = b
    return chaves


# ---------------------------------------------------------------------------
# Comparação com os dados do TSE (parquet do projeto)
# ---------------------------------------------------------------------------

def chave_secao(bol: BoletimQR) -> Optional[tuple]:
    c = bol.cabecalho
    try:
        return (c["UNFE"].lower(), f"{int(c['MUNI']):05d}", f"{int(c['ZONA']):04d}",
                f"{int(c['SECA']):04d}")
    except (KeyError, ValueError):
        return None


def carregar_tse(chaves: list[tuple], secoes: Path, votos: Path) -> tuple[dict, dict]:
    import duckdb

    if not chaves:
        return {}, {}
    con = duckdb.connect()
    con.execute("CREATE TEMP TABLE k(uf VARCHAR, cd_mun VARCHAR, zona VARCHAR, secao VARCHAR)")
    con.executemany("INSERT INTO k VALUES (?, ?, ?, ?)", [list(k) for k in set(chaves)])
    sec = con.execute(
        "SELECT s.* FROM read_parquet(?) s JOIN k USING (uf, cd_mun, zona, secao)",
        [str(secoes)]).df()
    vot = con.execute(
        "SELECT v.uf, v.cd_mun, v.zona, v.secao, v.tipo_voto, v.numero, v.votos "
        "FROM read_parquet(?) v JOIN k USING (uf, cd_mun, zona, secao)",
        [str(votos)]).df()
    con.close()
    tse_sec = {(r.uf, r.cd_mun, r.zona, r.secao): r._asdict()
               for r in sec.itertuples(index=False)}
    tse_vot: dict = {}
    for r in vot.itertuples(index=False):
        d = tse_vot.setdefault((r.uf, r.cd_mun, r.zona, r.secao),
                               {"candidatos": {}, "BRAN": 0, "NULO": 0})
        if r.tipo_voto == "nominal":
            d["candidatos"][int(r.numero)] = d["candidatos"].get(int(r.numero), 0) + int(r.votos)
        elif r.tipo_voto == "branco":
            d["BRAN"] += int(r.votos)
        elif r.tipo_voto == "nulo":
            d["NULO"] += int(r.votos)
    return tse_sec, tse_vot


def _int(v) -> Optional[int]:
    try:
        if v is None or v != v:  # NaN
            return None
        return int(v)
    except (TypeError, ValueError):
        return None


def comparar(bol: BoletimQR, tse_sec: dict, tse_vot: dict, escopo: dict) -> dict:
    k = chave_secao(bol)
    c = bol.cabecalho
    linha = {
        "origem": bol.origem,
        "uf": k[0] if k else None, "cd_mun": k[1] if k else None,
        "zona": k[2] if k else None, "secao": k[3] if k else None,
        "pleito": c.get("PLEI"), "turno": c.get("TURN"), "fase": c.get("FASE"),
        "vrqr": bol.vrqr, "qr_lidos": f"{len(bol.blocos_bu)}/{bol.total_bu}",
        "idue": c.get("IDUE"), "hash_ok": bol.hash_ok,
        "assinatura_ok": bol.assinatura_ok, "algoritmo": bol.algoritmo,
        "certificado_cn": bol.certificado.get("cn"),
        "cadeia_ac": bol.certificado.get("cadeia"),
        "divergencias": [], "erros": list(bol.erros), "status": "",
    }
    if k is None or not bol.hash_ok:
        linha["status"] = "qr_invalido_ou_incompleto"
        return linha
    fora = [f"{campo}={c.get(campo)}" for campo, v in escopo.items() if c.get(campo) != v]
    if fora:
        linha["status"] = "fora_escopo"
        linha["erros"].append("pleito/turno diferente do escopo dos dados do TSE: " + ", ".join(fora))
        return linha
    if c.get("FASE") != "O":
        linha["status"] = "nao_oficial"
        return linha
    sec = tse_sec.get(k)
    if sec is None:
        linha["status"] = "ausente_tse"
        return linha

    div = linha["divergencias"]

    def cmp(rotulo, qr, tse):
        if qr is None or tse is None:
            return
        if qr != tse:
            div.append(f"{rotulo}: QR={qr} TSE={tse}")

    cmp("IDUE (série da urna)", _int(c.get("IDUE")), _int(sec.get("numero_interno_urna")))
    if c.get("IDCA") and sec.get("codigo_carga") and str(sec.get("codigo_carga")) not in ("0", ""):
        cmp("IDCA (código de carga)", c.get("IDCA"), str(sec.get("codigo_carga")))
    cmp("APTO (aptos)", _int(c.get("APTO")), _int(sec.get("aptos")))
    cmp("COMP (comparecimento)", _int(c.get("COMP")), _int(sec.get("comparecimento")))
    cmp("FALT (faltosos)", _int(c.get("FALT")),
        (_int(sec.get("aptos")) - _int(sec.get("comparecimento")))
        if _int(sec.get("aptos")) is not None and _int(sec.get("comparecimento")) is not None
        else None)
    p = bol.presidente
    v = tse_vot.get(k)
    if p is None:
        linha["erros"].append("QR sem votos para Presidente (CARG:1)")
    elif v is None:
        div.append("TSE sem votos de Presidente para a seção")
    else:
        for n in sorted(set(p["candidatos"]) | set(v["candidatos"])):
            cmp(f"Presidente {n}", p["candidatos"].get(n, 0), v["candidatos"].get(n, 0))
        cmp("Presidente brancos", p["BRAN"], v["BRAN"])
        cmp("Presidente nulos", p["NULO"], v["NULO"])
        tot_tse = sum(v["candidatos"].values()) + v["BRAN"] + v["NULO"]
        cmp("Presidente total (TOTC)", p["TOTC"], tot_tse)
        linha["presidente_qr"] = json.dumps(
            {**{str(a): b for a, b in sorted(p["candidatos"].items())},
             "brancos": p["BRAN"], "nulos": p["NULO"]}, ensure_ascii=False)

    if div:
        linha["status"] = "DIVERGE" if bol.assinatura_ok else "diverge_sem_autenticidade"
    else:
        linha["status"] = "confere" if bol.assinatura_ok else "confere_sem_autenticidade"
    return linha


# ---------------------------------------------------------------------------
# Fontes de entrada
# ---------------------------------------------------------------------------

def ler_entrada(p: Path) -> list[tuple[str, str]]:
    """[(origem, texto_qr)] de um .txt (QR Codes) ou .json (CMInd: qr_raw)."""
    bruto = p.read_text(encoding="utf-8", errors="replace")
    if p.suffix.lower() == ".json":
        d = json.loads(bruto)
        itens = d.get("data", d) if isinstance(d, dict) else d
        if isinstance(itens, dict):
            itens = [itens]
        saida = []
        for it in itens:
            if isinstance(it, dict) and it.get("qr_raw"):
                saida.append((f"{p.name}#id={it.get('id', '?')}", it["qr_raw"]))
        return saida
    return [(p.name, bruto)]


def _get_json(url: str, tentativas: int = 3) -> dict:
    ultimo = None
    for t in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            ultimo = e
            time.sleep(2 * (t + 1))
    raise RuntimeError(f"falha ao baixar {url}: {ultimo}")


def baixar_cmind(destino: Path, maximo: int, intervalo: float) -> list[Path]:
    """Baixa, um por vez, os BUs públicos da Totalização Paralela (CMInd).

    Usa só a API pública que o próprio site consulta sem login
    (``/api/public-bu``). Requisições sequenciais, com pausa entre elas."""
    destino.mkdir(parents=True, exist_ok=True)
    ids = []
    pagina = 1
    while True:
        d = _get_json(f"{CMIND_API}?page={pagina}&pageSize=100&_tp_mode=oficial")
        ids.extend(str(r["id"]) for r in d.get("data", []))
        pag = d.get("pagination") or {}
        if pagina >= int(pag.get("totalPages") or pag.get("pages") or 1) or len(ids) >= maximo:
            break
        pagina += 1
        time.sleep(intervalo)
    arquivos = []
    for i in ids[:maximo]:
        alvo = destino / f"cmind_bu_{int(i):06d}.json"
        if not alvo.exists():
            time.sleep(intervalo)
            d = _get_json(f"{CMIND_API}/{urllib.parse.quote(i)}?_tp_mode=oficial")
            alvo.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        arquivos.append(alvo)
    return arquivos


# ---------------------------------------------------------------------------
# Autoteste (sem rede)
# ---------------------------------------------------------------------------

def _qr_sintetico(dados_por_qr: list[str], assinar, vrqr="1.5", vrch="20220829") -> list[str]:
    acumulado = ""
    blocos = []
    n = len(dados_por_qr)
    for i, dados in enumerate(dados_por_qr, 1):
        msg = f"{acumulado} {dados}" if acumulado else dados
        h = hashlib.sha512(msg.encode()).hexdigest().upper()
        acumulado = f"{msg} HASH:{h}"
        bloco = f"QRBU:{i}:{n} VRQR:{vrqr} VRCH:{vrch} {dados} HASH:{h}"
        if i == n:
            bloco += " ASSI:" + assinar(bytes.fromhex(h)).hex().upper()
        blocos.append(bloco)
    return blocos


def autoteste() -> int:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    falhas = 0

    def checa(nome, cond):
        nonlocal falhas
        print(("OK   " if cond else "FALHA") + " " + nome)
        falhas += 0 if cond else 1

    # 1. Vetor real do manual do TSE (BU simulado de 2016, chave de exemplo).
    manual = ("QRBU:1:1 ORIG:VOTA PROC:2000 DTPL:20161002 PLEI:2100 TURN:1 FASE:S UNFE:AC "
              "MUNI:1392 ZONA:9 SECA:31 IDUE:1760649 IDCA:529951844372447180336660 "
              "VERS:5.22.0.1 VRQR:4.0 LOCA:4 APTO:40 COMP:10 FALT:30 HBMA:4 DTAB:20161002 "
              "HRAB:173449 DTFC:20161002 HRFC:180133 IDEL:2101 CARG:13 TIPO:1 "
              "VERC:201606281643 PART:91 91001:1 91004:1 LEGP:0 TOTP:2 PART:92 92003:1 "
              "92004:1 92005:1 LEGP:0 TOTP:3 PART:93 93004:1 93005:1 LEGP:0 TOTP:2 PART:94 "
              "94001:2 LEGP:0 TOTP:2 NOMI:9 LEGC:0 BRAN:1 NULO:0 TOTC:10 CARG:11 TIPO:0 "
              "VERC:201606281643 91:2 92:2 93:3 97:1 NOMI:8 BRAN:2 NULO:0 TOTC:10 "
              "HASH:69720370FEF82D1235846B6500408F48068DF564553DEEAD273CA20BCE959A3791281379"
              "FF96B28755B15DFB7254EE6937C70BE69CB941D69AF73C57622DAA27 "
              "ASSI:D4A834C84DBE93DAF86CCF7B1D9743796FB478ED954C44896F551E53D3F1A9F7CCB27695"
              "64CDA02585070F313C003F8C046AD49C2250375B6818A76BD5842E0D")
    chave_manual = bytes.fromhex(
        "CF3AF898467A5B7A52D33D53BC037E2642A8DA996903FC252217E9C033E2F291")
    b = montar_boletim(manual, "manual-tse")
    verificar_assinatura(b, {"*": chave_manual}, None)
    checa("manual TSE: cadeia de hash", b.hash_ok is True)
    checa("manual TSE: assinatura Ed25519", b.assinatura_ok is True)
    adulterado = manual.replace("91:2 92:2", "91:3 92:1")
    b2 = montar_boletim(adulterado, "manual-adulterado")
    checa("manual TSE adulterado: hash acusa", b2.hash_ok is False)

    # 2. BU sintético com 3 QR Codes, assinado com chave gerada aqui.
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    dados = [
        "ORIG:VOTA ORLC:LEG PROC:1219 DTPL:20261004 PLEI:3220 TURN:1 FASE:O UNFE:ZZ "
        "MUNI:99999 ZONA:1 SECA:1 IDUE:1234567 IDCA:000000000000000000000001 "
        "VERS:10.23.0.0 LOCA:1 APTO:100 COMP:80 FALT:20 IDEL:6259 CARG:6 TIPO:1 "
        "VERC:202609221257 PART:10 10001:5",
        "LEGP:0 TOTP:5 NOMI:5 LEGC:0 BRAN:40 NULO:35 TOTC:80 IDEL:6257 CARG:1 TIPO:0 "
        "VERC:202609151528 13:30 22:35",
        "55:5 APTA:100 NOMI:70 BRAN:4 NULO:6 TOTC:80",
    ]
    blocos = _qr_sintetico(dados, priv.sign)
    texto = "\n".join(reversed(blocos))  # ordem de leitura embaralhada
    b3 = montar_boletim(texto, "sintetico")
    verificar_assinatura(b3, {"ozz": pub}, None)
    checa("sintético: cadeia de hash com 3 QR Codes", b3.hash_ok is True)
    checa("sintético: assinatura", b3.assinatura_ok is True)
    checa("sintético: votos de Presidente",
          b3.presidente and b3.presidente["candidatos"] == {13: 30, 22: 35, 55: 5}
          and b3.presidente["BRAN"] == 4 and b3.presidente["NULO"] == 6)
    k = chave_secao(b3)
    tse_sec = {k: {"numero_interno_urna": 1234567, "codigo_carga": "000000000000000000000001",
                   "aptos": 100, "comparecimento": 80}}
    tse_vot = {k: {"candidatos": {13: 30, 22: 35, 55: 5}, "BRAN": 4, "NULO": 6}}
    r = comparar(b3, tse_sec, tse_vot, ESCOPO_PADRAO)
    checa("sintético: confere com TSE igual", r["status"] == "confere")
    tse_vot_div = {k: {"candidatos": {13: 31, 22: 34, 55: 5}, "BRAN": 4, "NULO": 6}}
    r = comparar(b3, tse_sec, tse_vot_div, ESCOPO_PADRAO)
    checa("sintético: acusa divergência de 1 voto", r["status"] == "DIVERGE"
          and len(r["divergencias"]) == 2)
    r = comparar(b3, {}, {}, ESCOPO_PADRAO)
    checa("sintético: seção ausente no TSE", r["status"] == "ausente_tse")
    b4 = montar_boletim("\n".join(blocos[:2]), "incompleto")
    checa("sintético: QR Code faltando", b4.hash_ok is False and any("faltam" in e for e in b4.erros))
    outra = Ed25519PrivateKey.generate().public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    b5 = montar_boletim(texto, "chave-errada")
    verificar_assinatura(b5, {"ozz": outra}, None)
    checa("sintético: chave errada reprovada", b5.assinatura_ok is False)

    # 3. BU real de 2026 (formato VRQR 6.0, Ed521), se a fixture existir.
    fx = Path(__file__).resolve().parent / "fixtures" / "qr_sp_72133_0312_0209.txt"
    if fx.exists():
        b6 = montar_boletim(fx.read_text(encoding="ascii"), fx.name)
        verificar_assinatura(b6, {}, DIR_AC if DIR_AC.is_dir() else None)
        checa("BU real 2026: cadeia de hash", b6.hash_ok is True)
        checa("BU real 2026: assinatura Ed521 da urna", b6.assinatura_ok is True)
        checa("BU real 2026: certificado da urna 2385618",
              re.sub(r"\D", "", b6.certificado.get("cn") or "") == "02385618")
        if DIR_AC.is_dir():
            checa("BU real 2026: certificado emitido pela AC UE2022",
                  "AC UE2022" in (b6.certificado.get("cadeia") or ""))
        texto6 = fx.read_text(encoding="ascii")
        alvo = re.search(r" 22:(\d+) ", texto6.split("CARG:1 ", 1)[1])
        adult = texto6
        if alvo:
            ini = texto6.index("CARG:1 ") + len("CARG:1 ") + alvo.start()
            novo = f" 22:{int(alvo.group(1)) + 1} "
            adult = texto6[:ini] + novo + texto6[ini + len(alvo.group(0)):]
        b7 = montar_boletim(adult, "real-adulterado")
        checa("BU real 2026 com 1 voto alterado: hash acusa", b7.hash_ok is False)
    fx2 = Path(__file__).resolve().parent / "fixtures" / "qr_mg_46752_0140_0089.txt"
    if fx2.exists():
        b8 = montar_boletim(fx2.read_text(encoding="ascii"), fx2.name)
        verificar_assinatura(b8, {}, DIR_AC if DIR_AC.is_dir() else None)
        checa("BU real 2026 (UE2015): cadeia de hash", b8.hash_ok is True)
        checa("BU real 2026 (UE2015): assinatura ECDSA P-521 da urna", b8.assinatura_ok is True)
        if DIR_AC.is_dir():
            checa("BU real 2026 (UE2015): certificado emitido pela AC URNA",
                  "AC URNA" in (b8.certificado.get("cadeia") or ""))
    print(f"\n{'autoteste aprovado' if not falhas else f'{falhas} falha(s)'}")
    return 0 if not falhas else 1


# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--qr", action="append", type=Path, default=[],
                    help="arquivo .txt com os QR Codes de um BU, ou .json com qr_raw")
    ap.add_argument("--dir", type=Path, help="diretório com vários .txt/.json")
    ap.add_argument("--baixar-cmind", type=Path, metavar="DIR",
                    help="baixa os BUs públicos da Totalização Paralela (CMInd) para DIR")
    ap.add_argument("--cmind-max", type=int, default=500)
    ap.add_argument("--intervalo", type=float, default=1.0,
                    help="segundos entre requisições (padrão 1,0)")
    ap.add_argument("--secoes", type=Path, default=PARQUET_SECOES)
    ap.add_argument("--votos", type=Path, default=PARQUET_VOTOS)
    ap.add_argument("--dir-ac", type=Path, default=DIR_AC,
                    help="certificados das AC do TSE (cadeia do certificado da urna)")
    ap.add_argument("--chave-ed25519", help="chave Ed25519 (hex ou arquivo .pub) para BUs até 2024")
    ap.add_argument("--dir-chaves", type=Path, help="diretório com <fase><uf>qrcode.pub")
    ap.add_argument("--lista-hashes-chaves", type=Path,
                    help="lista SHA-512 das chaves publicada pelo TSE")
    ap.add_argument("--sem-escopo", action="store_true",
                    help="não exige DTPL 20261004 / TURN 1 (use com --secoes/--votos de outro pleito)")
    ap.add_argument("--saida-csv", type=Path)
    ap.add_argument("--saida-json", type=Path)
    ap.add_argument("--autoteste", action="store_true", help="roda os testes sem rede e sai")
    a = ap.parse_args(argv)

    if a.autoteste:
        return autoteste()

    arquivos = list(a.qr)
    if a.dir:
        arquivos += sorted(p for p in a.dir.iterdir() if p.suffix.lower() in (".txt", ".json"))
    if a.baixar_cmind:
        arquivos += baixar_cmind(a.baixar_cmind, a.cmind_max, a.intervalo)
    if not arquivos:
        ap.error("informe --qr, --dir ou --baixar-cmind (ou --autoteste)")

    chaves = carregar_chaves25519(a.chave_ed25519, a.dir_chaves, a.lista_hashes_chaves)
    boletins = []
    for p in arquivos:
        try:
            for origem, texto in ler_entrada(p):
                bol = montar_boletim(texto, origem)
                verificar_assinatura(bol, chaves, a.dir_ac)
                boletins.append(bol)
        except (OSError, ValueError, json.JSONDecodeError) as e:
            print(f"ERRO lendo {p}: {e}", file=sys.stderr)
            return 2

    chaves_sec = [k for k in (chave_secao(b) for b in boletins) if k]
    tse_sec, tse_vot = carregar_tse(chaves_sec, a.secoes, a.votos)
    escopo = {} if a.sem_escopo else ESCOPO_PADRAO
    linhas = [comparar(b, tse_sec, tse_vot, escopo) for b in boletins]

    from collections import Counter
    cont = Counter(lin["status"] for lin in linhas)
    for lin in linhas:
        ident = f"{lin['uf']}/{lin['cd_mun']}/{lin['zona']}/{lin['secao']}"
        print(f"{lin['status']:<28} {ident:<22} hash={lin['hash_ok']} assin={lin['assinatura_ok']} "
              f"[{lin['origem']}]")
        for d in lin["divergencias"]:
            print(f"    divergência: {d}")
        for e in lin["erros"]:
            print(f"    aviso: {e}")
    print("\nResumo:", dict(cont), f"| BUs lidos: {len(linhas)}")

    if a.saida_json:
        a.saida_json.write_text(json.dumps(linhas, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.saida_csv:
        campos = ["status", "uf", "cd_mun", "zona", "secao", "pleito", "turno", "fase", "vrqr",
                  "qr_lidos", "idue", "hash_ok", "assinatura_ok", "algoritmo",
                  "certificado_cn", "cadeia_ac", "presidente_qr", "divergencias", "erros",
                  "origem"]
        with open(a.saida_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
            w.writeheader()
            for lin in linhas:
                w.writerow({**lin, "divergencias": " | ".join(lin["divergencias"]),
                            "erros": " | ".join(lin["erros"])})
    return 1 if cont.get("DIVERGE") else 0


if __name__ == "__main__":
    sys.exit(main())
