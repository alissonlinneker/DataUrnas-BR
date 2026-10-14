"""Orquestrador de downloads do TSE."""

import asyncio
import logging
import random
from pathlib import Path
from typing import Callable, Optional

from ..config import JSON_DIR, RAW_DIR
from ..models import Section, UrnaMeta
from .client import DownloadResult, TSEClient, env_int
from .tse_api import TSEApi

logger = logging.getLogger(__name__)

#: Downloads simultâneos por gerenciador. Padrão conservador; ajuste com
#: a variável de ambiente DATAURNAS_MAX_CONCURRENT.
DEFAULT_MAX_CONCURRENT = env_int("DATAURNAS_MAX_CONCURRENT", 50)


def _new_stats() -> dict:
    return {"downloaded": 0, "skipped": 0, "errors": 0, "sections_processed": 0}


class DownloadManager:
    """Gerencia downloads massivos do TSE com concorrência controlada."""

    def __init__(
        self,
        raw_dir: Path = RAW_DIR,
        json_dir: Path = JSON_DIR,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        on_section_done: Optional[Callable[[Path, str], None]] = None,
    ):
        self._raw_dir = raw_dir
        self._json_dir = json_dir
        self._max_concurrent = max(1, max_concurrent)
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._on_section_done = on_section_done
        self._stats = _new_stats()

    def _section_dir(self, section: Section) -> Path:
        return (
            self._raw_dir
            / section.uf.lower()
            / section.municipio_codigo
            / section.zona
            / section.secao
        )

    async def download_section_files(
        self,
        client: TSEClient,
        api: TSEApi,
        ciclo: str,
        pleito: str,
        urna: UrnaMeta,
        file_types: Optional[list[str]] = None,
    ) -> dict:
        """Baixa os arquivos de uma urna especifica."""
        section = urna.section
        dest_dir = self._section_dir(section)
        results = {"ok": 0, "skip": 0, "fail": 0}

        for filename in urna.arquivos:
            # Filtrar por tipo de arquivo se especificado
            if file_types:
                matches = any(filename.endswith(ft) for ft in file_types)
                if not matches:
                    # Verificar também por sufixo parcial
                    matches = any(ft in filename for ft in file_types)
                    if not matches:
                        continue

            url = api.build_file_url(ciclo, pleito, section, urna.hash, filename)
            dest = dest_dir / filename

            async with self._semaphore:
                outcome = await client.download_file(url, dest)
            if outcome is DownloadResult.DOWNLOADED:
                results["ok"] += 1
            elif outcome is DownloadResult.SKIPPED:
                results["skip"] += 1
            else:
                results["fail"] += 1

        return results

    async def _process_one_section(
        self,
        section_sem: asyncio.Semaphore,
        client: TSEClient,
        api: TSEApi,
        ciclo: str,
        pleito: str,
        section,
        file_types: Optional[list[str]],
        uf: str,
        total: int,
    ):
        """Baixa e processa uma única seção (chamado em paralelo)."""
        async with section_sem:
            try:
                urnas = await api.get_section_meta(ciclo, pleito, section)
                for urna in urnas:
                    results = await self.download_section_files(
                        client, api, ciclo, pleito, urna, file_types
                    )
                    self._stats["downloaded"] += results["ok"]
                    self._stats["skipped"] += results["skip"]
                    self._stats["errors"] += results["fail"]

                self._stats["sections_processed"] += 1

                if self._on_section_done:
                    section_dir = self._section_dir(section)
                    try:
                        self._on_section_done(section_dir, pleito)
                    except Exception as cb_err:
                        logger.debug("Callback erro: %s", cb_err)

                processed = self._stats["sections_processed"]
                if processed % 100 == 0:
                    logger.info(
                        "Progresso %s: %d/%d seções | %d baixados, %d ignorados, %d erros",
                        uf.upper(),
                        processed,
                        total,
                        self._stats["downloaded"],
                        self._stats["skipped"],
                        self._stats["errors"],
                    )
            except Exception as e:
                logger.error(
                    "Erro na seção %s/%s/%s: %s",
                    section.municipio_codigo,
                    section.zona,
                    section.secao,
                    e,
                )
                self._stats["errors"] += 1

    async def download_state(
        self,
        client: TSEClient,
        api: TSEApi,
        ciclo: str,
        pleito: str,
        uf: str,
        file_types: Optional[list[str]] = None,
        max_sections: Optional[int] = None,
        municipio_filter: Optional[list[str]] = None,
    ) -> dict:
        """Baixa dados de um estado inteiro (ou amostra) com seções em paralelo."""
        logger.info("Baixando dados de %s...", uf.upper())

        try:
            state_config = await api.get_state_config(ciclo, pleito, uf)
        except Exception as exc:
            logger.error("Falha ao obter configuração de %s: %s", uf, exc)
            state_config = None
        if not state_config:
            logger.error("Não foi possível obter configuração de %s", uf)
            return self._stats

        total_sections = api.count_sections(state_config)
        logger.info(
            "%s: %d municípios, %d seções totais",
            state_config.nome,
            len(state_config.municipios),
            total_sections,
        )

        sections = list(api.iter_sections(state_config))

        # Filtrar por município se especificado
        if municipio_filter:
            codigos = set(municipio_filter)
            nomes = {m.upper() for m in municipio_filter}
            sections = [
                s for s in sections
                if s.municipio_codigo in codigos or s.municipio_nome.upper() in nomes
            ]
            logger.info("Filtrado para %d seções em municípios selecionados", len(sections))

        # Limitar amostra se especificado
        if max_sections and max_sections < len(sections):
            sections = random.sample(sections, max_sections)
            logger.info("Amostra aleatória de %d seções", max_sections)

        # Semáforo para limitar seções concorrentes (separado do semáforo de arquivos)
        section_sem = asyncio.Semaphore(self._max_concurrent)

        # Processar seções em lotes paralelos
        BATCH = 500
        for batch_start in range(0, len(sections), BATCH):
            batch = sections[batch_start:batch_start + BATCH]
            tasks = [
                self._process_one_section(
                    section_sem, client, api, ciclo, pleito,
                    section, file_types, uf, len(sections),
                )
                for section in batch
            ]
            await asyncio.gather(*tasks)

        logger.info(
            "Concluído %s: %d seções, %d baixados, %d ignorados, %d erros",
            uf.upper(),
            self._stats["sections_processed"],
            self._stats["downloaded"],
            self._stats["skipped"],
            self._stats["errors"],
        )
        return self._stats

    async def download_sample(
        self,
        client: TSEClient,
        api: TSEApi,
        ciclo: str,
        pleito: str,
        states: list[str],
        sections_per_state: int = 50,
        file_types: Optional[list[str]] = None,
    ) -> dict:
        """Baixa amostra de dados de múltiplos estados."""
        logger.info(
            "Baixando amostra: %d estados, %d seções/estado",
            len(states),
            sections_per_state,
        )
        all_stats = _new_stats()

        for uf in states:
            self._stats = _new_stats()
            await self.download_state(
                client, api, ciclo, pleito, uf,
                file_types=file_types,
                max_sections=sections_per_state,
            )
            for k in all_stats:
                all_stats[k] += self._stats[k]

        logger.info(
            "Amostra concluída: %d seções, %d baixados, %d erros",
            all_stats["sections_processed"],
            all_stats["downloaded"],
            all_stats["errors"],
        )
        return all_stats
