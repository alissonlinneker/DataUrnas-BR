"""Camada de persistência DuckDB para dados eleitorais."""

import logging
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Optional

import duckdb

from ..config import DB_DIR, RAW_DIR, TIMEZONE_OFFSETS  # noqa: F401 (reexport legado)
from . import metadados as _meta
from .rows import SECOES_COLUMNS, UF_REGIAO, SectionRows, extract_rows

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = DB_DIR / "eleicoes_2022.duckdb"

# Mantido por compatibilidade com scripts antigos
_UF_REGIAO = UF_REGIAO

_UPSERT_SECAO_SQL = (
    f"INSERT INTO secoes ({', '.join(SECOES_COLUMNS)}) "
    f"VALUES ({', '.join('?' for _ in SECOES_COLUMNS)}) "
    "ON CONFLICT (id) DO UPDATE SET "
    + ", ".join(f"{c} = excluded.{c}" for c in SECOES_COLUMNS if c != "id")
)


class DuckDBStore:
    """Gerencia persistência e consultas em DuckDB."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH, read_only: bool = False):
        db_path = Path(db_path)
        if not read_only:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._read_only = read_only
        self._conn = duckdb.connect(str(db_path), read_only=read_only)
        if not read_only:
            self._create_tables()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _create_tables(self):
        """Cria schema do banco."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS secoes (
                id VARCHAR PRIMARY KEY,
                turno INTEGER DEFAULT 1,
                uf VARCHAR,
                regiao VARCHAR,
                municipio VARCHAR,
                zona VARCHAR,
                secao VARCHAR,
                modelo_urna VARCHAR,
                tipo_urna VARCHAR,
                versao_sw VARCHAR,
                fuso_offset INTEGER,
                -- BU data
                emissao VARCHAR,
                eleitores_aptos INTEGER,
                comparecimento INTEGER,
                lib_codigo INTEGER,
                comp_biometrico INTEGER,
                pct_biometria FLOAT,
                pct_abstencao FLOAT,
                -- Timing (from log)
                hora_abertura VARCHAR,
                hora_encerramento VARCHAR,
                duracao_min INTEGER,
                -- Log stats
                reboots INTEGER DEFAULT 0,
                erros_log INTEGER DEFAULT 0,
                alertas_mesario INTEGER DEFAULT 0,
                votos_log INTEGER DEFAULT 0,
                substituicoes INTEGER DEFAULT 0,
                -- Flags
                is_reserva BOOLEAN DEFAULT FALSE,
                has_issues BOOLEAN DEFAULT FALSE,
                n_issues INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS votos (
                secao_id VARCHAR,
                eleicao_id INTEGER,
                cargo VARCHAR,
                codigo_cargo INTEGER,
                tipo_voto VARCHAR,
                codigo_candidato INTEGER,
                partido INTEGER,
                quantidade INTEGER,
                FOREIGN KEY (secao_id) REFERENCES secoes(id)
            );

            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER,
                secao_id VARCHAR,
                codigo VARCHAR,
                severidade VARCHAR,
                descricao VARCHAR,
                base_legal VARCHAR,
                detalhes VARCHAR,
                FOREIGN KEY (secao_id) REFERENCES secoes(id)
            );

            CREATE TABLE IF NOT EXISTS totais_cargo (
                secao_id VARCHAR,
                eleicao_id INTEGER,
                cargo VARCHAR,
                codigo_cargo INTEGER,
                comparecimento INTEGER,
                nominais INTEGER,
                brancos INTEGER,
                nulos INTEGER,
                legenda INTEGER,
                total INTEGER,
                FOREIGN KEY (secao_id) REFERENCES secoes(id)
            );

            CREATE SEQUENCE IF NOT EXISTS issue_seq START 1;
        """)
        self._conn.execute(_meta.DDL)

    def clear(self):
        """Limpa todos os dados (para rebuild)."""
        self._conn.execute("DELETE FROM votos")
        self._conn.execute("DELETE FROM issues")
        self._conn.execute("DELETE FROM totais_cargo")
        self._conn.execute("DELETE FROM secoes")
        self._conn.execute(f"DELETE FROM {_meta.TABELA}")  # o flag vale para os dados apagados
        self._conn.execute("DROP SEQUENCE IF EXISTS issue_seq")
        self._conn.execute("CREATE SEQUENCE issue_seq START 1")

    # ============================================================
    # Escrita
    # ============================================================

    def existing_ids(self) -> set[str]:
        """IDs de seções já presentes no banco."""
        return {r[0] for r in self._conn.execute("SELECT id FROM secoes").fetchall()}

    def insert_rows(self, batch: Iterable[SectionRows]) -> int:
        """Insere (ou substitui) um lote de seções em uma única transação.

        Idempotente: se uma seção já existe, suas linhas filhas (votos,
        issues, totais_cargo) são apagadas antes da reinserção, e a linha
        em seções e atualizada no lugar (sem violar as FKs).
        Em caso de erro, o lote inteiro e desfeito.

        Returns:
            Quantidade de seções gravadas.
        """
        batch = list(batch)
        if not batch:
            return 0

        # Última ocorrência vence se o mesmo id aparecer duas vezes no lote
        by_id = {rows.secao_id: rows for rows in batch}
        ids = list(by_id)

        self._conn.execute("BEGIN TRANSACTION")
        try:
            existentes = [
                r[0] for r in self._conn.execute(
                    "SELECT id FROM secoes WHERE id IN (SELECT UNNEST(?::VARCHAR[]))",
                    [ids],
                ).fetchall()
            ]
            if existentes:
                for tabela in ("votos", "issues", "totais_cargo"):
                    self._conn.execute(
                        f"DELETE FROM {tabela} "  # noqa: S608 (tabela e constante)
                        "WHERE secao_id IN (SELECT UNNEST(?::VARCHAR[]))",
                        [existentes],
                    )

            self._conn.executemany(_UPSERT_SECAO_SQL, [r.secao for r in by_id.values()])

            issue_rows = [i for r in by_id.values() for i in r.issues]
            if issue_rows:
                self._conn.executemany(
                    "INSERT INTO issues VALUES (nextval('issue_seq'), ?, ?, ?, ?, ?, ?)",
                    issue_rows,
                )
            voto_rows = [v for r in by_id.values() for v in r.votos]
            if voto_rows:
                self._conn.executemany(
                    "INSERT INTO votos VALUES (?, ?, ?, ?, ?, ?, ?, ?)", voto_rows
                )
            totais_rows = [t for r in by_id.values() for t in r.totais]
            if totais_rows:
                self._conn.executemany(
                    "INSERT INTO totais_cargo VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    totais_rows,
                )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        return len(by_id)

    def build_from_bu_files(
        self,
        analyzer,
        bu_files: Iterable[Path],
        batch_size: int = 500,
        skip_ids: Optional[set[str]] = None,
        progress: Optional[Callable[[int, int, int], None]] = None,
    ) -> tuple[int, int]:
        """Analisa e grava BUs em lotes transacionais.

        Args:
            analyzer: BatchAnalyzer.
            bu_files: arquivos BU a processar.
            batch_size: seções por transação.
            skip_ids: secao_ids a pular ANTES do parse (modo incremental).
            progress: callback(processados, gravados, erros).

        Returns:
            (gravados, erros)
        """
        batch: list[SectionRows] = []
        gravados = erros = processados = 0
        for bu_file in bu_files:
            processados += 1
            if skip_ids:
                secao_id = analyzer.secao_id_for(bu_file)
                if secao_id and secao_id in skip_ids:
                    continue
            try:
                result = analyzer.analyze_section(bu_file.parent, bu_file=bu_file)
                batch.append(extract_rows(result))
            except Exception as e:
                erros += 1
                if erros <= 20:
                    logger.warning("Erro ao processar %s: %s", bu_file, e)
                continue

            if len(batch) >= batch_size:
                gravados += self.insert_rows(batch)
                batch = []
                if progress:
                    progress(processados, gravados, erros)

        if batch:
            gravados += self.insert_rows(batch)
        self._conn.execute("CHECKPOINT")
        if progress:
            progress(processados, gravados, erros)
        return gravados, erros

    # ============================================================
    # Metadados de construção
    # ============================================================
    def metadados(self) -> dict[str, str]:
        """Metadados de construção gravados no banco (vazio se ausentes)."""
        return _meta.ler_metadados(self._conn)

    def hashes_verificados(self) -> Optional[bool]:
        """True/False conforme registrado; None se o banco não registrou."""
        return _meta.texto_para_bool(self.metadados().get(_meta.CHAVE_VERIFY_HASHES))

    def registrar_verificacao_hashes(
        self,
        verificado: bool,
        incremental: bool = False,
        secoes_anteriores: int = 0,
        origem: str = "raw",
    ) -> bool:
        """Registra se a verificação SHA-512 foi executada na construção.

        Em modo incremental, o banco só conta como verificado se a carga atual
        verificou E o registro anterior também, ou se não havia seções antes da
        carga (``secoes_anteriores``): uma base mista não pode ser apresentada
        como integralmente verificada.

        Returns:
            o valor efetivamente gravado.
        """
        efetivo = bool(verificado)
        if incremental and efetivo and secoes_anteriores > 0:
            efetivo = self.hashes_verificados() is True
        _meta.gravar_verificacao_hashes(self._conn, efetivo, origem)
        return efetivo

    def build_from_raw(
        self, raw_dir: Path = RAW_DIR, batch_size: int = 500, verify_hashes: bool = False,
    ) -> int:
        """Popula o banco do zero re-analisando todos os dados brutos."""
        from ..analyzer.batch import BatchAnalyzer

        self.clear()
        analyzer = BatchAnalyzer(raw_dir=raw_dir, verify_hashes=verify_hashes)
        bu_files = analyzer.find_bu_files()
        logger.info("Processando %d arquivos BU para DuckDB...", len(bu_files))
        _, erros = self.build_from_bu_files(analyzer, bu_files, batch_size=batch_size)
        self.registrar_verificacao_hashes(analyzer.verify_hashes)

        count, t1, t2 = self._contagem_turnos()
        logger.info("DuckDB populado: %d seções (1T: %d, 2T: %d, %d erros)",
                    count, t1, t2, erros)
        return count

    def build_incremental(
        self, raw_dir: Path = RAW_DIR, batch_size: int = 500, verify_hashes: bool = False,
    ) -> int:
        """Compila apenas BUs novos (não presentes no banco), sem reparsear os demais."""
        from ..analyzer.batch import BatchAnalyzer

        existing = self.existing_ids()
        logger.info("DuckDB tem %d seções existentes", len(existing))
        analyzer = BatchAnalyzer(raw_dir=raw_dir, verify_hashes=verify_hashes)
        bu_files = analyzer.find_bu_files()
        gravados, erros = self.build_from_bu_files(
            analyzer, bu_files, batch_size=batch_size, skip_ids=existing,
        )
        self.registrar_verificacao_hashes(
            analyzer.verify_hashes, incremental=True, secoes_anteriores=len(existing),
        )
        count, t1, t2 = self._contagem_turnos()
        logger.info("DuckDB incremental: +%d seções (%d erros). Total: %d (1T: %d, 2T: %d)",
                    gravados, erros, count, t1, t2)
        return count

    def _contagem_turnos(self) -> tuple[int, int, int]:
        row = self._conn.execute(
            "SELECT COUNT(*), COUNT(*) FILTER (WHERE turno = 1), "
            "COUNT(*) FILTER (WHERE turno = 2) FROM secoes"
        ).fetchone()
        return int(row[0]), int(row[1]), int(row[2])

    @staticmethod
    def _bu_file_to_secao_id(bu_file: Path, analyzer=None) -> str:
        """Calcula secao_id a partir do path do BU sem parsing ASN.1."""
        if analyzer is None:
            from ..analyzer.batch import BatchAnalyzer

            analyzer = BatchAnalyzer()
        secao_id = analyzer.secao_id_for(bu_file)
        if not secao_id:
            logger.warning("Não foi possível derivar secao_id de %s", bu_file)
        return secao_id

    def _process_section(self, analyzer, section_dir: Path, bu_file: Optional[Path] = None):
        """Processa uma seção e grava no DuckDB (uma transação)."""
        result = analyzer.analyze_section(section_dir, bu_file=bu_file)
        self.insert_rows([extract_rows(result)])

    # ============================================================
    # Consultas para o Dashboard
    # ============================================================

    def query(self, sql: str, params=None):
        """Executa query e retorna como lista de dicts."""
        result = self._conn.execute(sql, params or [])
        cols = [desc[0] for desc in result.description]
        return [dict(zip(cols, row, strict=True)) for row in result.fetchall()]

    def query_df(self, sql: str, params=None):
        """Executa query e retorna como DataFrame."""
        return self._conn.execute(sql, params or []).fetchdf()

    def get_summary(self) -> dict:
        """Resumo geral para a página principal do BI (uma consulta por tabela)."""
        row = self._conn.execute("""
            SELECT
                COUNT(*),
                COUNT(*) FILTER (WHERE NOT has_issues),
                COUNT(*) FILTER (WHERE has_issues),
                COALESCE(SUM(eleitores_aptos), 0),
                COALESCE(SUM(comparecimento), 0),
                COALESCE(SUM(reboots), 0),
                COUNT(DISTINCT uf)
            FROM secoes
        """).fetchone()
        total_issues = self._conn.execute("SELECT COUNT(*) FROM issues").fetchone()[0]
        return {
            "total_secoes": row[0],
            "total_issues": total_issues,
            "secoes_ok": row[1],
            "secoes_com_issues": row[2],
            "total_eleitores": row[3],
            "total_comparecimento": row[4],
            "total_reboots": row[5],
            "ufs": row[6],
        }

    def get_filter_options(self) -> dict:
        """Opções disponíveis para filtros do dashboard."""
        return {
            "turnos": [r[0] for r in self._conn.execute("SELECT DISTINCT turno FROM secoes ORDER BY turno").fetchall()],
            "ufs": [r[0] for r in self._conn.execute("SELECT DISTINCT uf FROM secoes ORDER BY uf").fetchall()],
            "regioes": [r[0] for r in self._conn.execute("SELECT DISTINCT regiao FROM secoes ORDER BY regiao").fetchall()],
            "modelos": [r[0] for r in self._conn.execute("SELECT DISTINCT modelo_urna FROM secoes WHERE modelo_urna IS NOT NULL ORDER BY modelo_urna").fetchall()],
            "severidades": [r[0] for r in self._conn.execute("SELECT DISTINCT severidade FROM issues ORDER BY severidade").fetchall()],
            "codigos_issue": [r[0] for r in self._conn.execute("SELECT DISTINCT codigo FROM issues ORDER BY codigo").fetchall()],
        }
