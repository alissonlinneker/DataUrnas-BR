"""Parser for the printed ballot box report image (-imgbu.dat, 2024+).

The -imgbu.dat file is an EntidadeEnvelopeGenerico (spec/v2/bu.asn1) whose
``conteudo`` is the text the voting machine printed as the paper BU
(Latin-1, fixed-width lines), followed by the "BU DIGITAL" QR code blocks,
the certificate blocks and the signature. Only the text part before
"BU DIGITAL" is parsed here.

Layout of the parts that are read (2026, 2nd round example)::

    Município                        01007
    Zona Eleitoral                    0009
    Local de Votação                  1104
    Seção Eleitoral                   0001
    Eleitores aptos                   0308
    Comparecimento                    0232
            Habilitação biométrica    0210
            Habilitação biográfica    0014
            Habilitação sem biometria 0008
    Eleitores faltosos                0076
    Código identificação UE       02468149
    ...
    --------------PRESIDENTE--------------
    Nome do candidato       Num cand Votos
      LULA                        13  0068
      FLAVIO BOLSONARO            22  0149
    --------------------------------------
    Eleitores aptos                   0308
    Total de votos Nominais           0217
    Brancos                           0002
    Nulos                             0013
    Total Apurado                     0232

Every "label   number" line becomes a key in the header (lines before the
first office block) or in the office block. Candidate lines (name, number,
votes) go to ``candidatos`` of the block.
"""

from __future__ import annotations

import re
from typing import Optional

# Office header: a run of dashes, the office name, a run of dashes.
_RE_CARGO = re.compile(r"^-{3,}([^-\d][^-]*?)-{3,}\s*$")
# Candidate line: indented name, candidate number, votes (zero padded).
_RE_CANDIDATO = re.compile(r"^\s{2}(\S.*?)\s{2,}(\d{1,5})\s+(\d{4,})\s*$")
# "Label    value" line; the value is the last integer on the line. A single
# space may separate them ("Habilitação sem biometria 0008" fills the width).
_RE_ROTULO = re.compile(r"^\s*(\S.*?)\s+(\d+)\s*$")
_RE_DATA_HORA = re.compile(r"^\s*(\S.*?)\s{2,}(\d{2}/\d{2}/\d{4}|\d{2}:\d{2}:\d{2})\s*$")

# Header labels kept (printed label -> key).
CAMPOS_CABECALHO = {
    "Município": "municipio",
    "Zona Eleitoral": "zona",
    "Local de Votação": "local",
    "Seção Eleitoral": "secao",
    "Eleitores aptos": "aptos",
    "Comparecimento": "comparecimento",
    "Habilitação biométrica": "hab_biometrica",
    "Habilitação biográfica": "hab_biografica",
    "Habilitação sem biometria": "hab_sem_biometria",
    "Eleitores faltosos": "faltosos",
    "Código identificação UE": "codigo_ue",
}
# Office block labels kept (printed label -> key).
CAMPOS_CARGO = {
    "Eleitores aptos": "aptos",
    "Total de votos Nominais": "nominais",
    "Brancos": "brancos",
    "Nulos": "nulos",
    "Total Apurado": "total_apurado",
}
CAMPOS_DATA_HORA = {
    "Data de abertura da UE": "data_abertura",
    "Horário de abertura": "hora_abertura",
    "Data de fechamento da UE": "data_fechamento",
    "Horário de fechamento": "hora_fechamento",
}
FIM_TEXTO = "BU DIGITAL"


def conteudo_imgbu(raw: bytes) -> bytes:
    """Envelope content of an -imgbu.dat; the raw bytes if it is not an envelope."""
    try:
        from ..models import SpecVersion
        from .asn1_helper import get_compiler

        env = get_compiler(SpecVersion.V2, "bu").decode(
            "EntidadeEnvelopeGenerico", bytearray(raw))
        return bytes(env["conteudo"])
    except Exception:  # noqa: BLE001 - any decoding failure falls back to the raw bytes
        return raw


def parse_imgbu_texto(texto: str) -> dict:
    """Parse the printed BU text.

    Returns ``{"cabecalho": {...}, "cargos": {NAME: [block, ...]}}`` where each
    block is ``{"candidatos": {number: votes}, <CAMPOS_CARGO keys>: int}``.
    An office may appear more than once (one block per election); blocks
    keep the printed order.
    """
    corte = texto.find(FIM_TEXTO)
    if corte >= 0:
        texto = texto[:corte]
    cab: dict = {}
    cargos: dict[str, list[dict]] = {}
    bloco: Optional[dict] = None
    for linha in texto.splitlines():
        m = _RE_CARGO.match(linha.strip())
        if m:
            nome = m.group(1).strip()
            bloco = {"candidatos": {}}
            cargos.setdefault(nome, []).append(bloco)
            continue
        if bloco is not None and linha.startswith("====="):
            bloco = None  # election banner closes the office block
            continue
        if bloco is not None:
            c = _RE_CANDIDATO.match(linha)
            if c and not c.group(1).startswith(tuple(CAMPOS_CARGO)):
                num = int(c.group(2))
                bloco["candidatos"][num] = bloco["candidatos"].get(num, 0) + int(c.group(3))
                continue
            r = _RE_ROTULO.match(linha)
            if r and r.group(1) in CAMPOS_CARGO:
                bloco.setdefault(CAMPOS_CARGO[r.group(1)], int(r.group(2)))
            continue
        d = _RE_DATA_HORA.match(linha)
        if d and d.group(1) in CAMPOS_DATA_HORA:
            cab.setdefault(CAMPOS_DATA_HORA[d.group(1)], d.group(2))
            continue
        r = _RE_ROTULO.match(linha)
        if r and r.group(1) in CAMPOS_CABECALHO:
            cab.setdefault(CAMPOS_CABECALHO[r.group(1)], int(r.group(2)))
    return {"cabecalho": cab, "cargos": cargos}


def parse_imgbu(raw: bytes) -> dict:
    """Parse an -imgbu.dat (envelope or bare text)."""
    return parse_imgbu_texto(conteudo_imgbu(raw).decode("latin-1", errors="replace"))
