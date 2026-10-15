"""Parser de logs da urna eletrônica (.logjez / .jez)."""

import logging
import re
from pathlib import Path
from typing import Optional

from ..models import LogEntry

logger = logging.getLogger(__name__)

# Formato de cada linha do log (separado por TAB):
# DD/MM/YYYY HH:MM:SS\tSEVERIDADE\tID_URNA\tAPLICATIVO\tDESCRICAO\tMAC
_LOG_LINE_PATTERN = re.compile(
    r"^(\d{2}/\d{2}/\d{4}) (\d{2}:\d{2}:\d{2})\t(\w+)\t(\d+)\t(\w+)\t(.+?)\t([A-Fa-f0-9]+)\s*$"
)

# Padrões de eventos relevantes
PATTERN_MODELO_URNA = re.compile(r"(?:Modelo de [Uu]rna|Modelo UE|UE)[\s:]*(\d{4})")
PATTERN_MODELO_VST = re.compile(r"avusrlibue(\d{4})\.vst")
PATTERN_ABERTURA = re.compile(r"Urna pronta para receber votos")
PATTERN_ENCERRAMENTO = re.compile(r"In[ií]cio do Encerramento")
PATTERN_ENCERRAMENTO_CONFIRMADO = re.compile(r"Procedimento de encerramento confirmado")
PATTERN_ERRO = re.compile(r"(?:ERRO|ERROR|FALHA|FAIL)", re.IGNORECASE)
PATTERN_SUBSTITUICAO = re.compile(r"(?:substitui|contingencia|conting[eê]ncia)", re.IGNORECASE)
PATTERN_AJUSTE_HORA = re.compile(r"(?:ajust|acert).*(?:hora|relogio|rel[oó]gio)", re.IGNORECASE)
PATTERN_MESARIO_ALERTA = re.compile(r"Mes[aá]rio indagado")
PATTERN_VOTO_COMPUTADO = re.compile(r"O voto do eleitor foi computado")
PATTERN_LIGADA = re.compile(r"Urna ligada em (.+)")
PATTERN_DESLIGADA = re.compile(r"Urna desligada")
PATTERN_CARGA = re.compile(r"Modo de carga da UE")
PATTERN_REBOOT = re.compile(r"In[ií]cio das opera[çc][oõ]es do logd")

# Limite de segurança para o log descompactado (logs reais têm poucos MB)
MAX_LOG_BYTES = 256 * 1024 * 1024


# Nome do .jez aninhado: <8 dígitos da urna><ddmmaaaahhmmss><sufixo>.jez
_NOME_ANINHADO = re.compile(r"^\d{8}(\d{2})(\d{2})(\d{4})(\d{2})(\d{2})(\d{2})")


def _chave_aninhado(nome: str) -> tuple:
    """Ordem dos arquivos do pacote: data e hora embutida no nome (aaaammddhhmmss),
    com o nome como desempate; nomes sem data (logd.dat) vão depois."""
    m = _NOME_ANINHADO.match(Path(nome).name)
    if not m:
        return (1, "", nome)
    d, mes, a, h, mi, s = m.groups()
    return (0, a + mes + d + h + mi + s, nome)


def _sem_linhas_repetidas(textos: list[str]) -> list[str]:
    """União dos logs por linha completa, na ordem dos arquivos.

    O pacote às vezes traz o mesmo log mais de uma vez: o log corrompido é
    guardado em dupla (<urna><data>01MI.jez e 02ME.jez, cópia da memória
    interna e da mídia externa, às vezes com a MI truncada) e cada urna de
    contingência que lê a mesma mídia externa grava a sua cópia. Uma linha
    só é duplicata se for idêntica byte a byte (data, hora, urna, aplicativo,
    evento e código de verificação), então eventos iguais de urnas diferentes
    continuam contando. A união é de multiconjuntos: uma linha que aparece k
    vezes num arquivo e j vezes num anterior entra max(k, j) vezes, o que
    preserva repetições legítimas dentro do mesmo log.
    """
    vistos: dict[str, int] = {}
    saida: list[str] = []
    for texto in textos:
        locais: dict[str, int] = {}
        linhas: list[str] = []
        for ln in texto.splitlines():
            if ln.strip():
                locais[ln] = locais.get(ln, 0) + 1
                if locais[ln] <= vistos.get(ln, 0):
                    continue
            linhas.append(ln)
        for ln, n in locais.items():
            if n > vistos.get(ln, 0):
                vistos[ln] = n
        saida.append("\n".join(linhas))
    return saida


def textos_zip(raw: bytes, nivel: int = 0) -> Optional[list[str]]:
    """Textos dos logs de um -log.jez em ZIP (2026), logs aninhados primeiro.

    Na troca de urna (contingência) o pacote traz o logd.dat da urna que
    encerrou a votação e, como .jez aninhado (outro ZIP com logd.dat), o log
    da urna substituída, nomeado <urna><ddmmaaaahhmmss>-NN.jez (ou ...01MI.jez
    e ...02ME.jez, cópias de log corrompido). Os aninhados vêm antes, na
    ordem da data e hora do nome (o nome começa pelo número da urna, então a
    ordem alfabética misturaria urnas), e o logd.dat do pacote por último,
    para que as entradas fiquem na ordem em que as urnas foram usadas. Linhas
    repetidas entre arquivos (o mesmo log copiado mais de uma vez) entram uma
    vez só (ver _sem_linhas_repetidas). Devolve None se o pacote estiver
    vazio ou passar de MAX_LOG_BYTES descompactado.
    """
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        if not infos or sum(i.file_size for i in infos) > MAX_LOG_BYTES:
            return None
        aninhados: list[str] = []
        proprios: list[str] = []
        for i in sorted(infos, key=lambda i: _chave_aninhado(i.filename)):
            dados = z.read(i)
            if dados[:4] == b"PK\x03\x04":
                if nivel < 2:
                    aninhados.extend(textos_zip(dados, nivel + 1) or [])
            else:
                proprios.append(dados.decode("latin-1", errors="replace"))
        textos = aninhados + proprios
        return _sem_linhas_repetidas(textos) if nivel == 0 else textos


class LogParser:
    """Parser de logs da urna eletrônica."""

    def parse(self, file_path: Path) -> list[LogEntry]:
        """Parseia um arquivo de log da urna.

        O arquivo .logjez/.jez e compactado em 7-zip.
        Dentro dele existe um arquivo logd.dat em texto puro.
        """
        file_path = Path(file_path)
        return self._parse_text(self._extract_text(file_path), str(file_path))

    def parse_bytes(self, raw: bytes, origem: str = "<memória>") -> list[LogEntry]:
        """Parseia um log .logjez/.jez já em memória (sem gravar em disco)."""
        import io

        return self._parse_text(self._extract_text(io.BytesIO(raw), origem), origem)

    def _parse_text(self, text: Optional[str], file_path: str) -> list[LogEntry]:
        if not text:
            return []

        entries = []
        ignoradas = 0
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            entry = self._parse_line(line)
            if entry:
                entries.append(entry)
            else:
                ignoradas += 1

        if ignoradas:
            logger.debug(
                "%s: %d linha(s) fora do formato esperado ignoradas", file_path, ignoradas
            )
        return entries

    def _extract_zip(self, file_path, origem: Optional[str] = None):
        """Logs de 2026 (-log.jez) vêm em ZIP, não em 7-zip.

        Retorna o texto dos logs do ZIP (ver textos_zip: na troca de urna, o
        log da urna substituída vem antes do logd.dat), None em erro, ou False
        quando o conteúdo não é ZIP (para tentar o 7-zip).
        """
        import zipfile

        try:
            if hasattr(file_path, "seek"):
                file_path.seek(0)
                magica = file_path.read(4)
                file_path.seek(0)
            else:
                with open(file_path, "rb") as fh:
                    magica = fh.read(4)
        except OSError:
            return False
        if magica != b"PK\x03\x04":
            return False
        try:
            if hasattr(file_path, "read"):
                raw = file_path.read()
            else:
                with open(file_path, "rb") as fh:
                    raw = fh.read()
            textos = textos_zip(raw)
            if textos is None:
                logger.error("Log %s vazio ou acima do limite descompactado",
                             origem or file_path)
                return None
            return "\n".join(textos)
        except (zipfile.BadZipFile, OSError, RuntimeError) as e:
            logger.error("Erro ao extrair log (zip) de %s: %s", origem or file_path, e)
            return None

    def _extract_text(self, file_path, origem: Optional[str] = None) -> Optional[str]:
        """Extrai em memória o texto do arquivo 7-zip.

        Le o primeiro arquivo do pacote (geralmente logd.dat), sem gravar
        nada em disco. Pacotes acima de MAX_LOG_BYTES (descompactados) são
        recusados: o conteúdo vem de fonte externa e não pode esgotar a
        memória.
        """
        texto_zip = self._extract_zip(file_path, origem)
        if texto_zip is not False:
            return texto_zip
        try:
            import py7zr
            from py7zr.io import BytesIOFactory
        except ImportError:
            logger.error("py7zr não instalado. Execute: pip install py7zr")
            return None

        try:
            with py7zr.SevenZipFile(file_path, mode="r") as archive:
                infos = [i for i in archive.list() if not i.is_directory]
                if not infos:
                    return None
                total = sum(i.uncompressed or 0 for i in infos)
                if total > MAX_LOG_BYTES:
                    logger.error(
                        "Log %s excede o limite (%d bytes descompactados)",
                        origem or file_path, total,
                    )
                    return None
                alvo = sorted(i.filename for i in infos)[0]
                factory = BytesIOFactory(MAX_LOG_BYTES)
                archive.extract(targets=[alvo], factory=factory)
            buf = factory.get(alvo)
            buf.seek(0)
            return buf.read().decode("latin-1", errors="replace")
        except Exception as e:
            logger.error("Erro ao extrair log de %s: %s", origem or file_path, e)
            return None

    def _parse_line(self, line: str) -> Optional[LogEntry]:
        """Parseia uma linha do log."""
        match = _LOG_LINE_PATTERN.match(line)
        if match:
            return LogEntry(
                data=match.group(1),
                hora=match.group(2),
                severidade=match.group(3),
                id_urna=match.group(4),
                aplicativo=match.group(5),
                descricao=match.group(6),
                mac=match.group(7),
            )
        # Linhas que não seguem o padrão são ignoradas silenciosamente
        return None

    def extract_model(self, entries: list[LogEntry]) -> Optional[str]:
        """Extrai o modelo da urna dos eventos de log."""
        for entry in entries:
            match = PATTERN_MODELO_URNA.search(entry.descricao)
            if match:
                return match.group(1)
        return None

    def extract_events(
        self, entries: list[LogEntry], turno_date: Optional[str] = None
    ) -> dict:
        """Extrai eventos relevantes do log.

        Critérios (assimetria intencional):
            - abertura: PRIMEIRA ocorrência de "Urna pronta para receber votos"
              no dia; as demais contam como reinicializações.
            - encerramento: ÚLTIMA ocorrência de "Início do Encerramento", que é
              o encerramento efetivo quando o procedimento é repetido.

        Args:
            entries: Lista de entradas do log.
            turno_date: Data do turno (DD/MM/YYYY) para filtrar entradas.
                Se fornecido, apenas entradas dessa data são consideradas.
                Necessário para T2, pois o .logjez acumula eventos do T1.
        """
        # Filtrar por data do turno (corrige T2 que acumula eventos do T1)
        if turno_date:
            entries = [e for e in entries if e.data == turno_date]

        events = {
            "modelo": None,
            "abertura": None,
            "aberturas": [],  # Todas as aberturas (para detectar reboots)
            "encerramento": None,
            "encerramento_confirmado": None,
            "erros": [],
            "substituicoes": [],
            "ajustes_hora": [],
            "alertas_mesario": [],
            "votos_computados": 0,
            "ligada": None,
            "desligadas": [],
            "reboots": 0,  # Reinicializações durante votação
            "total_entries": len(entries),
            "severidades": {},
        }

        for entry in entries:
            desc = entry.descricao

            # Contagem de severidades
            sev = entry.severidade.upper() if entry.severidade else "UNKNOWN"
            events["severidades"][sev] = events["severidades"].get(sev, 0) + 1

            # Modelo - tentar padrão principal e depois vst
            if not events["modelo"]:
                m = PATTERN_MODELO_URNA.search(desc)
                if m:
                    events["modelo"] = m.group(1)
                else:
                    m = PATTERN_MODELO_VST.search(desc)
                    if m:
                        events["modelo"] = m.group(1)

            if PATTERN_ABERTURA.search(desc):
                events["aberturas"].append(entry)
                # Usar a PRIMEIRA abertura como a oficial
                if not events["abertura"]:
                    events["abertura"] = entry

            if PATTERN_ENCERRAMENTO.search(desc):
                events["encerramento"] = entry

            if PATTERN_ENCERRAMENTO_CONFIRMADO.search(desc):
                events["encerramento_confirmado"] = entry

            if PATTERN_ERRO.search(desc):
                events["erros"].append(entry)

            if PATTERN_SUBSTITUICAO.search(desc):
                events["substituicoes"].append(entry)

            if PATTERN_AJUSTE_HORA.search(desc):
                events["ajustes_hora"].append(entry)

            if PATTERN_MESARIO_ALERTA.search(desc):
                events["alertas_mesario"].append(entry)

            if PATTERN_VOTO_COMPUTADO.search(desc):
                events["votos_computados"] += 1

            if not events["ligada"]:
                m = PATTERN_LIGADA.search(desc)
                if m:
                    events["ligada"] = entry

            if PATTERN_DESLIGADA.search(desc):
                events["desligadas"].append(entry)

        # Calcular reboots: múltiplas aberturas = reinicializações
        events["reboots"] = max(0, len(events["aberturas"]) - 1)

        return events
