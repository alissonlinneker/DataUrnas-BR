"""Filtros da auditoria 2022: estado estruturado e barra lateral.

O módulo de análise recebe os filtros como mapeamento com as chaves
``where``, ``params``, ``issue_where``, ``issue_params`` e ``turno``. A classe
``Filters`` preserva esse contrato (acesso por ``f["where"]`` e ``f.get``),
mas guarda as condições de forma estruturada. Assim é possível gerar o WHERE
sem a condição de turno (``where_sql(include_turno=False)``) sem manipular
strings com ``str.replace``, que dependia da ordem dos placeholders.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace

import streamlit as st

from dataurnas.config import REGIOES
from dataurnas.dashboard.reference import ISSUE_DESCRICOES, issue_label

Condition = tuple[str, tuple]  # (fragmento SQL com alias "s.", parâmetros)

TURNO_AMBOS = "Ambos os Turnos"
TURNO_LABELS = {1: "1º Turno", 2: "2º Turno"}

# Chaves de widget da barra lateral (prefixo usado para persistir entre páginas)
KEY_PREFIX = "flt_"


def _in(column: str, values) -> Condition:
    values = tuple(values)
    placeholders = ",".join("?" for _ in values)
    return f"{column} IN ({placeholders})", values


@dataclass(frozen=True)
class Filters(Mapping):
    """Filtros imutáveis e hasheáveis (servem de chave de cache)."""

    turno: int | None = None
    conditions: tuple[Condition, ...] = ()
    issue_conditions: tuple[Condition, ...] = ()
    _cache: dict = field(default_factory=dict, compare=False, hash=False, repr=False)

    # ------------------------------------------------------------------
    # Construção
    # ------------------------------------------------------------------
    @classmethod
    def build(
        cls,
        turno: int | None = None,
        ufs=(),
        regioes=(),
        municipios=(),
        modelos=(),
        tipo_urna: str = "Todos",
        apenas_issues: bool = False,
        severidades=(),
        codigos=(),
    ) -> Filters:
        conds: list[Condition] = []
        if ufs:
            conds.append(_in("s.uf", ufs))
        elif regioes:
            conds.append(_in("s.regiao", regioes))
        if municipios:
            conds.append(_in("s.municipio", municipios))
        if modelos:
            conds.append(_in("s.modelo_urna", modelos))
        if tipo_urna == "Normal":
            conds.append(("s.is_reserva = FALSE", ()))
        elif tipo_urna == "Reserva":
            conds.append(("s.is_reserva = TRUE", ()))
        if apenas_issues:
            conds.append(("s.has_issues = TRUE", ()))

        issue_conds: list[Condition] = []
        if severidades:
            issue_conds.append(_in("i.severidade", severidades))
        if codigos:
            issue_conds.append(_in("i.codigo", codigos))
        return cls(turno=turno, conditions=tuple(conds), issue_conditions=tuple(issue_conds))

    def with_turno(self, turno: int | None) -> Filters:
        return replace(self, turno=turno, _cache={})

    # ------------------------------------------------------------------
    # SQL
    # ------------------------------------------------------------------
    def where_sql(self, include_turno: bool = True, alias: str = "s") -> tuple[str, list]:
        """WHERE para a tabela de seções e seus parâmetros, na mesma ordem."""
        parts: list[str] = []
        params: list = []
        if include_turno and self.turno is not None:
            parts.append(f"{alias}.turno = ?")
            params.append(self.turno)
        for sql, values in self.conditions:
            parts.append(sql if alias == "s" else sql.replace("s.", f"{alias}.", 1))
            params.extend(values)
        return (" AND ".join(parts) if parts else "1=1"), params

    def issue_where_sql(self, include_turno: bool = True) -> tuple[str, list]:
        where, params = self.where_sql(include_turno=include_turno)
        for sql, values in self.issue_conditions:
            where += f" AND {sql}"
            params.extend(values)
        return where, params

    def cache_key(self) -> tuple:
        return (self.turno, self.conditions, self.issue_conditions)

    @classmethod
    def from_key(cls, key: tuple) -> Filters:
        turno, conditions, issue_conditions = key
        return cls(turno=turno, conditions=conditions, issue_conditions=issue_conditions)

    # ------------------------------------------------------------------
    # Contrato de mapeamento usado por analysis.py e páginas antigas
    # ------------------------------------------------------------------
    def _as_dict(self) -> dict:
        if not self._cache:
            where, params = self.where_sql()
            issue_where, issue_params = self.issue_where_sql()
            base_where, base_params = self.where_sql(include_turno=False)
            self._cache.update(
                where=where,
                params=params,
                issue_where=issue_where,
                issue_params=issue_params,
                turno=self.turno,
                base_where=base_where,
                base_params=base_params,
            )
        return self._cache

    def __getitem__(self, key):
        value = self._as_dict()[key]
        return list(value) if isinstance(value, list) else value

    def __iter__(self):
        return iter(self._as_dict())

    def __len__(self) -> int:
        return len(self._as_dict())

    def __hash__(self) -> int:
        return hash(self.cache_key())

    @property
    def turno_label(self) -> str:
        return TURNO_LABELS.get(self.turno, "Ambos")

    @property
    def file_suffix(self) -> str:
        """Sufixo de arquivo de exportação: T1, T2 ou ambos (nunca 'TNone')."""
        return f"T{self.turno}" if self.turno else "ambos"


# ----------------------------------------------------------------------
# Barra lateral
# ----------------------------------------------------------------------
def persist_widget_state() -> None:
    """Mantém os valores dos filtros ao trocar de página.

    O Streamlit descarta o estado de widgets que não foram desenhados no
    rerun anterior (ex.: ao visitar a página de 2026, que não tem filtros).
    Reatribuir a chave no início do script evita a perda.
    """
    for key in list(st.session_state.keys()):
        if isinstance(key, str) and key.startswith(KEY_PREFIX):
            st.session_state[key] = st.session_state[key]


def render_sidebar(store) -> Filters:
    """Desenha os filtros da auditoria 2022 e devolve um ``Filters``."""
    sb = st.sidebar
    sb.markdown("### Filtros da auditoria 2022")
    options = store.get_filter_options()

    turnos = options.get("turnos", [1])
    turno_opcoes = [TURNO_AMBOS] + [TURNO_LABELS[t] for t in (1, 2) if t in turnos]
    turno_sel = sb.radio("Turno", turno_opcoes, index=0, key=f"{KEY_PREFIX}turno", horizontal=True)
    turno = {v: k for k, v in TURNO_LABELS.items()}.get(turno_sel)

    regioes_sel = sb.multiselect(
        "Região", options.get("regioes", []), key=f"{KEY_PREFIX}regioes",
        format_func=lambda r: str(r).capitalize(),
    )

    ufs_disponiveis = options.get("ufs", [])
    if regioes_sel:
        permitidas = {u for r in regioes_sel for u in REGIOES.get(r, [])}
        ufs_disponiveis = [u for u in ufs_disponiveis if u in permitidas]
    ufs_sel = sb.multiselect(
        "Estado (UF)", ufs_disponiveis, key=f"{KEY_PREFIX}ufs", format_func=lambda u: str(u).upper(),
    )

    municipios = store.municipios(tuple(ufs_sel)) if ufs_sel else []
    municipios_sel = sb.multiselect("Município", municipios, key=f"{KEY_PREFIX}municipios")

    modelos_sel = sb.multiselect(
        "Modelo de urna", options.get("modelos", []), key=f"{KEY_PREFIX}modelos",
        format_func=lambda m: f"UE{m}",
    )
    tipo_urna_sel = sb.selectbox("Tipo de urna", ["Todos", "Normal", "Reserva"], key=f"{KEY_PREFIX}tipo")
    apenas_issues = sb.checkbox("Apenas seções com inconsistências", key=f"{KEY_PREFIX}apenas_issues")

    with sb.expander("Filtros de inconsistência", expanded=False):
        sev_sel = st.multiselect(
            "Severidade", options.get("severidades", []), key=f"{KEY_PREFIX}severidades",
            format_func=lambda s: {"critica": "Crítica", "alta": "Alta", "media": "Média",
                                   "informativa": "Informativa"}.get(s, s),
        )
        codigos = options.get("codigos_issue", [])
        codigos_sel = st.multiselect(
            "Código da inconsistência", codigos, key=f"{KEY_PREFIX}codigos",
            format_func=lambda c: issue_label(c) if c in ISSUE_DESCRICOES else c,
        )

    return Filters.build(
        turno=turno,
        ufs=ufs_sel,
        regioes=regioes_sel,
        municipios=municipios_sel,
        modelos=modelos_sel,
        tipo_urna=tipo_urna_sel,
        apenas_issues=apenas_issues,
        severidades=sev_sel,
        codigos=codigos_sel,
    )
