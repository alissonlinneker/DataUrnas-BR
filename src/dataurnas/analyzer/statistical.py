"""Análise estatística de dados de votação."""

import logging
import math
from collections import defaultdict

from ..models import BoletimUrna, Issue, IssueSeverity

logger = logging.getLogger(__name__)

# Limiares para detecção de anomalias
LIMIAR_NULOS_PCT = 15.0  # % de nulos acima disso e anômalo
LIMIAR_BRANCOS_PCT = 10.0  # % de brancos acima disso e anômalo
LIMIAR_ABSTENCAO_PCT = 40.0  # % de abstenção acima disso para alertar
LIMIAR_BIOMETRIA_PCT = 30.0  # % de liberação por código (sem biometria) acima disso


class StatisticalAnalyzer:
    """Análise estatística de padrões de votação."""

    def analyze_bu(self, bu: BoletimUrna) -> list[Issue]:
        """Analisa um BU individual para padrões anômalos."""
        issues = []
        issues.extend(self._check_nulos_brancos(bu))
        issues.extend(self._check_biometria(bu))
        issues.extend(self._check_abstencao(bu))
        return issues

    def _check_nulos_brancos(self, bu: BoletimUrna) -> list[Issue]:
        """Verifica proporção de votos nulos e brancos."""
        issues = []

        for eleicao in bu.resultados_por_eleicao:
            for resultado in eleicao.resultados:
                total = sum(v.quantidade for v in resultado.votos)
                if total == 0:
                    continue

                nulos = sum(
                    v.quantidade for v in resultado.votos
                    if v.tipo_voto.value == "nulo"
                )
                brancos = sum(
                    v.quantidade for v in resultado.votos
                    if v.tipo_voto.value == "branco"
                )

                pct_nulos = (nulos / total) * 100
                pct_brancos = (brancos / total) * 100

                if pct_nulos > LIMIAR_NULOS_PCT:
                    issues.append(
                        Issue(
                            codigo="I03",
                            severidade=IssueSeverity.INFO,
                            descricao=(
                                f"Proporção elevada de nulos: {pct_nulos:.1f}% "
                                f"para {resultado.nome_cargo} "
                                f"({nulos}/{total})"
                            ),
                            uf=str(bu.uf),
                            municipio=str(bu.municipio),
                            zona=str(bu.zona),
                            secao=str(bu.secao),
                            detalhes={
                                "cargo": resultado.nome_cargo,
                                "nulos": nulos,
                                "total": total,
                                "percentual": round(pct_nulos, 2),
                            },
                        )
                    )

                if pct_brancos > LIMIAR_BRANCOS_PCT:
                    issues.append(
                        Issue(
                            codigo="I04",
                            severidade=IssueSeverity.INFO,
                            descricao=(
                                f"Proporção elevada de brancos: {pct_brancos:.1f}% "
                                f"para {resultado.nome_cargo} "
                                f"({brancos}/{total})"
                            ),
                            uf=str(bu.uf),
                            municipio=str(bu.municipio),
                            zona=str(bu.zona),
                            secao=str(bu.secao),
                            detalhes={
                                "cargo": resultado.nome_cargo,
                                "brancos": brancos,
                                "total": total,
                                "percentual": round(pct_brancos, 2),
                            },
                        )
                    )

        return issues

    def _check_biometria(self, bu: BoletimUrna) -> list[Issue]:
        """Verifica proporção de liberação por código vs biometria."""
        issues = []

        lib_codigo = bu.qtd_eleitores_lib_codigo
        comp_bio = bu.qtd_eleitores_comp_biometrico

        total = lib_codigo + comp_bio
        if total == 0:
            return issues

        pct_codigo = (lib_codigo / total) * 100

        if pct_codigo > LIMIAR_BIOMETRIA_PCT:
            issues.append(
                Issue(
                    codigo="M06",
                    severidade=IssueSeverity.MEDIUM,
                    descricao=(
                        f"Alta taxa de liberação por código (sem biometria): "
                        f"{pct_codigo:.1f}% ({lib_codigo}/{total})"
                    ),
                    uf=str(bu.uf),
                    municipio=str(bu.municipio),
                    zona=str(bu.zona),
                    secao=str(bu.secao),
                    detalhes={
                        "lib_codigo": lib_codigo,
                        "comp_biometrico": comp_bio,
                        "total": total,
                        "percentual": round(pct_codigo, 2),
                    },
                    base_legal="Resolução TSE 23.669/2021: biometria obrigatória",
                )
            )

        return issues

    def _check_abstencao(self, bu: BoletimUrna) -> list[Issue]:
        """Verifica taxa de abstenção."""
        issues = []

        for eleicao in bu.resultados_por_eleicao:
            aptos = eleicao.eleitores_aptos
            if aptos == 0:
                continue

            # Pegar maior comparecimento entre cargos
            max_comp = max(
                (r.comparecimento for r in eleicao.resultados if r.comparecimento > 0),
                default=0,
            )

            if max_comp == 0:
                continue

            abstencao = ((aptos - max_comp) / aptos) * 100

            if abstencao > LIMIAR_ABSTENCAO_PCT:
                issues.append(
                    Issue(
                        codigo="I05",
                        severidade=IssueSeverity.INFO,
                        descricao=(
                            f"Alta taxa de abstenção: {abstencao:.1f}% "
                            f"({aptos - max_comp}/{aptos}) na eleição {eleicao.id_eleicao}"
                        ),
                        uf=str(bu.uf),
                        municipio=str(bu.municipio),
                        zona=str(bu.zona),
                        secao=str(bu.secao),
                        detalhes={
                            "eleicao": eleicao.id_eleicao,
                            "aptos": aptos,
                            "comparecimento": max_comp,
                            "abstencao_pct": round(abstencao, 2),
                        },
                    )
                )

        return issues


# Cargos cujo número de candidato é único no país inteiro
_CARGOS_NACIONAIS = {1, 2}  # Presidente, Vice-Presidente
# Cargos municipais: número só é único dentro do município
_CARGOS_MUNICIPAIS = {11, 12, 13}  # Prefeito, Vice-Prefeito, Vereador


def escopo_candidatura(codigo_cargo: int, uf: str = "", municipio="") -> str:
    """Circunscrição em que o número do candidato é único.

    Presidente: "BR". Governador, Senador e Deputados: a UF. Cargos
    municipais: "UF/municipio". Sem UF conhecida, cargos não nacionais
    ficam em "??" para nunca serem somados com outra circunscrição.
    """
    if codigo_cargo in _CARGOS_NACIONAIS:
        return "BR"
    uf_key = (uf or "??").lower()
    if codigo_cargo in _CARGOS_MUNICIPAIS:
        return f"{uf_key}/{municipio or '??'}"
    return uf_key


class VoteAggregator:
    """Agrega votos por candidato através de múltiplas seções.

    A chave de agregação é (turno, circunscrição, cargo, número): o número
    de Governador, Senador e Deputados só é único dentro da UF, e votos do
    1º e do 2º turno nunca podem ser somados.
    """

    def __init__(self):
        # (turno, escopo, cargo) -> código -> info
        self._votos: dict[tuple[int, str, str], dict[str, dict]] = defaultdict(
            lambda: defaultdict(lambda: {
                "votos": 0,
                "partido": None,
                "secoes": 0,
            })
        )
        # (turno, cargo) -> totais
        self._totais_cargo: dict[tuple[int, str], dict] = defaultdict(
            lambda: {
                "nominais": 0,
                "brancos": 0,
                "nulos": 0,
                "legenda": 0,
                "total": 0,
                "comparecimento": 0,
                "secoes": 0,
            }
        )

    def add_bu(self, bu: BoletimUrna, uf: str = "", turno: int = 1, municipio=""):
        """Adiciona dados de um BU à agregação."""
        uf = uf or bu.uf or ""
        municipio = municipio or bu.municipio or ""
        for eleicao in bu.resultados_por_eleicao:
            for resultado in eleicao.resultados:
                cargo = resultado.nome_cargo
                escopo = escopo_candidatura(resultado.codigo_cargo, uf, municipio)
                totais = self._totais_cargo[(turno, cargo)]
                totais["comparecimento"] += resultado.comparecimento
                totais["secoes"] += 1

                for voto in resultado.votos:
                    tipo = voto.tipo_voto.value
                    qtd = voto.quantidade
                    totais["total"] += qtd

                    if tipo == "nominal":
                        totais["nominais"] += qtd
                        cod = str(voto.codigo_votavel or 0)
                        info = self._votos[(turno, escopo, cargo)][cod]
                        info["votos"] += qtd
                        if info["partido"] is None:
                            info["partido"] = voto.partido
                        info["secoes"] += 1
                    elif tipo == "branco":
                        totais["brancos"] += qtd
                    elif tipo == "nulo":
                        totais["nulos"] += qtd
                    elif tipo == "legenda":
                        totais["legenda"] += qtd

    def get_results(self) -> dict:
        """Retorna resultados agregados.

        Estrutura:
            totais_por_cargo[turno][cargo] -> totais
            votos_por_candidato[turno][escopo][cargo] -> lista ordenada
        """
        results: dict = {
            "totais_por_cargo": {},
            "votos_por_candidato": {},
        }

        for (turno, cargo), totais in sorted(self._totais_cargo.items()):
            results["totais_por_cargo"].setdefault(turno, {})[cargo] = dict(totais)

        for (turno, escopo, cargo), candidatos in sorted(self._votos.items()):
            sorted_cands = sorted(
                candidatos.items(),
                key=lambda x: x[1]["votos"],
                reverse=True,
            )
            por_escopo = results["votos_por_candidato"].setdefault(turno, {})
            por_escopo.setdefault(escopo, {})[cargo] = [
                {
                    "codigo": cod,
                    "partido": info["partido"],
                    "votos": info["votos"],
                    "secoes": info["secoes"],
                }
                for cod, info in sorted_cands
            ]

        return results


def compute_outlier_scores(values: list[float]) -> list[float]:
    """Calcula z-scores para detecção de outliers.

    Usa desvio padrão populacional. Série constante (desvio zero) devolve
    zeros: nenhum ponto se destaca dos demais.

    Returns:
        Lista de z-scores (abs). Valores > 2.0 são potenciais outliers.
    """
    if len(values) < 3:
        return [0.0] * len(values)

    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    if variance == 0:
        return [0.0] * len(values)
    std = math.sqrt(variance)

    return [abs((x - mean) / std) for x in values]
