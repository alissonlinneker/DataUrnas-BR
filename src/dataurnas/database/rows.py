"""Conversão do resultado de análise de uma seção em linhas do banco.

Fonte única da montagem de linhas usada por DuckDBStore e pelos scripts de
rebuild (inclusive o paralelo), para que as regras não divirjam.
"""

from dataclasses import dataclass, field

from ..analyzer.timezones import get_tz_offset
from ..config import REGIOES
from ..models import TipoVoto

UF_REGIAO: dict[str, str] = {uf: regiao for regiao, ufs in REGIOES.items() for uf in ufs}

# Ordem das colunas da tabela seções (igual ao CREATE TABLE)
SECOES_COLUMNS = (
    "id", "turno", "uf", "regiao", "municipio", "zona", "secao",
    "modelo_urna", "tipo_urna", "versao_sw", "fuso_offset",
    "emissao", "eleitores_aptos", "comparecimento", "lib_codigo", "comp_biometrico",
    "pct_biometria", "pct_abstencao",
    "hora_abertura", "hora_encerramento", "duracao_min",
    "reboots", "erros_log", "alertas_mesario", "votos_log", "substituicoes",
    "is_reserva", "has_issues", "n_issues",
)


@dataclass
class SectionRows:
    """Linhas de uma seção prontas para inserção."""

    secao_id: str
    secao: list
    issues: list[list] = field(default_factory=list)  # sem a coluna id
    votos: list[list] = field(default_factory=list)
    totais: list[list] = field(default_factory=list)


def make_secao_id(turno: int, uf: str, municipio, zona, secao) -> str:
    return f"{turno}T/{uf}/{municipio}/{zona}/{secao}"


def extract_rows(result: dict) -> SectionRows:
    """Monta as linhas de seções, issues, votos e totais_cargo.

    Args:
        result: dicionário devolvido por BatchAnalyzer.analyze_section().
    """
    uf = result["uf"]
    turno = result.get("turno", 1)
    secao_id = make_secao_id(turno, uf, result["municipio"], result["zona"], result["secao"])

    regiao = UF_REGIAO.get(uf.lower(), "desconhecida")
    fuso = get_tz_offset(uf, result["municipio"])
    bu_info = result.get("bu")
    timing = result.get("log_timing") or {}
    log_events = result.get("log_events") or {}

    eleitores_aptos = 0
    comparecimento = 0
    if bu_info:
        eleicoes = bu_info.get("eleicoes", [])
        if eleicoes:
            eleitores_aptos = eleicoes[0].get("aptos", 0)
            comparecimento = max(
                (c.get("comparecimento", 0) for el in eleicoes for c in el.get("cargos", [])),
                default=0,
            )

    lib_codigo = bu_info.get("lib_codigo", 0) if bu_info else 0
    comp_bio = bu_info.get("comp_biometrico", 0) if bu_info else 0
    total_bio = lib_codigo + comp_bio
    pct_bio = round(comp_bio / total_bio * 100, 2) if total_bio > 0 else None
    pct_abs = (
        round((eleitores_aptos - comparecimento) / eleitores_aptos * 100, 2)
        if eleitores_aptos > 0 else None
    )

    issues = result.get("issues", [])
    secao_row = [
        secao_id, turno,
        uf, regiao, result["municipio"], result["zona"], result["secao"],
        result.get("modelo"), result.get("tipo_urna"), result.get("versao_sw"),
        fuso,
        bu_info.get("emissao") if bu_info else None,
        eleitores_aptos, comparecimento, lib_codigo, comp_bio, pct_bio, pct_abs,
        timing.get("hora_abertura"), timing.get("hora_encerramento"),
        timing.get("duracao_votacao_min"),
        log_events.get("reboots", 0), log_events.get("erros", 0),
        log_events.get("alertas_mesario", 0), log_events.get("votos_computados", 0),
        log_events.get("substituicoes", 0),
        result.get("tipo_urna") == "reservaSecao", len(issues) > 0, len(issues),
    ]

    rows = SectionRows(secao_id=secao_id, secao=secao_row)
    for issue in issues:
        rows.issues.append([
            secao_id, issue.codigo, issue.severidade.value,
            issue.descricao, issue.base_legal,
            str(issue.detalhes) if issue.detalhes else None,
        ])

    bu_obj = result.get("bu_obj")
    if bu_obj is not None:
        for eleicao in bu_obj.resultados_por_eleicao:
            for cargo in eleicao.resultados:
                soma = dict.fromkeys(TipoVoto, 0)
                for voto in cargo.votos:
                    rows.votos.append([
                        secao_id, eleicao.id_eleicao,
                        cargo.nome_cargo, cargo.codigo_cargo,
                        voto.tipo_voto.value, voto.codigo_votavel, voto.partido,
                        voto.quantidade,
                    ])
                    soma[voto.tipo_voto] += voto.quantidade
                nominais = soma[TipoVoto.NOMINAL]
                brancos = soma[TipoVoto.BRANCO]
                nulos = soma[TipoVoto.NULO]
                legenda = soma[TipoVoto.LEGENDA]
                rows.totais.append([
                    secao_id, eleicao.id_eleicao,
                    cargo.nome_cargo, cargo.codigo_cargo,
                    cargo.comparecimento, nominais, brancos, nulos, legenda,
                    nominais + brancos + nulos + legenda,
                ])

    return rows
