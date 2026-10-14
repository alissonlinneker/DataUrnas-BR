"""Parser de arquivos de assinatura digital (.vscmr / .vsc)."""

import hashlib
import logging
from pathlib import Path
from typing import Optional

from ..config import MODELOS_URNA
from ..models import HashVerification, SpecVersion
from .asn1_helper import decode_entity, detect_spec_version, get_compiler

logger = logging.getLogger(__name__)


def _resolve_signed_file(data_dir: Path, filename) -> Path | None:
    """Localiza no diretório da seção o arquivo listado na assinatura.

    O nome vem de conteúdo não confiável: nomes com separadores de
    caminho, ".." ou byte nulo são rejeitados e a busca alternativa
    compara strings (sem glob), sempre dentro de data_dir.
    """
    if isinstance(filename, bytes):
        filename = filename.decode("latin-1", errors="replace")
    name = str(filename)
    if not name or name in (".", "..") or "/" in name or "\\" in name or "\x00" in name:
        logger.warning("Nome de arquivo inválido na assinatura: %r", name)
        return None

    candidate = data_dir / name
    if candidate.is_file():
        return candidate

    # Fallback: arquivo baixado com prefixo/sufixo diferente do nome assinado
    for entry in sorted(data_dir.iterdir()):
        if entry.is_file() and name in entry.name:
            return entry
    return None


class SignatureParser:
    """Parser de arquivos de assinatura digital da urna."""

    def parse(self, file_path: Path) -> dict:
        """Parseia arquivo de assinatura e retorna estrutura completa."""
        file_path = Path(file_path)
        spec_version = detect_spec_version(file_path)
        module = "assinatura"

        with open(file_path, "rb") as f:
            raw = f.read()

        # V1 usa EntidadeAssinaturaResultado, V2 usa EntidadeAssinaturaEcourna
        if spec_version == SpecVersion.V2:
            entity_name = "EntidadeAssinaturaEcourna"
        else:
            entity_name = "EntidadeAssinaturaResultado"

        decoded = decode_entity(raw, entity_name, spec_version, module)
        return decoded

    def extract_file_hashes(self, file_path: Path) -> dict[str, bytes]:
        """Extrai hashes SHA-512 de todos os arquivos listados na assinatura.

        Returns:
            Dict mapeando nome_arquivo -> hash SHA-512 (bytes)
        """
        decoded = self.parse(file_path)
        hashes = {}

        for sig_type in ["assinaturaSW", "assinaturaHW"]:
            sig = decoded.get(sig_type, {})
            if not sig:
                continue

            conteudo = sig.get("conteudoAutoAssinado", b"")
            if not conteudo:
                continue

            # Decodificar o conteúdo auto-assinado como Assinatura
            spec_version = detect_spec_version(file_path)
            compiler = get_compiler(spec_version, "assinatura")
            try:
                assinatura = compiler.decode("Assinatura", bytearray(conteudo))
                # Campo da spec: arquivosAssinados (o nome antigo nunca casava,
                # e a verificação de hash não comparava arquivo algum)
                arquivos = assinatura.get("arquivosAssinados") or assinatura.get(
                    "assinaturaArquivos", []
                )
                for arq in arquivos:
                    nome = arq.get("nomeArquivo", "")
                    hash_val = arq.get("assinatura", {}).get("hash", b"")
                    if nome and hash_val:
                        hashes[nome] = hash_val
            except Exception as e:
                logger.warning("Erro ao decodificar assinatura %s: %s", sig_type, e)

        return hashes

    def verify_file_hashes(
        self, signature_path: Path, data_dir: Path
    ) -> list[HashVerification]:
        """Verifica hashes SHA-512 dos arquivos contra a assinatura.

        Args:
            signature_path: Caminho do arquivo .vscmr ou .vsc
            data_dir: Diretório contendo os arquivos de dados da urna

        Returns:
            Lista de resultados de verificação
        """
        expected_hashes = self.extract_file_hashes(signature_path)
        results = []

        for filename, expected_hash in expected_hashes.items():
            file_path = _resolve_signed_file(data_dir, filename)
            if file_path is None:
                results.append(
                    HashVerification(
                        arquivo=filename,
                        hash_esperado=expected_hash,
                        hash_calculado=b"",
                        valido=False,
                        encontrado=False,
                    )
                )
                continue

            with open(file_path, "rb") as f:
                calculated = hashlib.file_digest(f, "sha512").digest()
            results.append(
                HashVerification(
                    arquivo=filename,
                    hash_esperado=expected_hash,
                    hash_calculado=calculated,
                    valido=(expected_hash == calculated),
                )
            )

        return results

    def get_model(self, file_path: Path) -> Optional[str]:
        """Extrai o modelo da urna do arquivo de assinatura (ex.: "UE2020").

        Tenta a decodificação pela spec (2022: modeloUrna; spec v2 publicada:
        modeloEquipamento no início). Se falhar, lê o BER diretamente, o que
        cobre os .vsc de 2026, em que o modelo vem num bloco no final.
        """
        file_path = Path(file_path)
        try:
            raw = file_path.read_bytes()
        except OSError as e:
            logger.warning("Erro ao ler assinatura %s: %s", file_path, e)
            return None

        try:
            decoded = self.parse(file_path)
            model_raw = decoded.get("modeloUrna", decoded.get("modeloEquipamento"))
            nome = _nome_modelo(model_raw)
            if nome:
                return nome
        except Exception as e:
            logger.debug("Assinatura %s fora da spec (%s); lendo BER direto", file_path, e)

        nome = _nome_modelo(modelo_codigo_from_bytes(raw))
        if nome is None:
            logger.warning("Modelo da urna não encontrado em %s", file_path)
        return nome


def _nome_modelo(model_raw) -> Optional[str]:
    """Normaliza o modelo (enum por nome, por código ou tupla) para "UE2020"."""
    if isinstance(model_raw, tuple):
        model_raw = model_raw[1] if len(model_raw) > 1 else model_raw[0]
    if model_raw is None or model_raw == "":
        return None
    if isinstance(model_raw, str):
        return model_raw.upper()
    return MODELOS_URNA.get(model_raw, f"Modelo_{model_raw}")


def _ber_tlv(b: bytes, i: int) -> tuple[int, int, int]:
    """Lê tag/len BER em b[i]; retorna (tag, inicio_conteudo, tamanho)."""
    tag = b[i]
    i += 1
    ln = b[i]
    i += 1
    if ln & 0x80:
        n = ln & 0x7F
        if n == 0 or n > 4:
            raise ValueError("comprimento BER não suportado")
        ln = int.from_bytes(b[i:i + n], "big")
        i += n
    return tag, i, ln


def modelo_codigo_from_bytes(raw: bytes) -> Optional[int]:
    """Código do modelo da urna lido direto do BER do arquivo de assinatura.

    Formatos tratados:
        - 2022 (.vscmr) e spec v2 publicada: SEQUENCE { ENUMERATED modelo,
          assinaturaSW, assinaturaHW }.
        - 2026 (-vota.vsc): SEQUENCE { assinaturaSW, assinaturaHW,
          SEQUENCE { ENUMERATED modelo, ENUMERATED algoritmo } }.
    """
    try:
        tag, i, ln = _ber_tlv(raw, 0)
        if tag != 0x30:
            return None
        end = min(i + ln, len(raw))
        filhos = []
        while i < end:
            t, j, l2 = _ber_tlv(raw, i)
            filhos.append((t, j, l2))
            i = j + l2
        if filhos and filhos[0][0] == 0x0A:
            _, j, l2 = filhos[0]
            return int.from_bytes(raw[j:j + l2], "big")
        for t, j, l2 in reversed(filhos):
            if t == 0x30 and l2 <= 16:
                t2, k, l3 = _ber_tlv(raw, j)
                if t2 == 0x0A:
                    return int.from_bytes(raw[k:k + l3], "big")
    except (IndexError, ValueError):
        return None
    return None
