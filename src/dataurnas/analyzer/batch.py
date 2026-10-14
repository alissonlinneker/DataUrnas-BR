"""Análise em lote de todas as seções baixadas."""

import logging
from collections import defaultdict
from pathlib import Path
from typing import Optional

from ..config import ELECTIONS, RAW_DIR
from ..models import BoletimUrna, Issue, IssueSeverity, TipoVoto
from ..parsers.bu import BUParser
from ..parsers.log import LogParser
from ..parsers.signature import SignatureParser
from .integrity import ConsistencyAnalyzer, IntegrityAnalyzer
from .log_analyzer import LogAnalyzer
from .statistical import StatisticalAnalyzer, VoteAggregator

logger = logging.getLogger(__name__)

# Datas de votação por pleito (DD/MM/YYYY), usadas para filtrar logs do T2,
# que acumulam eventos do T1.
_PLEITO_DATAS = {
    "406": "02/10/2022",
    "407": "30/10/2022",
    "452": "06/10/2024",
    "453": "27/10/2024",
    "3220": "04/10/2026",
}


def _pleito_turnos() -> dict[str, int]:
    """Mapa pleito -> turno a partir de config.ELECTIONS."""
    mapping: dict[str, int] = {}
    for info in ELECTIONS.values():
        if info.get("pleito_1t"):
            mapping[str(info["pleito_1t"])] = 1
        if info.get("pleito_2t"):
            mapping[str(info["pleito_2t"])] = 2
    return mapping


def _soma_tipo(votos, tipo: TipoVoto) -> int:
    return sum(v.quantidade for v in votos if v.tipo_voto == tipo)


def _tag_issues(issues: list[Issue], result: dict) -> list[Issue]:
    """Preenche a localização da seção nas issues."""
    for issue in issues:
        issue.uf = result["uf"]
        issue.municipio = result["municipio"]
        issue.zona = result["zona"]
        issue.secao = result["secao"]
    return issues


class BatchAnalyzer:
    """Executa análise em lote em todas as seções baixadas."""

    def __init__(self, raw_dir: Path = RAW_DIR, verify_hashes: bool = False):
        self._raw_dir = Path(raw_dir)
        self._verify_hashes = verify_hashes
        self._bu_parser = BUParser()
        self._log_parser = LogParser()
        self._sig_parser = SignatureParser()
        self._consistency = ConsistencyAnalyzer()
        self._integrity = IntegrityAnalyzer()
        self._log_analyzer = LogAnalyzer()
        self._statistical = StatisticalAnalyzer()

    @property
    def verify_hashes(self) -> bool:
        """Se a verificação SHA-512 dos arquivos é executada em cada seção."""
        return self._verify_hashes

    def find_sections(self, uf: Optional[str] = None) -> list[Path]:
        """Encontra todas as seções baixadas (diretórios únicos, ordenados)."""
        sections = {bu_file.parent for bu_file in self.find_bu_files(uf)}
        return sorted(sections)

    def find_bu_files(self, uf: Optional[str] = None) -> list[Path]:
        """Encontra todos os arquivos BU individuais (um por turno/secao)."""
        base = self._raw_dir
        if uf:
            base = base / uf.lower()

        bu_files = sorted(base.rglob("*.bu"))
        bu_files.extend(sorted(base.rglob("*-bu.dat")))
        return bu_files

    @staticmethod
    def extract_pleito_from_filename(bu_path: Path) -> str:
        """Extrai o código do pleito do nome do arquivo BU.

        Ex: 'o00406-9701200170097.bu' -> '406'
            'o00407-9701200170097.bu' -> '407'
        """
        name = bu_path.name
        if name.startswith("o00"):
            # Formato v1: o00{pleito}-{resto}.bu
            return name[3:].split("-")[0]
        return ""

    @staticmethod
    def pleito_to_turno(pleito: str) -> int:
        """Converte código de pleito para número do turno.

        Pleito vazio (nome de arquivo sem prefixo) assume 1º turno. Pleito
        desconhecido também assume 1, mas registra aviso: o mapeamento deve
        ser adicionado em config.ELECTIONS.
        """
        if not pleito:
            return 1
        turno = _pleito_turnos().get(str(pleito))
        if turno is None:
            logger.warning("Pleito %s desconhecido; assumindo 1º turno", pleito)
            return 1
        return turno

    @staticmethod
    def pleito_to_date(pleito: str) -> str:
        """Converte código de pleito para data do turno (DD/MM/YYYY).

        Necessário para filtrar logs do T2, que acumulam eventos do T1.
        """
        return _PLEITO_DATAS.get(str(pleito), "")

    def locate(self, section_dir: Path) -> dict:
        """Extrai uf/municipio/zona/secao do caminho da seção.

        Estrutura: {raw_dir}/{uf}/{mun}/{zona}/{secao}/
        """
        section_dir = Path(section_dir)
        try:
            parts = section_dir.resolve().relative_to(self._raw_dir.resolve()).parts
        except ValueError:
            parts = ()
        if len(parts) < 4:
            # Fora de raw_dir: usar os 4 últimos componentes
            parts = section_dir.parts[-4:]
        parts = ("",) * (4 - len(parts)) + tuple(parts)
        uf, municipio, zona, secao = parts[-4:]
        return {"uf": uf, "municipio": municipio, "zona": zona, "secao": secao}

    def secao_id_for(self, bu_file: Path) -> str:
        """Calcula o secao_id ({turno}T/uf/mun/zona/secao) sem parsing ASN.1."""
        loc = self.locate(Path(bu_file).parent)
        if not all(loc.values()):
            return ""
        turno = self.pleito_to_turno(self.extract_pleito_from_filename(Path(bu_file)))
        return f"{turno}T/{loc['uf']}/{loc['municipio']}/{loc['zona']}/{loc['secao']}"

    def analyze_all(self, uf: Optional[str] = None) -> dict:
        """Analisa todas as seções (um BU por turno) e gera relatório completo."""
        bu_files = self.find_bu_files(uf)
        logger.info("Encontrados %d BUs para análise", len(bu_files))
        aggregator = VoteAggregator()

        results = {
            "total_secoes": len(bu_files),
            "secoes_ok": 0,
            "secoes_com_issues": 0,
            "total_issues": 0,
            "issues_por_severidade": defaultdict(int),
            "issues_por_codigo": defaultdict(int),
            "issues_por_uf": defaultdict(int),
            "modelos_urna": defaultdict(int),
            "tipos_urna": defaultdict(int),
            "versoes_sw": defaultdict(int),
            "eleitores_por_uf": defaultdict(
                lambda: {"aptos": 0, "comparecimento": 0, "secoes": 0}
            ),
            "biometria_por_uf": defaultdict(
                lambda: {"lib_codigo": 0, "comp_biometrico": 0}
            ),
            "timing": {
                "aberturas": [],
                "encerramentos": [],
                "duracoes_min": [],
            },
            "secoes_analisadas": [],
            "issues": [],
        }

        for i, bu_file in enumerate(bu_files):
            if (i + 1) % 50 == 0:
                logger.info("Progresso: %d/%d seções", i + 1, len(bu_files))

            section_result = self.analyze_section(bu_file.parent, bu_file=bu_file)
            self._aggregate(results, section_result)
            if section_result["bu_obj"] is not None:
                aggregator.add_bu(
                    section_result["bu_obj"],
                    uf=section_result["uf"],
                    turno=section_result["turno"],
                    municipio=section_result["municipio"],
                )

        results["abstencao_por_uf"] = self._calc_abstencao(results)
        results["biometria_por_uf_pct"] = self._calc_biometria_pct(results)
        results["votacao"] = aggregator.get_results()

        # Converter defaultdicts para dicts
        for key in ["issues_por_severidade", "issues_por_codigo", "issues_por_uf",
                     "modelos_urna", "tipos_urna", "versoes_sw"]:
            results[key] = dict(results[key])
        results["eleitores_por_uf"] = {k: dict(v) for k, v in results["eleitores_por_uf"].items()}
        results["biometria_por_uf"] = {k: dict(v) for k, v in results["biometria_por_uf"].items()}

        return results

    def analyze_section(self, section_dir: Path, bu_file: Optional[Path] = None) -> dict:
        """Analisa uma seção individual com todos os analyzers.

        Args:
            section_dir: Diretório da seção.
            bu_file: Arquivo BU específico (define o turno). Se None, usa o
                primeiro encontrado.
        """
        section_dir = Path(section_dir)
        loc = self.locate(section_dir)

        if bu_file is None:
            candidatos = sorted(section_dir.glob("*.bu")) + sorted(section_dir.glob("*-bu.dat"))
            bu_file = candidatos[0] if candidatos else None

        turno = 1
        turno_date = ""
        file_prefix = None
        if bu_file is not None:
            pleito = self.extract_pleito_from_filename(bu_file)
            turno = self.pleito_to_turno(pleito)
            turno_date = self.pleito_to_date(pleito)
            # Prefixo para achar os arquivos do mesmo turno (log, vscmr, etc.)
            file_prefix = bu_file.name[: -len("-bu.dat")] if bu_file.name.endswith(
                "-bu.dat") else bu_file.stem

        result = {
            "dir": str(section_dir),
            **loc,
            "turno": turno,
            "bu": None,
            "bu_obj": None,
            "modelo": None,
            "tipo_urna": None,
            "versao_sw": None,
            "issues": [],
            "log_timing": None,
            "log_events": None,
        }

        bu = self._parse_bu(bu_file, result) if bu_file is not None else None
        result["modelo"] = self._modelo_assinatura(section_dir, file_prefix)
        self._analyze_log(section_dir, file_prefix, bu, turno_date, result)

        if self._verify_hashes:
            result["issues"].extend(
                _tag_issues(self._integrity.verify_section_hashes(section_dir), result)
            )

        return result

    def analyze_section_bytes(
        self,
        loc: dict,
        bu_raw: Optional[bytes],
        log_raw: Optional[bytes] = None,
        turno: int = 1,
        turno_date: str = "",
        modelo: Optional[str] = None,
        nome_bu: str = "bu.dat",
        nome_log: str = "log.jez",
    ) -> dict:
        """Mesma análise de analyze_section, com BU e log em memória.

        Usada na coleta de 2026, que não grava arquivos brutos em disco.
        loc = {"uf", "municipio", "zona", "secao"}; modelo no formato do log
        ("2020"), já que o .vsc é lido pelo chamador.
        """
        result = {
            "dir": None, **loc, "turno": turno, "bu": None, "bu_obj": None,
            "modelo": modelo, "tipo_urna": None, "versao_sw": None, "issues": [],
            "log_timing": None, "log_events": None,
        }
        bu = None
        if bu_raw is not None:
            bu = self._parse_bu_com(lambda: self._bu_parser.parse_bytes(bu_raw), nome_bu, result)
        if log_raw is not None:
            self._analyze_log_com(
                lambda: self._log_analyzer.analyze_entries(
                    self._log_parser.parse_bytes(log_raw, nome_log), bu,
                    uf=loc["uf"], turno_date=turno_date or None,
                    municipio=loc["municipio"],
                ),
                nome_log, result,
            )
        return result

    # Compatibilidade: scripts antigos chamam o método privado
    _analyze_section = analyze_section

    def _parse_bu(self, bu_file: Path, result: dict) -> Optional[BoletimUrna]:
        """Parseia o BU e preenche result; falha vira issue E02."""
        if not bu_file.exists():
            return None
        return self._parse_bu_com(lambda: self._bu_parser.parse(bu_file), bu_file.name, result)

    def _parse_bu_com(self, parse, nome: str, result: dict) -> Optional[BoletimUrna]:
        """Executa parse() do BU, preenche result e roda as análises do BU."""
        try:
            bu = parse()
        except Exception as e:
            logger.error("Erro ao parsear BU %s: %s", nome, e)
            result["issues"].append(
                _tag_issues([
                    Issue(
                        codigo="E02",
                        severidade=IssueSeverity.MEDIUM,
                        descricao=(
                            "BU não pôde ser decodificado; seção excluída dos "
                            f"totais ({type(e).__name__})"
                        ),
                        uf="", municipio="", zona="", secao="",
                        detalhes={"arquivo": nome, "erro": str(e)[:300]},
                    )
                ], result)[0]
            )
            return None

        result["bu_obj"] = bu
        result["tipo_urna"] = bu.tipo_urna
        result["versao_sw"] = bu.versao_votacao
        result["bu"] = {
            "municipio": bu.municipio,
            "zona": bu.zona,
            "secao": bu.secao,
            "tipo_urna": bu.tipo_urna,
            "versao": bu.versao_votacao,
            "emissao": bu.data_hora_emissao,
            "lib_codigo": bu.qtd_eleitores_lib_codigo,
            "comp_biometrico": bu.qtd_eleitores_comp_biometrico,
            "eleicoes": [],
        }
        for eleicao in bu.resultados_por_eleicao:
            el_info = {"id": eleicao.id_eleicao, "aptos": eleicao.eleitores_aptos, "cargos": []}
            for cargo in eleicao.resultados:
                nominais = _soma_tipo(cargo.votos, TipoVoto.NOMINAL)
                brancos = _soma_tipo(cargo.votos, TipoVoto.BRANCO)
                nulos = _soma_tipo(cargo.votos, TipoVoto.NULO)
                legenda = _soma_tipo(cargo.votos, TipoVoto.LEGENDA)
                el_info["cargos"].append({
                    "cargo": cargo.nome_cargo,
                    "codigo": cargo.codigo_cargo,
                    "comparecimento": cargo.comparecimento,
                    "total_votos": nominais + brancos + nulos + legenda,
                    "nominais": nominais,
                    "brancos": brancos,
                    "nulos": nulos,
                    "legenda": legenda,
                })
            result["bu"]["eleicoes"].append(el_info)

        result["issues"].extend(_tag_issues(self._consistency.full_analysis(bu), result))
        result["issues"].extend(_tag_issues(self._statistical.analyze_bu(bu), result))
        return bu

    def _modelo_assinatura(self, section_dir: Path, file_prefix: Optional[str]) -> Optional[str]:
        """Modelo da urna a partir do arquivo de assinatura (.vscmr / -vota.vsc)."""
        if file_prefix:
            sig_files = sorted(section_dir.glob(f"{file_prefix}.vscmr")) + \
                sorted(section_dir.glob(f"{file_prefix}-vota.vsc"))
        else:
            sig_files = sorted(section_dir.glob("*.vscmr")) + \
                sorted(section_dir.glob("*-vota.vsc"))
        if not sig_files:
            return None
        modelo = self._sig_parser.get_model(sig_files[0])
        if modelo and modelo.upper().startswith("UE"):
            # Normalizar: "UE2010" -> "2010" (mesmo formato do modelo vindo do log)
            return modelo[2:]
        return modelo

    def _analyze_log(
        self,
        section_dir: Path,
        file_prefix: Optional[str],
        bu: Optional[BoletimUrna],
        turno_date: str,
        result: dict,
    ) -> None:
        """Analisa o log da urna e preenche result."""
        if file_prefix:
            log_files = sorted(section_dir.glob(f"{file_prefix}.logjez")) + \
                sorted(section_dir.glob(f"{file_prefix}-log.jez"))
        else:
            log_files = sorted(section_dir.glob("*.logjez")) + \
                sorted(section_dir.glob("*-log.jez"))
        if not log_files:
            return
        self._analyze_log_com(
            lambda: self._log_analyzer.analyze_log(
                log_files[0], bu, uf=result["uf"],
                turno_date=turno_date or None,
                municipio=result["municipio"],
            ),
            log_files[0].name, result,
        )

    def _analyze_log_com(self, analisar, nome: str, result: dict) -> None:
        """Executa analisar() (análise do log) e preenche result."""
        try:
            log_result = analisar()
        except Exception as e:
            logger.warning("Erro ao analisar log %s: %s", nome, e)
            return

        events = log_result["events"]
        result["log_events"] = {
            "modelo": events.get("modelo"),
            "votos_computados": events.get("votos_computados", 0),
            "erros": len(events.get("erros", [])),
            "alertas_mesario": len(events.get("alertas_mesario", [])),
            "substituicoes": len(events.get("substituicoes", [])),
            "reboots": events.get("reboots", 0),
            "severidades": events.get("severidades", {}),
        }
        result["log_timing"] = log_result["timing"]

        # Modelo do log como fallback
        if not result["modelo"] and events.get("modelo"):
            result["modelo"] = events["modelo"]

        result["issues"].extend(_tag_issues(log_result["issues"], result))

    def _aggregate(self, results: dict, section_result: dict):
        """Agrega resultado de uma seção no resumo geral."""
        uf = section_result["uf"]
        issues = section_result["issues"]

        if issues:
            results["secoes_com_issues"] += 1
            for issue in issues:
                results["total_issues"] += 1
                results["issues_por_severidade"][issue.severidade.value] += 1
                results["issues_por_codigo"][issue.codigo] += 1
                results["issues_por_uf"][uf] += 1
                results["issues"].append({
                    "codigo": issue.codigo,
                    "severidade": issue.severidade.value,
                    "descricao": issue.descricao,
                    "uf": uf,
                    "municipio": section_result["municipio"],
                    "zona": section_result["zona"],
                    "secao": section_result["secao"],
                    "detalhes": issue.detalhes,
                    "base_legal": issue.base_legal,
                })
        else:
            results["secoes_ok"] += 1

        # Modelo de urna (agora vem do .vscmr ou log, não do BU)
        modelo = section_result.get("modelo")
        if modelo:
            results["modelos_urna"][str(modelo)] += 1

        # Tipo de urna (secao/reservaSecao/contingencia)
        tipo_urna = section_result.get("tipo_urna")
        if tipo_urna:
            results["tipos_urna"][str(tipo_urna)] += 1

        # Versão de SW
        versao = section_result.get("versao_sw")
        if versao:
            results["versoes_sw"][str(versao)] += 1

        # Votos e eleitores (corrigido: sem double-counting)
        bu_info = section_result.get("bu")
        if bu_info:
            # Aptos: pegar da primeira eleição (e o mesmo caderno)
            eleicoes = bu_info.get("eleicoes", [])
            if eleicoes:
                # Usar aptos da primeira eleição (mesmo caderno para todos os cargos)
                results["eleitores_por_uf"][uf]["aptos"] += eleicoes[0]["aptos"]
                results["eleitores_por_uf"][uf]["secoes"] += 1

                # Comparecimento: usar o maior valor de comparecimento
                # entre todos os cargos (deve ser igual para todos)
                max_comp = 0
                for eleicao in eleicoes:
                    for cargo in eleicao.get("cargos", []):
                        comp = cargo.get("comparecimento", 0)
                        if comp > max_comp:
                            max_comp = comp
                results["eleitores_por_uf"][uf]["comparecimento"] += max_comp

            # Biometria
            results["biometria_por_uf"][uf]["lib_codigo"] += bu_info.get("lib_codigo", 0)
            results["biometria_por_uf"][uf]["comp_biometrico"] += bu_info.get("comp_biometrico", 0)

        # Timing
        timing = section_result.get("log_timing")
        if timing:
            if timing.get("hora_abertura"):
                results["timing"]["aberturas"].append(timing["hora_abertura"])
            if timing.get("hora_encerramento"):
                results["timing"]["encerramentos"].append(timing["hora_encerramento"])
            if timing.get("duracao_votacao_min") is not None:
                results["timing"]["duracoes_min"].append(timing["duracao_votacao_min"])

        results["secoes_analisadas"].append({
            "uf": uf,
            "municipio": section_result["municipio"],
            "zona": section_result["zona"],
            "secao": section_result["secao"],
            "modelo": modelo,
            "tipo_urna": tipo_urna,
            "ok": len(issues) == 0,
            "n_issues": len(issues),
        })

    def _calc_abstencao(self, results: dict) -> dict:
        """Calcula taxa de abstenção por UF."""
        abstencao = {}
        for uf, dados in results["eleitores_por_uf"].items():
            if dados["aptos"] > 0:
                abstencao[uf] = round(
                    (1 - dados["comparecimento"] / dados["aptos"]) * 100, 2
                )
        return abstencao

    def _calc_biometria_pct(self, results: dict) -> dict:
        """Calcula percentual de liberação por código (sem biometria) por UF."""
        bio_pct = {}
        for uf, dados in results["biometria_por_uf"].items():
            total = dados["lib_codigo"] + dados["comp_biometrico"]
            if total > 0:
                bio_pct[uf] = {
                    "pct_biometria": round(
                        (dados["comp_biometrico"] / total) * 100, 2
                    ),
                    "pct_codigo": round(
                        (dados["lib_codigo"] / total) * 100, 2
                    ),
                }
        return bio_pct

    def print_report(self, results: dict):
        """Imprime relatório completo no terminal."""
        print("=" * 70)
        print("RELATÓRIO DE AUDITORIA: DADOS DE URNA")
        print("=" * 70)
        print()

        # Resumo geral
        print(f"Total de seções analisadas: {results['total_secoes']}")
        print(f"Seções sem inconsistências: {results['secoes_ok']}")
        print(f"Seções com inconsistências: {results['secoes_com_issues']}")
        print(f"Total de inconsistências: {results['total_issues']}")
        print()

        # Inconsistências por severidade
        if results.get("issues_por_severidade"):
            print("--- Inconsistências por severidade ---")
            order = {"critica": 0, "alta": 1, "media": 2, "informativa": 3}
            for sev, count in sorted(
                results["issues_por_severidade"].items(),
                key=lambda x: order.get(x[0], 99),
            ):
                print(f"  {sev.upper()}: {count}")
            print()

        # Inconsistências por código
        if results.get("issues_por_codigo"):
            print("--- Inconsistências por código ---")
            for cod, count in sorted(results["issues_por_codigo"].items()):
                print(f"  {cod}: {count}")
            print()

        # Modelos de urna
        if results.get("modelos_urna"):
            print("--- Modelos de urna ---")
            total_urnas = sum(results["modelos_urna"].values())
            for modelo, count in sorted(results["modelos_urna"].items()):
                pct = (count / total_urnas * 100) if total_urnas > 0 else 0
                print(f"  UE{modelo}: {count} urnas ({pct:.1f}%)")
            print()

        # Versões de software
        if results.get("versoes_sw"):
            print("--- Versões de software ---")
            for versao, count in sorted(results["versoes_sw"].items()):
                print(f"  {versao}: {count} urnas")
            print()

        # Eleitores por UF
        if results.get("eleitores_por_uf"):
            print("--- Eleitores por UF ---")
            total_aptos = 0
            total_comp = 0
            for uf in sorted(results["eleitores_por_uf"]):
                dados = results["eleitores_por_uf"][uf]
                aptos = dados["aptos"]
                comp = dados["comparecimento"]
                secoes = dados.get("secoes", 0)
                abstencao = results.get("abstencao_por_uf", {}).get(uf, 0)
                total_aptos += aptos
                total_comp += comp
                print(
                    f"  {uf.upper()}: {aptos:>6} aptos, {comp:>6} comp. "
                    f"(abstenção {abstencao:.1f}%) [{secoes} seções]"
                )
            if total_aptos > 0:
                total_abs = (1 - total_comp / total_aptos) * 100
                print(f"  TOTAL: {total_aptos:>6} aptos, {total_comp:>6} comp. "
                      f"(abstenção {total_abs:.1f}%)")
            print()

        # Biometria por UF
        bio_pct = results.get("biometria_por_uf_pct", {})
        if bio_pct:
            print("--- Biometria por UF ---")
            for uf in sorted(bio_pct):
                dados = bio_pct[uf]
                print(
                    f"  {uf.upper()}: biometria {dados['pct_biometria']:.1f}%, "
                    f"código {dados['pct_codigo']:.1f}%"
                )
            print()

        # Timing
        timing = results.get("timing", {})
        duracoes = timing.get("duracoes_min", [])
        if duracoes:
            avg_dur = sum(duracoes) / len(duracoes)
            min_dur = min(duracoes)
            max_dur = max(duracoes)
            print("--- Duração da votação ---")
            print(f"  Duração média: {avg_dur:.0f} min ({avg_dur/60:.1f}h)")
            print(f"  Menor duração: {min_dur} min ({min_dur/60:.1f}h)")
            print(f"  Maior duração: {max_dur} min ({max_dur/60:.1f}h)")
            print()

        # Votos por candidato (Presidente), separados por turno
        votacao = results.get("votacao", {})
        for turno, por_escopo in sorted(votacao.get("votos_por_candidato", {}).items()):
            cands = por_escopo.get("BR", {}).get("Presidente")
            if not cands:
                continue
            print(f"--- Votação para Presidente ({turno}º turno) ---")
            totais = votacao.get("totais_por_cargo", {}).get(turno, {}).get("Presidente", {})
            if totais:
                print(
                    f"  Total: {totais.get('total', 0)} votos "
                    f"(nominais: {totais.get('nominais', 0)}, "
                    f"brancos: {totais.get('brancos', 0)}, "
                    f"nulos: {totais.get('nulos', 0)})"
                )
            total_nom = totais.get("nominais", 0) or 1
            for cand in cands[:10]:
                pct = cand["votos"] / total_nom * 100
                print(
                    f"  Candidato {cand['codigo']} "
                    f"(partido {cand['partido']}): "
                    f"{cand['votos']} votos ({pct:.1f}%) "
                    f"[{cand['secoes']} seções]"
                )
            print()

        # Detalhes das inconsistências
        issues = results.get("issues", [])
        if issues:
            # Agrupar por severidade
            criticas = [i for i in issues if i.get("severidade") == "critica"]
            altas = [i for i in issues if i.get("severidade") == "alta"]
            medias = [i for i in issues if i.get("severidade") == "media"]
            infos = [i for i in issues if i.get("severidade") == "informativa"]

            if criticas:
                print("--- INCONSISTÊNCIAS CRÍTICAS ---")
                for issue in criticas:
                    self._print_issue(issue)
                print()

            if altas:
                print("--- INCONSISTÊNCIAS ALTAS ---")
                for issue in altas:
                    self._print_issue(issue)
                print()

            if medias:
                print("--- INCONSISTÊNCIAS MÉDIAS ---")
                for issue in medias[:20]:
                    self._print_issue(issue)
                if len(medias) > 20:
                    print(f"  ... e mais {len(medias) - 20} inconsistências médias")
                print()

            if infos:
                print("--- INFORMATIVAS ---")
                for issue in infos[:20]:
                    self._print_issue(issue)
                if len(infos) > 20:
                    print(f"  ... e mais {len(infos) - 20} informativas")
                print()

        print("=" * 70)

    def _print_issue(self, issue: dict):
        """Imprime uma issue formatada."""
        loc = (
            f"{issue.get('uf', '').upper()}/"
            f"{issue.get('municipio', '')}/"
            f"{issue.get('zona', '')}/"
            f"{issue.get('secao', '')}"
        )
        print(f"  [{issue['codigo']}] ({loc}): {issue['descricao']}")
        if issue.get("base_legal"):
            print(f"         Base legal: {issue['base_legal']}")
