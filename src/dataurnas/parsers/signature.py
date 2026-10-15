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


# ---------------------------------------------------------------------------
# Arquivo de assinatura da urna de 2026 (-vota.vsc / -sa.vsc)
# ---------------------------------------------------------------------------
#
# Layout observado nos arquivos publicados (difere da spec v2 publicada em
# dois pontos: o modelo vem num SEQUENCE no final e os campos opcionais usam
# tags de contexto [0] e [1]):
#
#   SEQUENCE {
#     EntidadeAssinatura assinaturaSW   -- CEPESC (algoritmo 3), usuário SEVIN
#     EntidadeAssinatura assinaturaHW   -- hardware da urna: Ed521 (4) ou ECDSA P-521 (2)
#     SEQUENCE { ENUMERATED modeloEquipamento, ENUMERATED algoritmoAssinatura }
#   }
#   EntidadeAssinatura ::= SEQUENCE {
#     dataHoraCriacao GeneralString, versao INTEGER,
#     autoAssinado SEQUENCE { usuario SEQUENCE {nome, serial}, SEQUENCE {algHash},
#                             SEQUENCE {algAssinatura, bits},
#                             SEQUENCE {tamanho, hash OCTET STRING, assinatura OCTET STRING} },
#     conteudoAutoAssinado OCTET STRING,  -- BER de Assinatura (lista de arquivos)
#     [0] conjuntoChave OPTIONAL, [1] certificadoDigital OPTIONAL (PEM ou DER)
#   }
#
# Verificação (confirmada em arquivos reais de UE2013, UE2015, UE2020 e UE2022):
#   - hash de cada entrada = SHA-512 do conteúdo do arquivo;
#   - hash do autoAssinado = SHA-512 do conteudoAutoAssinado;
#   - a assinatura de hardware incide sobre SHA-512(hash), isto é:
#       Ed521 (ICP-Brasil, PureEdDSA, contexto vazio) de SHA-512(hash);
#       ECDSA P-521 com SHA-512 aplicado ao hash (mensagem = hash).
#   - a assinatura CEPESC (software) usa algoritmo de governo não publicado e
#     não pode ser verificada aqui.

ALGORITMOS_ASSINATURA = {1: "rsa", 2: "ecdsa", 3: "cepesc", 4: "eddsa"}
ALGORITMOS_HASH = {1: "sha1", 2: "sha256", 3: "sha384", 4: "sha512"}
OID_ED521 = "1.3.6.1.4.1.44588.2.1"


def _filhos(b: bytes, i: int, fim: int) -> list[tuple[int, int, int]]:
    out = []
    while i < fim:
        t, j, ln = _ber_tlv(b, i)
        if j + ln > fim:
            raise ValueError("BER truncado")
        out.append((t, j, ln))
        i = j + ln
    return out


def _val(b: bytes, tlv: tuple[int, int, int]) -> bytes:
    return b[tlv[1]:tlv[1] + tlv[2]]


def _int(b: bytes, tlv: tuple[int, int, int]) -> int:
    return int.from_bytes(_val(b, tlv), "big", signed=False)


def _txt(b: bytes, tlv: tuple[int, int, int]) -> str:
    return _val(b, tlv).decode("latin-1")


def _parse_entidade(b: bytes, tlv: tuple[int, int, int]) -> dict:
    k = _filhos(b, tlv[1], tlv[1] + tlv[2])
    auto = _filhos(b, k[2][1], k[2][1] + k[2][2])
    usuario = _filhos(b, auto[0][1], auto[0][1] + auto[0][2])
    alg_hash = _filhos(b, auto[1][1], auto[1][1] + auto[1][2])
    alg_ass = _filhos(b, auto[2][1], auto[2][1] + auto[2][2])
    dig = _filhos(b, auto[3][1], auto[3][1] + auto[3][2])
    conteudo = _val(b, k[3])
    ent = {
        "data_hora": _txt(b, k[0]),
        "versao": _int(b, k[1]),
        "usuario": _txt(b, usuario[0]),
        "serial": _int(b, usuario[1]),
        "algoritmo_hash": ALGORITMOS_HASH.get(_int(b, alg_hash[0]), str(_int(b, alg_hash[0]))),
        "algoritmo_assinatura": ALGORITMOS_ASSINATURA.get(_int(b, alg_ass[0]),
                                                          str(_int(b, alg_ass[0]))),
        "bits": _int(b, alg_ass[1]) if len(alg_ass) > 1 else None,
        "hash": _val(b, dig[1]),
        "assinatura": _val(b, dig[2]),
        "conteudo": conteudo,
        "conjunto_chave": None,
        "certificado": None,
        "arquivos": [],
    }
    for t, j, ln in k[4:]:
        if t in (0x80, 0x1B):
            ent["conjunto_chave"] = b[j:j + ln].decode("latin-1")
        elif t in (0x81, 0x04):
            ent["certificado"] = b[j:j + ln]
    # conteudoAutoAssinado: SEQUENCE { SEQUENCE OF AssinaturaArquivo }
    c = conteudo
    raiz = _filhos(c, 0, len(c))
    lista = _filhos(c, raiz[0][1], raiz[0][1] + raiz[0][2])
    if len(lista) == 1 and c[lista[0][1]] == 0x30:
        primeiro = _filhos(c, lista[0][1], lista[0][1] + lista[0][2])
        if primeiro and primeiro[0][0] == 0x30:  # nível extra: SEQUENCE OF
            lista = primeiro
    for _, j, ln in lista:
        e = _filhos(c, j, j + ln)
        d = _filhos(c, e[1][1], e[1][1] + e[1][2])
        ent["arquivos"].append({
            "nome": _txt(c, e[0]),
            "hash": _val(c, d[1]),
            "assinatura": _val(c, d[2]),
        })
    return ent


def parse_vsc(raw: bytes) -> dict:
    """Decodifica o arquivo de assinatura de 2026 em dados estruturados.

    Retorna {"modelo_cod", "algoritmo_hw_cod", "sw", "hw"}; sw e hw trazem
    data_hora, usuario, serial, algoritmos, hash e assinatura do próprio
    conteúdo, certificado (bytes) e a lista "arquivos" com nome, hash
    (SHA-512 do arquivo) e assinatura de cada arquivo assinado.
    Levanta ValueError/IndexError se o BER não tiver o formato esperado.
    """
    t, i, ln = _ber_tlv(raw, 0)
    if t != 0x30:
        raise ValueError("arquivo de assinatura não começa com SEQUENCE")
    filhos = _filhos(raw, i, min(i + ln, len(raw)))
    modelo = alg = None
    if filhos and filhos[0][0] == 0x0A:  # spec v2 publicada: modelo primeiro
        modelo = _int(raw, filhos[0])
        filhos = filhos[1:]
    ents = [f for f in filhos if f[0] == 0x30 and f[2] > 16]
    for f in filhos:
        if f[0] == 0x30 and f[2] <= 16:
            sub = _filhos(raw, f[1], f[1] + f[2])
            if sub and sub[0][0] == 0x0A:
                modelo = _int(raw, sub[0])
            if len(sub) > 1 and sub[1][0] == 0x0A:
                alg = _int(raw, sub[1])
    if len(ents) < 2:
        raise ValueError("assinaturaSW/assinaturaHW ausentes")
    return {
        "modelo_cod": modelo,
        "algoritmo_hw_cod": alg,
        "sw": _parse_entidade(raw, ents[0]),
        "hw": _parse_entidade(raw, ents[1]),
    }


def _carregar_certificado(cert: bytes):
    """Certificado X.509 (PEM ou DER com bytes de preenchimento no fim)."""
    from cryptography import x509

    if cert.lstrip().startswith(b"-----BEGIN"):
        return x509.load_pem_x509_certificate(cert)
    _, j, ln = _ber_tlv(cert, 0)
    return x509.load_der_x509_certificate(cert[:j + ln])


def _chave_ed521_do_certificado(der: bytes) -> bytes | None:
    """Chave pública Ed521 (66 bytes) lida do SubjectPublicKeyInfo."""
    _, i, ln = _ber_tlv(der, 0)
    cert = _filhos(der, i, i + ln)
    tbs = _filhos(der, cert[0][1], cert[0][1] + cert[0][2])
    if tbs and tbs[0][0] == 0xA0:  # [0] version
        tbs = tbs[1:]
    spki = _filhos(der, tbs[5][1], tbs[5][1] + tbs[5][2])
    bits = _val(der, spki[1])
    return bits[1:] if bits and bits[0] == 0 else None


def info_certificado(cert_bytes: bytes) -> dict:
    """Campos do certificado: subject, issuer, serial, sha256, validade, OIDs."""
    from cryptography.hazmat.primitives import serialization

    c = _carregar_certificado(cert_bytes)
    der = c.public_bytes(serialization.Encoding.DER)
    try:
        oid_chave = c.public_key_algorithm_oid.dotted_string
    except Exception:  # noqa: BLE001 - versões antigas da biblioteca
        oid_chave = None
    return {
        "subject": c.subject.rfc4514_string(),
        "issuer": c.issuer.rfc4514_string(),
        "serial": format(c.serial_number, "x"),
        "sha256": hashlib.sha256(der).hexdigest(),
        "nao_antes": c.not_valid_before_utc.isoformat(),
        "nao_depois": c.not_valid_after_utc.isoformat(),
        "oid_assinatura": c.signature_algorithm_oid.dotted_string,
        "oid_chave": oid_chave,
        "cn": next((a.value for a in c.subject
                    if a.oid.dotted_string == "2.5.4.3"), None),
        "_cert": c,
        "_der": der,
    }


def ecdsa_der_canonica(sig: bytes) -> bytes | None:
    """Reescreve uma assinatura ECDSA em DER canônico, ou None se ilegível.

    As urnas de 2022 (.vscmr) gravam r e s como INTEGER de largura fixa
    (66 bytes para P-521), com zeros à esquerda quando o valor é menor. Isso é
    BER válido, mas não DER mínimo, e o OpenSSL rejeita a codificação não
    canônica: cerca de metade das assinaturas válidas falharia. Aqui r e s são
    lidos como inteiros e recodificados. Também aceita r||s cru (2 x 66 bytes).
    """
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

    try:
        if sig[:1] == b"\x30":
            t, i, ln = _ber_tlv(sig, 0)
            partes = _filhos(sig, i, i + ln)
            if len(partes) != 2 or any(p[0] != 0x02 for p in partes):
                return None
            r, s = (int.from_bytes(_val(sig, p), "big", signed=True) for p in partes)
        elif len(sig) % 2 == 0 and len(sig) in (64, 96, 132):
            meio = len(sig) // 2
            r, s = int.from_bytes(sig[:meio], "big"), int.from_bytes(sig[meio:], "big")
        else:
            return None
    except (IndexError, ValueError):
        return None
    if r <= 0 or s <= 0:
        return None
    return encode_dss_signature(r, s)


def _verificador_hw(info: dict, algoritmo: str):
    """Função (hash_assinado, assinatura) -> bool para a chave do certificado,
    ou (None, motivo) se o algoritmo não for verificável."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec

    if algoritmo == "eddsa" or info["oid_chave"] == OID_ED521:
        from . import ed521

        chave = _chave_ed521_do_certificado(info["_der"])
        if chave is None or ed521.decodificar_ponto(chave) is None:
            return None, "chave pública Ed521 inválida no certificado"

        def v(h: bytes, s: bytes) -> bool:
            return ed521.verificar(chave, hashlib.sha512(h).digest(), s)
        return v, "Ed521"
    if algoritmo == "ecdsa":
        pk = info["_cert"].public_key()
        if not isinstance(pk, ec.EllipticCurvePublicKey):
            return None, "certificado sem chave ECDSA"

        def v(h: bytes, s: bytes) -> bool:
            canonica = ecdsa_der_canonica(s)
            if canonica is None:
                return False
            try:
                pk.verify(canonica, h, ec.ECDSA(hashes.SHA512()))
                return True
            except InvalidSignature:
                return False
        return v, f"ECDSA-{pk.curve.name}-SHA512"
    return None, f"algoritmo de hardware não suportado: {algoritmo}"


def verificar_vsc(raw: bytes, arquivos_verificar: set[str] | None = None) -> dict:
    """Verifica criptograficamente o arquivo de assinatura de 2026.

    Confere (1) SHA-512 do conteúdo assinado contra o hash do autoAssinado,
    nas partes de software e de hardware; (2) a assinatura de hardware do
    autoAssinado com a chave pública do certificado embutido; (3) a
    assinatura de hardware individual dos arquivos em arquivos_verificar
    (por nome; None = todos). A cadeia do certificado não é validada: os
    certificados das AC emissoras (AC URNA, AC UE2022) não vêm nos arquivos.

    Retorna dict com: assinatura_valida (True/False/None), algoritmo,
    hashes (nome -> SHA-512 assinado, da parte de hardware ou software),
    assinaturas_arquivos (nome -> bool), cert_* , modelo_cod, motivos.
    """
    out: dict = {
        "assinatura_valida": None, "algoritmo": None, "hashes": {},
        "assinaturas_arquivos": {}, "modelo_cod": None,
        "cert_subject": None, "cert_issuer": None, "cert_serial": None,
        "cert_sha256": None, "motivos": [], "falhas": [],
    }
    try:
        v = parse_vsc(raw)
    except (ValueError, IndexError) as e:
        out["falhas"].append(f"arquivo de assinatura ilegível: {e}")
        out["assinatura_valida"] = False
        return out
    out["modelo_cod"] = v["modelo_cod"]
    sw, hw = v["sw"], v["hw"]
    for parte, ent in (("SW", sw), ("HW", hw)):
        if hashlib.sha512(ent["conteudo"]).digest() != ent["hash"]:
            out["falhas"].append(f"{parte}: SHA-512 do conteúdo assinado difere do hash autoassinado")
    hs_sw = {a["nome"]: a["hash"] for a in sw["arquivos"]}
    hs_hw = {a["nome"]: a["hash"] for a in hw["arquivos"]}
    for nome in set(hs_sw) & set(hs_hw):
        if hs_sw[nome] != hs_hw[nome]:
            out["falhas"].append(f"{nome}: hash difere entre as partes SW e HW")
    out["hashes"] = {**hs_sw, **hs_hw}
    alg_sw = sw["algoritmo_assinatura"]
    if alg_sw != "cepesc":
        out["motivos"].append(f"parte SW com algoritmo {alg_sw}, não verificada")
    if not hw["certificado"]:
        out["motivos"].append("sem certificado na parte HW; assinatura não verificada")
        out["algoritmo"] = hw["algoritmo_assinatura"]
        if out["falhas"]:
            out["assinatura_valida"] = False
        return out
    try:
        info = info_certificado(hw["certificado"])
    except Exception as e:  # noqa: BLE001 - certificado malformado vira motivo
        out["falhas"].append(f"certificado ilegível: {e}")
        out["assinatura_valida"] = False
        return out
    out.update({"cert_subject": info["subject"], "cert_issuer": info["issuer"],
                "cert_serial": info["serial"], "cert_sha256": info["sha256"]})
    esperado = f"{hw['usuario']}{hw['serial']:08d}" if hw["usuario"].upper() == "UEAO" \
        else hw["usuario"]
    if info["cn"] and info["cn"].upper() != esperado.upper():
        out["motivos"].append(f"CN do certificado ({info['cn']}) difere do usuário ({esperado})")
    verif, alg = _verificador_hw(info, hw["algoritmo_assinatura"])
    out["algoritmo"] = alg
    if verif is None:
        out["motivos"].append(alg)
        if out["falhas"]:
            out["assinatura_valida"] = False
        return out
    if not verif(hw["hash"], hw["assinatura"]):
        out["falhas"].append(f"assinatura {alg} do conteúdo (autoAssinado) inválida")
    for a in hw["arquivos"]:
        if arquivos_verificar is not None and a["nome"] not in arquivos_verificar:
            continue
        ok = verif(a["hash"], a["assinatura"])
        out["assinaturas_arquivos"][a["nome"]] = ok
        if not ok:
            out["falhas"].append(f"{a['nome']}: assinatura {alg} do arquivo inválida")
    out["assinatura_valida"] = not out["falhas"]
    return out
