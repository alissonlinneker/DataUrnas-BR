#!/usr/bin/env python3
"""Verificação dos resultados assinados (.jws) da divulgação do TSE, Eleições 2026.

O TSE publica cada arquivo de resultado em dois formatos: .json (dados) e .jws
(os mesmos dados assinados com EdDSA/Ed25519, JWS compacto). Este script:

  baixar      baixa os .jws de Presidente (Brasil, 28 UFs e todos os municípios do
              mun-eXXXXXX-cm.json) de um turno, em um único processo sequencial,
              com teto de requisições por segundo (padrão 3), retomável.
  chave       confere a chave pública oficial fixada abaixo: JWK x certificado
              X.509 da entidade final (mesma chave, kid = identificador da chave
              do certificado) e a cadeia até a AC raiz (assinaturas Ed448).
  verificar   verifica a assinatura de cada .jws com a chave fixada, confere o
              cabeçalho (alg, kid) e extrai o resumo do payload; opcionalmente
              confere que o payload é idêntico a uma versão do .json guardada pelo
              coletor (totais/<abr>/*.json.gz e totais/indice.jsonl).
  confrontar  compara o resumo de cada .jws com a soma dos BUs por abrangência
              (TSV exportado do ClickHouse) e lista toda divergência.

A chave NÃO é lida do próprio .jws: ela está fixada aqui, copiada do "Manual de
verificação dos arquivos JWS" do TSE (Apêndice B, ambiente oficial), conforme o
próprio manual recomenda.

Uso:
  python3 scripts/ele2026/verificar_jws.py chave
  python3 scripts/ele2026/verificar_jws.py baixar --turno 2 --saida data/raw/jws-2026
  python3 scripts/ele2026/verificar_jws.py verificar --turno 2 --dir data/raw/jws-2026 \
      --totais ~/dataurnas-versoes-t2/totais --saida verif-t2.jsonl
  python3 scripts/ele2026/verificar_jws.py confrontar --verif verif-t2.jsonl \
      --bu bu-t2.tsv --saida confronto-t2.csv
"""

from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import glob
import gzip
import hashlib
import http.client
import json
import os
import sys
import time
import urllib.parse
from pathlib import Path

BASE = "https://resultados.tse.jus.br/oficial/ele2026"
ELEICAO = {1: "6257", 2: "6258"}
CARGO = 1
UA = {"User-Agent": "Mozilla/5.0 (dataurnas-br verificacao jws)"}

# ---------------------------------------------------------------------------
# Chave oficial (Manual de verificação dos arquivos JWS, TSE, 16/09/2026,
# Apêndice B). Fonte: https://www.tse.jus.br/eleicoes/eleicoes-2026-content/
# arquivos/divulgacao-de-resultados/manual-verificacao-jws (captura do Web
# Archive 20261009105842, PDF de 8 páginas, SHA-256
# db1145145e98283689e53d3261c2f9188369d42c9e1e9db351b9e62c38684244).

JWK_OFICIAL = {
    "kty": "OKP",
    "use": "sig",
    "key_ops": ["verify"],
    "alg": "EdDSA",
    "kid": "sNbt9Q_fLS65zE1_ZLNV-XRRwPY",
    "crv": "Ed25519",
    "x": "kWlpNHjuws1csyQZwzn3Fhzbi3RD435RbpThtSr4hMc",
}

# Chave de desenvolvimento (Apêndice A): só para detectar arquivo assinado com ela.
KID_DESENVOLVIMENTO = "pEGrlis0i8vO2Bz7Ergwr0MnKfg"

CERT_ENTIDADE_FINAL = """-----BEGIN CERTIFICATE-----
MIIDaDCCAuigAwIBAgIDAQAAMAUGAytlcTCBjDELMAkGA1UEBhMCQlIxETAPBgNV
BAcMCEJyYXNpbGlhMSQwIgYDVQQKDBtUcmlidW5hbCBTdXBlcmlvciBFbGVpdG9y
YWwxDDAKBgNVBAsMA1NUSTEOMAwGA1UECwwFQ1NFTEUxDjAMBgNVBAsMBVNFVE9U
MRYwFAYDVQQDDA1BQyBESVZVTEdBQ0FPMB4XDTI2MDEwMTAzMDAwMFoXDTMxMDEw
MTAzMDAwMFowgacxCzAJBgNVBAYTAkJSMREwDwYDVQQHDAhCcmFzaWxpYTEkMCIG
A1UECgwbVHJpYnVuYWwgU3VwZXJpb3IgRWxlaXRvcmFsMQwwCgYDVQQLDANTVEkx
DjAMBgNVBAsMBUNTRUxFMQ4wDAYDVQQLDAVTRVRPVDExMC8GA1UEAwwoRUxFSUNP
RVMgMjAyNiAtIERJVlVMR0FDQU8gREUgUkVTVUxUQURPUzAqMAUGAytlcAMhAJFp
aTR47sLNXLMkGcM59xYc24t0Q+N+UW6U4bUq+ITHo4IBTjCCAUowDAYDVR0TAQH/
BAIwADAOBgNVHQ8BAf8EBAMCB4AwUgYDVR0fBEswSTBHoEWgQ4ZBaHR0cDovL2Fj
dG90LnRzZS5qdXMuYnIvdG90YWxpemFjYW8vb2ZpY2lhbC9jcmxzL2FjZGl2dWxn
YWNhby5jcmwwIwYNKwYBBAGDrUoBAQEBAQQSMRAGDisGAQQBg61KAQEBAQECMHEG
A1UdIARqMGgwZgYOKwYBBAGDrUoBAQEBAwIwVDBSBggrBgEFBQcCARZGaHR0cHM6
Ly9hY3RvdC50c2UuanVzLmJyL3RvdGFsaXphY2FvL29maWNpYWwvZG9jcy9kcGMt
YWNkaXZ1bGdhY2FvLnBkZjAdBgNVHQ4EFgQUsNbt9Q/fLS65zE1/ZLNV+XRRwPYw
HwYDVR0jBBgwFoAU21Z354+aquKmUdLxj8QSh85H7VAwBQYDK2VxA3MAXC6NTmDt
39NbPwTIgEMFCDWiBdMpPgv0f6RUf/5+pcLyEcTcjmJoQM9L9hsg5awflhEuWRDi
y2mACwkSjbgXRWPUv6fd+iXho94GdprpvbP6Ywx2QzuXCZ/sg291XLp26zXIMT31
zxVxZmjZJvBxRAUA
-----END CERTIFICATE-----
"""

CERT_AC_DIVULGACAO = """-----BEGIN CERTIFICATE-----
MIIDNzCCAregAwIBAgIDAQABMAUGAytlcTCBjTELMAkGA1UEBhMCQlIxETAPBgNV
BAcMCEJyYXNpbGlhMSQwIgYDVQQKDBtUcmlidW5hbCBTdXBlcmlvciBFbGVpdG9y
YWwxDDAKBgNVBAsMA1NUSTEOMAwGA1UECwwFQ1NFTEUxDjAMBgNVBAsMBVNFVE9U
MRcwFQYDVQQDDA5BQyBUT1RBTElaQUNBTzAeFw0yNjAxMDEwMzAwMDBaFw00MjAx
MDEwMzAwMDBaMIGMMQswCQYDVQQGEwJCUjERMA8GA1UEBwwIQnJhc2lsaWExJDAi
BgNVBAoMG1RyaWJ1bmFsIFN1cGVyaW9yIEVsZWl0b3JhbDEMMAoGA1UECwwDU1RJ
MQ4wDAYDVQQLDAVDU0VMRTEOMAwGA1UECwwFU0VUT1QxFjAUBgNVBAMMDUFDIERJ
VlVMR0FDQU8wQzAFBgMrZXEDOgB/QsALY5YIJqV6czSlqUfRDjD4x3A7dsRAD4bO
2YQPCOPMtl6ik+9lE3lY7QZUYR2Zb/0ot5yIMgCjggEeMIIBGjASBgNVHRMBAf8E
CDAGAQH/AgEAMA4GA1UdDwEB/wQEAwIBBjBLBgNVHR8ERDBCMECgPqA8hjpodHRw
Oi8vYWN0b3QudHNlLmp1cy5ici90b3RhbGl6YWNhby9vZmljaWFsL2NybHMvYWN0
b3QuY3JsMGcGA1UdIARgMF4wXAYEVR0gADBUMFIGCCsGAQUFBwIBFkZodHRwczov
L2FjdG90LnRzZS5qdXMuYnIvdG90YWxpemFjYW8vb2ZpY2lhbC9kb2NzL2RwYy1h
Y2RpdnVsZ2FjYW8ucGRmMB0GA1UdDgQWBBTbVnfnj5qq4qZR0vGPxBKHzkftUDAf
BgNVHSMEGDAWgBQU3O4Cu3fLGoCRyIxA1yIH6etVNzAFBgMrZXEDcwB5INmlMV9r
nXPBTVh/v+MfJzaC2tkikpwhpFWjwe+VivCM5iTnnmxpsENcqaO+68ykwcFe1BZp
4gD8IfMgzS5L2bdxcwhm+7HRGlV6fXuaXnn5Yjq1CZV78oZA69IvGrh3SCv0oStD
TTHiWrc352y+DwA=
-----END CERTIFICATE-----
"""

CERT_AC_RAIZ = """-----BEGIN CERTIFICATE-----
MIIDCTCCAomgAwIBAgIBATAFBgMrZXEwgY0xCzAJBgNVBAYTAkJSMREwDwYDVQQH
DAhCcmFzaWxpYTEkMCIGA1UECgwbVHJpYnVuYWwgU3VwZXJpb3IgRWxlaXRvcmFs
MQwwCgYDVQQLDANTVEkxDjAMBgNVBAsMBUNTRUxFMQ4wDAYDVQQLDAVTRVRPVDEX
MBUGA1UEAwwOQUMgVE9UQUxJWkFDQU8wHhcNMjYwMTAxMDMwMDAwWhcNNDIwMTAx
MDMwMDAwWjCBjTELMAkGA1UEBhMCQlIxETAPBgNVBAcMCEJyYXNpbGlhMSQwIgYD
VQQKDBtUcmlidW5hbCBTdXBlcmlvciBFbGVpdG9yYWwxDDAKBgNVBAsMA1NUSTEO
MAwGA1UECwwFQ1NFTEUxDjAMBgNVBAsMBVNFVE9UMRcwFQYDVQQDDA5BQyBUT1RB
TElaQUNBTzBDMAUGAytlcQM6ABDdWGsxF4NHKj0wl1Bl/onU8eqwvIMFFsJTTdoJ
iY9g2rYF9eIitStETJNle5c1GUQbEohphF97AKOB8jCB7zAPBgNVHRMBAf8EBTAD
AQH/MA4GA1UdDwEB/wQEAwIBBjBLBgNVHR8ERDBCMECgPqA8hjpodHRwOi8vYWN0
b3QudHNlLmp1cy5ici90b3RhbGl6YWNhby9vZmljaWFsL2NybHMvYWN0b3QuY3Js
MGAGA1UdIARZMFcwVQYEVR0gADBNMEsGCCsGAQUFBwIBFj9odHRwczovL2FjdG90
LnRzZS5qdXMuYnIvdG90YWxpemFjYW8vb2ZpY2lhbC9kb2NzL2RwYy1hY3RvdC5w
ZGYwHQYDVR0OBBYEFBTc7gK7d8sagJHIjEDXIgfp61U3MAUGAytlcQNzAFegim+F
df3FOedMCkHiBG4X8gg66goHqm8d5YnRmO3FM6wsw6u8gctmUfo/Ti7B9hA3y4fe
jbkggOCJ5Ykeo+yonU0XqPNh65odV2COzftTQXkVOK9O7LjPaI8lBhR+BAthyY1M
HOkFOyHxttOBTqsMAA==
-----END CERTIFICATE-----
"""


def agora() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def b64url_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def jwk_sha256() -> str:
    """SHA-256 da forma canônica da JWK (RFC 7638: crv, kty, x em ordem)."""
    canon = json.dumps({k: JWK_OFICIAL[k] for k in ("crv", "kty", "x")},
                       separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canon.encode()).hexdigest()


def chave_publica():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    return Ed25519PublicKey.from_public_bytes(b64url_dec(JWK_OFICIAL["x"]))


# ---------------------------------------------------------------------------
# Abrangências


def nome_arquivo(abr: str, turno: int, formato: str = "jws") -> str:
    return f"{abr}-c{CARGO:04d}-e{int(ELEICAO[turno]):06d}-u.{formato}"


def url_jws(abr: str, turno: int, formato: str = "jws") -> str:
    return (f"{BASE}/{ELEICAO[turno]}/dados/{abr[:2]}/"
            f"{nome_arquivo(abr, turno, formato)}")


_CONEXAO: http.client.HTTPSConnection | None = None


def http_get(url: str, tentativas: int = 10) -> tuple[int, dict, bytes]:
    """GET sequencial reaproveitando uma única conexão HTTPS (keep-alive), com
    novas tentativas espaçadas para 429/5xx e falhas de rede."""
    global _CONEXAO
    u = urllib.parse.urlsplit(url)
    espera = 2.0
    for i in range(tentativas):
        try:
            if _CONEXAO is None:
                _CONEXAO = http.client.HTTPSConnection(u.netloc, timeout=60)
            _CONEXAO.request("GET", u.path, headers={**UA, "Connection": "keep-alive"})
            r = _CONEXAO.getresponse()
            body = r.read()
            h = {k: v for k, v in r.getheaders()}
            if r.status in (429, 500, 502, 503, 504) and i < tentativas - 1:
                time.sleep(espera)
                espera = min(espera * 2, 120.0)
                continue
            return r.status, h, (body if r.status == 200 else b"")
        except (OSError, http.client.HTTPException):
            if _CONEXAO is not None:
                _CONEXAO.close()
            _CONEXAO = None
            if i < tentativas - 1:
                time.sleep(espera)
                espera = min(espera * 2, 120.0)
                continue
            raise
    raise RuntimeError("inalcançável")


def abrangencias(turno: int, saida: Path) -> list[str]:
    """br, as UFs (com zz) e os municípios do mun-eXXXXXX-cm.json do turno."""
    e = ELEICAO[turno]
    cm_path = saida / f"mun-e{int(e):06d}-cm.json"
    if not cm_path.exists():
        st, _, body = http_get(f"{BASE}/{e}/config/mun-e{int(e):06d}-cm.json")
        if st != 200:
            raise SystemExit(f"cm.json indisponível: HTTP {st}")
        cm_path.write_bytes(body)
        time.sleep(0.34)
    cm = json.loads(cm_path.read_bytes())
    ufs, muns = [], []
    for a in cm["abr"]:
        uf = a["cd"].lower()
        ufs.append(uf)
        muns += [f"{uf}{m['cd']}" for m in a["mu"]]
    return ["br"] + sorted(ufs) + sorted(muns)


# ---------------------------------------------------------------------------
# baixar


def hdr(h: dict, nome: str) -> str | None:
    for k, v in h.items():
        if k.lower() == nome.lower():
            return v
    return None


def cmd_baixar(a: argparse.Namespace) -> int:
    saida = Path(a.saida) / (f"t{a.turno}" + ("" if a.formato == "jws" else "-json"))
    saida.mkdir(parents=True, exist_ok=True)
    abrs = abrangencias(a.turno, saida)
    if a.lista:
        quero = set(Path(a.lista).read_text(encoding="utf-8").split())
        abrs = [x for x in abrs if x in quero]
    manifesto = saida / "manifesto.jsonl"
    feitos = set()
    if manifesto.exists():
        for ln in manifesto.read_text(encoding="utf-8").splitlines():
            r = json.loads(ln)
            if r.get("status") == 200:
                feitos.add(r["abr"])
    intervalo = 1.0 / a.rps
    pend = [x for x in abrs if x not in feitos]
    print(f"turno {a.turno} ({a.formato}): {len(abrs)} abrangências, {len(pend)} a baixar "
          f"a no máximo {a.rps} req/s", flush=True)
    ult = 0.0
    with open(manifesto, "a", encoding="utf-8") as fm:
        for i, abr in enumerate(pend, 1):
            folga = intervalo - (time.monotonic() - ult)
            if folga > 0:
                time.sleep(folga)
            ult = time.monotonic()
            url = url_jws(abr, a.turno, a.formato)
            st, h, body = http_get(url)
            r = {"abr": abr, "url": url, "status": st, "baixado_em": agora(),
                 "last_modified": hdr(h, "Last-Modified"), "etag": hdr(h, "ETag"), "tamanho": len(body),
                 "sha256": hashlib.sha256(body).hexdigest() if body else None}
            if st == 200:
                d = saida / abr[:2]
                d.mkdir(exist_ok=True)
                tmp = d / (nome_arquivo(abr, a.turno, a.formato) + ".tmp")
                tmp.write_bytes(body)
                tmp.replace(d / nome_arquivo(abr, a.turno, a.formato))
            fm.write(json.dumps(r, ensure_ascii=False) + "\n")
            fm.flush()
            if i % 250 == 0 or st != 200:
                print(f"{i}/{len(pend)} {abr} HTTP {st}", flush=True)
    print("concluído", flush=True)
    return 0


# ---------------------------------------------------------------------------
# chave


def cmd_chave(a: argparse.Namespace) -> int:
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization

    certs = {n: x509.load_pem_x509_certificate(p.encode()) for n, p in (
        ("entidade_final", CERT_ENTIDADE_FINAL),
        ("ac_divulgacao", CERT_AC_DIVULGACAO),
        ("ac_totalizacao", CERT_AC_RAIZ))}
    ef = certs["entidade_final"]
    pub_cert = ef.public_key().public_bytes(serialization.Encoding.Raw,
                                            serialization.PublicFormat.Raw)
    ski = ef.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value.digest
    ok = True
    print(f"JWK oficial kid={JWK_OFICIAL['kid']} x={JWK_OFICIAL['x']}")
    print(f"SHA-256 da chave pública bruta (32 bytes): "
          f"{hashlib.sha256(b64url_dec(JWK_OFICIAL['x'])).hexdigest()}")
    print(f"Impressão digital RFC 7638 (SHA-256 da JWK canônica): {jwk_sha256()}")
    for n, c in certs.items():
        print(f"{n}: {c.subject.rfc4514_string()} | serial {c.serial_number} | "
              f"{c.not_valid_before_utc:%Y-%m-%d} a {c.not_valid_after_utc:%Y-%m-%d} | "
              f"SHA-256 DER {hashlib.sha256(c.public_bytes(serialization.Encoding.DER)).hexdigest()}")
    r = pub_cert == b64url_dec(JWK_OFICIAL["x"])
    ok &= r
    print(f"chave do certificado da entidade final == JWK x: {r}")
    r = base64.urlsafe_b64encode(ski).rstrip(b"=").decode() == JWK_OFICIAL["kid"]
    ok &= r
    print(f"kid == identificador da chave (SKI) do certificado: {r}")
    for filho, pai in (("entidade_final", "ac_divulgacao"),
                       ("ac_divulgacao", "ac_totalizacao"),
                       ("ac_totalizacao", "ac_totalizacao")):
        try:
            certs[filho].verify_directly_issued_by(certs[pai])
            r = True
        except Exception as e:  # noqa: BLE001
            print(f"  falha {filho} <- {pai}: {e!r}")
            r = False
        ok &= r
        print(f"{filho} assinado por {pai}: {r}")
    print("RESULTADO:", "chave e cadeia conferem" if ok else "FALHA")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# verificar


def int0(x) -> int | None:
    try:
        return int(str(x))
    except (TypeError, ValueError):
        return None


def resumo_payload(d: dict) -> dict:
    s, e, v = d.get("s") or {}, d.get("e") or {}, d.get("v") or {}
    cand = {}
    for carg in d.get("carg") or []:
        for agr in carg.get("agr") or []:
            for par in agr.get("par") or []:
                for c in par.get("cand") or []:
                    cand[str(c.get("n"))] = int0(c.get("vap"))
    return {
        "ele": d.get("ele"), "t": d.get("t"), "tpabr": d.get("tpabr"),
        "cdabr": d.get("cdabr"), "dg": d.get("dg"), "hg": d.get("hg"),
        "idg": d.get("idg"), "dt": d.get("dt"), "ht": d.get("ht"),
        "tf": d.get("tf"), "and": d.get("and"),
        "ts": int0(s.get("ts")), "st": int0(s.get("st")),
        "si": int0(s.get("si")), "sni": int0(s.get("sni")),
        "eleitores": int0(e.get("te")), "eleitores_instaladas": int0(e.get("esi")), "comparecimento": int0(e.get("c")),
        "abstencao": int0(e.get("a")), "tv": int0(v.get("tv")),
        "vv": int0(v.get("vv")), "vb": int0(v.get("vb")),
        "tvn": int0(v.get("tvn")), "vn": int0(v.get("vn")),
        "vnt": int0(v.get("vnt")) or 0,
        "v13": cand.get("13"), "v22": cand.get("22"),
        "outros": sum(q or 0 for n, q in cand.items() if n not in ("13", "22")),
        "candidatos": len(cand),
    }


def carregar_totais(dirs: list[str]) -> tuple[dict, dict]:
    """sha256 -> (abr, idg) das versões de .json guardadas pelos coletores e
    abr -> {idg: caminho .json.gz}."""
    por_sha: dict[str, tuple[str, str]] = {}
    por_abr: dict[str, dict[str, str]] = {}
    for d in dirs:
        d = os.path.expanduser(d)
        idx = os.path.join(d, "indice.jsonl")
        if os.path.exists(idx):
            with open(idx, encoding="utf-8") as fh:
                for ln in fh:
                    r = json.loads(ln)
                    por_sha[r["sha256"]] = (r["abr"], str(r.get("idg")))
        for p in glob.glob(os.path.join(d, "*", "*.json.gz")):
            abr = os.path.basename(os.path.dirname(p))
            idg = os.path.basename(p)[:-8].rsplit("_", 1)[-1]
            por_abr.setdefault(abr, {})[idg] = p
    return por_sha, por_abr


def verificar_um(path: Path, pub) -> dict:
    from cryptography.exceptions import InvalidSignature

    txt = path.read_bytes().strip()
    r: dict = {"arquivo": str(path), "sha256_jws": hashlib.sha256(txt).hexdigest()}
    partes = txt.split(b".")
    if len(partes) != 3:
        r.update(assinatura="malformado", erro=f"{len(partes)} partes")
        return r
    h64, p64, s64 = partes
    try:
        hdr = json.loads(b64url_dec(h64.decode()))
    except Exception as e:  # noqa: BLE001
        r.update(assinatura="malformado", erro=f"cabeçalho: {e!r}")
        return r
    r["alg"], r["kid"] = hdr.get("alg"), hdr.get("kid")
    r["cabecalho"] = json.dumps(hdr, ensure_ascii=False, sort_keys=True)
    try:
        pub.verify(b64url_dec(s64.decode()), h64 + b"." + p64)
        valida = True
    except InvalidSignature:
        valida = False
    # controle negativo: o mesmo conteúdo com um bit trocado tem de ser recusado
    alterado = bytearray(h64 + b"." + p64)
    alterado[len(h64) + 1 + len(p64) // 2] ^= 0x01
    try:
        pub.verify(b64url_dec(s64.decode()), bytes(alterado))
        r["controle_negativo"] = "FALHOU"
    except InvalidSignature:
        r["controle_negativo"] = "recusado"
    if hdr.get("alg") != "EdDSA" or hdr.get("kid") != JWK_OFICIAL["kid"]:
        r["assinatura"] = "valida_cabecalho_inesperado" if valida else "invalida"
        if hdr.get("kid") == KID_DESENVOLVIMENTO:
            r["erro"] = "kid de desenvolvimento"
    else:
        r["assinatura"] = "valida" if valida else "invalida"
    payload = b64url_dec(p64.decode())
    r["sha256_payload"] = hashlib.sha256(payload).hexdigest()
    r["tamanho_payload"] = len(payload)
    try:
        r.update(resumo_payload(json.loads(payload)))
    except Exception as e:  # noqa: BLE001
        r["erro"] = f"payload: {e!r}"
    return r


def cmd_verificar(a: argparse.Namespace) -> int:
    pub = chave_publica()
    base = Path(a.dir) / f"t{a.turno}"
    man = {}
    mp = base / "manifesto.jsonl"
    if mp.exists():
        for ln in mp.read_text(encoding="utf-8").splitlines():
            x = json.loads(ln)
            if x.get("status") == 200:
                man[x["abr"]] = x
    por_sha, por_abr = carregar_totais(a.totais or [])
    arquivos = sorted(base.glob("*/*.jws"))
    cont: dict[str, int] = {}
    with open(a.saida, "w", encoding="utf-8") as fo:
        for p in arquivos:
            abr = p.name.split("-")[0]
            r = {"abr": abr, "turno": a.turno, **verificar_um(p, pub)}
            # o payload assinado tem de ser da abrangência e da eleição do arquivo
            cd = str(r.get("cdabr") or "").lower()
            r["abrangencia_confere"] = (cd in (abr, abr[2:]) and
                                        r.get("ele") == ELEICAO[a.turno] and
                                        r.get("t") == str(a.turno))
            if not r["abrangencia_confere"]:
                cont["abrangencia_nao_confere"] = cont.get("abrangencia_nao_confere", 0) + 1
            m = man.get(abr) or {}
            r["last_modified"] = m.get("last_modified")
            r["baixado_em"] = m.get("baixado_em")
            jd = Path(a.json_dir) / abr[:2] / nome_arquivo(abr, a.turno, "json") \
                if a.json_dir else None
            if jd is not None and jd.exists():
                corpo = jd.read_bytes()
                payload = b64url_dec(p.read_bytes().strip().split(b".")[1].decode())
                if corpo == payload:
                    r["json_publicado"] = "identico"
                elif json.loads(corpo) == json.loads(payload):
                    r["json_publicado"] = "mesmo_conteudo_bytes_diferentes"
                else:
                    r["json_publicado"] = "DIFERENTE"
                r["sha256_json_publicado"] = hashlib.sha256(corpo).hexdigest()
                k = "json_publicado_" + r["json_publicado"]
                cont[k] = cont.get(k, 0) + 1
            if a.totais:
                hit = por_sha.get(r.get("sha256_payload", ""))
                if hit and hit[0] == abr:
                    r["json_coletor"] = "identico"
                    r["json_idg"] = hit[1]
                else:
                    cam = (por_abr.get(abr) or {}).get(str(r.get("idg")))
                    if cam:
                        corpo = gzip.decompress(Path(cam).read_bytes())
                        payload = b64url_dec(p.read_bytes().strip().split(b".")[1].decode())
                        if corpo == payload:
                            r["json_coletor"] = "identico"
                        elif json.loads(corpo) == json.loads(payload):
                            r["json_coletor"] = "mesmo_conteudo_bytes_diferentes"
                        else:
                            r["json_coletor"] = "DIFERENTE"
                        r["json_idg"] = str(r.get("idg"))
                    else:
                        r["json_coletor"] = "sem_versao_do_mesmo_idg"
                cont["json_" + r["json_coletor"]] = cont.get("json_" + r["json_coletor"], 0) + 1
            cont[r.get("assinatura", "?")] = cont.get(r.get("assinatura", "?"), 0) + 1
            k = "controle_negativo_" + str(r.get("controle_negativo"))
            cont[k] = cont.get(k, 0) + 1
            fo.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps({"turno": a.turno, "arquivos": len(arquivos), **cont},
                     ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# confrontar

# (coluna do TSV da soma dos BUs, campo do resumo do .jws). Seções com BU são
# comparadas com as seções instaladas (si) e os aptos com o eleitorado das seções
# instaladas (esi): seção não instalada não tem BU. A abstenção do TSE é
# esi - comparecimento. Nulos: o BU registra o voto em número de candidato cujo
# registro foi indeferido depois como voto nominal; o TSE o soma como nulo técnico
# (vnt) e deixa vn só com os nulos digitados. Por isso o BU "nulos" se compara com
# vn e o BU "outros" (nominais fora de 13 e 22) com outros + vnt.
CAMPOS = (("secoes", "si"), ("aptos", "eleitores_instaladas"),
          ("comparecimento", "comparecimento"), ("abstencao", "abstencao"),
          ("votos_13", "v13"), ("votos_22", "v22"), ("brancos", "vb"),
          ("nulos", "vn"), ("outros", "outros_mais_vnt"))


def cmd_confrontar(a: argparse.Namespace) -> int:
    """TSV do ClickHouse com cabeçalho: abr, secoes, aptos, comparecimento,
    abstencao, votos_13, votos_22, brancos, nulos[, outros]."""
    bu = {}
    with open(a.bu, encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            bu[r["abr"]] = r
    n_div = 0
    niveis: dict[str, int] = {}
    with open(a.verif, encoding="utf-8") as fv, open(a.saida, "w", newline="",
                                                    encoding="utf-8") as fo:
        w = csv.writer(fo)
        w.writerow(["abr", "campo", "jws", "soma_bu", "diferenca"])
        for ln in fv:
            v = json.loads(ln)
            abr = v["abr"]
            niv = "br" if abr == "br" else ("uf" if len(abr) == 2 else "municipio")
            niveis[niv] = niveis.get(niv, 0) + 1
            b = bu.get(abr)
            if b is None:
                # abrangência sem nenhum BU (por exemplo, cidade do exterior sem
                # seção instalada): a soma dos BUs é zero em todos os campos
                b = {cb: "0" for cb, _ in CAMPOS}
            v["outros_mais_vnt"] = (v.get("outros") or 0) + (v.get("vnt") or 0)
            for cb, cj in CAMPOS:
                if cb not in b or b[cb] in ("", None) or v.get(cj) is None:
                    continue
                x, y = int(v[cj]), int(b[cb])
                if x != y:
                    w.writerow([abr, cb, x, y, x - y])
                    n_div += 1
    print(json.dumps({"abrangencias": niveis, "divergencias": n_div},
                     ensure_ascii=False))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("baixar")
    b.add_argument("--turno", type=int, choices=(1, 2), required=True)
    b.add_argument("--saida", required=True)
    b.add_argument("--rps", type=float, default=3.0)
    b.add_argument("--formato", choices=("jws", "json"), default="jws")
    b.add_argument("--lista", help="arquivo com as abrangências a baixar (uma por linha)")
    sub.add_parser("chave")
    v = sub.add_parser("verificar")
    v.add_argument("--turno", type=int, choices=(1, 2), required=True)
    v.add_argument("--dir", required=True)
    v.add_argument("--totais", nargs="*", help="pastas totais/ dos coletores")
    v.add_argument("--json-dir", help="pasta t<turno>-json/ com os .json baixados agora")
    v.add_argument("--saida", required=True)
    c = sub.add_parser("confrontar")
    c.add_argument("--verif", required=True)
    c.add_argument("--bu", required=True)
    c.add_argument("--saida", required=True)
    a = ap.parse_args()
    if a.rps if a.cmd == "baixar" else 0:
        if a.rps > 3:
            raise SystemExit("teto de 3 req/s")
    return {"baixar": cmd_baixar, "chave": cmd_chave, "verificar": cmd_verificar,
            "confrontar": cmd_confrontar}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
