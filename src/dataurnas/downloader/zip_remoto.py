"""Leitura de pacotes zip remotos por faixas de bytes (HTTP Range), sem disco.

Os arquivos de urna de 2022 já não estão na API de resultados (o pleito saiu
de ``ele-c.json`` e os caminhos ``ele2022/arquivo-urna/...`` respondem 404).
O TSE mantém os mesmos arquivos no portal de dados abertos, um zip por turno
e UF (CDN com ``accept-ranges: bytes``)::

    https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2022/arqurnatot/
        bu_imgbu_logjez_rdv_vscmr_2022_<1|2>t_<UF>.zip

Cada entrada se chama ``o00406-MMMMMZZZZSSSS.<ext>`` (pleito, município,
zona e seção). Este módulo lê o diretório central do zip (inclusive ZIP64,
necessário em SP, que passa de 16 GB) e devolve, para faixas contíguas de
bytes, o conteúdo descompactado de cada entrada com o CRC-32 conferido.
As funções puras daqui são testadas sem rede; o cliente HTTP fica no script
``scripts/ele2022/fetch_integridade.py``.
"""

from __future__ import annotations

import re
import struct
import zlib
from dataclasses import dataclass
from typing import Iterable, Optional

CDN_2022 = "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2022/arqurnatot"

SIG_EOCD = b"PK\x05\x06"
SIG_ZIP64_LOCATOR = b"PK\x06\x07"
SIG_ZIP64_EOCD = b"PK\x06\x06"
SIG_CENTRAL = b"PK\x01\x02"
SIG_LOCAL = b"PK\x03\x04"

# o00406-0100700090001.bu -> pleito 406, município 01007, zona 0009, seção 0001
NOME_V1 = re.compile(r"^o0*(?P<pleito>\d+)-(?P<mun>\d{5})(?P<zona>\d{4})(?P<secao>\d{4})"
                     r"\.(?P<ext>[a-z0-9]+)$")

# extensão -> tipo do aux.json (normalizado por integrity.tipo_arquivo)
TIPO_POR_EXTENSAO = {"bu": "bu", "rdv": "rdv", "logjez": "log", "imgbu": "imgbu",
                     "vscmr": "vota", "busa": "busa", "logsajez": "logsa",
                     "vscsa": "sa", "imgbusa": "imgbusa"}


def url_pacote_2022(turno: int, uf: str) -> str:
    """URL do zip de arquivos de urna de 2022 (dados abertos do TSE)."""
    return f"{CDN_2022}/bu_imgbu_logjez_rdv_vscmr_2022_{int(turno)}t_{uf.upper()}.zip"


def parse_nome_v1(nome: str) -> Optional[dict]:
    """Identificação da seção a partir do nome da entrada; None se fora do padrão."""
    m = NOME_V1.match(nome)
    if not m:
        return None
    return {"pleito": m["pleito"], "cd_mun": m["mun"], "zona": m["zona"],
            "secao": m["secao"], "ext": m["ext"]}


@dataclass(frozen=True)
class Entrada:
    """Uma entrada do diretório central."""

    nome: str
    metodo: int
    crc: int
    tamanho_compactado: int
    tamanho: int
    offset: int          # início do cabeçalho local
    data_hora: str       # data e hora DOS da entrada, "AAAA-MM-DD hh:mm:ss"
    fim: int = 0         # início da entrada seguinte (ou do diretório central)


@dataclass(frozen=True)
class Diretorio:
    offset: int
    tamanho: int
    n_entradas: int


def localizar_diretorio(cauda: bytes, tamanho_total: int) -> tuple[Optional[Diretorio], Optional[int]]:
    """Lê o fim do zip (EOCD e, se houver, o localizador ZIP64).

    cauda: últimos bytes do arquivo. Retorna (diretorio, offset_zip64_eocd):
    no zip comum, o diretório vem pronto e o segundo valor é None; no ZIP64
    o diretório é None e é preciso ler o registro ZIP64 no offset devolvido.
    """
    i = cauda.rfind(SIG_EOCD)
    if i < 0 or len(cauda) - i < 22:
        raise ValueError("fim do diretório central (EOCD) não encontrado")
    (_sig, _disk, _disk_cd, _n_disk, n_total, cd_size, cd_off,
     _clen) = struct.unpack("<4sHHHHIIH", cauda[i:i + 22])
    loc = i - 20
    if loc >= 0 and cauda[loc:loc + 4] == SIG_ZIP64_LOCATOR:
        (_s, _d, z64_off, _nd) = struct.unpack("<4sIQI", cauda[loc:loc + 20])
        return None, z64_off
    if 0xFFFFFFFF in (cd_size, cd_off) or n_total == 0xFFFF:
        raise ValueError("zip com campos ZIP64 sem localizador")
    if cd_off + cd_size > tamanho_total:
        raise ValueError("diretório central fora do arquivo")
    return Diretorio(cd_off, cd_size, n_total), None


def parse_zip64_eocd(buf: bytes) -> Diretorio:
    """Registro de fim de diretório ZIP64 (56 bytes a partir da assinatura)."""
    if buf[:4] != SIG_ZIP64_EOCD:
        raise ValueError("registro ZIP64 EOCD inválido")
    (_sig, _size, _vm, _vn, _d, _dcd, _n_disk, n_total, cd_size,
     cd_off) = struct.unpack("<4sQHHIIQQQQ", buf[:56])
    return Diretorio(cd_off, cd_size, n_total)


def _data_hora_dos(data: int, hora: int) -> str:
    return (f"{1980 + (data >> 9):04d}-{(data >> 5) & 0xF:02d}-{data & 0x1F:02d} "
            f"{hora >> 11:02d}:{(hora >> 5) & 0x3F:02d}:{(hora & 0x1F) * 2:02d}")


def parse_diretorio(cd: bytes, fim_dados: int) -> list[Entrada]:
    """Entradas do diretório central, em ordem de offset, com o campo fim
    preenchido (offset da entrada seguinte; a última termina em fim_dados,
    o início do diretório central)."""
    out: list[Entrada] = []
    i = 0
    n = len(cd)
    while i + 46 <= n and cd[i:i + 4] == SIG_CENTRAL:
        (_sig, _vm, _vn, _flag, metodo, hora, data, crc, csize, usize, nlen, xlen,
         clen, _disk, _iattr, _eattr, off) = struct.unpack("<4sHHHHHHIIIHHHHHII", cd[i:i + 46])
        nome = cd[i + 46:i + 46 + nlen].decode("utf-8", errors="replace")
        extra = cd[i + 46 + nlen:i + 46 + nlen + xlen]
        if 0xFFFFFFFF in (csize, usize, off):
            j = 0
            while j + 4 <= len(extra):
                hid, hlen = struct.unpack("<HH", extra[j:j + 4])
                if hid == 0x0001:
                    vals = extra[j + 4:j + 4 + hlen]
                    k = 0
                    if usize == 0xFFFFFFFF:
                        usize = struct.unpack("<Q", vals[k:k + 8])[0]
                        k += 8
                    if csize == 0xFFFFFFFF:
                        csize = struct.unpack("<Q", vals[k:k + 8])[0]
                        k += 8
                    if off == 0xFFFFFFFF:
                        off = struct.unpack("<Q", vals[k:k + 8])[0]
                    break
                j += 4 + hlen
        out.append(Entrada(nome, metodo, crc, csize, usize, off, _data_hora_dos(data, hora)))
        i += 46 + nlen + xlen + clen
    out.sort(key=lambda e: e.offset)
    com_fim = []
    for k, e in enumerate(out):
        fim = out[k + 1].offset if k + 1 < len(out) else fim_dados
        com_fim.append(Entrada(e.nome, e.metodo, e.crc, e.tamanho_compactado, e.tamanho,
                               e.offset, e.data_hora, fim))
    return com_fim


def extrair(buf: bytes, base: int, e: Entrada) -> bytes:
    """Conteúdo descompactado da entrada e, lida de buf (que começa em base).

    Confere assinatura do cabeçalho local, tamanho e CRC-32; levanta
    ValueError se algo não bater (o bloco é baixado de novo).
    """
    i = e.offset - base
    if buf[i:i + 4] != SIG_LOCAL:
        raise ValueError(f"{e.nome}: cabeçalho local ausente")
    nlen, xlen = struct.unpack("<HH", buf[i + 26:i + 30])
    ini = i + 30 + nlen + xlen
    dados = buf[ini:ini + e.tamanho_compactado]
    if len(dados) != e.tamanho_compactado:
        raise ValueError(f"{e.nome}: bloco truncado")
    if e.metodo == 8:
        d = zlib.decompressobj(-15)
        raw = d.decompress(dados) + d.flush()
    elif e.metodo == 0:
        raw = bytes(dados)
    else:
        raise ValueError(f"{e.nome}: método de compressão {e.metodo} não suportado")
    if len(raw) != e.tamanho:
        raise ValueError(f"{e.nome}: tamanho descompactado {len(raw)} difere de {e.tamanho}")
    if zlib.crc32(raw) & 0xFFFFFFFF != e.crc:
        raise ValueError(f"{e.nome}: CRC-32 não confere")
    return raw


def agrupar_secoes(entradas: Iterable[Entrada]) -> tuple[dict[tuple, list[Entrada]], list[str]]:
    """Agrupa as entradas por (cd_mun, zona, secao); devolve também os nomes
    fora do padrão (ex.: leiame.pdf)."""
    secoes: dict[tuple, list[Entrada]] = {}
    outros: list[str] = []
    for e in entradas:
        p = parse_nome_v1(e.nome)
        if p is None:
            outros.append(e.nome)
            continue
        secoes.setdefault((p["cd_mun"], p["zona"], p["secao"]), []).append(e)
    return secoes, outros


def montar_blocos(secoes: dict[tuple, list[Entrada]], alvo_bytes: int = 8 << 20
                  ) -> list[tuple[int, int, list[tuple]]]:
    """Agrupa seções em blocos de bytes contíguos para baixar numa só requisição.

    Retorna [(inicio, fim, [chaves de seção])], com fim exclusivo. Uma seção
    só entra num bloco junto com outras se suas entradas forem contíguas e a
    seção começar exatamente onde a anterior terminou; caso contrário (ou se
    passar de alvo_bytes), abre outro bloco. Seção com entradas espalhadas
    vira um bloco próprio cobrindo do menor ao maior offset.
    """
    faixas = []
    for k, es in secoes.items():
        ini = min(e.offset for e in es)
        fim = max(e.fim for e in es)
        faixas.append((ini, fim, k))
    faixas.sort()
    blocos: list[tuple[int, int, list[tuple]]] = []
    for ini, fim, k in faixas:
        if blocos:
            b_ini, b_fim, ks = blocos[-1]
            if ini == b_fim and fim - b_ini <= alvo_bytes:
                blocos[-1] = (b_ini, fim, ks + [k])
                continue
        blocos.append((ini, fim, [k]))
    return blocos
