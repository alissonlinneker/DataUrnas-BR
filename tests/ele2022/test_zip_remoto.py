"""Leitura de zip remoto por faixas de bytes (funções puras, sem rede)."""

import io
import zipfile

import pytest

from dataurnas.downloader import zip_remoto as Z


def _zip(arquivos: dict[str, bytes], metodo: int = zipfile.ZIP_DEFLATED) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=metodo) as z:
        for nome, raw in arquivos.items():
            z.writestr(zipfile.ZipInfo(nome, (2022, 10, 2, 17, 30, 10)), raw,
                       compress_type=metodo)
    return buf.getvalue()


def _entradas(dados: bytes) -> list[Z.Entrada]:
    d, z64 = Z.localizar_diretorio(dados[-(65536 + 22):], len(dados))
    if d is None:
        d = Z.parse_zip64_eocd(dados[z64:z64 + 56])
    return Z.parse_diretorio(dados[d.offset:d.offset + d.tamanho], d.offset)


ARQS = {
    "o00406-0100700090001.bu": b"bu" * 500,
    "o00406-0100700090001.vscmr": bytes(range(256)) * 10,
    "o00406-0100700090002.bu": b"outro" * 300,
    "o00406-0100700090002.logjez": b"\x00" * 4000,
    "leiame.pdf": b"%PDF-1.4",
}


def test_url_pacote_2022():
    assert Z.url_pacote_2022(1, "ac").endswith(
        "/arqurnatot/bu_imgbu_logjez_rdv_vscmr_2022_1t_AC.zip")
    assert Z.url_pacote_2022(2, "zz").endswith("_2022_2t_ZZ.zip")


def test_parse_nome_v1():
    p = Z.parse_nome_v1("o00406-0100700090001.vscmr")
    assert p == {"pleito": "406", "cd_mun": "01007", "zona": "0009", "secao": "0001",
                 "ext": "vscmr"}
    assert Z.parse_nome_v1("o00407-9999900010002.logsajez")["pleito"] == "407"
    assert Z.parse_nome_v1("leiame.pdf") is None
    assert Z.parse_nome_v1("o00406-01007000900.bu") is None


@pytest.mark.parametrize("metodo", [zipfile.ZIP_DEFLATED, zipfile.ZIP_STORED])
def test_diretorio_e_extracao(metodo):
    dados = _zip(ARQS, metodo=metodo)
    ents = _entradas(dados)
    assert [e.nome for e in ents] == list(ARQS)
    assert all(e.fim > e.offset for e in ents)
    assert ents[-1].fim == ents[-1].offset + (ents[-1].fim - ents[-1].offset)
    assert ents[0].data_hora == "2022-10-02 17:30:10"
    for e in ents:
        assert Z.extrair(dados, 0, e) == ARQS[e.nome]
        # extração a partir de uma faixa que começa no offset da entrada
        assert Z.extrair(dados[e.offset:e.fim], e.offset, e) == ARQS[e.nome]


def test_diretorio_com_extra_zip64():
    # registro do diretório central com tamanhos e offset em 0xFFFFFFFF e os
    # valores reais no campo extra ZIP64 (caso de SP, com mais de 16 GB)
    import struct

    nome = b"o00406-0100700090001.bu"
    extra = struct.pack("<HHQQQ", 0x0001, 24, 5000, 4000, 17_000_000_000)
    reg = struct.pack("<4sHHHHHHIIIHHHHHII", Z.SIG_CENTRAL, 45, 45, 0, 8, 0x8C05, 0x5542,
                      0x1234, 0xFFFFFFFF, 0xFFFFFFFF, len(nome), len(extra), 0, 0, 0, 0,
                      0xFFFFFFFF) + nome + extra
    (e,) = Z.parse_diretorio(reg, 17_000_010_000)
    assert (e.tamanho, e.tamanho_compactado, e.offset) == (5000, 4000, 17_000_000_000)
    assert e.fim == 17_000_010_000 and e.crc == 0x1234


def test_localizar_diretorio_zip64_pelo_localizador():
    # EOCD precedido do localizador ZIP64: o diretório vem do registro ZIP64
    import struct

    z64 = struct.pack("<4sQHHIIQQQQ", Z.SIG_ZIP64_EOCD, 44, 45, 45, 0, 0, 3, 3, 150, 1000)
    loc = struct.pack("<4sIQI", Z.SIG_ZIP64_LOCATOR, 0, 1150, 1)
    eocd = struct.pack("<4sHHHHIIH", Z.SIG_EOCD, 0, 0, 0xFFFF, 0xFFFF, 0xFFFFFFFF,
                       0xFFFFFFFF, 0)
    cauda = z64 + loc + eocd
    d, off = Z.localizar_diretorio(cauda, 1150 + len(cauda))
    assert d is None and off == 1150
    d = Z.parse_zip64_eocd(z64)
    assert (d.offset, d.tamanho, d.n_entradas) == (1000, 150, 3)


def test_extrair_detecta_corrupcao():
    dados = bytearray(_zip(ARQS, metodo=zipfile.ZIP_STORED))
    ents = _entradas(bytes(dados))
    e = ents[0]
    ini = e.offset + 30 + len(e.nome)
    dados[ini + 10] ^= 0xFF
    with pytest.raises(ValueError, match="CRC-32"):
        Z.extrair(bytes(dados), 0, e)
    with pytest.raises(ValueError, match="cabeçalho local"):
        Z.extrair(bytes(dados), 1, e)


def test_agrupar_e_montar_blocos():
    dados = _zip(ARQS)
    secoes, outros = Z.agrupar_secoes(_entradas(dados))
    assert outros == ["leiame.pdf"]
    assert set(secoes) == {("01007", "0009", "0001"), ("01007", "0009", "0002")}
    blocos = Z.montar_blocos(secoes, alvo_bytes=1 << 20)
    assert len(blocos) == 1
    ini, fim, ks = blocos[0]
    assert ks == [("01007", "0009", "0001"), ("01007", "0009", "0002")]
    for k in ks:
        for e in secoes[k]:
            assert ini <= e.offset < e.fim <= fim
            assert Z.extrair(dados[ini:fim], ini, e) == ARQS[e.nome]
    # alvo pequeno: uma seção por bloco
    assert len(Z.montar_blocos(secoes, alvo_bytes=10)) == 2


def test_montar_blocos_secao_espalhada():
    e = lambda nome, ini, fim: Z.Entrada(nome, 8, 0, 1, 1, ini, "", fim)  # noqa: E731
    secoes = {("1", "1", "1"): [e("a", 0, 10), e("b", 20, 30)],
              ("1", "1", "2"): [e("c", 10, 20)]}
    blocos = Z.montar_blocos(secoes, alvo_bytes=100)
    # a seção 1 cobre [0, 30) e engloba a seção 2: ficam em blocos separados
    assert blocos[0] == (0, 30, [("1", "1", "1")])
    assert blocos[1] == (10, 20, [("1", "1", "2")])
