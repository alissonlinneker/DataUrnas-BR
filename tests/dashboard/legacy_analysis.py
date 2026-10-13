"""Oráculo dos testes de equivalência: análises do dashboard ANTES dos agregados.

Cópia congelada das funções de ``dataurnas.dashboard.analysis`` que consultavam
a tabela ``votos`` linha a linha (e extraíam os dígitos de Benford em pandas).
Serve só para comparar resultados com a versão otimizada em
``test_aggregates_equivalencia.py``. Não editar: a ideia é preservar o
comportamento original.
"""
# ruff: noqa

import math
import re

import numpy as np
import pandas as pd
from scipy import stats

BENFORD_EXPECTED = {d: math.log10(1 + 1 / d) for d in range(1, 10)}

BENFORD_SECOND_EXPECTED = {}
for _d in range(0, 10):
    _prob = sum(math.log10(1 + 1 / (10 * _k + _d)) for _k in range(1, 10))
    BENFORD_SECOND_EXPECTED[_d] = _prob

_EMPTY_DF_CACHE = {}


def _empty_df(columns):
    """Retorna DataFrame vazio com as colunas especificadas."""
    key = tuple(columns)
    if key not in _EMPTY_DF_CACHE:
        _EMPTY_DF_CACHE[key] = pd.DataFrame(columns=columns)
    return _EMPTY_DF_CACHE[key].copy()


def _cramers_v(chi2, n, k):
    """Calcula Cramer's V a partir de chi2, n (total de observações), k (categorias).

    V = sqrt(chi2 / (n * (k - 1)))
    """
    if n == 0 or k <= 1:
        return 0.0
    return math.sqrt(chi2 / (n * (k - 1)))


def _benford_cramers_v_score(cramers_v_value):
    """Converte Cramer's V em score (0-100) para o confidence score.

    V < 0.05:  conforme     -> score 100
    V < 0.10:  aceitavel    -> score 75
    V < 0.20:  atencao      -> score 50
    V >= 0.20: não conforme -> score 0
    """
    if cramers_v_value < 0.05:
        return 100.0
    elif cramers_v_value < 0.10:
        return 75.0
    elif cramers_v_value < 0.20:
        return 50.0
    else:
        return 0.0


def benford_first_digit(store, f) -> pd.DataFrame:
    """Distribuição do primeiro dígito dos votos por candidato (Presidente).

    Returns:
        DataFrame com: candidato, digito (1-9), contagem, pct_observado, pct_esperado
    """
    cols = ["candidato", "digito", "contagem", "pct_observado", "pct_esperado"]

    df = store.query_df(f"""
        SELECT
            v.codigo_candidato AS candidato,
            v.quantidade
        FROM votos v
        JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']}
            AND v.cargo = 'Presidente'
            AND v.tipo_voto = 'nominal'
            AND v.quantidade > 0
    """, f["params"])

    if df.empty:
        return _empty_df(cols)

    # Extrair primeiro dígito
    df["digito"] = df["quantidade"].astype(str).str[0].astype(int)
    df = df[df["digito"].between(1, 9)]

    if df.empty:
        return _empty_df(cols)

    # Contar por candidato e dígito
    grouped = df.groupby(["candidato", "digito"]).size().reset_index(name="contagem")

    # Calcular percentual observado por candidato
    totals = grouped.groupby("candidato")["contagem"].transform("sum")
    grouped["pct_observado"] = np.where(
        totals > 0,
        (grouped["contagem"] / totals * 100).round(4),
        0.0,
    )

    # Adicionar percentual esperado (Benford)
    grouped["pct_esperado"] = grouped["digito"].map(
        lambda d: round(BENFORD_EXPECTED[d] * 100, 4)
    )

    return grouped[cols].sort_values(["candidato", "digito"]).reset_index(drop=True)


def benford_chi_squared(store, f) -> pd.DataFrame:
    """Teste chi-quadrado por candidato vs distribuição esperada de Benford.

    Returns:
        DataFrame com: candidato, chi2, p_value, conforme (bool: p_value > 0.05)
    """
    cols = ["candidato", "chi2", "p_value", "conforme"]

    digit_df = benford_first_digit(store, f)
    if digit_df.empty:
        return _empty_df(cols)

    results = []
    for candidato, grp in digit_df.groupby("candidato"):
        # Garantir que todos os dígitos 1-9 estejam presentes
        full = pd.DataFrame({"digito": range(1, 10)})
        merged = full.merge(grp[["digito", "contagem"]], on="digito", how="left").fillna(0)
        observed = merged["contagem"].values.astype(float)
        total = observed.sum()

        if total == 0:
            continue

        expected = np.array([BENFORD_EXPECTED[d] * total for d in range(1, 10)])

        # Evitar expected zeros
        mask = expected > 0
        if mask.sum() == 0:
            continue

        chi2_stat, p_val = stats.chisquare(observed[mask], f_exp=expected[mask])

        results.append({
            "candidato": candidato,
            "chi2": round(float(chi2_stat), 4),
            "p_value": round(float(p_val), 6),
            "conforme": bool(p_val > 0.05),
        })

    if not results:
        return _empty_df(cols)

    return pd.DataFrame(results)[cols]


def benford_by_state(store, f) -> pd.DataFrame:
    """Conformidade Benford por estado para Presidente (candidatos 13 e 22).

    Returns:
        DataFrame com: uf, chi2_13, chi2_22, conforme_13, conforme_22
    """
    cols = ["uf", "chi2_13", "chi2_22", "conforme_13", "conforme_22"]

    df = store.query_df(f"""
        SELECT
            s.uf,
            v.codigo_candidato AS candidato,
            v.quantidade
        FROM votos v
        JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']}
            AND v.cargo = 'Presidente'
            AND v.tipo_voto = 'nominal'
            AND v.quantidade > 0
            AND v.codigo_candidato IN (13, 22)
    """, f["params"])

    if df.empty:
        return _empty_df(cols)

    df["digito"] = df["quantidade"].astype(str).str[0].astype(int)
    df = df[df["digito"].between(1, 9)]

    if df.empty:
        return _empty_df(cols)

    results = []
    for uf, uf_grp in df.groupby("uf"):
        row = {"uf": uf}
        for cand_id, suffix in [(13, "13"), (22, "22")]:
            cand_data = uf_grp[uf_grp["candidato"] == cand_id]
            if cand_data.empty:
                row[f"chi2_{suffix}"] = None
                row[f"conforme_{suffix}"] = None
                continue

            digit_counts = cand_data.groupby("digito").size()
            observed = np.array([digit_counts.get(d, 0) for d in range(1, 10)], dtype=float)
            total = observed.sum()

            if total < 10:  # Amostra muito pequena
                row[f"chi2_{suffix}"] = None
                row[f"conforme_{suffix}"] = None
                continue

            expected = np.array([BENFORD_EXPECTED[d] * total for d in range(1, 10)])
            mask = expected > 0
            if mask.sum() == 0:
                row[f"chi2_{suffix}"] = None
                row[f"conforme_{suffix}"] = None
                continue

            chi2_stat, p_val = stats.chisquare(observed[mask], f_exp=expected[mask])
            row[f"chi2_{suffix}"] = round(float(chi2_stat), 4)
            row[f"conforme_{suffix}"] = bool(p_val > 0.05)

        results.append(row)

    if not results:
        return _empty_df(cols)

    return pd.DataFrame(results)[cols].sort_values("uf").reset_index(drop=True)


def benford_second_digit(store, f) -> pd.DataFrame:
    """Distribuição do segundo dígito dos votos por candidato (Presidente).

    A distribuição esperada do 2o dígito de Benford é:
        P(d) = sum_{k=1}^{9} log10(1 + 1/(10k + d)), para d = 0..9

    Votos com apenas 1 dígito são excluídos (não possuem segundo dígito).

    Returns:
        DataFrame com: candidato, digito, quantidade, percentual
    """
    cols = ["candidato", "digito", "quantidade", "percentual"]

    df = store.query_df(f"""
        SELECT
            v.codigo_candidato AS candidato,
            v.quantidade
        FROM votos v
        JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']}
            AND v.cargo = 'Presidente'
            AND v.tipo_voto = 'nominal'
            AND v.quantidade >= 10
    """, f["params"])

    if df.empty:
        return _empty_df(cols)

    # Extrair segundo dígito: posição [1] da representação string
    df["digito"] = df["quantidade"].astype(str).str[1].astype(int)

    if df.empty:
        return _empty_df(cols)

    # Contar por candidato e dígito
    grouped = df.groupby(["candidato", "digito"]).size().reset_index(name="quantidade")

    # Calcular percentual observado por candidato
    totals = grouped.groupby("candidato")["quantidade"].transform("sum")
    grouped["percentual"] = np.where(
        totals > 0,
        (grouped["quantidade"] / totals * 100).round(4),
        0.0,
    )

    return grouped[cols].sort_values(["candidato", "digito"]).reset_index(drop=True)


def benford_second_digit_chi(store, f) -> list:
    """Teste chi-quadrado + KS + Cramer's V por candidato vs Benford 2o dígito.

    Returns:
        Lista de dicts com: candidato, chi2, p_chi2, ks_stat, p_ks, cramers_v, conforme
    """
    digit_df = benford_second_digit(store, f)
    if digit_df.empty:
        return []

    results = []
    for candidato, grp in digit_df.groupby("candidato"):
        # Garantir que todos os dígitos 0-9 estejam presentes
        full = pd.DataFrame({"digito": range(0, 10)})
        merged = full.merge(
            grp[["digito", "quantidade"]], on="digito", how="left"
        ).fillna(0)
        observed = merged["quantidade"].values.astype(float)
        total = observed.sum()

        if total == 0:
            continue

        expected = np.array(
            [BENFORD_SECOND_EXPECTED[d] * total for d in range(0, 10)]
        )

        # Evitar expected zeros
        mask = expected > 0
        if mask.sum() == 0:
            continue

        # Chi-quadrado
        chi2_stat, p_chi2 = stats.chisquare(observed[mask], f_exp=expected[mask])

        # Kolmogorov-Smirnov: comparar distribuições acumuladas empíricas
        obs_freq = observed / total
        exp_freq = np.array([BENFORD_SECOND_EXPECTED[d] for d in range(0, 10)])
        exp_freq = exp_freq / exp_freq.sum()

        obs_cdf = np.cumsum(obs_freq)
        exp_cdf = np.cumsum(exp_freq)

        ks_stat = float(np.max(np.abs(obs_cdf - exp_cdf)))
        sample = np.repeat(np.arange(10), observed.astype(int))
        if len(sample) > 0:
            ks_result = stats.kstest(
                sample,
                lambda x, cdf=exp_cdf: np.interp(x, np.arange(10), cdf),
            )
            p_ks = float(ks_result.pvalue)
        else:
            p_ks = np.nan

        # Cramer's V
        k = int(mask.sum())
        n = total
        v = _cramers_v(float(chi2_stat), n, k)

        conforme = bool(p_chi2 > 0.05) and (v < 0.10)

        results.append({
            "candidato": candidato,
            "chi2": round(float(chi2_stat), 4),
            "p_chi2": round(float(p_chi2), 6),
            "ks_stat": round(ks_stat, 6),
            "p_ks": round(p_ks, 6) if not np.isnan(p_ks) else np.nan,
            "cramers_v": round(v, 6),
            "conforme": conforme,
        })

    return results


def benford_all_offices(store, f) -> pd.DataFrame:
    """Aplica Benford 1o dígito para TODOS os cargos (não apenas Presidente).

    Returns:
        DataFrame com: cargo, chi2, p_value, cramers_v, conforme
    """
    cols = ["cargo", "chi2", "p_value", "cramers_v", "conforme"]

    df = store.query_df(f"""
        SELECT
            v.cargo,
            v.quantidade
        FROM votos v
        JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']}
            AND v.tipo_voto = 'nominal'
            AND v.quantidade > 0
    """, f["params"])

    if df.empty:
        return _empty_df(cols)

    df["digito"] = df["quantidade"].astype(str).str[0].astype(int)
    df = df[df["digito"].between(1, 9)]

    if df.empty:
        return _empty_df(cols)

    results = []
    for cargo, grp in df.groupby("cargo"):
        digit_counts = grp.groupby("digito").size()
        observed = np.array(
            [digit_counts.get(d, 0) for d in range(1, 10)], dtype=float
        )
        total = observed.sum()

        if total < 10:
            continue

        expected = np.array([BENFORD_EXPECTED[d] * total for d in range(1, 10)])
        mask = expected > 0
        if mask.sum() == 0:
            continue

        chi2_stat, p_val = stats.chisquare(observed[mask], f_exp=expected[mask])

        k = int(mask.sum())
        v = _cramers_v(float(chi2_stat), total, k)

        results.append({
            "cargo": cargo,
            "chi2": round(float(chi2_stat), 4),
            "p_value": round(float(p_val), 6),
            "cramers_v": round(v, 6),
            "conforme": bool(p_val > 0.05),
        })

    if not results:
        return _empty_df(cols)

    return pd.DataFrame(results)[cols].sort_values("cargo").reset_index(drop=True)


def zscore_outliers(store, f, threshold=3.0) -> pd.DataFrame:
    """Seções com z-score > threshold em abstenção, biometria ou duração.

    Returns:
        DataFrame com: id, uf, municipio, zona, secao, metric, value, zscore
    """
    cols = ["id", "uf", "municipio", "zona", "secao", "metric", "value", "zscore"]

    metrics = [
        ("pct_abstencao", "abstencao"),
        ("pct_biometria", "biometria"),
        ("duracao_min", "duracao"),
    ]

    all_outliers = []
    for col_name, metric_label in metrics:
        df = store.query_df(f"""
            SELECT
                s.id, s.uf, s.municipio, s.zona, s.secao,
                s.{col_name} AS value,
                (s.{col_name} - AVG(s.{col_name}) OVER())
                    / NULLIF(STDDEV(s.{col_name}) OVER(), 0) AS zscore
            FROM secoes s
            WHERE {f['where']} AND s.{col_name} IS NOT NULL
        """, f["params"])

        if df.empty:
            continue

        outliers = df[df["zscore"].abs() > threshold].copy()
        if not outliers.empty:
            outliers["metric"] = metric_label
            outliers["zscore"] = outliers["zscore"].round(4)
            outliers["value"] = outliers["value"].round(4)
            all_outliers.append(outliers[cols])

    if not all_outliers:
        return _empty_df(cols)

    return pd.concat(all_outliers, ignore_index=True).sort_values(
        "zscore", ascending=False, key=abs
    ).reset_index(drop=True)


def outlier_summary(store, f) -> pd.DataFrame:
    """Resumo de outliers por estado e métrica.

    Returns:
        DataFrame com: uf, outliers_abstencao, outliers_biometria, outliers_duracao, total
    """
    cols = ["uf", "outliers_abstencao", "outliers_biometria", "outliers_duracao", "total"]

    outliers_df = zscore_outliers(store, f, threshold=3.0)
    if outliers_df.empty:
        return _empty_df(cols)

    pivot = outliers_df.groupby(["uf", "metric"]).size().unstack(fill_value=0)

    result = pd.DataFrame({"uf": pivot.index})
    result["outliers_abstencao"] = pivot.get("abstencao", pd.Series(0, index=pivot.index)).values
    result["outliers_biometria"] = pivot.get("biometria", pd.Series(0, index=pivot.index)).values
    result["outliers_duracao"] = pivot.get("duracao", pd.Series(0, index=pivot.index)).values
    result["total"] = result["outliers_abstencao"] + result["outliers_biometria"] + result["outliers_duracao"]

    return result[cols].sort_values("total", ascending=False).reset_index(drop=True)


def reboot_vote_distribution(store, f) -> pd.DataFrame:
    """Distribuição de votos para Presidente em seções com/sem reboot.

    Returns:
        DataFrame com: grupo, candidato, votos, pct
    """
    cols = ["grupo", "candidato", "votos", "pct"]

    df = store.query_df(f"""
        SELECT
            CASE WHEN s.reboots > 0 THEN 'Com Reboot' ELSE 'Sem Reboot' END AS grupo,
            v.codigo_candidato AS candidato,
            SUM(v.quantidade) AS votos
        FROM votos v
        JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']}
            AND v.cargo = 'Presidente'
            AND v.tipo_voto = 'nominal'
            AND v.codigo_candidato IN (13, 22)
        GROUP BY grupo, v.codigo_candidato
        ORDER BY grupo, votos DESC
    """, f["params"])

    if df.empty:
        return _empty_df(cols)

    # Calcular percentual por grupo
    totals_by_group = df.groupby("grupo")["votos"].transform("sum")
    df["pct"] = np.where(
        totals_by_group > 0,
        (df["votos"] / totals_by_group * 100).round(2),
        0.0,
    )

    return df[cols].reset_index(drop=True)


def reboot_by_state(store, f) -> pd.DataFrame:
    """Taxa de reboot e impacto por estado.

    Returns:
        DataFrame com: uf, secoes, secoes_reboot, pct_reboot,
                       pct_lula_reboot, pct_lula_normal, diff_pp
    """
    cols = [
        "uf", "secoes", "secoes_reboot", "pct_reboot",
        "pct_lula_reboot", "pct_lula_normal", "diff_pp",
    ]

    # Seções por estado com/sem reboot
    secoes_df = store.query_df(f"""
        SELECT
            s.uf,
            COUNT(*) AS secoes,
            SUM(CASE WHEN s.reboots > 0 THEN 1 ELSE 0 END) AS secoes_reboot,
            ROUND(SUM(CASE WHEN s.reboots > 0 THEN 1.0 ELSE 0 END)
                  / NULLIF(COUNT(*), 0) * 100, 2) AS pct_reboot
        FROM secoes s
        WHERE {f['where']}
        GROUP BY s.uf
    """, f["params"])

    if secoes_df.empty:
        return _empty_df(cols)

    # Votos Lula por grupo reboot/normal por UF
    votos_df = store.query_df(f"""
        SELECT
            s.uf,
            CASE WHEN s.reboots > 0 THEN 'reboot' ELSE 'normal' END AS grupo,
            SUM(CASE WHEN v.codigo_candidato = 13 THEN v.quantidade ELSE 0 END) AS lula,
            SUM(v.quantidade) AS total
        FROM votos v
        JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']}
            AND v.cargo = 'Presidente'
            AND v.tipo_voto = 'nominal'
            AND v.codigo_candidato IN (13, 22)
        GROUP BY s.uf, grupo
    """, f["params"])

    if votos_df.empty:
        secoes_df["pct_lula_reboot"] = np.nan
        secoes_df["pct_lula_normal"] = np.nan
        secoes_df["diff_pp"] = np.nan
        return secoes_df[cols].sort_values("uf").reset_index(drop=True)

    votos_df["pct_lula"] = np.where(
        votos_df["total"] > 0,
        (votos_df["lula"] / votos_df["total"] * 100).round(2),
        np.nan,
    )

    pivot = votos_df.pivot_table(
        index="uf", columns="grupo", values="pct_lula", aggfunc="first"
    )

    result = secoes_df.merge(
        pivot.rename(columns={"reboot": "pct_lula_reboot", "normal": "pct_lula_normal"}),
        on="uf", how="left",
    )

    result["diff_pp"] = np.where(
        result["pct_lula_reboot"].notna() & result["pct_lula_normal"].notna(),
        (result["pct_lula_reboot"] - result["pct_lula_normal"]).round(2),
        np.nan,
    )

    return result[cols].sort_values("uf").reset_index(drop=True)


def reboot_candidate_correlation(store, f) -> dict:
    """Teste chi-quadrado: reboots favorecem algum candidato?

    Returns:
        dict com chi2, p_value, conclusion
    """
    df = reboot_vote_distribution(store, f)
    if df.empty or len(df) < 4:
        return {
            "chi2": None,
            "p_value": None,
            "conclusion": "Dados insuficientes para teste estatístico.",
        }

    # Montar tabela de contingência: grupo x candidato
    try:
        pivot = df.pivot_table(
            index="grupo", columns="candidato", values="votos", fill_value=0
        )

        if pivot.shape[0] < 2 or pivot.shape[1] < 2:
            return {
                "chi2": None,
                "p_value": None,
                "conclusion": "Dados insuficientes para tabela de contingência.",
            }

        chi2_stat, p_val, dof, expected = stats.chi2_contingency(pivot.values)
        chi2_stat = round(float(chi2_stat), 4)
        p_val = round(float(p_val), 6)

        if p_val > 0.05:
            conclusion = (
                f"NÃO há evidência estatística de que reboots favorecem um candidato "
                f"(chi2={chi2_stat}, p={p_val}, p > 0.05). "
                f"A distribuição de votos em seções com e sem reboot é estatisticamente similar."
            )
        else:
            conclusion = (
                f"Há diferença estatisticamente significativa na distribuição de votos "
                f"entre seções com e sem reboot (chi2={chi2_stat}, p={p_val}, p <= 0.05). "
                f"Isso pode refletir distribuição geográfica e não necessariamente causalidade."
            )

        return {"chi2": chi2_stat, "p_value": p_val, "conclusion": conclusion}

    except Exception as e:
        return {
            "chi2": None,
            "p_value": None,
            "conclusion": f"Erro no teste estatístico: {e}",
        }


def _where_alias(f, alias="s", include_turno=False):
    """WHERE das seções com outro alias de tabela, opcionalmente sem o turno.

    Com ``Filters`` (dashboard) o SQL é montado a partir das condições
    estruturadas. Para dicionários legados, só é aceito o caso trivial.
    """
    if hasattr(f, "where_sql"):
        return f.where_sql(include_turno=include_turno, alias=alias)
    if f.get("turno") is not None and not include_turno:
        raise ValueError("Filtros legados com turno exigem dataurnas.dashboard.filters.Filters")
    where = f["where"]
    if alias != "s":
        where = re.sub(r"\bs\.", f"{alias}.", where)
    return where, list(f["params"])


def _build_cross_turno_base_where(f):
    """WHERE sem a condição de turno (para comparar os dois turnos)."""
    return _where_alias(f, "s", include_turno=False)


def cross_turno_attendance(store, f) -> pd.DataFrame:
    """Variação de comparecimento entre T1 e T2 para mesmas seções.

    O pareamento usa uf/municipio/zona/secao (sem prefixo de turno).

    Returns:
        DataFrame com: uf, secoes_pareadas, comp_t1, comp_t2, variacao_pct
    """
    cols = ["uf", "secoes_pareadas", "comp_t1", "comp_t2", "variacao_pct"]

    _, base_params = _build_cross_turno_base_where(f)

    df = store.query_df(f"""
        SELECT
            t1.uf,
            COUNT(*) AS secoes_pareadas,
            SUM(t1.comparecimento) AS comp_t1,
            SUM(t2.comparecimento) AS comp_t2,
            ROUND(
                (SUM(t2.comparecimento) - SUM(t1.comparecimento)) * 100.0
                / NULLIF(SUM(t1.comparecimento), 0),
                2
            ) AS variacao_pct
        FROM secoes t1
        JOIN secoes t2
            ON t1.uf = t2.uf
            AND t1.municipio = t2.municipio
            AND t1.zona = t2.zona
            AND t1.secao = t2.secao
            AND t1.turno = 1
            AND t2.turno = 2
        WHERE {_where_alias(f, 't1')[0]}
        GROUP BY t1.uf
        ORDER BY t1.uf
    """, base_params)

    if df.empty:
        return _empty_df(cols)

    return df[cols].reset_index(drop=True)


def cross_turno_vote_migration(store, f) -> pd.DataFrame:
    """Migração de votos entre T1 e T2 para Presidente.

    Returns:
        DataFrame com: uf, lula_t1_pct, lula_t2_pct, bolso_t1_pct, bolso_t2_pct, swing_lula
    """
    cols = ["uf", "lula_t1_pct", "lula_t2_pct", "bolso_t1_pct", "bolso_t2_pct", "swing_lula"]

    base_where, base_params = _build_cross_turno_base_where(f)

    df = store.query_df(f"""
        WITH votos_turno AS (
            SELECT
                s.uf,
                s.turno,
                SUM(CASE WHEN v.codigo_candidato = 13 THEN v.quantidade ELSE 0 END) AS lula,
                SUM(CASE WHEN v.codigo_candidato = 22 THEN v.quantidade ELSE 0 END) AS bolso,
                SUM(v.quantidade) AS total
            FROM votos v
            JOIN secoes s ON v.secao_id = s.id
            WHERE {base_where}
                AND v.cargo = 'Presidente'
                AND v.tipo_voto = 'nominal'
                AND v.codigo_candidato IN (13, 22)
            GROUP BY s.uf, s.turno
        )
        SELECT
            t1.uf,
            ROUND(t1.lula * 100.0 / NULLIF(t1.total, 0), 2) AS lula_t1_pct,
            ROUND(t2.lula * 100.0 / NULLIF(t2.total, 0), 2) AS lula_t2_pct,
            ROUND(t1.bolso * 100.0 / NULLIF(t1.total, 0), 2) AS bolso_t1_pct,
            ROUND(t2.bolso * 100.0 / NULLIF(t2.total, 0), 2) AS bolso_t2_pct,
            ROUND(
                (t2.lula * 100.0 / NULLIF(t2.total, 0))
                - (t1.lula * 100.0 / NULLIF(t1.total, 0)),
                2
            ) AS swing_lula
        FROM votos_turno t1
        JOIN votos_turno t2 ON t1.uf = t2.uf AND t1.turno = 1 AND t2.turno = 2
        ORDER BY t1.uf
    """, base_params)

    if df.empty:
        return _empty_df(cols)

    return df[cols].reset_index(drop=True)


def issue_density_by_state(store, f) -> pd.DataFrame:
    """Densidade de issues (issues/seção) por estado, normalizada com z-score.

    Returns:
        DataFrame com: uf, secoes, issues, density, z_density
    """
    cols = ["uf", "secoes", "issues", "density", "z_density"]

    df = store.query_df(f"""
        SELECT
            s.uf,
            COUNT(DISTINCT s.id) AS secoes,
            COUNT(i.id) AS issues,
            ROUND(
                COUNT(i.id) * 1.0 / NULLIF(COUNT(DISTINCT s.id), 0),
                4
            ) AS density
        FROM secoes s
        LEFT JOIN issues i ON i.secao_id = s.id
        WHERE {f['where']}
        GROUP BY s.uf
        ORDER BY s.uf
    """, f["params"])

    if df.empty:
        return _empty_df(cols)

    # Calcular z-score da densidade
    mean_d = df["density"].mean()
    std_d = df["density"].std()
    df["z_density"] = np.where(
        std_d > 0,
        ((df["density"] - mean_d) / std_d).round(4),
        0.0,
    )

    return df[cols].reset_index(drop=True)


def geographic_issue_vs_result(store, f) -> pd.DataFrame:
    """Correlação entre densidade de issues e resultado eleitoral por estado.

    Returns:
        DataFrame com: uf, density, pct_lula, pct_bolso
    """
    cols = ["uf", "density", "pct_lula", "pct_bolso"]

    density_df = issue_density_by_state(store, f)
    if density_df.empty:
        return _empty_df(cols)

    votos_df = store.query_df(f"""
        SELECT
            s.uf,
            SUM(CASE WHEN v.codigo_candidato = 13 THEN v.quantidade ELSE 0 END) AS lula,
            SUM(CASE WHEN v.codigo_candidato = 22 THEN v.quantidade ELSE 0 END) AS bolso,
            SUM(v.quantidade) AS total
        FROM votos v
        JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']}
            AND v.cargo = 'Presidente'
            AND v.tipo_voto = 'nominal'
            AND v.codigo_candidato IN (13, 22)
        GROUP BY s.uf
    """, f["params"])

    if votos_df.empty:
        density_df["pct_lula"] = np.nan
        density_df["pct_bolso"] = np.nan
        return density_df[["uf", "density", "pct_lula", "pct_bolso"]].reset_index(drop=True)

    votos_df["pct_lula"] = np.where(
        votos_df["total"] > 0,
        (votos_df["lula"] / votos_df["total"] * 100).round(2),
        np.nan,
    )
    votos_df["pct_bolso"] = np.where(
        votos_df["total"] > 0,
        (votos_df["bolso"] / votos_df["total"] * 100).round(2),
        np.nan,
    )

    result = density_df[["uf", "density"]].merge(
        votos_df[["uf", "pct_lula", "pct_bolso"]],
        on="uf", how="left",
    )

    return result[cols].sort_values("uf").reset_index(drop=True)


def zero_biometry_sections(store, f) -> pd.DataFrame:
    """Seções com 0% de verificação biométrica.

    Returns:
        DataFrame com: id, uf, municipio, zona, secao, modelo, comparecimento, lib_codigo
    """
    cols = ["id", "uf", "municipio", "zona", "secao", "modelo",
            "comparecimento", "lib_codigo"]

    df = store.query_df(f"""
        SELECT
            s.id,
            s.uf,
            s.municipio,
            s.zona,
            s.secao,
            s.modelo_urna AS modelo,
            s.comparecimento,
            s.lib_codigo
        FROM secoes s
        WHERE {f['where']}
            AND (s.pct_biometria IS NULL OR s.pct_biometria = 0)
            AND s.comparecimento > 0
        ORDER BY s.comparecimento DESC
    """, f["params"])

    if df.empty:
        return _empty_df(cols)

    return df[cols].reset_index(drop=True)


def biometry_vs_vote(store, f) -> pd.DataFrame:
    """Correlação entre taxa de biometria e padrão de voto por quartil.

    Returns:
        DataFrame com: quartil, secoes, pct_bio_media, pct_lula, pct_bolso
    """
    cols = ["quartil", "secoes", "pct_bio_media", "pct_lula", "pct_bolso"]

    df = store.query_df(f"""
        SELECT
            s.id,
            s.pct_biometria
        FROM secoes s
        WHERE {f['where']} AND s.pct_biometria IS NOT NULL
    """, f["params"])

    if df.empty or len(df) < 4:
        return _empty_df(cols)

    # Calcular quartis
    try:
        df["quartil"] = pd.qcut(
            df["pct_biometria"], q=4, labels=["Q1 (baixa)", "Q2", "Q3", "Q4 (alta)"],
            duplicates="drop",
        )
    except ValueError:
        # Se não há variação suficiente para 4 quartis
        return _empty_df(cols)

    secao_quartil = df[["id", "quartil", "pct_biometria"]]

    # Buscar votos para Presidente
    votos_df = store.query_df(f"""
        SELECT
            v.secao_id,
            SUM(CASE WHEN v.codigo_candidato = 13 THEN v.quantidade ELSE 0 END) AS lula,
            SUM(CASE WHEN v.codigo_candidato = 22 THEN v.quantidade ELSE 0 END) AS bolso,
            SUM(v.quantidade) AS total
        FROM votos v
        JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']}
            AND v.cargo = 'Presidente'
            AND v.tipo_voto = 'nominal'
            AND v.codigo_candidato IN (13, 22)
        GROUP BY v.secao_id
    """, f["params"])

    if votos_df.empty:
        return _empty_df(cols)

    merged = secao_quartil.merge(votos_df, left_on="id", right_on="secao_id", how="inner")

    if merged.empty:
        return _empty_df(cols)

    result = merged.groupby("quartil", observed=True).agg(
        secoes=("id", "count"),
        pct_bio_media=("pct_biometria", "mean"),
        lula=("lula", "sum"),
        bolso=("bolso", "sum"),
        total=("total", "sum"),
    ).reset_index()

    result["pct_bio_media"] = result["pct_bio_media"].round(2)
    result["pct_lula"] = np.where(
        result["total"] > 0,
        (result["lula"] / result["total"] * 100).round(2),
        0.0,
    )
    result["pct_bolso"] = np.where(
        result["total"] > 0,
        (result["bolso"] / result["total"] * 100).round(2),
        0.0,
    )

    return result[cols].reset_index(drop=True)


def abnormal_duration_sections(store, f) -> pd.DataFrame:
    """Seções com duração de votação anormal (z-score > 3).

    Returns:
        DataFrame com: id, uf, municipio, zona, secao, duracao_min, zscore
    """
    cols = ["id", "uf", "municipio", "zona", "secao", "duracao_min", "zscore"]

    df = store.query_df(f"""
        SELECT
            s.id,
            s.uf,
            s.municipio,
            s.zona,
            s.secao,
            s.duracao_min,
            (s.duracao_min - AVG(s.duracao_min) OVER())
                / NULLIF(STDDEV(s.duracao_min) OVER(), 0) AS zscore
        FROM secoes s
        WHERE {f['where']} AND s.duracao_min IS NOT NULL
    """, f["params"])

    if df.empty:
        return _empty_df(cols)

    df = df[df["zscore"].abs() > 3.0].copy()
    if df.empty:
        return _empty_df(cols)

    df["zscore"] = df["zscore"].round(4)

    return df[cols].sort_values("zscore", ascending=False, key=abs).reset_index(drop=True)


def duration_vs_vote(store, f) -> pd.DataFrame:
    """Correlação entre duração de votação e padrão de voto por quartil.

    Returns:
        DataFrame com: quartil, secoes, duracao_media, pct_lula, pct_bolso
    """
    cols = ["quartil", "secoes", "duracao_media", "pct_lula", "pct_bolso"]

    df = store.query_df(f"""
        SELECT
            s.id,
            s.duracao_min
        FROM secoes s
        WHERE {f['where']} AND s.duracao_min IS NOT NULL
    """, f["params"])

    if df.empty or len(df) < 4:
        return _empty_df(cols)

    try:
        df["quartil"] = pd.qcut(
            df["duracao_min"], q=4, labels=["Q1 (curta)", "Q2", "Q3", "Q4 (longa)"],
            duplicates="drop",
        )
    except ValueError:
        return _empty_df(cols)

    secao_quartil = df[["id", "quartil", "duracao_min"]]

    votos_df = store.query_df(f"""
        SELECT
            v.secao_id,
            SUM(CASE WHEN v.codigo_candidato = 13 THEN v.quantidade ELSE 0 END) AS lula,
            SUM(CASE WHEN v.codigo_candidato = 22 THEN v.quantidade ELSE 0 END) AS bolso,
            SUM(v.quantidade) AS total
        FROM votos v
        JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']}
            AND v.cargo = 'Presidente'
            AND v.tipo_voto = 'nominal'
            AND v.codigo_candidato IN (13, 22)
        GROUP BY v.secao_id
    """, f["params"])

    if votos_df.empty:
        return _empty_df(cols)

    merged = secao_quartil.merge(votos_df, left_on="id", right_on="secao_id", how="inner")

    if merged.empty:
        return _empty_df(cols)

    result = merged.groupby("quartil", observed=True).agg(
        secoes=("id", "count"),
        duracao_media=("duracao_min", "mean"),
        lula=("lula", "sum"),
        bolso=("bolso", "sum"),
        total=("total", "sum"),
    ).reset_index()

    result["duracao_media"] = result["duracao_media"].round(2)
    result["pct_lula"] = np.where(
        result["total"] > 0,
        (result["lula"] / result["total"] * 100).round(2),
        0.0,
    )
    result["pct_bolso"] = np.where(
        result["total"] > 0,
        (result["bolso"] / result["total"] * 100).round(2),
        0.0,
    )

    return result[cols].reset_index(drop=True)


def model_vote_pattern(store, f) -> pd.DataFrame:
    """Padrão de voto por modelo de urna para Presidente.

    Returns:
        DataFrame com: modelo, secoes, pct_lula, pct_bolso, pct_brancos, pct_nulos
    """
    cols = ["modelo", "secoes", "pct_lula", "pct_bolso", "pct_brancos", "pct_nulos"]

    df = store.query_df(f"""
        SELECT
            s.modelo_urna AS modelo,
            COUNT(DISTINCT s.id) AS secoes,
            SUM(CASE WHEN v.codigo_candidato = 13 AND v.tipo_voto = 'nominal'
                THEN v.quantidade ELSE 0 END) AS lula,
            SUM(CASE WHEN v.codigo_candidato = 22 AND v.tipo_voto = 'nominal'
                THEN v.quantidade ELSE 0 END) AS bolso,
            SUM(CASE WHEN v.tipo_voto = 'branco'
                THEN v.quantidade ELSE 0 END) AS brancos,
            SUM(CASE WHEN v.tipo_voto = 'nulo'
                THEN v.quantidade ELSE 0 END) AS nulos,
            SUM(v.quantidade) AS total
        FROM votos v
        JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']}
            AND v.cargo = 'Presidente'
            AND s.modelo_urna IS NOT NULL
        GROUP BY s.modelo_urna
        ORDER BY s.modelo_urna
    """, f["params"])

    if df.empty:
        return _empty_df(cols)

    df["pct_lula"] = np.where(
        df["total"] > 0, (df["lula"] / df["total"] * 100).round(2), 0.0
    )
    df["pct_bolso"] = np.where(
        df["total"] > 0, (df["bolso"] / df["total"] * 100).round(2), 0.0
    )
    df["pct_brancos"] = np.where(
        df["total"] > 0, (df["brancos"] / df["total"] * 100).round(2), 0.0
    )
    df["pct_nulos"] = np.where(
        df["total"] > 0, (df["nulos"] / df["total"] * 100).round(2), 0.0
    )

    return df[cols].reset_index(drop=True)


def null_blank_by_section(store, f) -> pd.DataFrame:
    """Seções outliers em percentual de nulos ou brancos por cargo.

    Returns:
        DataFrame com: secao_id, uf, cargo, comparecimento, nulos, brancos,
                       pct_nulos, pct_brancos, zscore_nulos, zscore_brancos
    """
    cols = [
        "secao_id", "uf", "cargo", "comparecimento", "nulos", "brancos",
        "pct_nulos", "pct_brancos", "zscore_nulos", "zscore_brancos",
    ]

    df = store.query_df(f"""
        SELECT
            t.secao_id,
            s.uf,
            t.cargo,
            t.comparecimento,
            t.nulos,
            t.brancos,
            ROUND(t.nulos * 100.0 / NULLIF(t.total, 0), 4) AS pct_nulos,
            ROUND(t.brancos * 100.0 / NULLIF(t.total, 0), 4) AS pct_brancos
        FROM totais_cargo t
        JOIN secoes s ON t.secao_id = s.id
        WHERE {f['where']} AND t.total > 0
    """, f["params"])

    if df.empty:
        return _empty_df(cols)

    all_outliers = []
    for _cargo, grp in df.groupby("cargo"):
        mean_nulos = grp["pct_nulos"].mean()
        std_nulos = grp["pct_nulos"].std()
        mean_brancos = grp["pct_brancos"].mean()
        std_brancos = grp["pct_brancos"].std()

        grp = grp.copy()
        grp["zscore_nulos"] = np.where(
            std_nulos > 0,
            ((grp["pct_nulos"] - mean_nulos) / std_nulos).round(4),
            0.0,
        )
        grp["zscore_brancos"] = np.where(
            std_brancos > 0,
            ((grp["pct_brancos"] - mean_brancos) / std_brancos).round(4),
            0.0,
        )

        mask = (grp["zscore_nulos"].abs() > 3) | (grp["zscore_brancos"].abs() > 3)
        outliers = grp[mask]
        if not outliers.empty:
            all_outliers.append(outliers[cols])

    if not all_outliers:
        return _empty_df(cols)

    result = pd.concat(all_outliers, ignore_index=True)
    result["_max_zscore"] = result[["zscore_nulos", "zscore_brancos"]].abs().max(axis=1)
    result = result.sort_values("_max_zscore", ascending=False).head(1000)
    result = result.drop(columns=["_max_zscore"])

    return result[cols].reset_index(drop=True)


def null_blank_summary(store, f) -> pd.DataFrame:
    """Resumo por UF: total de seções com outliers de nulos e brancos.

    Returns:
        DataFrame com: uf, outliers_nulos, outliers_brancos, total_secoes
    """
    cols = ["uf", "outliers_nulos", "outliers_brancos", "total_secoes"]

    outliers_df = null_blank_by_section(store, f)

    secoes_df = store.query_df(f"""
        SELECT s.uf, COUNT(*) AS total_secoes
        FROM secoes s
        WHERE {f['where']}
        GROUP BY s.uf
    """, f["params"])

    if secoes_df.empty:
        return _empty_df(cols)

    if outliers_df.empty:
        secoes_df["outliers_nulos"] = 0
        secoes_df["outliers_brancos"] = 0
        return secoes_df[cols].sort_values("uf").reset_index(drop=True)

    nulos_outliers = outliers_df[outliers_df["zscore_nulos"].abs() > 3]
    nulos_by_uf = nulos_outliers.groupby("uf")["secao_id"].nunique().reset_index()
    nulos_by_uf.columns = ["uf", "outliers_nulos"]

    brancos_outliers = outliers_df[outliers_df["zscore_brancos"].abs() > 3]
    brancos_by_uf = brancos_outliers.groupby("uf")["secao_id"].nunique().reset_index()
    brancos_by_uf.columns = ["uf", "outliers_brancos"]

    result = secoes_df.merge(nulos_by_uf, on="uf", how="left")
    result = result.merge(brancos_by_uf, on="uf", how="left")
    result["outliers_nulos"] = result["outliers_nulos"].fillna(0).astype(int)
    result["outliers_brancos"] = result["outliers_brancos"].fillna(0).astype(int)

    return result[cols].sort_values("uf").reset_index(drop=True)


def null_blank_vs_result(store, f) -> pd.DataFrame:
    """Divide seções em quartis de pct_nulos para Presidente.

    Returns:
        DataFrame com: quartil, faixa, secoes, pct_lula, pct_bolso
    """
    cols = ["quartil", "faixa", "secoes", "pct_lula", "pct_bolso"]

    df = store.query_df(f"""
        SELECT
            t.secao_id,
            ROUND(t.nulos * 100.0 / NULLIF(t.total, 0), 4) AS pct_nulos
        FROM totais_cargo t
        JOIN secoes s ON t.secao_id = s.id
        WHERE {f['where']}
            AND t.cargo = 'Presidente'
            AND t.total > 0
    """, f["params"])

    if df.empty or len(df) < 4:
        return _empty_df(cols)

    try:
        df["quartil"] = pd.qcut(
            df["pct_nulos"], q=4,
            labels=["Q1 (baixo)", "Q2", "Q3", "Q4 (alto)"],
            duplicates="drop",
        )
    except ValueError:
        return _empty_df(cols)

    quartil_stats = df.groupby("quartil", observed=True)["pct_nulos"].agg(["min", "max"])
    faixas = {
        q: f"{row['min']:.2f}%-{row['max']:.2f}%"
        for q, row in quartil_stats.iterrows()
    }

    secao_quartil = df[["secao_id", "quartil"]]

    votos_df = store.query_df(f"""
        SELECT
            v.secao_id,
            SUM(CASE WHEN v.codigo_candidato = 13 THEN v.quantidade ELSE 0 END) AS lula,
            SUM(CASE WHEN v.codigo_candidato = 22 THEN v.quantidade ELSE 0 END) AS bolso,
            SUM(v.quantidade) AS total
        FROM votos v
        JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']}
            AND v.cargo = 'Presidente'
            AND v.tipo_voto = 'nominal'
            AND v.codigo_candidato IN (13, 22)
        GROUP BY v.secao_id
    """, f["params"])

    if votos_df.empty:
        return _empty_df(cols)

    merged = secao_quartil.merge(votos_df, on="secao_id", how="inner")
    if merged.empty:
        return _empty_df(cols)

    result = merged.groupby("quartil", observed=True).agg(
        secoes=("secao_id", "count"),
        lula=("lula", "sum"),
        bolso=("bolso", "sum"),
        total=("total", "sum"),
    ).reset_index()

    result["faixa"] = result["quartil"].map(faixas).fillna("")
    result["pct_lula"] = np.where(
        result["total"] > 0,
        (result["lula"] / result["total"] * 100).round(2),
        0.0,
    )
    result["pct_bolso"] = np.where(
        result["total"] > 0,
        (result["bolso"] / result["total"] * 100).round(2),
        0.0,
    )

    return result[cols].reset_index(drop=True)


def candidate_section_distribution(store, f) -> pd.DataFrame:
    """Seções com z-score > 3 na distribuição de pct_lula por UF.

    Returns:
        DataFrame com: secao_id, uf, municipio, zona, secao,
                       votos_13, votos_22, pct_lula, zscore
    """
    cols = [
        "secao_id", "uf", "municipio", "zona", "secao",
        "votos_13", "votos_22", "pct_lula", "zscore",
    ]

    df = store.query_df(f"""
        SELECT
            s.id AS secao_id,
            s.uf,
            s.municipio,
            s.zona,
            s.secao,
            SUM(CASE WHEN v.codigo_candidato = 13 THEN v.quantidade ELSE 0 END) AS votos_13,
            SUM(CASE WHEN v.codigo_candidato = 22 THEN v.quantidade ELSE 0 END) AS votos_22
        FROM votos v
        JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']}
            AND v.cargo = 'Presidente'
            AND v.tipo_voto = 'nominal'
            AND v.codigo_candidato IN (13, 22)
        GROUP BY s.id, s.uf, s.municipio, s.zona, s.secao
        HAVING (SUM(CASE WHEN v.codigo_candidato = 13 THEN v.quantidade ELSE 0 END)
              + SUM(CASE WHEN v.codigo_candidato = 22 THEN v.quantidade ELSE 0 END)) > 0
    """, f["params"])

    if df.empty:
        return _empty_df(cols)

    df["pct_lula"] = (df["votos_13"] / (df["votos_13"] + df["votos_22"]) * 100).round(4)

    all_outliers = []
    for _uf, grp in df.groupby("uf"):
        mean_pct = grp["pct_lula"].mean()
        std_pct = grp["pct_lula"].std()

        grp = grp.copy()
        grp["zscore"] = np.where(
            std_pct > 0,
            ((grp["pct_lula"] - mean_pct) / std_pct).round(4),
            0.0,
        )

        outliers = grp[grp["zscore"].abs() > 3]
        if not outliers.empty:
            all_outliers.append(outliers[cols])

    if not all_outliers:
        return _empty_df(cols)

    result = pd.concat(all_outliers, ignore_index=True)
    result = result.sort_values("zscore", ascending=False, key=abs).head(500)

    return result[cols].reset_index(drop=True)


def candidate_extreme_sections(store, f) -> pd.DataFrame:
    """Seções onde um candidato (13 ou 22) tem >= 95% ou <= 5% dos votos válidos.

    Returns:
        DataFrame com: secao_id, uf, municipio, comparecimento,
                       votos_13, votos_22, pct_lula, tipo_extremo
    """
    cols = [
        "secao_id", "uf", "municipio", "comparecimento",
        "votos_13", "votos_22", "pct_lula", "tipo_extremo",
    ]

    df = store.query_df(f"""
        SELECT
            s.id AS secao_id,
            s.uf,
            s.municipio,
            s.comparecimento,
            SUM(CASE WHEN v.codigo_candidato = 13 THEN v.quantidade ELSE 0 END) AS votos_13,
            SUM(CASE WHEN v.codigo_candidato = 22 THEN v.quantidade ELSE 0 END) AS votos_22
        FROM votos v
        JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']}
            AND v.cargo = 'Presidente'
            AND v.tipo_voto = 'nominal'
            AND v.codigo_candidato IN (13, 22)
        GROUP BY s.id, s.uf, s.municipio, s.comparecimento
        HAVING (SUM(CASE WHEN v.codigo_candidato = 13 THEN v.quantidade ELSE 0 END)
              + SUM(CASE WHEN v.codigo_candidato = 22 THEN v.quantidade ELSE 0 END)) > 0
    """, f["params"])

    if df.empty:
        return _empty_df(cols)

    total_validos = df["votos_13"] + df["votos_22"]
    df["pct_lula"] = (df["votos_13"] / total_validos * 100).round(2)

    mask_dom_13 = df["pct_lula"] >= 95
    mask_dom_22 = df["pct_lula"] <= 5

    extremos = df[mask_dom_13 | mask_dom_22].copy()
    if extremos.empty:
        return _empty_df(cols)

    extremos["tipo_extremo"] = np.where(
        extremos["pct_lula"] >= 95,
        "dominancia_13",
        "dominancia_22",
    )

    extremos = extremos.sort_values("pct_lula", ascending=False).head(500)

    return extremos[cols].reset_index(drop=True)


def candidate_distribution_by_state(store, f) -> pd.DataFrame:
    """Estatísticas de pct_lula por UF.

    Returns:
        DataFrame com: uf, media, mediana, std, min, max, secoes
    """
    cols = ["uf", "media", "mediana", "std", "min", "max", "secoes"]

    df = store.query_df(f"""
        SELECT
            s.uf,
            SUM(CASE WHEN v.codigo_candidato = 13 THEN v.quantidade ELSE 0 END) AS votos_13,
            SUM(CASE WHEN v.codigo_candidato = 22 THEN v.quantidade ELSE 0 END) AS votos_22
        FROM votos v
        JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']}
            AND v.cargo = 'Presidente'
            AND v.tipo_voto = 'nominal'
            AND v.codigo_candidato IN (13, 22)
        GROUP BY s.id, s.uf
        HAVING (SUM(CASE WHEN v.codigo_candidato = 13 THEN v.quantidade ELSE 0 END)
              + SUM(CASE WHEN v.codigo_candidato = 22 THEN v.quantidade ELSE 0 END)) > 0
    """, f["params"])

    if df.empty:
        return _empty_df(cols)

    df["pct_lula"] = (df["votos_13"] / (df["votos_13"] + df["votos_22"]) * 100).round(4)

    result = df.groupby("uf")["pct_lula"].agg(
        media="mean",
        mediana="median",
        std="std",
        min="min",
        max="max",
        secoes="count",
    ).reset_index()

    result["media"] = result["media"].round(2)
    result["mediana"] = result["mediana"].round(2)
    result["std"] = result["std"].round(2)
    result["min"] = result["min"].round(2)
    result["max"] = result["max"].round(2)

    return result[cols].sort_values("uf").reset_index(drop=True)


def map_state_votes(store, f) -> pd.DataFrame:
    """Votos por UF para Presidente (candidatos 13 e 22).

    Returns:
        DataFrame com: uf, votos_13, votos_22, pct_lula, pct_bolso
    """
    cols = ["uf", "votos_13", "votos_22", "pct_lula", "pct_bolso"]

    df = store.query_df(f"""
        SELECT
            s.uf,
            SUM(CASE WHEN v.codigo_candidato = 13 THEN v.quantidade ELSE 0 END) AS votos_13,
            SUM(CASE WHEN v.codigo_candidato = 22 THEN v.quantidade ELSE 0 END) AS votos_22,
            SUM(v.quantidade) AS total
        FROM votos v
        JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']}
            AND v.cargo = 'Presidente'
            AND v.tipo_voto = 'nominal'
            AND v.codigo_candidato IN (13, 22)
        GROUP BY s.uf
        ORDER BY s.uf
    """, f["params"])

    if df.empty:
        return _empty_df(cols)

    df["pct_lula"] = np.where(
        df["total"] > 0,
        (df["votos_13"] / df["total"] * 100).round(2),
        np.nan,
    )
    df["pct_bolso"] = np.where(
        df["total"] > 0,
        (df["votos_22"] / df["total"] * 100).round(2),
        np.nan,
    )

    return df[cols].reset_index(drop=True)


def reserve_vote_pattern(store, f) -> pd.DataFrame:
    """Padrão de votação em seções reserva vs normais para Presidente.

    Returns:
        DataFrame com: tipo, secoes, pct_lula, pct_bolso, pct_nulos, pct_brancos
    """
    cols = ["tipo", "secoes", "pct_lula", "pct_bolso", "pct_nulos", "pct_brancos"]

    df = store.query_df(f"""
        SELECT
            s.tipo_urna AS tipo,
            COUNT(DISTINCT s.id) AS secoes,
            SUM(CASE WHEN v.codigo_candidato = 13 AND v.tipo_voto = 'nominal'
                THEN v.quantidade ELSE 0 END) AS lula,
            SUM(CASE WHEN v.codigo_candidato = 22 AND v.tipo_voto = 'nominal'
                THEN v.quantidade ELSE 0 END) AS bolso,
            SUM(CASE WHEN v.tipo_voto = 'nulo'
                THEN v.quantidade ELSE 0 END) AS nulos,
            SUM(CASE WHEN v.tipo_voto = 'branco'
                THEN v.quantidade ELSE 0 END) AS brancos,
            SUM(v.quantidade) AS total
        FROM votos v
        JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']}
            AND v.cargo = 'Presidente'
            AND s.tipo_urna IS NOT NULL
        GROUP BY s.tipo_urna
        ORDER BY s.tipo_urna
    """, f["params"])

    if df.empty:
        return _empty_df(cols)

    df["pct_lula"] = np.where(
        df["total"] > 0, (df["lula"] / df["total"] * 100).round(2), np.nan
    )
    df["pct_bolso"] = np.where(
        df["total"] > 0, (df["bolso"] / df["total"] * 100).round(2), np.nan
    )
    df["pct_nulos"] = np.where(
        df["total"] > 0, (df["nulos"] / df["total"] * 100).round(2), np.nan
    )
    df["pct_brancos"] = np.where(
        df["total"] > 0, (df["brancos"] / df["total"] * 100).round(2), np.nan
    )

    return df[cols].reset_index(drop=True)


def substitution_vs_result(store, f) -> pd.DataFrame:
    """Comparar votação em seções com substituição vs sem.

    Returns:
        DataFrame com: grupo, secoes, pct_lula, pct_bolso
    """
    cols = ["grupo", "secoes", "pct_lula", "pct_bolso"]

    df = store.query_df(f"""
        SELECT
            CASE WHEN s.substituicoes > 0
                THEN 'com_substituição'
                ELSE 'sem_substituição'
            END AS grupo,
            COUNT(DISTINCT s.id) AS secoes,
            SUM(CASE WHEN v.codigo_candidato = 13 THEN v.quantidade ELSE 0 END) AS lula,
            SUM(CASE WHEN v.codigo_candidato = 22 THEN v.quantidade ELSE 0 END) AS bolso,
            SUM(v.quantidade) AS total
        FROM votos v
        JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']}
            AND v.cargo = 'Presidente'
            AND v.tipo_voto = 'nominal'
            AND v.codigo_candidato IN (13, 22)
        GROUP BY grupo
        ORDER BY grupo
    """, f["params"])

    if df.empty:
        return _empty_df(cols)

    df["pct_lula"] = np.where(
        df["total"] > 0,
        (df["lula"] / df["total"] * 100).round(2),
        np.nan,
    )
    df["pct_bolso"] = np.where(
        df["total"] > 0,
        (df["bolso"] / df["total"] * 100).round(2),
        np.nan,
    )

    return df[cols].reset_index(drop=True)


def zscore_outliers_by_state(store, f, threshold=3.0) -> pd.DataFrame:
    """Z-score de outliers calculado POR ESTADO (não global).

    Returns:
        DataFrame com: secao_id, uf, metrica, valor, zscore, media_uf, std_uf
    """
    cols = ["secao_id", "uf", "metrica", "valor", "zscore", "media_uf", "std_uf"]

    metrics = [
        ("pct_abstencao", "abstencao"),
        ("pct_biometria", "biometria"),
        ("duracao_min", "duracao"),
    ]

    all_outliers = []
    for col_name, metric_label in metrics:
        df = store.query_df(f"""
            SELECT
                s.id AS secao_id,
                s.uf,
                s.{col_name} AS valor,
                AVG(s.{col_name}) OVER(PARTITION BY s.uf) AS media_uf,
                STDDEV(s.{col_name}) OVER(PARTITION BY s.uf) AS std_uf,
                (s.{col_name} - AVG(s.{col_name}) OVER(PARTITION BY s.uf))
                    / NULLIF(STDDEV(s.{col_name}) OVER(PARTITION BY s.uf), 0) AS zscore
            FROM secoes s
            WHERE {f['where']} AND s.{col_name} IS NOT NULL
        """, f["params"])

        if df.empty:
            continue

        outliers = df[df["zscore"].abs() > threshold].copy()
        if not outliers.empty:
            outliers["metrica"] = metric_label
            outliers["valor"] = outliers["valor"].round(4)
            outliers["zscore"] = outliers["zscore"].round(4)
            outliers["media_uf"] = outliers["media_uf"].round(4)
            outliers["std_uf"] = outliers["std_uf"].round(4)
            all_outliers.append(outliers[cols])

    if not all_outliers:
        return _empty_df(cols)

    return pd.concat(all_outliers, ignore_index=True).sort_values(
        "zscore", ascending=False, key=abs
    ).reset_index(drop=True)
