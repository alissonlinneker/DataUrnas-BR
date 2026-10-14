"""Verificação de integridade: hashes SHA-512, assinaturas digitais."""

import logging
from pathlib import Path

from ..models import (
    BoletimUrna,
    Issue,
    IssueSeverity,
)
from ..parsers.signature import SignatureParser

logger = logging.getLogger(__name__)

# C01 só é emitido quando o hash foi de fato calculado e diverge do assinado.
# Falha de parse ou arquivo ausente vira E01: a verificação não foi possível,
# o que não é evidência de adulteração.
CODIGO_HASH_INVALIDO = "C01"
CODIGO_NAO_VERIFICAVEL = "E01"


class IntegrityAnalyzer:
    """Analisa integridade criptográfica dos arquivos de urna."""

    def __init__(self):
        self._sig_parser = SignatureParser()

    def verify_section_hashes(self, section_dir: Path) -> list[Issue]:
        """Verifica hashes de todos os arquivos em uma seção.

        Procura o arquivo de assinatura (.vscmr para V1) e verifica
        o SHA-512 de cada arquivo contra o hash armazenado.
        """
        issues = []

        # Encontrar arquivo de assinatura
        sig_files = list(section_dir.glob("*.vscmr")) + list(section_dir.glob("*-vota.vsc"))
        if not sig_files:
            return issues  # Sem arquivo de assinatura para verificar

        sig_file = sig_files[0]

        try:
            results = self._sig_parser.verify_file_hashes(sig_file, section_dir)
        except Exception as e:
            logger.error("Erro ao verificar hashes em %s: %s", section_dir, e)
            issues.append(
                Issue(
                    codigo=CODIGO_NAO_VERIFICAVEL,
                    severidade=IssueSeverity.INFO,
                    descricao=(
                        "Assinatura não verificável: falha ao processar o arquivo "
                        f"de assinatura ({type(e).__name__})"
                    ),
                    uf="",
                    municipio="",
                    zona="",
                    secao="",
                    detalhes={"arquivo": str(sig_file), "erro": str(e)},
                )
            )
            return issues

        for result in results:
            if not result.encontrado:
                issues.append(
                    Issue(
                        codigo=CODIGO_NAO_VERIFICAVEL,
                        severidade=IssueSeverity.INFO,
                        descricao=(
                            f"Hash não verificável: {result.arquivo} ausente no "
                            "diretório da seção"
                        ),
                        uf="",
                        municipio="",
                        zona="",
                        secao="",
                        detalhes={
                            "arquivo": result.arquivo,
                            "hash_esperado": result.hash_esperado.hex(),
                        },
                    )
                )
            elif not result.valido:
                issues.append(
                    Issue(
                        codigo=CODIGO_HASH_INVALIDO,
                        severidade=IssueSeverity.CRITICAL,
                        descricao=f"Hash SHA-512 INVÁLIDO para {result.arquivo}",
                        uf="",
                        municipio="",
                        zona="",
                        secao="",
                        detalhes={
                            "arquivo": result.arquivo,
                            "hash_esperado": result.hash_esperado.hex(),
                            "hash_calculado": result.hash_calculado.hex(),
                        },
                        base_legal="Art. 59, Lei 9.504/97: Cerimônia de Lacração",
                    )
                )

        return issues


def votos_por_eleitor(nome_cargo, data_hora_emissao) -> int:
    """Votos que cada eleitor dá no cargo: 2 para Senador nos anos de
    renovação de 2/3 do Senado (2018, 2026, 2034...), 1 nos demais casos.

    O BU não informa o número de vagas; o ano vem da data de emissão
    (YYYYMMDDThhmmss ou DD/MM/YYYY ...). Sem ano conhecido, assume 1.
    """
    if "senador" not in str(nome_cargo or "").lower():
        return 1
    import re

    m = re.search(r"(20\d\d)", str(data_hora_emissao or ""))
    if not m:
        return 1
    ano = int(m.group(1))
    return 2 if ano >= 2018 and (ano - 2018) % 8 == 0 else 1


def aptos_sem_transito(eleicao) -> int:
    """Eleitores aptos da própria seção, sem os habilitados em trânsito (TTE).

    Usa eleitores_aptos_secao quando o BU traz o campo; senão desconta
    eleitores_aptos_tte de eleitores_aptos (TTE ausente conta como 0).
    """
    if eleicao.eleitores_aptos_secao is not None:
        return eleicao.eleitores_aptos_secao
    return eleicao.eleitores_aptos - (eleicao.eleitores_aptos_tte or 0)


class ConsistencyAnalyzer:
    """Analisa consistência lógica dos dados de votação."""

    def check_votes_vs_eligible(self, bu: BoletimUrna) -> list[Issue]:
        """Verifica se total de votos não excede eleitores aptos."""
        issues = []

        for eleicao in bu.resultados_por_eleicao:
            for resultado in eleicao.resultados:
                total_votos = sum(v.quantidade for v in resultado.votos)
                # Senador com 2 vagas (renovação de 2/3): 2 votos por eleitor
                vagas = votos_por_eleitor(resultado.nome_cargo, bu.data_hora_emissao)
                limite_aptos = eleicao.eleitores_aptos * vagas
                if total_votos > limite_aptos:
                    issues.append(
                        Issue(
                            codigo="C05",
                            severidade=IssueSeverity.CRITICAL,
                            descricao=(
                                f"Total de votos ({total_votos}) EXCEDE eleitores "
                                f"aptos ({eleicao.eleitores_aptos}) para {resultado.nome_cargo}"
                            ),
                            uf=str(bu.uf),
                            municipio=str(bu.municipio),
                            zona=str(bu.zona),
                            secao=str(bu.secao),
                            detalhes={
                                "cargo": resultado.nome_cargo,
                                "total_votos": total_votos,
                                "eleitores_aptos": eleicao.eleitores_aptos,
                                "comparecimento": resultado.comparecimento,
                                "excesso": total_votos - limite_aptos,
                                "votos_por_eleitor": vagas,
                            },
                            base_legal="Art. 59, Lei 9.504/97",
                        )
                    )

                # Verificar comparecimento vs votos
                if (resultado.comparecimento > 0
                        and total_votos > resultado.comparecimento * vagas):
                    issues.append(
                        Issue(
                            codigo="A02",
                            severidade=IssueSeverity.HIGH,
                            descricao=(
                                f"Total de votos ({total_votos}) excede comparecimento "
                                f"({resultado.comparecimento}) para {resultado.nome_cargo}"
                            ),
                            uf=str(bu.uf),
                            municipio=str(bu.municipio),
                            zona=str(bu.zona),
                            secao=str(bu.secao),
                            detalhes={
                                "cargo": resultado.nome_cargo,
                                "total_votos": total_votos,
                                "comparecimento": resultado.comparecimento,
                                "votos_por_eleitor": vagas,
                            },
                        )
                    )
        return issues

    def check_cross_election_consistency(self, bu: BoletimUrna) -> list[Issue]:
        """Verifica consistência entre eleições na mesma urna.

        Ex: eleitores aptos para presidente vs deputado federal
        devem ser iguais na mesma seção.
        """
        issues = []

        if len(bu.resultados_por_eleicao) < 2:
            return issues

        # Comparar eleitores aptos entre todas as eleições, descontando o voto
        # em trânsito (TTE): o eleitor em trânsito fora da UF só vota para
        # Presidente, então a eleição federal tem mais aptos que a estadual
        # sem que haja inconsistência. Compara-se o eleitorado da própria
        # seção (aptos_secao); na falta dele, aptos - aptos_tte. Sem esse
        # desconto, 2022 teve 30.572 falsos positivos de A01.
        aptos_por_eleicao = {}
        for eleicao in bu.resultados_por_eleicao:
            aptos_por_eleicao[eleicao.id_eleicao] = aptos_sem_transito(eleicao)

        valores_aptos = list(aptos_por_eleicao.values())
        if len(set(valores_aptos)) > 1:
            issues.append(
                Issue(
                    codigo="A01",
                    severidade=IssueSeverity.HIGH,
                    descricao=(
                        f"Divergência de eleitores aptos entre eleições: "
                        f"{aptos_por_eleicao}"
                    ),
                    uf=str(bu.uf),
                    municipio=str(bu.municipio),
                    zona=str(bu.zona),
                    secao=str(bu.secao),
                    detalhes={
                        "aptos_por_eleicao": aptos_por_eleicao,
                        "aptos_com_transito": {
                            e.id_eleicao: e.eleitores_aptos
                            for e in bu.resultados_por_eleicao
                        },
                        "regra": "aptos da seção, sem voto em trânsito (TTE)",
                    },
                    base_legal="Caderno de eleitores único por seção",
                )
            )

        return issues

    def check_comparecimento_consistency(self, bu: BoletimUrna) -> list[Issue]:
        """Verifica se comparecimento é igual entre cargos da mesma eleição.

        Na mesma urna, o comparecimento deve ser idêntico para todos os cargos
        da mesma eleição (o eleitor vota em todos os cargos na mesma sessão).
        """
        issues = []

        for eleicao in bu.resultados_por_eleicao:
            comps = {}
            for resultado in eleicao.resultados:
                if resultado.comparecimento > 0:
                    comps[resultado.nome_cargo] = resultado.comparecimento

            valores = list(comps.values())
            if len(valores) >= 2 and len(set(valores)) > 1:
                issues.append(
                    Issue(
                        codigo="A06",
                        severidade=IssueSeverity.HIGH,
                        descricao=(
                            f"Comparecimento divergente entre cargos da eleição "
                            f"{eleicao.id_eleicao}: {comps}"
                        ),
                        uf=str(bu.uf),
                        municipio=str(bu.municipio),
                        zona=str(bu.zona),
                        secao=str(bu.secao),
                        detalhes={
                            "eleicao": eleicao.id_eleicao,
                            "comparecimentos": comps,
                        },
                        base_legal="Eleitor vota em todos os cargos na mesma sessão",
                    )
                )

        return issues

    def check_tipo_urna(self, bu: BoletimUrna) -> list[Issue]:
        """Verifica se o tipo de urna e regular (seção)."""
        issues = []

        if bu.tipo_urna and bu.tipo_urna not in ("secao", "votacaoUE"):
            issues.append(
                Issue(
                    codigo="I06",
                    severidade=IssueSeverity.INFO,
                    descricao=f"Urna não padrão: tipo={bu.tipo_urna}",
                    uf=str(bu.uf),
                    municipio=str(bu.municipio),
                    zona=str(bu.zona),
                    secao=str(bu.secao),
                    detalhes={"tipo_urna": bu.tipo_urna},
                )
            )

        return issues

    def full_analysis(self, bu: BoletimUrna) -> list[Issue]:
        """Executa todas as verificações de consistência."""
        issues = []
        issues.extend(self.check_votes_vs_eligible(bu))
        issues.extend(self.check_cross_election_consistency(bu))
        issues.extend(self.check_comparecimento_consistency(bu))
        issues.extend(self.check_tipo_urna(bu))
        return issues


# ---------------------------------------------------------------------------
# Auditoria de arquivos da urna de 2026 (funções puras, sem rede)
# ---------------------------------------------------------------------------

# Arquivos que a urna assina e o TSE publica sempre que existem. Os demais
# nomes listados no .vsc (jufa, imgbu, imgze, hash, wsq*, mr.ver, imgbusa)
# não são publicados por padrão e por isso não contam como ausentes.
SUFIXOS_PUBLICADOS = ("-bu.dat", "-rdv.dat", "-log.jez", "-busa.dat", "-logsa.jez")

# 2022 (spec v1, .vscmr): o pacote de dados abertos do TSE traz .bu, .rdv,
# .logjez, .imgbu e .vscmr de cada seção; .jufa, .hash, .wsq*, .ver e .chvtp
# são assinados, mas não publicados.
SUFIXOS_PUBLICADOS_V1 = (".bu", ".rdv", ".logjez", ".imgbu", ".busa", ".imgbusa", ".logsajez")

CATEGORIAS_DIVERGENCIA = (
    "hash_diverge",            # SHA-512 calculado difere do assinado no .vsc
    "assinatura_invalida",     # assinatura ou estrutura do .vsc não confere
    "hash_assinado_ausente",   # arquivo publicado sem hash assinado no .vsc
    "arquivo_ausente_tse",     # listado no .vsc, mas ausente no aux.json do TSE
)

TIPOS_ARQUIVO = {"bu": "bu", "rdv": "rdv", "log": "log", "vota": "vota",
                 "busa": "busa", "imgbu": "imgbu",
                 "sa": "vota", "logsa": "log",
                 # extensões de 2022 (spec v1)
                 "logjez": "log", "vscmr": "vota", "logsajez": "log"}


def tipo_arquivo(tp: str, nome: str) -> str:
    """Normaliza o tipo do aux.json para bu, rdv, log, vota, busa, imgbu ou other.

    O .vsc do Sistema de Apuração (tp "sa") vira "vota" (é o arquivo de
    assinatura) e o log do SA ("logsa") vira "log"; o nome preserva a origem.
    """
    t = TIPOS_ARQUIVO.get((tp or "").lower())
    if t:
        return t
    if nome.endswith((".vsc", ".vscmr", ".vscsa")):
        return "vota"
    return "other"


def eh_assinatura(tp: str, nome: str) -> bool:
    return tipo_arquivo(tp, nome) == "vota"


def digests(raw: bytes) -> dict:
    """Tamanho e digests MD5, SHA-256 e SHA-512 (hex) de um arquivo."""
    import hashlib

    return {
        "tamanho": len(raw),
        "md5": hashlib.md5(raw).hexdigest(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "sha512": hashlib.sha512(raw).hexdigest(),
    }


def _votos_bu(raw: bytes, eleicao: int | str | None = None) -> tuple:
    from ..downloader.ele2026 import bu_to_rows

    _sec, votos = bu_to_rows(raw, eleicao=int(eleicao)) if eleicao else bu_to_rows(raw)
    return tuple(sorted((v["tipo_voto"], v["numero"] or 0, v["votos"] or 0) for v in votos))


def auditar_conjunto(ident: dict, conjunto: dict,
                     sufixos_publicados: tuple[str, ...] = SUFIXOS_PUBLICADOS,
                     fonte: str = "aux.json") -> dict:
    """Audita um conjunto de arquivos (um hash do aux.json) de uma seção.

    conjunto = {"token", "data_hora", "arquivos": [(tp, nome, bytes|None), ...]}
    bytes None = arquivo listado no aux.json, mas indisponível no servidor
    (HTTP 404): vira linha com disponivel False e sem hashes calculados.
    sufixos_publicados: arquivos assinados que o TSE publica (os demais nomes
    do .vsc não contam como ausentes); fonte: onde a lista de arquivos
    publicados foi lida ("aux.json" em 2026, o pacote zip em 2022).
    Retorna {"linhas": [...], "verificacao": dict|None, "divergencias": [...]}.
    """
    from ..parsers.signature import verificar_vsc

    todos = conjunto["arquivos"]
    arqs = [(tp, nm, raw) for tp, nm, raw in todos if raw is not None]
    vscs = [(tp, nm, raw) for tp, nm, raw in arqs if eh_assinatura(tp, nm)]
    dados = [(tp, nm, raw) for tp, nm, raw in arqs if not eh_assinatura(tp, nm)]
    verif = None
    if vscs:
        verif = verificar_vsc(vscs[0][2], {nm for _, nm, _ in dados})
    assinados = (verif or {}).get("hashes", {})
    divs: list[dict] = []

    def div(categoria: str, arquivo, calc, assin, motivo: str) -> None:
        divs.append({**ident, "arquivo": arquivo, "sha512_calculado": calc,
                     "sha512_assinado": assin, "categoria": categoria,
                     "motivo": motivo, "token_tse": conjunto["token"]})

    linhas = []
    for tp, nm, raw in arqs:
        d = digests(raw)
        assin = None
        confere = None
        if not eh_assinatura(tp, nm):
            h = assinados.get(nm)
            if h is not None:
                assin = h.hex()
                confere = assin == d["sha512"]
                if not confere:
                    div("hash_diverge", nm, d["sha512"], assin,
                        "SHA-512 calculado difere do assinado no .vsc")
            elif vscs:
                div("hash_assinado_ausente", nm, d["sha512"], None,
                    "arquivo publicado sem hash assinado no .vsc do conjunto")
            else:
                div("hash_assinado_ausente", nm, d["sha512"], None,
                    "conjunto publicado sem arquivo de assinatura (.vsc)")
        linhas.append({**ident, "tipo": tipo_arquivo(tp, nm), "nome": nm, **d,
                       "sha512_assinado": assin, "hash_confere": confere,
                       "token_tse": conjunto["token"],
                       "data_hora_tse": conjunto["data_hora"],
                       "disponivel": True, "http_status": 200})
    indisponiveis = {nm for _tp, nm, raw in todos if raw is None}
    for tp, nm, raw in todos:
        if raw is not None:
            continue
        h = assinados.get(nm)
        linhas.append({**ident, "tipo": tipo_arquivo(tp, nm), "nome": nm,
                       "tamanho": None, "md5": None, "sha256": None, "sha512": None,
                       "sha512_assinado": h.hex() if h is not None else None,
                       "hash_confere": None, "token_tse": conjunto["token"],
                       "data_hora_tse": conjunto["data_hora"],
                       "disponivel": False, "http_status": 404})
    if verif is not None:
        if verif["assinatura_valida"] is False:
            div("assinatura_invalida", vscs[0][1], None, None,
                "; ".join(verif["falhas"]) or "assinatura inválida")
        publicados = {nm for _, nm, _ in arqs}
        for nm, h in assinados.items():
            if nm.endswith(sufixos_publicados) and nm not in publicados:
                motivo = (f"arquivo listado no .vsc e no {fonte}, mas indisponível no "
                          "servidor do TSE (HTTP 404)" if nm in indisponiveis else
                          f"arquivo listado no .vsc, mas ausente no {fonte} do TSE")
                div("arquivo_ausente_tse", nm, None, h.hex(), motivo)
    return {"linhas": linhas, "verificacao": verif, "divergencias": divs}


_BATCH = None


def _votos_presidente(bu, eleicao: int | str | None = None) -> tuple:
    """Votos de Presidente (2026; por padrão o 1º turno, eleição 6257) de um
    BoletimUrna, no mesmo formato normalizado de _votos_bu."""
    from ..config import ELE2026

    eleicao = int(eleicao or ELE2026["eleicao_1t"])
    cargo = ELE2026["cargo_presidente"]
    out = []
    for res in bu.resultados_por_eleicao:
        if res.id_eleicao != eleicao:
            continue
        for rc in res.resultados:
            if rc.codigo_cargo != cargo:
                continue
            out.extend((v.tipo_voto.value, v.codigo_votavel or 0, v.quantidade or 0)
                       for v in rc.votos)
    return tuple(sorted(out))


def analisar_secao_2026(ident: dict, conjunto: dict, modelo_cod: int | None,
                        turno: int = 1, data: str | None = None) -> dict:
    """Auditoria por seção de 2022 (BatchAnalyzer) aplicada a BU e log em memória.

    Usa o BU da urna (-bu.dat) ou, na falta, o do Sistema de Apuração
    (-busa.dat), e o log da urna (-log.jez) ou do SA (-logsa.jez).
    turno define o prefixo do secao_id ('1T/' ou '2T/'); data (DD/MM/AAAA,
    padrão: a data do turno) filtra o log, que no 2º turno acumula o 1º.
    Retorna {"secao_log": dict, "issues": [linhas], "bu_obj": BoletimUrna|None}.
    """
    from ..database.rows import SECOES_COLUMNS, extract_rows
    from ..downloader.ele2026 import parametros_turno
    from .batch import BatchAnalyzer

    global _BATCH
    if _BATCH is None:
        _BATCH = BatchAnalyzer()
    arqs = {tp: (nm, raw) for tp, nm, raw in conjunto["arquivos"] if raw is not None}
    bu = arqs.get("bu") or arqs.get("busa")
    lg = arqs.get("log") or arqs.get("logsa")
    loc = {"uf": ident["uf"], "municipio": ident["cd_mun"], "zona": ident["zona"],
           "secao": ident["secao"]}
    modelo = None
    if modelo_cod:
        modelo = str(2000 + modelo_cod) if modelo_cod < 100 else str(modelo_cod)
    result = _BATCH.analyze_section_bytes(
        loc, bu[1] if bu else None, lg[1] if lg else None, turno=int(turno),
        turno_date=data or parametros_turno(turno)["data"], modelo=modelo,
        nome_bu=bu[0] if bu else "bu.dat", nome_log=lg[0] if lg else "log.jez")
    rows = extract_rows(result)
    secao_log = dict(zip(SECOES_COLUMNS, rows.secao, strict=True))
    secao_log["secao_id"] = secao_log.pop("id")
    secao_log["cd_mun"] = ident["cd_mun"]
    secao_log["tem_log"] = lg is not None
    secao_log["origem_bu"] = ("bu" if "bu" in arqs else "busa") if bu else None
    return {"secao_log": secao_log, "issues": rows.issues, "bu_obj": result.get("bu_obj")}


def auditar_secao(ident: dict, conjuntos: list[dict], escolhido: int = -1,
                  votos_esperados: tuple | None = None, analisar: bool = False,
                  turno: int = 1, eleicao: int | str | None = None,
                  data: str | None = None) -> dict:
    """Audita todos os conjuntos de arquivos de uma seção.

    Executada no pool de processos (só recebe tipos serializáveis).
    escolhido: índice do conjunto usado para os campos da seção (o hash
    totalizado). votos_esperados: tupla ordenada (tipo_voto, numero, votos)
    já coletada; None desliga a conferência. turno, eleicao e data seguem
    parametros_turno(turno) quando não informados (1º turno: eleição 6257,
    04/10/2026; 2º turno: eleição 6258, 25/10/2026).
    Retorna {"linhas", "secao", "divergencias"}.
    """
    from ..config import MODELOS_URNA
    from ..downloader.ele2026 import parametros_turno

    pt = parametros_turno(turno)
    eleicao = int(eleicao or pt["eleicao"])
    data = data or pt["data"]

    linhas: list[dict] = []
    divs: list[dict] = []
    res = [auditar_conjunto(ident, c) for c in conjuntos]
    for r in res:
        linhas.extend(r["linhas"])
        divs.extend(r["divergencias"])
    principal = res[escolhido] if res else None
    v = (principal or {}).get("verificacao") or {}
    motivos: list[str] = []
    for c, r in zip(conjuntos, res, strict=True):
        vv = r["verificacao"]
        pre = f"[{c['token']}] " if len(conjuntos) > 1 else ""
        if vv is None:
            motivos.append(pre + "conjunto sem arquivo de assinatura (.vsc)")
        else:
            motivos.extend(pre + m for m in vv["falhas"] + vv["motivos"])
        motivos.extend(f"{pre}arquivo listado no aux.json e indisponível no servidor "
                       f"(HTTP 404): {nm}" for _tp, nm, raw in c["arquivos"] if raw is None)
    validas = [r["verificacao"]["assinatura_valida"] for r in res if r["verificacao"]]
    if any(x is False for x in validas):
        assinatura_valida = False
    elif validas and all(x is True for x in validas) and len(validas) == len(res):
        assinatura_valida = True
    else:
        assinatura_valida = None
    analise = None
    if analisar and conjuntos:
        try:
            analise = analisar_secao_2026(ident, conjuntos[escolhido], v.get("modelo_cod"),
                                          turno, data)
        except Exception as e:  # noqa: BLE001 - falha da análise não derruba a auditoria
            motivos.append(f"análise BU/log falhou: {e!r}"[:200])
    votos_conferem = None
    if votos_esperados is not None and conjuntos:
        arqs = {tp: raw for tp, _nm, raw in conjuntos[escolhido]["arquivos"]
                if raw is not None}
        raw_bu = arqs.get("bu") or arqs.get("busa")
        if raw_bu is not None:
            try:
                if analise is not None and analise["bu_obj"] is not None:
                    votos_conferem = (_votos_presidente(analise["bu_obj"], eleicao)
                                      == votos_esperados)
                else:
                    votos_conferem = _votos_bu(raw_bu, eleicao) == votos_esperados
            except Exception as e:  # noqa: BLE001 - BU ilegível vira motivo
                motivos.append(f"BU não decodificado: {e!r}"[:200])
            if votos_conferem is False:
                motivos.append("votos do BU diferem de votos_presidente_2026.parquet")
    cod = v.get("modelo_cod")
    secao = {
        **ident,
        "status_secao": "ok" if linhas else "sem_arquivos",
        "n_arquivos": len(linhas),
        "n_hash_confere": sum(1 for x in linhas if x["hash_confere"] is True),
        "n_hash_diverge": sum(1 for x in linhas if x["hash_confere"] is False),
        "n_sem_hash": sum(1 for x in linhas
                          if x["hash_confere"] is None and x["disponivel"]),
        "n_indisponiveis": sum(1 for x in linhas if not x["disponivel"]),
        "assinatura_valida": assinatura_valida,
        "assinatura_algoritmo": v.get("algoritmo"),
        "cert_subject": v.get("cert_subject"),
        "cert_issuer": v.get("cert_issuer"),
        "cert_serial": v.get("cert_serial"),
        "cert_sha256": v.get("cert_sha256"),
        "modelo_urna": MODELOS_URNA.get(cod, f"Modelo_{cod}") if cod else None,
        "motivo": "; ".join(motivos)[:2000] or None,
        "votos_conferem": votos_conferem,
    }
    out = {"linhas": linhas, "secao": secao, "divergencias": divs}
    if analise is not None:
        out["secao_log"] = analise["secao_log"]
        out["issues"] = analise["issues"]
    return out
