"""KPIs do topo das páginas da auditoria 2022."""

from __future__ import annotations

from dataurnas.dashboard.components.formatting import fmt_int, fmt_pct, pct
from dataurnas.dashboard.components.ui import empty_state, kpi_cards


def render_kpis(store, f) -> bool:
    """Cartões de resumo; devolve False (e mostra estado vazio) se não há dados."""
    summary_df = store.query_df(f"""
        SELECT
            COUNT(*) AS total_secoes,
            COUNT(*) FILTER (WHERE has_issues) AS com_issues,
            COALESCE(SUM(eleitores_aptos), 0) AS eleitores,
            COALESCE(SUM(comparecimento), 0) AS comparecimento,
            COALESCE(SUM(reboots), 0) AS total_reboots,
            COUNT(DISTINCT uf) AS ufs
        FROM secoes s
        WHERE {f['where']}
    """, f["params"])

    if summary_df.empty or int(summary_df.iloc[0]["total_secoes"] or 0) == 0:
        empty_state(
            "Nenhum dado para os filtros selecionados",
            "Remova alguns filtros na barra lateral para ampliar a seleção.",
        )
        return False

    row = summary_df.iloc[0]
    total = int(row["total_secoes"])
    eleitores = int(row["eleitores"])
    comparecimento = int(row["comparecimento"])
    com_issues = int(row["com_issues"])
    kpi_cards([
        {"label": "Seções analisadas", "value": fmt_int(total), "help": f"{int(row['ufs'])} UFs"},
        {"label": "Com inconsistências", "value": fmt_int(com_issues),
         "help": f"{fmt_pct(pct(com_issues, total), 1)} das seções", "tone": "amber"},
        {"label": "Eleitores aptos", "value": fmt_int(eleitores)},
        {"label": "Comparecimento", "value": fmt_int(comparecimento), "tone": "green"},
        {"label": "Abstenção", "value": fmt_pct(100 - pct(comparecimento, eleitores), 1) if eleitores else "-",
         "tone": "grey"},
        {"label": "Reboots", "value": fmt_int(row["total_reboots"]), "tone": "red"},
    ])
    return True
