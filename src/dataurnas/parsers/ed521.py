"""Verificação de assinaturas Ed521 (EdDSA sobre a curva E-521).

Implementa só a verificação, em Python puro, conforme a definição da
ICP-Brasil (DOC-ICP-01.01, tabela "Parâmetros para a curva E521", incluída
pela IN ITI nº 15/2018 e mantida nas versões seguintes):

    p = 2^521 - 1, a = 1, d = -376014, c = 2 (cofator 4)
    B = (Gx, 12), L = ordem do subgrupo
    codificação: 527 bits little-endian de y, bit 527 = paridade de x
    H(x) = SHAKE256(dom5(phflag, context) || x, 132 bytes)
    dom5 = "SigEd521" || octet(phflag) || octet(len(context)) || context

A biblioteca `cryptography` não oferece a curva E-521, por isso a
aritmética é feita aqui. O código só lida com dados públicos (chave pública,
mensagem e assinatura), então não há segredo a proteger contra canais
laterais de tempo.
"""

from __future__ import annotations

import hashlib

P = 2**521 - 1
D = -376014 % P
L = int(
    "1716199415032652428745475199770348304317358825035826352348615864796385"
    "7958494136754758766516636578496366936590652341426043192829487025423179"
    "93421293670108523"
)
GX = int(
    "1571054894184995387535939749894317568645297350402905821437625181152304"
    "9943811885296325911960676041007726739279151142671933899050032766737490"
    "12051148356041324"
)
GY = 12

TAMANHO_CHAVE = 66
TAMANHO_ASSINATURA = 132

_Ponto = tuple[int, int, int, int]  # coordenadas estendidas (X, Y, Z, T)


def _soma(p: _Ponto, q: _Ponto) -> _Ponto:
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = x1 * x2 % P
    b = y1 * y2 % P
    c = D * t1 % P * t2 % P
    dd = z1 * z2 % P
    e = ((x1 + y1) * (x2 + y2) - a - b) % P
    f = (dd - c) % P
    g = (dd + c) % P
    h = (b - a) % P
    return (e * f % P, g * h % P, f * g % P, e * h % P)


def _estendido(x: int, y: int) -> _Ponto:
    return (x, y, 1, x * y % P)


_NEUTRO: _Ponto = (0, 1, 1, 0)


def _dobro(p: _Ponto) -> _Ponto:
    """2P (fórmula dbl-2008-hwcd com a = 1)."""
    x, y, z, _ = p
    a = x * x % P
    b = y * y % P
    c = 2 * z * z % P
    e = ((x + y) * (x + y) - a - b) % P
    g = (a + b) % P
    f = (g - c) % P
    h = (a - b) % P
    return (e * f % P, g * h % P, f * g % P, e * h % P)


def _neg(p: _Ponto) -> _Ponto:
    x, y, z, t = p
    return ((-x) % P, y, z, (-t) % P)


_JANELA = 4


def _mult(k: int, p: _Ponto) -> _Ponto:
    """k*P por janela fixa de 4 bits."""
    tab = [_NEUTRO, p]
    for _ in range(2, 1 << _JANELA):
        tab.append(_soma(tab[-1], p))
    r = _NEUTRO
    for i in range((k.bit_length() + _JANELA - 1) // _JANELA - 1, -1, -1):
        for _ in range(_JANELA):
            r = _dobro(r)
        d = (k >> (i * _JANELA)) & ((1 << _JANELA) - 1)
        if d:
            r = _soma(r, tab[d])
    return r


_TABELA_B: list[list[_Ponto]] = []


def _mult_base(k: int) -> _Ponto:
    """k*B com tabela fixa por janela (calculada uma vez por processo)."""
    if not _TABELA_B:
        q = _estendido(GX, GY)
        for _ in range((528 + _JANELA - 1) // _JANELA):
            linha = [_NEUTRO, q]
            for _ in range(2, 1 << _JANELA):
                linha.append(_soma(linha[-1], q))
            _TABELA_B.append(linha)
            for _ in range(_JANELA):
                q = _dobro(q)
    r = _NEUTRO
    i = 0
    while k:
        d = k & ((1 << _JANELA) - 1)
        if d:
            r = _soma(r, _TABELA_B[i][d])
        k >>= _JANELA
        i += 1
    return r


def _iguais(p: _Ponto, q: _Ponto) -> bool:
    x1, y1, z1, _ = p
    x2, y2, z2, _ = q
    return (x1 * z2 - x2 * z1) % P == 0 and (y1 * z2 - y2 * z1) % P == 0


def decodificar_ponto(b: bytes) -> tuple[int, int] | None:
    """Decodifica um ponto de 66 bytes; None se não estiver na curva."""
    if len(b) != TAMANHO_CHAVE:
        return None
    v = int.from_bytes(b, "little")
    sinal = v >> 527
    y = v & ((1 << 527) - 1)
    if y >= P:
        return None
    u = (y * y - 1) % P
    w = (D * y * y - 1) % P
    if w == 0:
        return None
    x2 = u * pow(w, P - 2, P) % P
    x = pow(x2, (P + 1) // 4, P)  # p = 3 mod 4
    if x * x % P != x2:
        return None
    if x == 0 and sinal:
        return None
    if (x & 1) != sinal:
        x = P - x
    return x, y


def _dom5(phflag: int, contexto: bytes) -> bytes:
    if len(contexto) > 255:
        raise ValueError("contexto maior que 255 bytes")
    return b"SigEd521" + bytes([phflag, len(contexto)]) + contexto


def verificar(chave_publica: bytes, mensagem: bytes, assinatura: bytes,
              contexto: bytes = b"") -> bool:
    """Verifica uma assinatura Ed521 pura (phflag 0). Retorna True/False."""
    if len(assinatura) != TAMANHO_ASSINATURA:
        return False
    a = decodificar_ponto(chave_publica)
    r_bytes = assinatura[:TAMANHO_CHAVE]
    r = decodificar_ponto(r_bytes)
    if a is None or r is None:
        return False
    s = int.from_bytes(assinatura[TAMANHO_CHAVE:], "little")
    if s >= L:
        return False
    h = hashlib.shake_256(
        _dom5(0, contexto) + r_bytes + chave_publica + mensagem
    ).digest(132)
    k = int.from_bytes(h, "little") % L
    return _iguais(_mult_base(s), _soma(_estendido(*r), _mult(k, _estendido(*a))))
