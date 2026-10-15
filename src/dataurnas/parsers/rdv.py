"""Parser do Registro Digital do Voto (RDV), spec v2 (2024+).

O RDV (``-rdv.dat``) guarda cada voto digitado na urna, um registro por
escolha, embaralhado e sem vínculo com o eleitor. Recontar o RDV e comparar
com o BU da mesma seção é a conferência independente mais forte que os
arquivos publicados permitem: o BU é a soma que a urna calculou, o RDV é a
lista de votos de onde essa soma deveria sair.

Estrutura (spec/v2/rdv.asn1, conferida em arquivos reais de 2026):

    EntidadeResultadoRDV ::= SEQUENCE {                 -- arquivo -rdv.dat
        cabecalho  { dataGeracao "YYYYMMDDThhmmss", idEleitoral CHOICE (idPleito 3220) }
        urna       { tipoUrna, versaoVotacao, correspondenciaResultado { identificacao, carga },
                     tipoArquivo, numeroSerieFV, motivoUtilizacaoSA OPTIONAL }
        rdv        EntidadeRegistroDigitalVoto {
            pleito, fase, identificacao { municipioZona { municipio, zona }, local, secao },
            historicoCodigosCarga SEQUENCE OF GeneralString,
            eleicoes CHOICE {
                eleicoesVota [1] SEQUENCE OF { idEleicao, votosCargos }
                eleicoesSA   [2] SEQUENCE OF { idEleicao, tipoCedulaSA, origemVotosSA, votosCargos }
            }
        }
    }
    VotosCargo ::= { idCargo CHOICE, quantidadeEscolhas, votos SEQUENCE OF Voto }
    Voto       ::= { tipoVoto ENUMERATED, digitacao NumericString OPTIONAL }

Diferente do BU, o RDV não vem dentro do EntidadeEnvelopeGenerico: o arquivo
é a própria EntidadeResultadoRDV. Em 2026 o RDV traz duas eleições: 6257
(Presidente) e 6259 (Governador, Senador com duas escolhas, Deputado Federal,
Deputado Estadual ou Distrital). Cada cargo tem ``comparecimento x
quantidadeEscolhas`` registros.

Tipos de voto do RDV e equivalente no BU (spec v2 do BU só tem cinco tipos):

    nominal (2)                       -> nominal, código = digitação
    legenda (1)                       -> legenda, partido = 2 primeiros dígitos
    branco (3), brancoAposSuspensao (5) -> branco
    nulo (4), nuloAposSuspensao (6), nuloPorRepeticao (7) -> nulo
    nuloCargoSemCandidato (8), nuloAposSuspensaoCargoSemCandidato (9)
                                      -> cargoSemCandidato (ou nulo, se o BU
                                         não tiver o tipo para o cargo)

A digitação não existe para os tipos 3, 5, 6, 8 e 9 (comentário do spec).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..models import SpecVersion
from .asn1_helper import get_compiler

ENTIDADE = "EntidadeResultadoRDV"

# CargoConstitucional (mesmos códigos do BU)
CARGOS_RDV: dict[str, int] = {
    "presidente": 1, "vicePresidente": 2, "governador": 3, "viceGovernador": 4,
    "senador": 5, "deputadoFederal": 6, "deputadoEstadual": 7, "deputadoDistrital": 8,
    "primeiroSuplenteSenador": 9, "segundoSuplenteSenador": 10, "prefeito": 11,
    "vicePrefeito": 12, "vereador": 13,
}
NOMES_CARGO: dict[int, str] = {
    1: "Presidente", 2: "Vice-Presidente", 3: "Governador", 4: "Vice-Governador",
    5: "Senador", 6: "Deputado Federal", 7: "Deputado Estadual", 8: "Deputado Distrital",
    9: "1º Suplente Senador", 10: "2º Suplente Senador", 11: "Prefeito",
    12: "Vice-Prefeito", 13: "Vereador",
}

TIPOS_VOTO = (
    "legenda", "nominal", "branco", "nulo", "brancoAposSuspensao", "nuloAposSuspensao",
    "nuloPorRepeticao", "nuloCargoSemCandidato", "nuloAposSuspensaoCargoSemCandidato",
)
# Tipos que, pelo spec, não têm digitação
SEM_DIGITACAO = {"branco", "brancoAposSuspensao", "nuloAposSuspensao",
                 "nuloCargoSemCandidato", "nuloAposSuspensaoCargoSemCandidato"}
# Tipos que precisam de digitação para serem recontados
COM_DIGITACAO = {"nominal", "legenda"}

# Classe de recontagem (comparável com o tipoVoto do BU)
CLASSE_RDV: dict[str, str] = {
    "nominal": "nominal",
    "legenda": "legenda",
    "branco": "branco",
    "brancoAposSuspensao": "branco",
    "nulo": "nulo",
    "nuloAposSuspensao": "nulo",
    "nuloPorRepeticao": "nulo",
    "nuloCargoSemCandidato": "cargoSemCandidato",
    "nuloAposSuspensaoCargoSemCandidato": "cargoSemCandidato",
}


class RDVParseError(ValueError):
    """RDV que não pode ser decodificado com segurança."""


@dataclass
class CargoRDV:
    codigo_cargo: int
    nome_cargo: str
    qtd_escolhas: int
    votos: list[tuple[str, Optional[str]]]  # (tipoVoto, digitacao)

    @property
    def n_registros(self) -> int:
        return len(self.votos)

    def tipos(self) -> Counter:
        return Counter(t for t, _ in self.votos)


@dataclass
class EleicaoRDV:
    id_eleicao: int
    origem: str  # "vota" (urna) ou "sa" (Sistema de Apuração)
    cargos: list[CargoRDV]
    tipo_cedula_sa: Optional[str] = None
    origem_votos_sa: Optional[str] = None


@dataclass
class RegistroDigitalVoto:
    data_geracao: Optional[str]
    id_pleito_cabecalho: Optional[int]
    pleito: int
    fase: str
    municipio: int
    zona: int
    local: int
    secao: int
    tipo_urna: Optional[str]
    tipo_arquivo: Optional[str]
    versao_votacao: Optional[str]
    numero_interno_urna: Optional[int]
    codigo_carga: Optional[str]
    historico_codigos_carga: list[str]
    eleicoes: list[EleicaoRDV] = field(default_factory=list)

    def cargos(self):
        """Itera (id_eleicao, CargoRDV) de todas as eleições."""
        for e in self.eleicoes:
            for c in e.cargos:
                yield e.id_eleicao, c

    def cargos_agregados(self):
        """Itera (id_eleicao, CargoRDV, n_blocos) somando os blocos repetidos do SA.

        O RDV do Sistema de Apuração traz a mesma eleição (ou o mesmo cargo)
        em mais de um bloco, um por urna ou mídia apurada; a seção é a soma
        dos blocos. Só blocos de origem "sa" com a mesma quantidade de
        escolhas são somados. Repetição na urna (origem "vota") continua
        separada e é apontada por validar().
        """
        grupos: dict[tuple[int, int], list[CargoRDV]] = {}
        ordem: list[tuple] = []
        for e in self.eleicoes:
            for c in e.cargos:
                if e.origem == "sa":
                    k = (e.id_eleicao, c.codigo_cargo, c.qtd_escolhas)
                    if k not in grupos:
                        grupos[k] = []
                        ordem.append(("sa", k))
                    grupos[k].append(c)
                else:
                    ordem.append(("vota", (e.id_eleicao, c)))
        for tipo, k in ordem:
            if tipo == "vota":
                yield k[0], k[1], 1
                continue
            blocos = grupos[k]
            if len(blocos) == 1:
                yield k[0], blocos[0], 1
                continue
            b0 = blocos[0]
            votos = [v for b in blocos for v in b.votos]
            yield k[0], CargoRDV(codigo_cargo=b0.codigo_cargo, nome_cargo=b0.nome_cargo,
                                 qtd_escolhas=b0.qtd_escolhas, votos=votos), len(blocos)


def _codigo_cargo(raw) -> int:
    """idCargo é CHOICE: ('cargoConstitucional', 'presidente') ou
    ('numeroCargoConsultaLivre', 25)."""
    if isinstance(raw, tuple) and len(raw) == 2:
        _, val = raw
        if isinstance(val, str):
            if val not in CARGOS_RDV:
                raise RDVParseError(f"cargo desconhecido: {val!r}")
            return CARGOS_RDV[val]
        return int(val)
    return int(raw)


def _eleicoes(raw) -> list[EleicaoRDV]:
    if not (isinstance(raw, tuple) and len(raw) == 2):
        raise RDVParseError("campo eleicoes fora do formato CHOICE")
    escolha, lista = raw
    origem = {"eleicoesVota": "vota", "eleicoesSA": "sa"}.get(escolha)
    if origem is None:
        raise RDVParseError(f"tipo de eleicoes desconhecido: {escolha!r}")
    out = []
    for e in lista:
        cargos = []
        for vc in e.get("votosCargos", []):
            cod = _codigo_cargo(vc.get("idCargo"))
            votos = [(v.get("tipoVoto"), v.get("digitacao")) for v in vc.get("votos", [])]
            cargos.append(CargoRDV(codigo_cargo=cod,
                                   nome_cargo=NOMES_CARGO.get(cod, f"Cargo {cod}"),
                                   qtd_escolhas=int(vc.get("quantidadeEscolhas", 1)),
                                   votos=votos))
        out.append(EleicaoRDV(id_eleicao=int(e.get("idEleicao")), origem=origem, cargos=cargos,
                              tipo_cedula_sa=e.get("tipoCedulaSA"),
                              origem_votos_sa=e.get("origemVotosSA")))
    return out


def parse_rdv_bytes(raw: bytes) -> RegistroDigitalVoto:
    """Decodifica um -rdv.dat (EntidadeResultadoRDV, BER) em memória."""
    comp = get_compiler(SpecVersion.V2, "rdv")
    try:
        ent = comp.decode(ENTIDADE, bytearray(raw))
    except Exception as e:  # asn1tools levanta tipos variados
        raise RDVParseError(f"RDV não decodificado: {e}") from e
    cab = ent.get("cabecalho") or {}
    ide = cab.get("idEleitoral")
    id_pleito_cab = ide[1] if isinstance(ide, tuple) and ide[0] == "idPleito" else None
    urna = ent.get("urna") or {}
    carga = (urna.get("correspondenciaResultado") or {}).get("carga") or {}
    r = ent.get("rdv") or {}
    ident = r.get("identificacao") or {}
    mz = ident.get("municipioZona") or {}
    return RegistroDigitalVoto(
        data_geracao=cab.get("dataGeracao"),
        id_pleito_cabecalho=id_pleito_cab,
        pleito=int(r.get("pleito", 0)),
        fase=str(r.get("fase")),
        municipio=int(mz.get("municipio", 0)),
        zona=int(mz.get("zona", 0)),
        local=int(ident.get("local", 0)),
        secao=int(ident.get("secao", 0)),
        tipo_urna=urna.get("tipoUrna"),
        tipo_arquivo=urna.get("tipoArquivo"),
        versao_votacao=urna.get("versaoVotacao"),
        numero_interno_urna=carga.get("numeroInternoUrna"),
        codigo_carga=carga.get("codigoCarga"),
        historico_codigos_carga=list(r.get("historicoCodigosCarga") or []),
        eleicoes=_eleicoes(r.get("eleicoes")),
    )


def parse_rdv(path: Path) -> RegistroDigitalVoto:
    return parse_rdv_bytes(Path(path).read_bytes())


def recontar(cargo: CargoRDV) -> Counter:
    """Conta os votos de um cargo em chaves comparáveis com o BU.

    Chaves: ("nominal", número), ("legenda", partido), ("branco", None),
    ("nulo", None), ("cargoSemCandidato", None). Registros inválidos (tipo
    desconhecido, digitação ausente ou não numérica em voto nominal ou de
    legenda) vão para ("invalido", tipo) e aparecem em validar().
    """
    c: Counter = Counter()
    for tipo, dig in cargo.votos:
        classe = CLASSE_RDV.get(tipo)
        if classe is None:
            c[("invalido", str(tipo))] += 1
        elif classe in COM_DIGITACAO:
            if not dig or not dig.isdigit():
                c[("invalido", str(tipo))] += 1
            elif classe == "nominal":
                c[("nominal", int(dig))] += 1
            else:  # legenda: o partido são os dois primeiros dígitos digitados
                c[("legenda", int(dig[:2]))] += 1
        else:
            c[(classe, None)] += 1
    return c


def validar(rdv: RegistroDigitalVoto, pleito: Optional[int] = None,
            ident: Optional[dict] = None) -> list[str]:
    """Problemas estruturais do RDV (lista vazia = estrutura íntegra).

    Confere pleito e fase, identificação da seção contra o caminho publicado,
    eleições e cargos repetidos, quantidade de registros múltipla da
    quantidade de escolhas, tipos de voto conhecidos e a regra de digitação
    do spec (ausente nos tipos 3, 5, 6, 8 e 9; numérica de 1 a 5 dígitos nos
    votos nominais e de legenda).
    """
    probs: list[str] = []
    if pleito is not None and rdv.pleito != int(pleito):
        probs.append(f"pleito {rdv.pleito} diferente de {pleito}")
    if rdv.id_pleito_cabecalho is not None and rdv.id_pleito_cabecalho != rdv.pleito:
        probs.append(f"pleito do cabeçalho {rdv.id_pleito_cabecalho} difere de {rdv.pleito}")
    if rdv.fase != "oficial":
        probs.append(f"fase {rdv.fase}")
    if ident:
        for campo, val in (("municipio", ident.get("cd_mun")), ("zona", ident.get("zona")),
                           ("secao", ident.get("secao"))):
            if val is not None and int(val) != getattr(rdv, campo):
                probs.append(f"{campo} {getattr(rdv, campo)} difere do caminho ({int(val)})")
    # Blocos repetidos do Sistema de Apuração (origem "sa") são normais: um
    # por urna ou mídia, somados em cargos_agregados(). Lá a repetição só vira
    # problema se a soma não fechar com o BU (analyzer.rdv_recontagem).
    vistos_e: set[int] = set()
    for e in rdv.eleicoes:
        if e.id_eleicao in vistos_e and e.origem != "sa":
            probs.append(f"eleição {e.id_eleicao} repetida")
        vistos_e.add(e.id_eleicao)
        vistos_c: set[int] = set()
        for c in e.cargos:
            rot = f"{e.id_eleicao}/{c.nome_cargo}"
            if c.codigo_cargo in vistos_c and e.origem != "sa":
                probs.append(f"cargo {rot} repetido")
            vistos_c.add(c.codigo_cargo)
            if c.qtd_escolhas < 1 or c.n_registros % c.qtd_escolhas:
                probs.append(f"{rot}: {c.n_registros} registros não é múltiplo de "
                             f"{c.qtd_escolhas} escolhas")
            ruins: Counter = Counter()
            for tipo, dig in c.votos:
                if tipo not in CLASSE_RDV:
                    ruins[f"tipo desconhecido {tipo!r}"] += 1
                elif tipo in SEM_DIGITACAO and dig:
                    ruins[f"{tipo} com digitação"] += 1
                elif tipo in COM_DIGITACAO and not (dig and dig.isdigit() and len(dig) <= 5):
                    ruins[f"{tipo} sem digitação válida"] += 1
                elif dig is not None and not (dig.isdigit() and 1 <= len(dig) <= 5):
                    ruins[f"{tipo} com digitação inválida"] += 1
            for msg, n in sorted(ruins.items()):
                probs.append(f"{rot}: {n} registro(s) {msg}")
    return probs
