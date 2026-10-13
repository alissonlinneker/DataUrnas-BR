"""Equivalência das análises com tabelas agregadas (agg_*) e as consultas antigas.

Um banco sintético pequeno, com o schema dos Parquet distribuídos, é montado
duas vezes: com as tabelas agregadas (como faz ``scripts/build_db.py``) e sem
elas (o dashboard cai na fonte bruta equivalente). Cada função otimizada é
comparada com a versão antiga congelada em ``legacy_analysis.py`` para vários
conjuntos de filtros, inclusive filtros que os cubos não cobrem (município).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import legacy_analysis as legacy  # noqa: E402

from dataurnas.dashboard import aggregates  # noqa: E402
from dataurnas.dashboard import analysis as novo  # noqa: E402
from dataurnas.dashboard.filters import Filters  # noqa: E402

SCHEMA = ROOT / "data" / "parquet" / "schema.sql"

pytestmark = pytest.mark.skipif(not SCHEMA.exists(), reason="schema.sql dos Parquet ausente")

UFS = {"sp": "sudeste", "mg": "sudeste", "ba": "nordeste", "ac": "norte", "rs": "sul"}
MODELOS = ["2009", "2010", "2015", "2020", None]


# ----------------------------------------------------------------------
# Banco sintético
# ----------------------------------------------------------------------
def _dados_sinteticos(seed: int = 7) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    secoes, votos, totais, issues = [], [], [], []
    issue_id = 1
    for uf, regiao in UFS.items():
        for mun in range(3):
            for zona in range(2):
                for sec in range(14):
                    base = dict(
                        uf=uf, regiao=regiao, municipio=f"{uf.upper()}-MUN{mun}",
                        zona=f"{zona + 1:04d}", secao=f"{sec + 1:04d}",
                    )
                    for turno in (1, 2):
                        if turno == 2 and rng.random() < 0.08:
                            continue  # seção ausente no 2º turno
                        sid = f"{turno}T/{uf}/{mun}/{base['zona']}/{base['secao']}"
                        aptos = int(rng.integers(50, 450))
                        comp = int(aptos * rng.uniform(0.6, 0.95))
                        reserva = rng.random() < 0.1
                        has_issues = rng.random() < 0.3
                        bio = None if rng.random() < 0.05 else float(
                            0.0 if rng.random() < 0.05 else rng.uniform(60, 100))
                        dur = None if rng.random() < 0.05 else int(rng.normal(540, 40))
                        if dur is not None and rng.random() < 0.02:
                            dur = int(rng.integers(30, 200))  # outlier de duração
                        secoes.append(dict(
                            id=sid, turno=turno, **base,
                            modelo_urna=MODELOS[int(rng.integers(0, len(MODELOS)))],
                            tipo_urna="reservaSecao" if reserva else "secao",
                            versao_sw="8.26.0.0", fuso_offset=0, emissao=None,
                            eleitores_aptos=aptos, comparecimento=comp, lib_codigo=0,
                            comp_biometrico=0, pct_biometria=bio,
                            pct_abstencao=float(100 - comp * 100 / aptos),
                            hora_abertura=None, hora_encerramento=None, duracao_min=dur,
                            reboots=int(rng.choice([0, 0, 0, 0, 1, 2])),
                            erros_log=int(rng.integers(0, 3)), alertas_mesario=0, votos_log=comp,
                            substituicoes=int(rng.choice([0, 0, 0, 1])),
                            is_reserva=bool(reserva), has_issues=bool(has_issues),
                            n_issues=0,
                        ))
                        # Presidente: candidatos variam por turno; quantidades com
                        # várias ordens de grandeza (Benford) e alguns zeros
                        # 13 e 22 dividem um total com fração perto de 50%, com
                        # algumas seções extremas (outliers de % Lula)
                        cands = [13, 22, 12, 15, 44] if turno == 1 else [13, 22]
                        sem_nominal = rng.random() < 0.02
                        total_1322 = int(rng.lognormal(4.0, 1.0))
                        frac = 0.99 if rng.random() < 0.02 else float(np.clip(rng.normal(0.5, 0.05), 0, 1))
                        q_por_cand = {13: round(total_1322 * frac)}
                        q_por_cand[22] = total_1322 - q_por_cand[13]
                        for c in cands:
                            if sem_nominal or (c == 22 and rng.random() < 0.05):
                                continue
                            q = q_por_cand.get(c, int(rng.lognormal(1.5, 1.2)))
                            votos.append((sid, 1, "Presidente", 1, "nominal", c, c, q))
                        for tipo in ("branco", "nulo"):
                            if rng.random() < 0.7:
                                votos.append((sid, 1, "Presidente", 1, tipo, None, None,
                                               int(rng.integers(0, 40))))
                        if turno == 1:
                            for c in rng.choice(np.arange(1000, 1060), size=12, replace=False):
                                votos.append((sid, 2, "Deputado Federal", 6, "nominal", int(c),
                                              int(c) // 100, int(rng.lognormal(1.5, 1.3))))
                            votos.append((sid, 2, "Deputado Federal", 6, "legenda", None, 10,
                                          int(rng.integers(0, 20))))
                            for c in (10, 11, 15):
                                votos.append((sid, 3, "Governador", 3, "nominal", c, c,
                                              int(rng.lognormal(3.0, 1.0))))
                        for cargo in (["Presidente", "Governador", "Deputado Federal"]
                                      if turno == 1 else ["Presidente"]):
                            nulos = int(rng.integers(0, 30))
                            brancos = int(rng.integers(0, 30))
                            if rng.random() < 0.01:
                                nulos = int(rng.integers(120, 200))  # outlier de nulos
                            nominais = int(rng.integers(0, 300))
                            total = 0 if rng.random() < 0.01 else nominais + nulos + brancos
                            totais.append((sid, 1, cargo, 1, comp, nominais, brancos, nulos, 0, total))
                        if has_issues:
                            for _ in range(int(rng.integers(1, 4))):
                                cod, sev = [("C01", "critica"), ("C05", "critica"), ("A03", "alta"),
                                            ("A02", "alta"), ("M03", "media"),
                                            ("I05", "informativa")][int(rng.integers(0, 6))]
                                issues.append((issue_id, sid, cod, sev, "desc", "base", "det"))
                                issue_id += 1
    cols_v = ["secao_id", "eleicao_id", "cargo", "codigo_cargo", "tipo_voto",
              "codigo_candidato", "partido", "quantidade"]
    cols_t = ["secao_id", "eleicao_id", "cargo", "codigo_cargo", "comparecimento", "nominais",
              "brancos", "nulos", "legenda", "total"]
    cols_i = ["id", "secao_id", "codigo", "severidade", "descricao", "base_legal", "detalhes"]
    return {
        "secoes": pd.DataFrame(secoes),
        "votos": pd.DataFrame(votos, columns=cols_v),
        "totais_cargo": pd.DataFrame(totais, columns=cols_t),
        "issues": pd.DataFrame(issues, columns=cols_i),
    }


def _montar_banco(path: Path, dados: dict, com_agregados: bool) -> None:
    conn = duckdb.connect(str(path))
    for stmt in SCHEMA.read_text(encoding="utf-8").split(";;"):
        if stmt.strip():
            conn.execute(stmt)
    for table in ("secoes", "issues", "totais_cargo", "votos"):
        conn.register("df_tmp", dados[table])
        cols = ", ".join(dados[table].columns)
        conn.execute(f"INSERT INTO {table} ({cols}) SELECT {cols} FROM df_tmp")
        conn.unregister("df_tmp")
    if com_agregados:
        aggregates.create_aggregates(conn)
    conn.close()


class Store:
    """Store mínimo (mesma interface usada pelas análises)."""

    def __init__(self, path: Path):
        self.conn = duckdb.connect(str(path), read_only=True)

    def query_df(self, sql, params=None):
        return self.conn.execute(sql, list(params or [])).fetchdf()

    def query(self, sql, params=None):
        return self.query_df(sql, params).to_dict(orient="records")


@pytest.fixture(scope="module")
def stores(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("agg")
    dados = _dados_sinteticos()
    _montar_banco(pasta / "agg.duckdb", dados, com_agregados=True)
    _montar_banco(pasta / "bruto.duckdb", dados, com_agregados=False)
    com, sem = Store(pasta / "agg.duckdb"), Store(pasta / "bruto.duckdb")
    yield com, sem
    com.conn.close()
    sem.conn.close()


FILTROS = {
    "sem_filtro": Filters.build(),
    "turno1": Filters.build(turno=1),
    "turno2": Filters.build(turno=2),
    "ufs": Filters.build(ufs=["sp", "ba"]),
    "regiao": Filters.build(regioes=["sudeste"]),
    "municipio": Filters.build(ufs=["sp"], municipios=["SP-MUN0", "SP-MUN2"]),  # fora dos cubos
    "modelo_reserva": Filters.build(turno=1, modelos=["2020", "2015"], tipo_urna="Normal"),
    "reserva": Filters.build(tipo_urna="Reserva"),
    "issues": Filters.build(turno=1, ufs=["mg"], apenas_issues=True),
}


# ----------------------------------------------------------------------
# Comparação
# ----------------------------------------------------------------------
def _canon(df: pd.DataFrame) -> pd.DataFrame:
    """Ordem canônica (a ordem de empates não é garantida em nenhuma versão)."""
    if df.empty:
        return df.reset_index(drop=True)
    tmp = df.copy()
    for col in tmp.columns:
        if isinstance(tmp[col].dtype, pd.CategoricalDtype):
            tmp[col] = tmp[col].astype(str)
    order = tmp.astype(str).sort_values(list(tmp.columns)).index
    return df.loc[order].reset_index(drop=True)


def _assert_equal(novo_res, antigo_res, ctx=""):
    if isinstance(antigo_res, pd.DataFrame):
        assert isinstance(novo_res, pd.DataFrame), ctx
        assert list(novo_res.columns) == list(antigo_res.columns), ctx
        assert len(novo_res) == len(antigo_res), ctx
        pd.testing.assert_frame_equal(
            _canon(novo_res), _canon(antigo_res), check_dtype=True,
            check_exact=False, rtol=1e-9, atol=1e-12, obj=ctx,
        )
    elif isinstance(antigo_res, dict):
        assert novo_res.keys() == antigo_res.keys(), ctx
        for k in antigo_res:
            _assert_equal(novo_res[k], antigo_res[k], f"{ctx}[{k}]")
    elif isinstance(antigo_res, list):
        assert len(novo_res) == len(antigo_res), ctx
        for i, (a, b) in enumerate(zip(novo_res, antigo_res, strict=True)):
            _assert_equal(a, b, f"{ctx}[{i}]")
    elif isinstance(antigo_res, float) and not isinstance(antigo_res, bool):
        if math.isnan(antigo_res):
            assert math.isnan(novo_res), ctx
        else:
            assert novo_res == pytest.approx(antigo_res, rel=1e-9, abs=1e-12), ctx
    else:
        assert novo_res == antigo_res, ctx


FUNCOES = [
    "benford_first_digit", "benford_chi_squared", "benford_by_state", "benford_second_digit",
    "benford_second_digit_chi", "benford_all_offices", "zscore_outliers", "outlier_summary",
    "reboot_vote_distribution", "reboot_by_state", "reboot_candidate_correlation",
    "cross_turno_vote_migration", "geographic_issue_vs_result", "biometry_vs_vote",
    "abnormal_duration_sections", "duration_vs_vote", "model_vote_pattern",
    "null_blank_by_section", "null_blank_summary", "null_blank_vs_result",
    "candidate_section_distribution", "candidate_extreme_sections",
    "candidate_distribution_by_state", "map_state_votes", "reserve_vote_pattern",
    "substitution_vs_result", "zscore_outliers_by_state",
]


def test_agregados_criados_e_nao_vazios(stores):
    com, sem = stores
    assert aggregates.available_tables(com) == frozenset(aggregates.AGGREGATE_TABLES)
    assert aggregates.available_tables(sem) == frozenset()
    for nome in aggregates.AGGREGATE_TABLES:
        assert com.query_df(f"SELECT COUNT(*) AS n FROM {nome}")["n"][0] > 0


def test_cubo_usado_so_quando_filtro_permite(stores):
    com, sem = stores
    assert aggregates.cube_source(com, FILTROS["ufs"]["where"], "agg_benford_cargo").is_cube
    assert not aggregates.cube_source(com, FILTROS["municipio"]["where"], "agg_benford_cargo").is_cube
    assert not aggregates.cube_source(sem, FILTROS["ufs"]["where"], "agg_benford_cargo").is_cube
    assert aggregates.cube_usable("1=1")
    assert not aggregates.cube_usable("s.zona = ?")


@pytest.mark.parametrize("filtro", list(FILTROS))
@pytest.mark.parametrize("nome", FUNCOES)
def test_funcao_equivale_a_versao_antiga(stores, nome, filtro):
    com, sem = stores
    f = FILTROS[filtro]
    esperado = getattr(legacy, nome)(sem, f)
    assert not (isinstance(esperado, pd.DataFrame) and esperado.empty and filtro == "sem_filtro"), \
        f"{nome}: dados sintéticos não exercitam a função"
    for store, origem in ((com, "agregados"), (sem, "fonte bruta")):
        _assert_equal(getattr(novo, nome)(store, f), esperado, f"{nome}/{filtro}/{origem}")


# Consultas que antes ficavam nas páginas (SQL original copiado de lá)
def _legado_votos_amostra(store, f):  # veredicto.py
    return store.query_df(f"""
        SELECT v.codigo_candidato as candidato, SUM(v.quantidade) as votos
        FROM votos v JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']} AND v.cargo = 'Presidente' AND v.tipo_voto = 'nominal'
        GROUP BY v.codigo_candidato ORDER BY votos DESC
    """, f["params"])


def _legado_dist_issues(store, f):  # veredicto.py
    return store.query_df(f"""
        SELECT
            CASE WHEN s.has_issues THEN 'Com Issues' ELSE 'Sem Issues' END as grupo,
            v.codigo_candidato as candidato,
            SUM(v.quantidade) as votos
        FROM votos v JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']} AND v.cargo = 'Presidente' AND v.tipo_voto = 'nominal'
            AND v.codigo_candidato IN (13, 22)
        GROUP BY grupo, v.codigo_candidato
        ORDER BY grupo, votos DESC
    """, f["params"])


def _legado_modelo_voto(store, f):  # veredicto.py
    return store.query_df(f"""
        SELECT
            'UE' || s.modelo_urna as modelo,
            COUNT(DISTINCT s.id) as secoes,
            SUM(CASE WHEN v.codigo_candidato = 13 THEN v.quantidade ELSE 0 END) as lula,
            SUM(CASE WHEN v.codigo_candidato = 22 THEN v.quantidade ELSE 0 END) as bolsonaro,
            SUM(v.quantidade) as total
        FROM votos v JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']} AND v.cargo = 'Presidente' AND v.tipo_voto = 'nominal'
            AND v.codigo_candidato IN (13, 22) AND s.modelo_urna IS NOT NULL
        GROUP BY s.modelo_urna ORDER BY s.modelo_urna
    """, f["params"])


def _legado_votacao(store, f, cargo):  # votacao.py (sem LIMIT: empates no corte)
    return store.query_df(f"""
        SELECT
            v.codigo_candidato as candidato,
            v.partido,
            SUM(v.quantidade) as votos,
            COUNT(DISTINCT v.secao_id) as secoes
        FROM votos v JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']}
            AND v.cargo = ?
            AND v.tipo_voto = 'nominal'
            AND v.codigo_candidato IS NOT NULL
        GROUP BY v.codigo_candidato, v.partido
        ORDER BY votos DESC
    """, list(f["params"]) + [cargo])


def _legado_hist(store, f):  # votacao.py
    return store.query_df(f"""
        SELECT
            s.id AS secao_id,
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


def _legado_votos_turno(store, f):  # turnos.py
    base_where, base_params = f.where_sql(include_turno=False)
    return store.query_df(f"""
        SELECT
            s.turno,
            v.codigo_candidato as candidato,
            SUM(v.quantidade) as votos
        FROM votos v JOIN secoes s ON v.secao_id = s.id
        WHERE {base_where}
            AND v.cargo = 'Presidente' AND v.tipo_voto = 'nominal'
            AND v.codigo_candidato IN (13, 22)
        GROUP BY s.turno, v.codigo_candidato
        ORDER BY s.turno, votos DESC
    """, base_params)


def _legado_votos_pres_turno(store, f):  # compute_confidence_score
    return store.query_df(f"""
        SELECT
            s.turno,
            v.codigo_candidato AS candidato,
            SUM(v.quantidade) AS votos
        FROM votos v JOIN secoes s ON v.secao_id = s.id
        WHERE {f['where']}
            AND v.cargo = 'Presidente'
            AND v.tipo_voto = 'nominal'
        GROUP BY s.turno, v.codigo_candidato
        ORDER BY s.turno, votos DESC
    """, f["params"])


@pytest.mark.parametrize("filtro", list(FILTROS))
def test_consultas_das_paginas_equivalem(stores, filtro):
    com, sem = stores
    f = FILTROS[filtro]
    casos = [
        (novo.presidente_votos_por_candidato, (), _legado_votos_amostra),
        (novo.votos_13_22_por_grupo,
         ("CASE WHEN s.has_issues THEN 'Com Issues' ELSE 'Sem Issues' END",), _legado_dist_issues),
        (novo.presidente_13_22_por_modelo, (), _legado_modelo_voto),
        (novo.presidente_13_22_por_secao, (), _legado_hist),
        (novo.presidente_13_22_por_turno, (), _legado_votos_turno),
    ]
    for store in (com, sem):
        for fn, args, legado in casos:
            _assert_equal(fn(store, f, *args), legado(sem, f), f"{fn.__name__}/{filtro}")
        for cargo in ("Presidente", "Governador", "Deputado Federal"):
            esperado = _legado_votacao(sem, f, cargo)
            obtido = novo.votos_por_candidato(store, f, cargo, limite=10_000)
            _assert_equal(obtido, esperado, f"votacao/{cargo}/{filtro}")
            if len(esperado) > 20:  # o LIMIT 20 corta só depois da maior votação
                top = novo.votos_por_candidato(store, f, cargo)
                assert len(top) == 20
                assert top["votos"].tolist() == esperado["votos"].head(20).tolist()

        # Parte de votos do score de confiança (por turno e candidato)
        src = aggregates.cube_source(store, f["where"], "agg_votos_nominais")
        obtido = store.query_df(f"""
            SELECT s.turno, s.codigo_candidato AS candidato, SUM(s.votos) AS votos
            FROM {src.sql} s WHERE {f['where']} AND s.cargo = 'Presidente'
            GROUP BY s.turno, s.codigo_candidato ORDER BY s.turno, votos DESC
        """, f["params"])
        _assert_equal(obtido, _legado_votos_pres_turno(sem, f), f"votos_pres/{filtro}")


@pytest.mark.parametrize("filtro", ["sem_filtro", "turno1", "municipio", "issues"])
def test_score_de_confianca_igual_com_e_sem_agregados(stores, filtro):
    com, sem = stores
    f = FILTROS[filtro]
    _assert_equal(novo.compute_confidence_score(com, f), novo.compute_confidence_score(sem, f), filtro)


def test_filtro_legado_em_dict_usa_fonte_bruta(stores):
    com, sem = stores
    f = {"where": "s.uf IN (?) AND s.zona = ?", "params": ["sp", "0001"],
         "issue_where": "1=1", "issue_params": [], "turno": None}
    _assert_equal(novo.benford_all_offices(com, f), legacy.benford_all_offices(sem, f), "dict")
    _assert_equal(novo.benford_first_digit(com, f), legacy.benford_first_digit(sem, f), "dict")
