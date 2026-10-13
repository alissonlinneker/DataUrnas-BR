"""Fixtures sintéticas: BU (ASN.1/BER v1), log 7z e árvore data/raw.

Os arquivos são gerados em tempo de teste a partir da spec oficial em
spec/v1, então não dependem dos 181 GB de dados brutos.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dataurnas.models import SpecVersion  # noqa: E402
from dataurnas.parsers.asn1_helper import get_compiler  # noqa: E402

DEFAULT_VOTOS = {
    # cargo -> lista de (tipoVoto, quantidade, partido, codigo)
    "presidente": [
        ("nominal", 120, 13, 13),
        ("nominal", 100, 22, 22),
        ("branco", 5, None, None),
        ("nulo", 10, None, None),
    ],
    "governador": [
        ("nominal", 150, 44, 44),
        ("nominal", 70, 15, 15),
        ("branco", 10, None, None),
        ("nulo", 5, None, None),
    ],
}


def _ident(municipio: int, zona: int, secao: int) -> dict:
    return {
        "municipioZona": {"municipio": municipio, "zona": zona},
        "local": 1015,
        "secao": secao,
    }


def make_bu_bytes(
    municipio: int = 2291,
    zona: int = 5,
    secao: int = 10,
    aptos: int = 300,
    comparecimento: int = 235,
    votos: dict | None = None,
    tipo_urna: str = "secao",
    lib_codigo: int = 5,
    comp_biometrico: int = 230,
    id_eleicao: int = 544,
) -> bytes:
    """Codifica um BU v1 (EntidadeEnvelopeGenerico com EntidadeBoletimUrna)."""
    votos = DEFAULT_VOTOS if votos is None else votos
    compiler = get_compiler(SpecVersion.V1, "bu")
    ident = _ident(municipio, zona, secao)

    totais = []
    for ordem, (cargo, linhas) in enumerate(votos.items(), start=1):
        votaveis = []
        for tipo, qtd, partido, codigo in linhas:
            vv = {"tipoVoto": tipo, "quantidadeVotos": qtd, "assinatura": b""}
            if codigo is not None:
                vv["identificacaoVotavel"] = {"partido": partido, "codigo": codigo}
            votaveis.append(vv)
        totais.append({
            "codigoCargo": ("cargoConstitucional", cargo),
            "ordemImpressao": ordem,
            "votosVotaveis": votaveis,
        })

    bu = {
        "cabecalho": {
            "dataGeracao": "20221002T170500",
            "idEleitoral": ("idProcessoEleitoral", 406),
        },
        "fase": "oficial",
        "urna": {
            "tipoUrna": tipo_urna,
            "versaoVotacao": "8.26.0.0 - Onca-pintada",
            "correspondenciaResultado": {
                "identificacao": ("identificacaoSecaoEleitoral", ident),
                "carga": {
                    "numeroInternoUrna": 1234567,
                    "numeroSerieFC": b"\x00\x00\x00\x07",
                    "dataHoraCarga": "20220920T101010",
                    "codigoCarga": "123.456.789",
                },
            },
            "tipoArquivo": "votacaoUE",
            "numeroSerieFV": b"\x00\x00\x01\x00",
        },
        "identificacaoSecao": ident,
        "dataHoraEmissao": "20221002T170300",
        "dadosSecaoSA": ("dadosSecao", {
            "dataHoraAbertura": "20221002T070000",
            "dataHoraEncerramento": "20221002T170000",
        }),
        "qtdEleitoresLibCodigo": lib_codigo,
        "qtdEleitoresCompBiometrico": comp_biometrico,
        "resultadosVotacaoPorEleicao": [{
            "idEleicao": id_eleicao,
            "qtdEleitoresAptos": aptos,
            "resultadosVotacao": [{
                "tipoCargo": "majoritario",
                "qtdComparecimento": comparecimento,
                "totaisVotosCargo": totais,
            }],
        }],
        "chaveAssinaturaVotosVotavel": b"",
    }
    conteudo = compiler.encode("EntidadeBoletimUrna", bu)
    envelope = {
        "cabecalho": bu["cabecalho"],
        "fase": "oficial",
        "identificacao": ("identificacaoSecaoEleitoral", ident),
        "tipoEnvelope": "envelopeBoletimUrna",
        "conteudo": bytes(conteudo),
    }
    return bytes(compiler.encode("EntidadeEnvelopeGenerico", envelope))


def log_line(data: str, hora: str, desc: str, sev: str = "INFO", app: str = "VOTA") -> str:
    return f"{data} {hora}\t{sev}\t67305985\t{app}\t{desc}\tABCDEF12"


def make_log_7z(path: Path, lines: list[str]) -> Path:
    """Grava um .logjez (7z com logd.dat) contendo as linhas dadas."""
    import py7zr

    content = ("\r\n".join(lines) + "\r\n").encode("latin-1")
    with py7zr.SevenZipFile(path, "w") as archive:
        archive.writestr(content, "logd.dat")
    return path


def default_log_lines(data: str = "02/10/2022", abertura: str = "07:00:05",
                      encerramento: str = "16:00:30", votos: int = 235) -> list[str]:
    lines = [
        log_line(data, "06:30:00", "Urna ligada em 02/10/2022 as 06:30:00"),
        log_line(data, "06:31:00", "Modelo de Urna: 2020"),
        log_line(data, abertura, "Urna pronta para receber votos"),
    ]
    lines += [log_line(data, "10:00:00", "O voto do eleitor foi computado")] * votos
    lines.append(log_line(data, encerramento, "Início do Encerramento"))
    return lines


@pytest.fixture
def bu_bytes() -> bytes:
    return make_bu_bytes()


@pytest.fixture
def raw_tree(tmp_path) -> Path:
    """data/raw com uma seção de Eirunepé (AM, UTC-5) nos dois turnos."""
    raw = tmp_path / "raw"
    sec = raw / "am" / "02291" / "0005" / "0010"
    sec.mkdir(parents=True)
    (sec / "o00406-0229100050010.bu").write_bytes(make_bu_bytes())
    make_log_7z(sec / "o00406-0229100050010.logjez", default_log_lines())
    t2_votos = {
        "presidente": [
            ("nominal", 130, 13, 13),
            ("nominal", 95, 22, 22),
            ("branco", 4, None, None),
            ("nulo", 6, None, None),
        ],
    }
    (sec / "o00407-0229100050010.bu").write_bytes(
        make_bu_bytes(votos=t2_votos, id_eleicao=545)
    )
    # Log do T2 acumula eventos do T1 (comportamento real da urna)
    make_log_7z(
        sec / "o00407-0229100050010.logjez",
        default_log_lines() + default_log_lines(data="30/10/2022"),
    )

    # Seção de SP (UTC-3) só no 1º turno
    sp = raw / "sp" / "71072" / "0001" / "0001"
    sp.mkdir(parents=True)
    (sp / "o00406-7107200010001.bu").write_bytes(
        make_bu_bytes(municipio=71072, zona=1, secao=1)
    )
    return raw
