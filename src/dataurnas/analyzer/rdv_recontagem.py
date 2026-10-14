"""Recontagem do RDV contra o BU e linha do tempo dos votos no log (2026).

Funções puras, sem rede, usadas por scripts/ele2026/fetch_rdv.py dentro de
processos do pool (recebem só bytes e dicts).

1. RDV x BU: cada registro do RDV é recontado (parsers.rdv.recontar) e o
   total por candidato, legenda, brancos e nulos de cada cargo é comparado
   com o BU da mesma seção e do mesmo conjunto de arquivos. Também confere
   registros do RDV = comparecimento x escolhas e a estrutura do RDV.
2. Log x BU minuto a minuto: cada "O voto do eleitor foi computado" do log é
   um eleitor que terminou de votar. Conta os votos do dia, compara com o
   comparecimento do BU e mede a linha do tempo (antes da abertura oficial,
   antes da "Urna pronta para receber votos", depois do "Inicio do
   Encerramento", máximo por minuto, menor intervalo, lacunas).

Grupos de leitura (dashboard/reference.py): divergência RDV x BU é grupo 1;
contagem do log diferente do BU e voto fora da sequência de eventos são
grupo 2; padrões de horário são grupo 3.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from collections import Counter
from typing import Any, Optional

from ..parsers.rdv import RDVParseError, parse_rdv_bytes, recontar, validar
from .timezones import get_tz_offset

GRUPO_1, GRUPO_2, GRUPO_3 = 1, 2, 3

# Categorias de achado e grupo de leitura (espelhadas em dashboard/reference.py)
CATEGORIAS: dict[str, int] = {
    "rdv_bu_diverge": GRUPO_1,          # recontagem do RDV difere do BU num cargo
    "rdv_registros_diverge": GRUPO_1,   # registros do RDV != comparecimento x escolhas
    "rdv_estrutura": GRUPO_1,           # registro inválido, cargo repetido, seção trocada
    "rdv_nao_decodificado": GRUPO_2,    # RDV publicado que o decodificador não lê
    "rdv_hash_diverge": GRUPO_1,        # SHA-512 baixado difere do catálogo assinado
    "rdv_bu_diverge_sa": GRUPO_2,       # divergência em BU do Sistema de Apuração (cédulas)
    "log_votos_diverge": GRUPO_2,       # votos computados no log != comparecimento do BU
    "log_voto_fora_sequencia": GRUPO_2,  # voto antes da abertura ou depois do encerramento
    "log_voto_outra_data": GRUPO_2,     # voto computado com data diferente do dia da eleição
    "log_voto_antes_8h": GRUPO_3,       # voto antes das 8h de Brasília (hora local)
    "log_intervalo_curto": GRUPO_3,     # votos consecutivos a menos de 10 s
    "log_lacuna_60min": GRUPO_3,        # mais de 60 min sem voto durante a votação
    "log_relogio_inverso": GRUPO_3,     # hora do voto menor que a do voto anterior
}

EVENTO_VOTO = "O voto do eleitor foi computado"
EVENTO_PRONTA = "Urna pronta para receber votos"
EVENTOS_ENCERRAMENTO = ("Inicio do Encerramento", "Início do Encerramento")

# Faixas do histograma de intervalos entre votos consecutivos (segundos):
# [0,1) [1,2) [2,3) [3,5) [5,10) [10,15) [15,20) [20,30) [30,45) [45,60)
# [60,120) [120,300) [300,600) [600,3600) [3600,inf)
FAIXAS_INTERVALO = (1, 2, 3, 5, 10, 15, 20, 30, 45, 60, 120, 300, 600, 3600)
LIMIAR_RAJADA_S = 10
LIMIAR_LACUNA_S = 3600
MAX_LOG_BYTES = 256 * 1024 * 1024


def sha512(b: bytes) -> str:
    return hashlib.sha512(b).hexdigest()


# ---------------------------------------------------------------------------
# RDV x BU
# ---------------------------------------------------------------------------

def contagens_bu(bu) -> dict[tuple[int, int], dict]:
    """(id_eleicao, cargo) -> {comparecimento, votos: Counter} do BoletimUrna."""
    from ..models import TipoVoto

    out: dict[tuple[int, int], dict] = {}
    for res in bu.resultados_por_eleicao:
        for rc in res.resultados:
            c: Counter = Counter()
            for v in rc.votos:
                q = int(v.quantidade or 0)
                if v.tipo_voto == TipoVoto.NOMINAL:
                    c[("nominal", int(v.codigo_votavel))] += q
                elif v.tipo_voto == TipoVoto.LEGENDA:
                    c[("legenda", int(v.partido if v.partido is not None
                                      else v.codigo_votavel))] += q
                elif v.tipo_voto == TipoVoto.BRANCO:
                    c[("branco", None)] += q
                elif v.tipo_voto == TipoVoto.NULO:
                    c[("nulo", None)] += q
                else:
                    c[("cargoSemCandidato", None)] += q
            out[(int(res.id_eleicao), int(rc.codigo_cargo))] = {
                "comparecimento": int(rc.comparecimento or 0), "votos": +c}
    return out


def _chave_txt(k: tuple) -> str:
    tipo, n = k
    return tipo if n is None else f"{tipo}:{n}"


def _diferencas(a: Counter, b: Counter) -> dict[str, list[int]]:
    """{chave: [rdv, bu]} só das chaves que diferem."""
    return {_chave_txt(k): [int(a.get(k, 0)), int(b.get(k, 0))]
            for k in sorted(set(a) | set(b), key=lambda k: (k[0], k[1] or 0))
            if a.get(k, 0) != b.get(k, 0)}


def _resumo_cargo(c: Counter) -> dict[str, int]:
    return {"nominais": sum(q for (t, _), q in c.items() if t == "nominal"),
            "legenda": sum(q for (t, _), q in c.items() if t == "legenda"),
            "brancos": c.get(("branco", None), 0),
            "nulos": c.get(("nulo", None), 0) + c.get(("cargoSemCandidato", None), 0)}


def comparar_rdv_bu(rdv, bu_cont: dict, ident: dict, origem_bu: str = "bu",
                    pleito: Optional[int] = None) -> dict:
    """Compara a recontagem do RDV com o BU, cargo a cargo.

    Retorna {"linhas": [...], "achados": [...], "presidente": Counter,
    "estrutura": [...]}. Cada linha é uma (seção, cargo) do esquema de
    recontagem_secoes.parquet; cada achado é uma divergência com categoria.
    """
    linhas, achados = [], []
    estrutura = validar(rdv, pleito=pleito, ident=ident)
    if estrutura:
        achados.append({**ident, "categoria": "rdv_estrutura", "grupo": GRUPO_1,
                        "detalhes": estrutura[:20]})
    presidente: Counter = Counter()
    vistos = set()
    for id_el, cargo in rdv.cargos():
        chave = (id_el, cargo.codigo_cargo)
        vistos.add(chave)
        cont_rdv = recontar(cargo)
        bu = bu_cont.get(chave)
        cont_bu = Counter(bu["votos"]) if bu else Counter()
        comp_bu = bu["comparecimento"] if bu else None
        nota = None
        # cargo sem candidato: o BU pode registrar como nulo; agrupa nos dois
        # lados quando só um deles tem o tipo
        k_csc = ("cargoSemCandidato", None)
        if (k_csc in cont_rdv) != (k_csc in cont_bu):
            for c in (cont_rdv, cont_bu):
                if k_csc in c:
                    c[("nulo", None)] += c.pop(k_csc)
            nota = "cargoSemCandidato agrupado em nulo"
        if cargo.codigo_cargo == 1:
            presidente.update(cont_rdv)
        dif = _diferencas(cont_rdv, cont_bu) if bu else {"cargo_ausente_no_bu": [
            cargo.n_registros, 0]}
        esperado = (comp_bu * cargo.qtd_escolhas) if comp_bu is not None else None
        reg_ok = esperado is not None and esperado == cargo.n_registros
        confere = bool(bu) and not dif and reg_ok
        det: dict[str, Any] = {}
        if dif:
            det["diferencas"] = dif
        if not reg_ok:
            det["registros_rdv"] = cargo.n_registros
            det["comparecimento_bu_x_escolhas"] = esperado
        if nota:
            det["nota"] = nota
        rs, bs = _resumo_cargo(cont_rdv), _resumo_cargo(cont_bu)
        linhas.append({
            **ident, "id_eleicao": id_el, "cargo": cargo.nome_cargo,
            "codigo_cargo": cargo.codigo_cargo, "qtd_escolhas": cargo.qtd_escolhas,
            "registros_rdv": cargo.n_registros, "comparecimento_bu": comp_bu,
            "votos_rdv": sum(cont_rdv.values()), "votos_bu": sum(cont_bu.values()),
            "nominais_rdv": rs["nominais"], "nominais_bu": bs["nominais"],
            "legenda_rdv": rs["legenda"], "legenda_bu": bs["legenda"],
            "brancos_rdv": rs["brancos"], "brancos_bu": bs["brancos"],
            "nulos_rdv": rs["nulos"], "nulos_bu": bs["nulos"],
            "n_votaveis": len([k for k in cont_rdv if k[0] in ("nominal", "legenda")]),
            "confere": confere,
            "detalhes": json.dumps(det, ensure_ascii=False) if det else None,
        })
        if dif:
            cat = "rdv_bu_diverge" if origem_bu == "bu" else "rdv_bu_diverge_sa"
            achados.append({**ident, "categoria": cat, "grupo": CATEGORIAS[cat],
                            "id_eleicao": id_el, "cargo": cargo.nome_cargo,
                            "origem_bu": origem_bu, "detalhes": dif})
        if not reg_ok:
            achados.append({**ident, "categoria": "rdv_registros_diverge", "grupo": GRUPO_1,
                            "id_eleicao": id_el, "cargo": cargo.nome_cargo,
                            "registros_rdv": cargo.n_registros,
                            "comparecimento_bu": comp_bu, "qtd_escolhas": cargo.qtd_escolhas})
    for (id_el, cod), bu in sorted(bu_cont.items()):
        if (id_el, cod) in vistos:
            continue
        from ..parsers.rdv import NOMES_CARGO

        nome = NOMES_CARGO.get(cod, f"Cargo {cod}")
        total = sum(bu["votos"].values())
        bs = _resumo_cargo(bu["votos"])
        linhas.append({
            **ident, "id_eleicao": id_el, "cargo": nome, "codigo_cargo": cod,
            "qtd_escolhas": None, "registros_rdv": 0,
            "comparecimento_bu": bu["comparecimento"], "votos_rdv": 0, "votos_bu": total,
            "nominais_rdv": 0, "nominais_bu": bs["nominais"], "legenda_rdv": 0,
            "legenda_bu": bs["legenda"], "brancos_rdv": 0, "brancos_bu": bs["brancos"],
            "nulos_rdv": 0, "nulos_bu": bs["nulos"], "n_votaveis": 0,
            "confere": total == 0,
            "detalhes": json.dumps({"cargo_ausente_no_rdv": True}, ensure_ascii=False),
        })
        if total:
            cat = "rdv_bu_diverge" if origem_bu == "bu" else "rdv_bu_diverge_sa"
            achados.append({**ident, "categoria": cat, "grupo": CATEGORIAS[cat],
                            "id_eleicao": id_el, "cargo": nome, "origem_bu": origem_bu,
                            "detalhes": {"cargo_ausente_no_rdv": [0, total]}})
    return {"linhas": linhas, "achados": achados, "presidente": presidente,
            "estrutura": estrutura}


# ---------------------------------------------------------------------------
# Log: linha do tempo dos votos
# ---------------------------------------------------------------------------

def _textos_zip(raw: bytes, nivel: int = 0) -> Optional[list[str]]:
    """Textos dos logs de um ZIP, logs aninhados primeiro.

    Na troca de urna (contingência) o -log.jez traz o logd.dat da urna que
    terminou a votação e, como .jez aninhado (ZIP com outro logd.dat), o log
    da urna substituída, nomeado <urna><ddmmaaaahhmmss>-NN.jez. Os aninhados
    vêm antes, em ordem de nome; o logd.dat do pacote fica por último.
    """
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        if not infos or sum(i.file_size for i in infos) > MAX_LOG_BYTES:
            return None
        aninhados, proprios = [], []
        for i in sorted(infos, key=lambda i: i.filename):
            dados = z.read(i)
            if dados[:4] == b"PK\x03\x04":
                if nivel < 2:
                    sub = _textos_zip(dados, nivel + 1)
                    if sub:
                        aninhados.extend(sub)
            else:
                proprios.append(dados.decode("latin-1", errors="replace"))
        return aninhados + proprios


def texto_log(raw: bytes) -> Optional[str]:
    """Texto de um -log.jez (ZIP em 2026, com logs aninhados de urnas
    substituídas; 7-zip como reserva)."""
    if raw[:4] == b"PK\x03\x04":
        textos = _textos_zip(raw)
        return "\n".join(textos) if textos else None
    from ..parsers.log import LogParser

    return LogParser()._extract_text(io.BytesIO(raw), "<memória>")


def _seg(hora: str) -> int:
    return int(hora[0:2]) * 3600 + int(hora[3:5]) * 60 + int(hora[6:8])


def _hms(s: Optional[int]) -> Optional[str]:
    if s is None:
        return None
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def _faixa(d: int) -> int:
    for i, lim in enumerate(FAIXAS_INTERVALO):
        if d < lim:
            return i
    return len(FAIXAS_INTERVALO)


def analisar_log_tempo(texto: str, uf: str, cd_mun, comparecimento: Optional[int],
                       data_eleicao: str = "04/10/2026") -> dict:
    """Métricas de horário dos votos de um log (hora local da urna).

    Abertura oficial: 8h de Brasília, que é 8h + offset na hora local
    (timezones.get_tz_offset; AC: 6h local). 17h de Brasília: 17h + offset.
    Eleitor na fila depois das 17h vota legalmente: o que se marca é voto
    computado depois do "Inicio do Encerramento" da mesma urna, sem nova
    "Urna pronta para receber votos" no meio.
    """
    offset = get_tz_offset(uf, cd_mun)
    if (uf or "").lower() == "zz":
        offset = 0  # exterior: urna no horário local do país, 8h às 17h locais
    abertura_oficial = (8 + offset) * 3600
    fim_oficial = (17 + offset) * 3600

    votos: list[tuple[int, str]] = []     # (segundos, id_urna) na ordem do arquivo
    outras_datas = 0
    fora_seq = 0
    antes_pronta = 0
    apos_enc = 0
    estado: dict[str, str] = {}           # id_urna -> "fechada" | "aberta" | "encerrada"
    prontas: list[int] = []
    encerramentos: list[int] = []
    urnas_voto: set[str] = set()
    ajustes_hora = 0
    for ln in texto.split("\n"):
        if len(ln) < 30:
            continue
        p = ln.split("\t")
        if len(p) < 5:
            continue
        desc = p[4]
        data, hora = p[0][:10], p[0][11:19]
        if "hora" in desc and ("atualizada" in desc or "ajust" in desc.lower()):
            if data == data_eleicao:
                ajustes_hora += 1
        if EVENTO_PRONTA in desc:
            if data == data_eleicao:
                prontas.append(_seg(hora))
            estado[p[2]] = "aberta"
            continue
        if any(e in desc for e in EVENTOS_ENCERRAMENTO):
            if data == data_eleicao:
                encerramentos.append(_seg(hora))
            estado[p[2]] = "encerrada"
            continue
        if EVENTO_VOTO not in desc:
            continue
        if data != data_eleicao:
            outras_datas += 1
            continue
        st = estado.get(p[2], "fechada")
        if st != "aberta":
            fora_seq += 1
            if st == "encerrada":
                apos_enc += 1
            else:
                antes_pronta += 1
        votos.append((_seg(hora), p[2]))
        urnas_voto.add(p[2])

    n = len(votos)
    ts = [t for t, _ in votos]
    hist = [0] * (len(FAIXAS_INTERVALO) + 1)
    intervalos: list[int] = []
    inversoes = 0
    for (t0, u0), (t1, u1) in zip(votos, votos[1:], strict=False):
        if u0 != u1:
            continue  # troca de urna: o intervalo não mede um eleitor
        d = t1 - t0
        if d < 0:
            inversoes += 1
            continue
        intervalos.append(d)
        hist[_faixa(d)] += 1
    por_minuto = Counter(t // 60 for t in ts)
    lacunas = [d for d in intervalos if d > LIMIAR_LACUNA_S]
    intervalos_ord = sorted(intervalos)
    mediana = intervalos_ord[len(intervalos_ord) // 2] if intervalos_ord else None
    max_min = por_minuto.most_common(1)[0] if por_minuto else (None, 0)
    r = {
        "fuso_offset": offset,
        "comparecimento_bu": comparecimento,
        "votos_log": n,
        "diferenca_log_bu": (n - comparecimento) if comparecimento is not None else None,
        "votos_outras_datas": outras_datas,
        "n_urnas_log": len(urnas_voto),
        "aberturas": len(prontas),
        "hora_pronta": _hms(min(prontas)) if prontas else None,
        "hora_encerramento": _hms(max(encerramentos)) if encerramentos else None,
        "primeiro_voto": _hms(min(ts)) if ts else None,
        "ultimo_voto": _hms(max(ts)) if ts else None,
        "votos_antes_8h": sum(1 for t in ts if t < abertura_oficial),
        "votos_apos_17h": sum(1 for t in ts if t >= fim_oficial),
        "votos_antes_pronta": antes_pronta,
        "votos_apos_encerramento": apos_enc,
        "max_votos_minuto": int(max_min[1]),
        "minuto_pico": _hms(max_min[0] * 60) if max_min[0] is not None else None,
        "intervalo_min_s": intervalos_ord[0] if intervalos_ord else None,
        "intervalo_mediana_s": mediana,
        "intervalos_lt_10s": sum(1 for d in intervalos if d < LIMIAR_RAJADA_S),
        "intervalos_lt_5s": sum(1 for d in intervalos if d < 5),
        "maior_lacuna_min": round(max(intervalos) / 60, 1) if intervalos else None,
        "lacunas_60min": len(lacunas),
        "inversoes_relogio": inversoes,
        "ajustes_hora": ajustes_hora,
        "hist_intervalos": hist,
    }
    flags = []
    if comparecimento is not None and n != comparecimento:
        flags.append("log_votos_diverge")
    if fora_seq:
        flags.append("log_voto_fora_sequencia")
    if outras_datas:
        flags.append("log_voto_outra_data")
    if r["votos_antes_8h"]:
        flags.append("log_voto_antes_8h")
    if r["intervalos_lt_10s"]:
        flags.append("log_intervalo_curto")
    if lacunas:
        flags.append("log_lacuna_60min")
    if inversoes:
        flags.append("log_relogio_inverso")
    r["flags"] = flags
    r["grupo"] = min((CATEGORIAS[f] for f in flags), default=None)
    return r


# ---------------------------------------------------------------------------
# Seção inteira (executado no pool)
# ---------------------------------------------------------------------------

def processar_secao(ident: dict, arquivos: dict[str, tuple[str, bytes]],
                    sha_catalogo: Optional[dict[str, str]] = None,
                    pleito: Optional[int] = None,
                    data_eleicao: str = "04/10/2026") -> dict:
    """Recontagem e linha do tempo de uma seção.

    arquivos: tipo -> (nome, bytes) com 'rdv', 'bu' (ou 'busa') e 'log'.
    sha_catalogo: tipo -> SHA-512 do catálogo de integridade (opcional).
    """
    from ..parsers.bu import BUParser

    achados: list[dict] = []
    sec: dict[str, Any] = {**ident, "status": "ok", "motivo": None}
    hashes_ok = None
    if sha_catalogo:
        hashes_ok = True
        for tp, (nome, b) in arquivos.items():
            esperado = sha_catalogo.get(tp)
            if esperado and sha512(b) != esperado:
                hashes_ok = False
                achados.append({**ident, "categoria": "rdv_hash_diverge", "grupo": GRUPO_1,
                                "arquivo": nome, "sha512_catalogo": esperado})
    sec["hash_confere"] = hashes_ok

    tipo_bu = "bu" if "bu" in arquivos else ("busa" if "busa" in arquivos else None)
    bu = None
    if tipo_bu:
        try:
            bu = BUParser().parse_bytes(arquivos[tipo_bu][1])
        except Exception as e:  # noqa: BLE001 - registrado como status da seção
            sec.update(status="bu_nao_decodificado", motivo=repr(e)[:200])
    bu_cont = contagens_bu(bu) if bu is not None else {}
    comp = None
    for (_id_el, cod), v in bu_cont.items():
        if cod == 1:
            comp = v["comparecimento"]
    if comp is None and bu_cont:
        comp = max(v["comparecimento"] for v in bu_cont.values())
    sec["comparecimento_bu"] = comp
    sec["origem_bu"] = tipo_bu

    linhas: list[dict] = []
    presidente: Counter = Counter()
    sec["n_cargos"] = 0
    sec["registros_rdv"] = None
    if "rdv" in arquivos and bu is not None:
        try:
            rdv = parse_rdv_bytes(arquivos["rdv"][1])
        except RDVParseError as e:
            rdv = None
            sec.update(status="rdv_nao_decodificado", motivo=str(e)[:200])
            achados.append({**ident, "categoria": "rdv_nao_decodificado", "grupo": GRUPO_2,
                            "detalhes": str(e)[:200]})
        if rdv is not None:
            r = comparar_rdv_bu(rdv, bu_cont, ident, origem_bu=tipo_bu or "bu", pleito=pleito)
            linhas = r["linhas"]
            presidente = r["presidente"]
            achados.extend(r["achados"])
            sec["n_cargos"] = len(linhas)
            sec["registros_rdv"] = sum(ln["registros_rdv"] for ln in linhas)
            sec["tipo_arquivo_rdv"] = rdv.tipo_arquivo
            sec["tipo_urna_rdv"] = rdv.tipo_urna
            sec["origem_rdv"] = rdv.eleicoes[0].origem if rdv.eleicoes else None
            sec["estrutura_ok"] = not r["estrutura"]
    elif "rdv" not in arquivos:
        sec.update(status="sem_rdv", motivo="RDV não publicado no conjunto de arquivos")
    sec["rdv_confere"] = bool(linhas) and all(ln["confere"] for ln in linhas)

    tempo = None
    if "log" in arquivos:
        try:
            txt = texto_log(arquivos["log"][1])
        except Exception as e:  # noqa: BLE001
            txt = None
            sec["motivo"] = (sec["motivo"] or "") + f" log: {e!r}"[:200]
        if txt:
            tempo = {**ident, **analisar_log_tempo(txt, ident["uf"], ident["cd_mun"], comp,
                                                   data_eleicao)}
            for f in tempo["flags"]:
                if CATEGORIAS[f] <= GRUPO_2:
                    det = {k: tempo[k] for k in ("votos_log", "comparecimento_bu",
                                                 "votos_antes_pronta",
                                                 "votos_apos_encerramento",
                                                 "votos_outras_datas", "n_urnas_log",
                                                 "aberturas")}
                    achados.append({**ident, "categoria": f, "grupo": CATEGORIAS[f],
                                    "detalhes": det})
    return {"secao": sec, "linhas": linhas, "tempo": tempo, "achados": achados,
            "presidente": {_chave_txt(k): int(v) for k, v in presidente.items()}}
