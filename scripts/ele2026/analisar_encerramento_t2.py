#!/usr/bin/env python3
"""Horário de abertura e encerramento das seções no 2º turno de 2026.

Lê os BUs versionados por versionar_t2.py (bus/parts/versoes-*.parquet), de um
ou mais diretórios com a mesma estrutura (por exemplo, a coleta deste
computador e a do servidor remoto), decodifica cada BU e converte os horários
gravados pela urna (horário LOCAL do município) para o horário de Brasília.

Contexto: em 25/10/2026 a votação foi prorrogada até as 19h onde ainda não
tinha sido encerrada às 17h (ver docs/prorrogacao-votacao-2turno-2026.md). O
objetivo é descrever, com os dados públicos, quais seções encerraram depois do
horário normal e se há inconsistência nelas. A análise é só descritiva.

Saída em data/parquet/2026/t2/encerramento/ (ignorada pelo git):
  secoes_encerramento.parquet   uma linha por seção do Brasil (última versão do BU)
  secoes_exterior.parquet       seções do exterior (fuso de cada país, sem conversão)
  versoes_multiplas.parquet     seções com mais de uma versão de BU (todas as versões)
  resumo.json                   distribuição por UF e faixa, seções tardias, resultados

Uso:
  python3 scripts/ele2026/analisar_encerramento_t2.py
  python3 scripts/ele2026/analisar_encerramento_t2.py --parts DIR1 --parts DIR2
  python3 scripts/ele2026/analisar_encerramento_t2.py --municipios mun-e006258-cm.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

ROOT = Path(__file__).resolve().parents[2]
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

log = logging.getLogger("analisar_encerramento_t2")

ELEICAO = 6258
CARGO = 1
DIA = "20261025"
PARTS_PADRAO = ROOT / "data" / "versoes" / "2026" / "t2" / "bus" / "parts"
SAIDA_PADRAO = ROOT / "data" / "parquet" / "2026" / "t2" / "encerramento"
URL_MUNICIPIOS = ("https://resultados.tse.jus.br/oficial/ele2026/6258/config/"
                  "mun-e006258-cm.json")

# ---------------------------------------------------------------------------
# Fusos horários (offset em horas em relação ao UTC), 25/10/2026.
#
# Não há horário de verão no Brasil em 2026 (extinto pelo Decreto 9.772/2019),
# então os offsets abaixo valem o dia inteiro. Brasília = UTC-3.
#
#   UTC-5  AC inteiro e 11 municípios do oeste do AM (lista FUSO_MUNICIPIO)
#   UTC-4  AM (demais municípios), MT, MS, RO, RR
#   UTC-2  Fernando de Noronha (PE, código TSE 30015)
#   UTC-3  demais UFs e municípios
#   exterior ('zz'): fuso de cada país; NÃO convertido, vai para tabela à parte
#
# Municípios do AM em UTC-5: determinados pelos próprios BUs de 25/10/2026. Nos
# municípios abaixo o encerramento normal está gravado às 15h00 locais (17h00
# de Brasília), e o recebimento pelo TSE (hr_recebimento, horário de Brasília)
# vem minutos depois de 17h00; nos demais municípios do AM o encerramento
# normal está às 16h00 locais. Boca do Acre, Pauini e Lábrea aparecem em UTC-4.
# A verificação de consistência (ver verificar_fusos) refaz esse teste a cada
# execução e acusa município cuja mediana de encerramento fuja das 17h00.
# ---------------------------------------------------------------------------

UTC_BRASILIA = -3

FUSO_UF: dict[str, int] = {
    "ac": -5,
    "am": -4,
    "mt": -4,
    "ms": -4,
    "ro": -4,
    "rr": -4,
}

FUSO_MUNICIPIO: dict[str, int] = {
    # AM, UTC-5
    "02020": -5,  # Guajará
    "02054": -5,  # Atalaia do Norte
    "02135": -5,  # Benjamin Constant
    "02291": -5,  # Eirunepé
    "02313": -5,  # Envira
    "02399": -5,  # Ipixuna
    "02496": -5,  # Jutaí
    "02755": -5,  # São Paulo de Olivença
    "02917": -5,  # Amaturá
    "98370": -5,  # Itamarati
    "98477": -5,  # Tabatinga
    # PE, UTC-2
    "30015": -2,  # Fernando de Noronha
}

# Faixas de encerramento em horário de Brasília, pelo minuto (HH:MM, segundos
# desprezados). "ate_17h10" inclui qualquer horário até 17:10:59.
FAIXAS = (
    ("ate_17h10", "até 17:10"),
    ("17h11_17h30", "17:11 a 17:30"),
    ("17h31_18h00", "17:31 a 18:00"),
    ("18h01_19h00", "18:01 a 19:00"),
    ("depois_19h00", "depois de 19:00"),
)
ROTULO_FAIXA = dict(FAIXAS)

CANDIDATOS = (13, 22)


def fuso_utc(uf: str, cd_mun: str) -> Optional[int]:
    """Offset UTC (horas) do município; None para o exterior ('zz')."""
    uf = (uf or "").lower()
    if uf == "zz":
        return None
    cd = str(cd_mun).zfill(5)
    if cd in FUSO_MUNICIPIO:
        return FUSO_MUNICIPIO[cd]
    return FUSO_UF.get(uf, UTC_BRASILIA)


def parse_hora_urna(valor: Optional[str]) -> Optional[datetime]:
    """'20261025T150046' (formato do BU) para datetime ingênuo; None se vazio."""
    if not valor:
        return None
    try:
        return datetime.strptime(str(valor)[:15], "%Y%m%dT%H%M%S")
    except ValueError:
        return None


def para_brasilia(local: Optional[datetime], utc: Optional[int]) -> Optional[datetime]:
    """Converte horário local (offset utc) para horário de Brasília (UTC-3)."""
    if local is None or utc is None:
        return None
    return local + timedelta(hours=UTC_BRASILIA - utc)


def minutos_apos_17h(bsb: Optional[datetime], dia: str = DIA) -> Optional[float]:
    """Minutos (com fração) entre 17:00:00 de Brasília do dia e o horário dado."""
    if bsb is None:
        return None
    ref = datetime.strptime(dia, "%Y%m%d").replace(hour=17)
    return round((bsb - ref).total_seconds() / 60.0, 2)


def faixa_encerramento(bsb: Optional[datetime], dia: str = DIA) -> Optional[str]:
    """Faixa do encerramento (horário de Brasília), pelo minuto truncado."""
    if bsb is None:
        return None
    ref = datetime.strptime(dia, "%Y%m%d").replace(hour=17)
    minuto = (bsb.replace(second=0, microsecond=0) - ref).total_seconds() // 60
    if minuto <= 10:
        return "ate_17h10"
    if minuto <= 30:
        return "17h11_17h30"
    if minuto <= 60:
        return "17h31_18h00"
    if minuto <= 120:
        return "18h01_19h00"
    return "depois_19h00"


def fmt(dt: Optional[datetime]) -> Optional[str]:
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

COLUNAS = ["coletado_em", "uf", "cd_mun", "zona", "secao", "tipo", "hash",
           "st_secao", "dt_recebimento", "hr_recebimento", "nome", "sha512",
           "tamanho", "conteudo"]


def iter_bus(dirs: Iterable[Path]) -> Iterable[dict]:
    """Registros de BU (tipo bu ou busa) de todos os parts, arquivo a arquivo."""
    for d in dirs:
        arquivos = sorted(Path(d).glob("versoes-*.parquet"))
        log.info("%s: %d arquivos", d, len(arquivos))
        for f in arquivos:
            try:
                nomes = set(pq.read_schema(f).names)
                cols = [c for c in COLUNAS if c in nomes]
                t = pq.read_table(f, columns=cols,
                                  filters=[("tipo", "in", ["bu", "busa"])])
            except Exception as e:  # part em gravação ou corrompido
                log.warning("ignorado %s: %s", f.name, e)
                continue
            for r in t.to_pylist():
                r["origem_part"] = f"{Path(d).name}/{f.name}"
                yield r


def _decodificar(raw: bytes) -> tuple[Optional[dict], Optional[list], Optional[str]]:
    from dataurnas.downloader.ele2026 import bu_to_rows
    try:
        c, v = bu_to_rows(raw, ELEICAO, CARGO)
        return c, v, None
    except Exception as e:  # BU ilegível vira linha com erro, não some
        return None, None, f"{type(e).__name__}: {e}"


def carregar_municipios(caminho: Optional[str], saida: Path) -> dict[str, str]:
    """{cd_mun: nome}. Lê o arquivo dado, o cache em saida ou baixa do TSE."""
    cache = saida / "municipios.json"
    fonte = Path(caminho) if caminho else cache
    try:
        if not fonte.exists():
            with urllib.request.urlopen(URL_MUNICIPIOS, timeout=30) as resp:
                fonte.write_bytes(resp.read())
        cm = json.loads(fonte.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("sem nomes de municípios (%s)", e)
        return {}
    return {mu["cd"]: mu.get("nm") for abr in cm.get("abr", []) for mu in abr.get("mu", [])}


# ---------------------------------------------------------------------------
# Linha por seção
# ---------------------------------------------------------------------------

def _hms_recebimento(dt_rec: Optional[str], hr_rec: Optional[str]) -> Optional[datetime]:
    """dt_recebimento '25/10/2026' + hr_recebimento '19:32:29' (Brasília)."""
    if not dt_rec or not hr_rec:
        return None
    try:
        return datetime.strptime(f"{dt_rec} {hr_rec}", "%d/%m/%Y %H:%M:%S")
    except ValueError:
        return None


def inconsistencias(linha: dict) -> list[str]:
    """Verificações internas do BU e de horário. Lista vazia = nada a apontar."""
    out = []
    ab, en = linha["abertura_local_dt"], linha["encerramento_local_dt"]
    em = linha["emissao_local_dt"]
    if ab is None:
        out.append("sem_hora_abertura")
    if en is None:
        out.append("sem_hora_encerramento")
    if ab and en and en <= ab:
        out.append("encerramento_antes_abertura")
    if en and em and em < en:
        out.append("emissao_antes_encerramento")
    for nome, dt in (("abertura", ab), ("encerramento", en), ("emissao", em)):
        if dt and dt.strftime("%Y%m%d") != DIA:
            out.append(f"{nome}_fora_do_dia")
    if ab and not (6 <= ab.hour < 9):
        out.append("abertura_fora_de_06h_09h_local")
    bsb_em, rec = linha["emissao_bsb_dt"], linha["recebimento_bsb_dt"]
    if bsb_em and rec and rec < bsb_em:
        out.append("recebimento_antes_emissao")
    bsb_en = linha["encerramento_bsb_dt"]
    if bsb_en and bsb_en.replace(second=0) < bsb_en.replace(hour=17, minute=0, second=0):
        out.append("encerramento_antes_17h_bsb")
    apt, comp = linha["aptos"], linha["comparecimento"]
    if apt is not None and comp is not None and comp > apt:
        out.append("comparecimento_maior_que_aptos")
    if comp is not None and linha["votos_total"] != comp:
        out.append("soma_votos_difere_comparecimento")
    if not linha["tem_presidente"]:
        out.append("sem_cargo_presidente")
    return out


def montar_linha(reg: dict, campos: Optional[dict], votos: Optional[list],
                 erro: Optional[str], nomes_mun: dict[str, str]) -> dict:
    uf = reg["uf"]
    cd = str(reg["cd_mun"]).zfill(5)
    utc = fuso_utc(uf, cd)
    c = campos or {}
    ab = parse_hora_urna(c.get("hora_abertura"))
    en = parse_hora_urna(c.get("hora_encerramento"))
    em = parse_hora_urna(c.get("data_hora_emissao"))
    por_num = defaultdict(int)
    for v in votos or []:
        if v["tipo_voto"] == "nominal" and v["numero"] is not None:
            por_num[int(v["numero"])] += v["votos"] or 0
    linha = {
        "uf": uf, "cd_mun": cd, "municipio": nomes_mun.get(cd),
        "zona": reg["zona"], "secao": reg["secao"],
        "tipo_arquivo": reg["tipo"], "nome_arquivo": reg.get("nome"),
        "hash": reg.get("hash"), "sha512": reg.get("sha512"),
        "coletado_em": reg.get("coletado_em"), "origem_part": reg.get("origem_part"),
        "st_secao": reg.get("st_secao"),
        "fuso_utc": utc,
        "abertura_local_dt": ab, "encerramento_local_dt": en, "emissao_local_dt": em,
        "abertura_bsb_dt": para_brasilia(ab, utc),
        "encerramento_bsb_dt": para_brasilia(en, utc),
        "emissao_bsb_dt": para_brasilia(em, utc),
        "recebimento_bsb_dt": _hms_recebimento(reg.get("dt_recebimento"),
                                               reg.get("hr_recebimento")),
        "tipo_urna": c.get("tipo_urna"),
        "aptos": c.get("aptos"), "comparecimento": c.get("comparecimento"),
        "votos_13": por_num.get(13, 0), "votos_22": por_num.get(22, 0),
        "votos_outros_nominais": sum(q for n, q in por_num.items() if n not in CANDIDATOS),
        "votos_brancos": c.get("votos_brancos"), "votos_nulos": c.get("votos_nulos"),
        "votos_total": c.get("votos_total"), "tem_presidente": bool(c.get("tem_presidente")),
        "erro_decodificacao": erro,
    }
    linha["minutos_apos_17h_bsb"] = minutos_apos_17h(linha["encerramento_bsb_dt"])
    linha["faixa"] = faixa_encerramento(linha["encerramento_bsb_dt"])
    linha["inconsistencias"] = ",".join(inconsistencias(linha)) if campos else "bu_ilegivel"
    return linha


def finalizar(linha: dict) -> dict:
    """Troca os datetime auxiliares por texto (local e Brasília)."""
    out = {}
    for k, v in linha.items():
        if k.endswith("_dt"):
            out[k[:-3]] = fmt(v)
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Deduplicação e verificações
# ---------------------------------------------------------------------------

def deduplicar(linhas: list[dict]) -> tuple[list[dict], list[dict]]:
    """Uma linha por seção (última versão coletada). O mesmo BU visto em mais de
    um diretório (mesmo SHA-512) conta como uma versão só. Devolve (principal,
    todas_as_versoes_das_secoes_com_mais_de_uma)."""
    grupos: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for ln in linhas:
        k = (ln["uf"], ln["cd_mun"], ln["zona"], ln["secao"])
        ident = ln.get("sha512") or ln.get("hash") or ln.get("nome_arquivo")
        atual = grupos[k].get(ident)
        if atual is None or (ln.get("coletado_em") or "") < (atual.get("coletado_em") or ""):
            grupos[k][ident] = ln  # guarda a primeira coleta de cada versão
    principal, multiplas = [], []
    for _k, versoes in grupos.items():
        vs = sorted(versoes.values(), key=lambda x: x.get("coletado_em") or "")
        ultima = dict(vs[-1])
        ultima["n_versoes_bu"] = len(vs)
        principal.append(ultima)
        if len(vs) > 1:
            for i, v in enumerate(vs, 1):
                multiplas.append({**v, "versao": i, "n_versoes_bu": len(vs)})
    return principal, multiplas


def verificar_fusos(linhas: list[dict]) -> list[dict]:
    """Municípios cuja mediana de encerramento em Brasília fuja de 17:00 por
    mais de 30 minutos: sinal de fuso errado na tabela (ou de prorrogação geral
    no município). Só municípios com 5 ou mais seções."""
    por_mun = defaultdict(list)
    for ln in linhas:
        if ln["minutos_apos_17h_bsb"] is not None:
            por_mun[(ln["uf"], ln["cd_mun"])].append(ln["minutos_apos_17h_bsb"])
    alertas = []
    for (uf, cd), ms in sorted(por_mun.items()):
        if len(ms) < 5:
            continue
        ms.sort()
        med = ms[len(ms) // 2]
        if abs(med) > 30:
            alertas.append({"uf": uf, "cd_mun": cd, "secoes": len(ms),
                            "mediana_min_apos_17h": med})
    return alertas


# ---------------------------------------------------------------------------
# Resumo
# ---------------------------------------------------------------------------

def _pct(a: int, b: int) -> Optional[float]:
    return round(100.0 * a / b, 3) if b else None


def agregar_resultado(linhas: list[dict]) -> dict:
    s = {"secoes": len(linhas)}
    for k in ("aptos", "comparecimento", "votos_13", "votos_22", "votos_outros_nominais",
              "votos_brancos", "votos_nulos"):
        s[k] = sum(int(ln.get(k) or 0) for ln in linhas)
    validos = s["votos_13"] + s["votos_22"] + s["votos_outros_nominais"]
    s["validos"] = validos
    s["pct_13_validos"] = _pct(s["votos_13"], validos)
    s["pct_22_validos"] = _pct(s["votos_22"], validos)
    s["pct_brancos_comparecimento"] = _pct(s["votos_brancos"], s["comparecimento"])
    s["pct_nulos_comparecimento"] = _pct(s["votos_nulos"], s["comparecimento"])
    s["pct_comparecimento_aptos"] = _pct(s["comparecimento"], s["aptos"])
    return s


def grupo_horario(faixa: Optional[str]) -> str:
    if faixa == "ate_17h10":
        return "no_horario"
    if faixa == "17h11_17h30":
        return "intermediario"
    if faixa is None:
        return "sem_horario"
    return "tarde"


CAMPOS_LISTA = ("uf", "cd_mun", "municipio", "zona", "secao", "tipo_arquivo",
                "abertura_local", "encerramento_local", "emissao_local",
                "encerramento_bsb", "recebimento_bsb", "minutos_apos_17h_bsb", "faixa",
                "aptos", "comparecimento", "votos_13", "votos_22", "votos_brancos",
                "votos_nulos", "n_versoes_bu", "inconsistencias")


def montar_resumo(linhas: list[dict], exterior: list[dict], multiplas: list[dict],
                  alertas_fuso: list[dict], dirs: list[str], erros: int) -> dict:
    por_uf_faixa: dict[str, Counter] = defaultdict(Counter)
    for ln in linhas:
        por_uf_faixa[ln["uf"]][ln["faixa"] or "sem_horario"] += 1
    total = Counter()
    for c in por_uf_faixa.values():
        total.update(c)

    tardias = sorted((ln for ln in linhas
                      if ln["minutos_apos_17h_bsb"] is not None
                      and ln["minutos_apos_17h_bsb"] >= 31),
                     key=lambda x: -x["minutos_apos_17h_bsb"])

    por_uf_grupo: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for ln in linhas:
        g = grupo_horario(ln["faixa"])
        por_uf_grupo[ln["uf"]][g].append(ln)
        por_uf_grupo["_brasil"][g].append(ln)

    inc = Counter()
    inc_tardias = Counter()
    for ln in linhas:
        for i in filter(None, (ln["inconsistencias"] or "").split(",")):
            inc[i] += 1
            if grupo_horario(ln["faixa"]) == "tarde":
                inc_tardias[i] += 1

    return {
        "gerado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
        "diretorios": dirs,
        "observacao": ("Dados parciais enquanto a coleta continua. Horários do BU "
                       "convertidos do fuso do município para Brasília (UTC-3). "
                       "Faixas pelo minuto do encerramento; 'tarde' = depois de 17:30. "
                       "Descritivo, sem inferência causal."),
        "faixas": dict(FAIXAS),
        "secoes_brasil": len(linhas),
        "secoes_exterior": len(exterior),
        "secoes_com_versoes_multiplas": len({(m["uf"], m["cd_mun"], m["zona"], m["secao"])
                                             for m in multiplas}),
        "bus_ilegiveis": erros,
        "distribuicao_total": dict(total),
        "distribuicao_por_uf": {uf: dict(c) for uf, c in sorted(por_uf_faixa.items())},
        "depois_17h30": len(tardias),
        "depois_18h00": sum(1 for ln in tardias if ln["minutos_apos_17h_bsb"] >= 61),
        "depois_19h00": sum(1 for ln in tardias if ln["minutos_apos_17h_bsb"] >= 121),
        "secoes_depois_17h30": [{k: ln.get(k) for k in CAMPOS_LISTA} for ln in tardias],
        "resultado_por_uf_e_grupo": {
            uf: {g: agregar_resultado(ls) for g, ls in sorted(grupos.items())}
            for uf, grupos in sorted(por_uf_grupo.items())
        },
        "inconsistencias_total": dict(inc.most_common()),
        "inconsistencias_nas_tardias": dict(inc_tardias.most_common()),
        "alertas_fuso": alertas_fuso,
    }


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def gravar(linhas: list[dict], caminho: Path) -> None:
    tmp = caminho.with_suffix(".parquet.tmp")
    pq.write_table(pa.Table.from_pylist(linhas), tmp, compression="zstd")
    tmp.replace(caminho)
    log.info("gravado %s (%d linhas)", caminho.name, len(linhas))


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--parts", action="append",
                    help="diretório com versoes-*.parquet (repetível)")
    ap.add_argument("--saida", default=str(SAIDA_PADRAO))
    ap.add_argument("--municipios", help="mun-e006258-cm.json local (senão baixa e guarda)")
    ap.add_argument("--workers", type=int, default=1,
                    help="processos para decodificar BUs (padrão 1)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    dirs = [Path(p) for p in (args.parts or [str(PARTS_PADRAO)])]
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    nomes = carregar_municipios(args.municipios, saida)

    regs = list(iter_bus(dirs))
    log.info("%d registros de BU lidos", len(regs))
    raws = [r.pop("conteudo") for r in regs]
    if args.workers > 1:
        with ProcessPoolExecutor(args.workers) as ex:
            dec = list(ex.map(_decodificar, raws, chunksize=256))
    else:
        dec = [_decodificar(r) for r in raws]
    del raws

    linhas = [montar_linha(r, c, v, e, nomes) for r, (c, v, e) in zip(regs, dec, strict=True)]
    erros = sum(1 for ln in linhas if ln["erro_decodificacao"])
    principal, multiplas = deduplicar(linhas)
    brasil = [ln for ln in principal if ln["uf"] != "zz"]
    exterior = [ln for ln in principal if ln["uf"] == "zz"]
    alertas = verificar_fusos(brasil)
    for a in alertas:
        log.warning("fuso suspeito: %s", a)

    brasil = [finalizar(ln) for ln in sorted(
        brasil, key=lambda x: (x["uf"], x["cd_mun"], x["zona"], x["secao"]))]
    exterior = [finalizar(ln) for ln in exterior]
    multiplas = [finalizar(ln) for ln in multiplas]

    gravar(brasil, saida / "secoes_encerramento.parquet")
    gravar(exterior, saida / "secoes_exterior.parquet")
    gravar(multiplas, saida / "versoes_multiplas.parquet")
    resumo = montar_resumo(brasil, exterior, multiplas, alertas,
                           [str(d) for d in dirs], erros)
    (saida / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    log.info("seções Brasil %d, exterior %d, depois de 17:30 %d, depois de 18:00 %d",
             len(brasil), len(exterior), resumo["depois_17h30"], resumo["depois_18h00"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
