"""Análise de logs da urna eletrônica."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import BoletimUrna, Issue, IssueSeverity, LogEntry
from ..parsers.log import LogParser
from .timezones import get_tz_offset

logger = logging.getLogger(__name__)

# Horários esperados de votação (eleição 2022)
# A votação ocorre das 8h às 17h de Brasília. Logs usam hora LOCAL.
# As constantes abaixo referem-se ao horário de Brasília;
# _adjust_for_tz() converte para hora local antes de comparar.
HORA_ABERTURA_BRT = (8, 0)   # 08:00 Brasília
HORA_ABERTURA_TOL = 30       # Tolerância em minutos após 08:00
HORA_ENCERRAMENTO_BRT = (17, 0)  # 17:00 Brasília
HORA_ENCERRAMENTO_MAX_BRT = (22, 0)  # Máximo razoável

# Limiar para alertas de mesário (indagação frequente pode indicar problemas)
LIMIAR_ALERTAS_MESARIO = 20


def _time_to_min(h: int, m: int) -> int:
    """Converte hora:minuto para minutos desde 00:00."""
    return h * 60 + m


def _parse_time(hora_str: str) -> float:
    """Parseia HH:MM[:SS] para minutos desde 00:00 (segundos como fração)."""
    parts = hora_str.split(":")
    if len(parts) not in (2, 3):
        raise ValueError(f"hora inválida: {hora_str!r}")
    h, m = int(parts[0]), int(parts[1])
    sec = int(parts[2]) if len(parts) == 3 else 0
    if not (0 <= h < 24 and 0 <= m < 60 and 0 <= sec < 60):
        raise ValueError(f"hora inválida: {hora_str!r}")
    return h * 60 + m + sec / 60


def _entry_datetime(entry: LogEntry) -> Optional[datetime]:
    """Combina data (DD/MM/YYYY) e hora (HH:MM:SS) de uma entrada do log."""
    return entry.timestamp


def _local_limits(uf: str, municipio=None) -> dict:
    """Retorna horários limites em hora LOCAL para uma seção."""
    offset = get_tz_offset(uf, municipio)

    ab_h, ab_m = HORA_ABERTURA_BRT
    enc_h, enc_m = HORA_ENCERRAMENTO_BRT
    enc_max_h, enc_max_m = HORA_ENCERRAMENTO_MAX_BRT

    return {
        "abertura_min": _time_to_min(ab_h + offset - 1, ab_m),  # 1h antes
        "abertura_max": _time_to_min(ab_h + offset, ab_m + HORA_ABERTURA_TOL),
        "encerramento_min": _time_to_min(enc_h + offset, enc_m),
        "encerramento_max": _time_to_min(enc_max_h + offset, enc_max_m),
    }


class LogAnalyzer:
    """Analisa logs da urna para detecção de anomalias."""

    def __init__(self):
        self._parser = LogParser()

    def analyze_log(
        self,
        log_path: Path,
        bu: Optional[BoletimUrna] = None,
        uf: str = "",
        turno_date: Optional[str] = None,
        municipio=None,
    ) -> dict:
        """Analisa um arquivo de log e retorna resultados completos.

        Args:
            log_path: Caminho do arquivo .logjez/.jez.
            bu: Boletim de Urna parseado (para comparação votos).
            uf: Sigla do estado (para ajuste de fuso horário).
            municipio: Código TSE do município (fusos que diferem da UF,
                como o oeste do Amazonas e Fernando de Noronha).
            turno_date: Data do turno (DD/MM/YYYY) para filtrar entradas.
                Necessário para T2, cujo .logjez acumula eventos do T1.

        Returns:
            Dict com eventos, issues, e métricas de timing.
        """
        entries = self._parser.parse(log_path)
        return self.analyze_entries(entries, bu, uf=uf, turno_date=turno_date,
                                    municipio=municipio)

    def analyze_entries(
        self,
        entries: list[LogEntry],
        bu: Optional[BoletimUrna] = None,
        uf: str = "",
        turno_date: Optional[str] = None,
        municipio=None,
    ) -> dict:
        """Mesma análise de analyze_log, a partir de entradas já parseadas
        (permite analisar o log em memória, sem arquivo em disco)."""
        events = self._parser.extract_events(entries, turno_date=turno_date)

        issues = []
        timing = self._extract_timing(events)
        issues.extend(self._check_timing(events, uf, municipio))
        issues.extend(self._check_timeline(timing))
        issues.extend(self._check_errors(events))
        issues.extend(self._check_mesario_alerts(events))

        if bu:
            issues.extend(self._check_votos_vs_log(bu, events))

        return {
            "events": events,
            "issues": issues,
            "timing": timing,
        }

    def _check_timing(self, events: dict, uf: str = "", municipio=None) -> list[Issue]:
        """Verifica horários de abertura e encerramento.

        Ajusta os limites para o fuso horário do estado.
        Logs usam hora local. A votação ocorre das 8h às 17h de Brasília.
        """
        issues = []
        limits = _local_limits(uf, municipio)
        offset = get_tz_offset(uf, municipio)
        tz_note = f" (fuso {offset:+d}h)" if offset != 0 else ""

        abertura = events.get("abertura")
        if abertura:
            try:
                ab_min = _parse_time(abertura.hora)

                if ab_min < limits["abertura_min"]:
                    issues.append(
                        Issue(
                            codigo="M01",
                            severidade=IssueSeverity.MEDIUM,
                            descricao=(
                                f"Urna pronta antes do horário: {abertura.hora}{tz_note}"
                            ),
                            uf="", municipio="", zona="", secao="",
                            detalhes={
                                "hora_abertura": abertura.hora,
                                "data": abertura.data,
                                "fuso_offset": offset,
                            },
                            base_legal="Art. 144 do Código Eleitoral: votação das 8h às 17h (BRT)",
                        )
                    )
                elif ab_min > limits["abertura_max"]:
                    issues.append(
                        Issue(
                            codigo="A04",
                            severidade=IssueSeverity.HIGH,
                            descricao=(
                                f"Urna aberta MUITO após o horário: "
                                f"{abertura.hora}{tz_note}"
                            ),
                            uf="", municipio="", zona="", secao="",
                            detalhes={
                                "hora_abertura": abertura.hora,
                                "data": abertura.data,
                                "fuso_offset": offset,
                            },
                            base_legal="Art. 144 do Código Eleitoral: votação das 8h às 17h (BRT)",
                        )
                    )
            except (ValueError, IndexError):
                logger.warning("Hora de abertura malformada no log: %r", abertura.hora)

        encerramento = events.get("encerramento")
        if encerramento:
            try:
                enc_min = _parse_time(encerramento.hora)

                if enc_min < limits["encerramento_min"]:
                    issues.append(
                        Issue(
                            codigo="A05",
                            severidade=IssueSeverity.HIGH,
                            descricao=(
                                f"Votação encerrada ANTES do horário: "
                                f"{encerramento.hora}{tz_note}"
                            ),
                            uf="", municipio="", zona="", secao="",
                            detalhes={
                                "hora_encerramento": encerramento.hora,
                                "data": encerramento.data,
                                "fuso_offset": offset,
                            },
                            base_legal="Art. 153, CE: encerramento às 17h BRT",
                        )
                    )
                elif enc_min > limits["encerramento_max"]:
                    issues.append(
                        Issue(
                            codigo="M02",
                            severidade=IssueSeverity.MEDIUM,
                            descricao=(
                                f"Votação encerrada muito tarde: "
                                f"{encerramento.hora}{tz_note}"
                            ),
                            uf="", municipio="", zona="", secao="",
                            detalhes={
                                "hora_encerramento": encerramento.hora,
                                "data": encerramento.data,
                                "fuso_offset": offset,
                            },
                        )
                    )
            except (ValueError, IndexError):
                logger.warning(
                    "Hora de encerramento malformada no log: %r", encerramento.hora
                )

        # Sem evento de abertura detectado
        if not abertura and events.get("total_entries", 0) > 100:
            issues.append(
                Issue(
                    codigo="M03",
                    severidade=IssueSeverity.MEDIUM,
                    descricao="Evento de abertura não encontrado no log",
                    uf="", municipio="", zona="", secao="",
                    detalhes={"total_entries": events.get("total_entries", 0)},
                )
            )

        # Reinicializações durante votação
        reboots = events.get("reboots", 0)
        if reboots > 0:
            aberturas = events.get("aberturas", [])
            horarios = [f"{a.data} {a.hora}" for a in aberturas]
            sev = IssueSeverity.HIGH if reboots >= 2 else IssueSeverity.MEDIUM
            issues.append(
                Issue(
                    codigo="C06",
                    severidade=sev,
                    descricao=(
                        f"Urna reiniciou {reboots}x durante a votação"
                    ),
                    uf="", municipio="", zona="", secao="",
                    detalhes={
                        "reboots": reboots,
                        "horarios_abertura": horarios,
                        "desligamentos": len(events.get("desligadas", [])),
                    },
                    base_legal="Integridade do processo de votação: reinício pode indicar falha de hardware ou software",
                )
            )

        return issues

    def _check_errors(self, events: dict) -> list[Issue]:
        """Verifica erros registrados no log."""
        issues = []
        erros = events.get("erros", [])

        if len(erros) > 10:
            issues.append(
                Issue(
                    codigo="M04",
                    severidade=IssueSeverity.MEDIUM,
                    descricao=f"Número elevado de erros no log: {len(erros)}",
                    uf="", municipio="", zona="", secao="",
                    detalhes={
                        "total_erros": len(erros),
                        "primeiros_erros": [
                            {"hora": e.hora, "desc": e.descricao[:100]}
                            for e in erros[:5]
                        ],
                    },
                )
            )

        # Substituições de urna
        substituicoes = events.get("substituicoes", [])
        if substituicoes:
            issues.append(
                Issue(
                    codigo="I01",
                    severidade=IssueSeverity.INFO,
                    descricao=f"Eventos de substituição/contingência: {len(substituicoes)}",
                    uf="", municipio="", zona="", secao="",
                    detalhes={
                        "total_substituicoes": len(substituicoes),
                        "eventos": [
                            {"hora": s.hora, "desc": s.descricao[:100]}
                            for s in substituicoes
                        ],
                    },
                )
            )

        # Ajustes de hora
        ajustes = events.get("ajustes_hora", [])
        if ajustes:
            issues.append(
                Issue(
                    codigo="M05",
                    severidade=IssueSeverity.MEDIUM,
                    descricao=f"Ajustes de hora detectados: {len(ajustes)}",
                    uf="", municipio="", zona="", secao="",
                    detalhes={
                        "total_ajustes": len(ajustes),
                        "eventos": [
                            {"hora": a.hora, "desc": a.descricao[:100]}
                            for a in ajustes
                        ],
                    },
                    base_legal="Integridade da linha do tempo de eventos",
                )
            )

        return issues

    def _check_mesario_alerts(self, events: dict) -> list[Issue]:
        """Verifica quantidade de alertas de mesário."""
        issues = []
        alertas = events.get("alertas_mesario", [])

        if len(alertas) > LIMIAR_ALERTAS_MESARIO:
            issues.append(
                Issue(
                    codigo="I02",
                    severidade=IssueSeverity.INFO,
                    descricao=(
                        f"Número elevado de alertas de mesário: {len(alertas)} "
                        f"(limiar: {LIMIAR_ALERTAS_MESARIO})"
                    ),
                    uf="", municipio="", zona="", secao="",
                    detalhes={"total_alertas": len(alertas)},
                )
            )

        return issues

    def _check_votos_vs_log(self, bu: BoletimUrna, events: dict) -> list[Issue]:
        """Compara votos computados no log com totais do BU."""
        issues = []
        votos_log = events.get("votos_computados", 0)

        if votos_log == 0:
            return issues

        # Total de comparecimento do BU (usar o maior valor entre cargos)
        max_comparecimento = 0
        for eleicao in bu.resultados_por_eleicao:
            for resultado in eleicao.resultados:
                if resultado.comparecimento > max_comparecimento:
                    max_comparecimento = resultado.comparecimento

        if max_comparecimento > 0 and votos_log != max_comparecimento:
            diff = abs(votos_log - max_comparecimento)
            if diff > 2:  # Tolerância de 2 por possível contagem dupla no log
                issues.append(
                    Issue(
                        codigo="A03",
                        severidade=IssueSeverity.HIGH,
                        descricao=(
                            f"Divergência entre votos no log ({votos_log}) "
                            f"e comparecimento no BU ({max_comparecimento})"
                        ),
                        uf=str(bu.uf),
                        municipio=str(bu.municipio),
                        zona=str(bu.zona),
                        secao=str(bu.secao),
                        detalhes={
                            "votos_log": votos_log,
                            "comparecimento_bu": max_comparecimento,
                            "diferenca": diff,
                        },
                    )
                )

        return issues

    def _extract_timing(self, events: dict) -> dict:
        """Extrai métricas de timing do log."""
        timing = {
            "hora_abertura": None,
            "hora_encerramento": None,
            "hora_ligada": None,
            "duracao_votacao_min": None,
        }

        abertura = events.get("abertura")
        if abertura:
            timing["hora_abertura"] = f"{abertura.data} {abertura.hora}"

        encerramento = events.get("encerramento")
        if encerramento:
            timing["hora_encerramento"] = f"{encerramento.data} {encerramento.hora}"

        ligada = events.get("ligada")
        if ligada:
            timing["hora_ligada"] = f"{ligada.data} {ligada.hora}"

        # Duração: datetime completo (data + hora + segundos), o que cobre
        # votação que atravessa a meia-noite. Valores negativos indicam linha
        # do tempo inconsistente e são descartados (ver _check_timeline).
        if abertura and encerramento:
            inicio = _entry_datetime(abertura)
            fim = _entry_datetime(encerramento)
            if inicio is None or fim is None:
                logger.warning(
                    "Data/hora malformada no log: abertura=%s %s, encerramento=%s %s",
                    abertura.data, abertura.hora, encerramento.data, encerramento.hora,
                )
            else:
                minutos = (fim - inicio).total_seconds() / 60
                if minutos < 0:
                    timing["duracao_invalida_min"] = round(minutos)
                else:
                    timing["duracao_votacao_min"] = round(minutos)

        return timing

    def _check_timeline(self, timing: dict) -> list[Issue]:
        """Sinaliza encerramento registrado antes da abertura."""
        negativo = timing.get("duracao_invalida_min")
        if negativo is None:
            return []
        return [
            Issue(
                codigo="E03",
                severidade=IssueSeverity.INFO,
                descricao=(
                    "Linha do tempo inconsistente no log: encerramento registrado "
                    f"antes da abertura ({timing.get('hora_abertura')} -> "
                    f"{timing.get('hora_encerramento')})"
                ),
                uf="", municipio="", zona="", secao="",
                detalhes={
                    "hora_abertura": timing.get("hora_abertura"),
                    "hora_encerramento": timing.get("hora_encerramento"),
                    "diferenca_min": negativo,
                },
            )
        ]
