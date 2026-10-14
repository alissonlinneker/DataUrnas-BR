"""Fonte única de dados de referência usados pelo dashboard.

Resultados oficiais de 2022 (Presidente) divulgados pelo TSE e o catálogo de
códigos de inconsistência. Antes havia duas cópias divergentes (app.py e
analysis.py); ambos os módulos agora leem daqui.

Fonte dos resultados: TSE, resultados.tse.jus.br, totalização oficial de
02/10/2022 (1º turno) e 30/10/2022 (2º turno).
"""

from __future__ import annotations

try:  # limiar real usado pelo analisador; o fallback mantém o valor documentado
    from dataurnas.analyzer.statistical import LIMIAR_ABSTENCAO_PCT
except ImportError:  # pragma: no cover
    LIMIAR_ABSTENCAO_PCT = 40.0

FONTE_TSE_2022 = "TSE, totalização oficial (resultados.tse.jus.br), Eleições Gerais 2022"

TSE_2022: dict[int, dict] = {
    1: {
        "turno": 1,
        "label": "1º Turno",
        "data": "02/10/2022",
        "eleitores_aptos": 156_454_011,
        "comparecimento": 123_682_372,
        "abstencao": 32_770_982,
        "votos_validos": 118_229_719,
        "brancos": 1_964_779,
        "nulos": 3_487_874,
        "pct_abstencao": 20.95,
        "candidatos": {
            13: {"nome": "Luiz Inácio Lula da Silva", "curto": "Lula", "partido": "PT",
                 "votos": 57_259_504, "pct": 48.43},
            22: {"nome": "Jair Messias Bolsonaro", "curto": "Bolsonaro", "partido": "PL",
                 "votos": 51_072_345, "pct": 43.20},
            15: {"nome": "Simone Tebet", "curto": "Tebet", "partido": "MDB",
                 "votos": 4_915_423, "pct": 4.16},
            12: {"nome": "Ciro Gomes", "curto": "Ciro", "partido": "PDT",
                 "votos": 3_599_287, "pct": 3.04},
        },
        "diferenca_1_2": 6_187_159,
        "vencedor": 13,
    },
    2: {
        "turno": 2,
        "label": "2º Turno",
        "data": "30/10/2022",
        "eleitores_aptos": 156_454_011,
        "comparecimento": 124_252_796,
        "abstencao": 32_201_215,
        "votos_validos": 118_556_778,
        "brancos": 1_958_988,
        "nulos": 3_736_630,
        "pct_abstencao": 20.59,
        "candidatos": {
            13: {"nome": "Luiz Inácio Lula da Silva", "curto": "Lula", "partido": "PT",
                 "votos": 60_345_999, "pct": 50.90},
            22: {"nome": "Jair Messias Bolsonaro", "curto": "Bolsonaro", "partido": "PL",
                 "votos": 58_206_354, "pct": 49.10},
        },
        "diferenca_1_2": 2_139_645,
        "vencedor": 13,
    },
}


def oficial_resumo(turno: int) -> dict:
    """Formato compacto (chaves lula_pct/bolso_pct) usado pelo módulo de análise."""
    ref = TSE_2022[turno]
    return {
        "turno": turno,
        "eleitores_aptos": ref["eleitores_aptos"],
        "comparecimento": ref["comparecimento"],
        "votos_validos": ref["votos_validos"],
        "lula_pct": ref["candidatos"][13]["pct"],
        "bolso_pct": ref["candidatos"][22]["pct"],
        "diferenca": ref["diferenca_1_2"],
    }


def _limiar(valor: float) -> str:
    return f"{valor:g}".replace(".", ",")


# Catálogo único de códigos de inconsistência (descrição curta para a UI)
ISSUE_DESCRICOES: dict[str, str] = {
    "C01": "Hash SHA-512 inválido",
    "C05": "Total de votos > eleitores aptos",
    "C06": "Reinício durante votação",
    "A01": "Divergência de eleitores aptos entre eleições",
    "A02": "Votos > comparecimento",
    "A03": "Divergência de votos no log vs BU",
    "A04": "Abertura muito tardia",
    "A05": "Encerramento antes do horário",
    "A06": "Comparecimento divergente entre cargos",
    "E01": "Assinatura não verificável (falha de leitura ou arquivo ausente; não é hash inválido)",
    "E02": "BU com tipo de voto desconhecido (seção excluída dos totais)",
    "E03": "Duração negativa de votação no log",
    "I01": "Eventos de substituição/contingência",
    "I02": "Alertas de mesário elevados",
    "I03": "Proporção elevada de nulos",
    "I04": "Proporção elevada de brancos",
    "I05": f"Abstenção acima de {_limiar(LIMIAR_ABSTENCAO_PCT)}%",
    "I06": "Urna não padrão (reservaSeção)",
    "M01": "Abertura antes do horário ajustado",
    "M02": "Encerramento muito tarde",
    "M03": "Abertura não encontrada no log",
    "M04": "Número elevado de erros no log",
    "M05": "Ajustes de hora detectados",
    "M06": "Alta taxa de liberação sem biometria",
}


def issue_label(codigo: str) -> str:
    """Rótulo 'C01: Hash SHA-512 inválido' para listas e legendas."""
    desc = ISSUE_DESCRICOES.get(codigo)
    return f"{codigo}: {desc}" if desc else codigo
