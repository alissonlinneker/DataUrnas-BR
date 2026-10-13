"""Testes unitários do dashboard: formatação, filtros, referência e importação das páginas."""

import importlib
import pkgutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from dataurnas.dashboard.components import formatting as fmt  # noqa: E402
from dataurnas.dashboard.filters import Filters  # noqa: E402
from dataurnas.dashboard.reference import ISSUE_DESCRICOES, TSE_2022, oficial_resumo  # noqa: E402

DASHBOARD_DIR = ROOT / "src" / "dataurnas" / "dashboard"
TRACOS_PROIBIDOS = (chr(0x2014), chr(0x2013))


# ----------------------------------------------------------------------
# Formatação pt-BR
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("valor", "esperado"),
    [(1234567, "1.234.567"), (0, "0"), (-1500, "-1.500"), (999.6, "1.000"), (None, "-"),
     (float("nan"), "-"), ("abc", "-")],
)
def test_fmt_int(valor, esperado):
    assert fmt.fmt_int(valor) == esperado


def test_fmt_pct_e_num():
    assert fmt.fmt_pct(12.345) == "12,35%"
    assert fmt.fmt_pct(12.345, 1) == "12,3%"
    assert fmt.fmt_pct(1234.5, 1) == "1.234,5%"
    assert fmt.fmt_num(1234.5, 2) == "1.234,50"
    assert fmt.fmt_num(1.5, 2, sign=True) == "+1,50"
    assert fmt.fmt_pp(-0.25) == "-0,25 p.p."
    assert fmt.fmt_pct(None) == "-"


def test_fmt_compact_e_pct():
    assert fmt.fmt_compact(158_745_502) == "158,7 mi"
    assert fmt.fmt_compact(2_500) == "2,5 mil"
    assert fmt.fmt_compact(12) == "12"
    assert fmt.pct(1, 4) == 25.0
    assert fmt.pct(1, 0) == 0.0


def test_acentuar_textos_do_banco():
    assert fmt.acentuar("Divergencia entre votos no log") == "Divergência entre votos no log"
    assert fmt.acentuar("Votacao encerrada ANTES do horario") == "Votação encerrada ANTES do horário"
    assert fmt.acentuar("Urna nao-padrao: tipo=reservaSecao") == "Urna não padrão: tipo=reservaSecao"
    assert fmt.acentuar("NAO") == "NÃO"
    assert fmt.acentuar(None) is None
    assert fmt.severidade_label("critica") == "Crítica"


def test_textos_sem_travessao():
    for path in DASHBOARD_DIR.rglob("*.py"):
        texto = path.read_text(encoding="utf-8")
        assert not any(t in texto for t in TRACOS_PROIBIDOS), path


# ----------------------------------------------------------------------
# Filtros estruturados
# ----------------------------------------------------------------------
def test_filters_where_e_params_na_mesma_ordem():
    f = Filters.build(turno=2, ufs=["sp", "rj"], modelos=["2020"], tipo_urna="Reserva",
                      severidades=["alta"], codigos=["C06"])
    assert f["where"] == "s.turno = ? AND s.uf IN (?,?) AND s.modelo_urna IN (?) AND s.is_reserva = TRUE"
    assert f["params"] == [2, "sp", "rj", "2020"]
    assert f["issue_where"].endswith("AND i.severidade IN (?) AND i.codigo IN (?)")
    assert f["issue_params"] == [2, "sp", "rj", "2020", "alta", "C06"]
    assert f["turno"] == 2
    assert f.get("turno") == 2


def test_filters_sem_turno_nao_depende_de_replace():
    # Um parâmetro inteiro igual ao turno não pode sumir (bug do str.replace antigo)
    f = Filters.build(turno=1, municipios=[1], ufs=["sp"])
    where, params = f.where_sql(include_turno=False)
    assert "turno" not in where
    assert params == ["sp", 1]
    where_t1, params_t1 = f.where_sql(include_turno=False, alias="t1")
    assert where_t1 == "t1.uf IN (?) AND t1.municipio IN (?)"
    assert params_t1 == params


def test_filters_vazio_e_chave_de_cache():
    f = Filters.build()
    assert f["where"] == "1=1" and f["params"] == []
    assert f.file_suffix == "ambos"
    assert Filters.build(turno=1).file_suffix == "T1"
    g = Filters.from_key(Filters.build(turno=1, ufs=["ba"]).cache_key())
    assert g == Filters.build(turno=1, ufs=["ba"])
    assert hash(g) == hash(Filters.build(turno=1, ufs=["ba"]))
    assert f.with_turno(2)["where"] == "s.turno = ?"


def test_filters_regiao_so_quando_sem_uf():
    assert Filters.build(regioes=["norte"])["where"] == "s.regiao IN (?)"
    assert Filters.build(regioes=["norte"], ufs=["ac"])["where"] == "s.uf IN (?)"


# ----------------------------------------------------------------------
# Referência única
# ----------------------------------------------------------------------
def test_referencia_unica_tse_2022():
    from dataurnas.dashboard import analysis

    assert analysis.OFICIAL_1T == oficial_resumo(1)
    assert analysis.OFICIAL_2T["lula_pct"] == TSE_2022[2]["candidatos"][13]["pct"]
    assert analysis.ISSUE_DESCRICOES is ISSUE_DESCRICOES


def test_descricao_i05_segue_limiar_real():
    from dataurnas.analyzer.statistical import LIMIAR_ABSTENCAO_PCT

    assert f"{LIMIAR_ABSTENCAO_PCT:g}".replace(".", ",") + "%" in ISSUE_DESCRICOES["I05"]
    for codigo in ("M03", "E01", "E02", "E03"):
        assert codigo in ISSUE_DESCRICOES


# ----------------------------------------------------------------------
# Páginas e componentes importam sem erro
# ----------------------------------------------------------------------
def _modulos(pacote: str) -> list[str]:
    pkg = importlib.import_module(pacote)
    return [f"{pacote}.{m.name}" for m in pkgutil.iter_modules(pkg.__path__)]


@pytest.mark.parametrize(
    "modulo",
    _modulos("dataurnas.dashboard.pages") + _modulos("dataurnas.dashboard.components")
    + ["dataurnas.dashboard.navigation", "dataurnas.dashboard.state", "dataurnas.dashboard.data2026"],
)
def test_importa_modulo(modulo):
    importlib.import_module(modulo)


def test_assets_existem_e_geojson_tem_27_ufs():
    from dataurnas.dashboard.components.geo import brazil_geojson

    for nome in ("logo.svg", "hero.svg", "empty-data.svg", "empty-progress.svg", "empty-database.svg"):
        conteudo = (DASHBOARD_DIR / "assets" / nome).read_text(encoding="utf-8")
        assert conteudo.lstrip().startswith("<svg") and "<title" in conteudo
    siglas = {ft["properties"]["sigla"] for ft in brazil_geojson()["features"]}
    assert len(siglas) == 27 and {"SP", "DF", "AC"} <= siglas
