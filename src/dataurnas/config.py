"""Configurações globais e constantes do sistema."""

from pathlib import Path

# Diretórios
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
JSON_DIR = DATA_DIR / "json"
DB_DIR = DATA_DIR / "db"
SPEC_DIR = PROJECT_ROOT / "spec"

# API do TSE
TSE_BASE_URL = "https://resultados.tse.jus.br/oficial"
TSE_CONFIG_URL = f"{TSE_BASE_URL}/comum/config/ele-c.json"

# Limites de download
MAX_RETRIES = 10
CONNECT_TIMEOUT = 20
READ_TIMEOUT = 30

# Eleições conhecidas
ELECTIONS = {
    "municipal_2024": {
        "ciclo": "ele2024",
        "pleito_1t": "452",
        "pleito_2t": "453",
        "eleicao_1t": "619",
        "eleicao_2t": "620",
        "cargos": {"prefeito": 11, "vereador": 13},
        "spec_version": "v2",
    },
    "presidencial_2022": {
        "ciclo": "ele2022",
        "pleito_1t": "406",
        "pleito_2t": "407",
        "eleicao_1t": "544",
        "eleicao_2t": "545",
        "cargos": {
            "presidente": 1,
            "governador": 3,
            "senador": 5,
            "deputado_federal": 6,
            "deputado_estadual": 7,
        },
        "spec_version": "v1",
    },
}

# Eleição geral de 2026 (1º turno em 04/10/2026, 2º turno em 25/10/2026).
# Spec ASN.1 v2 (arquivos -bu.dat).
ELE2026 = {
    "ciclo": "ele2026",
    "pleito_1t": "3220",
    "eleicao_1t": "6257",  # Eleição Ordinária Federal 2026 1º Turno (Presidente)
    "eleicao_2t": "6258",  # Eleição Ordinária Federal 2026 2º Turno (Presidente)
    "pleito_2t": "3221",
    "data_1t": "04/10/2026",
    "data_2t": "25/10/2026",
    "cargo_presidente": 1,
    "spec_version": "v2",
}
ELECTIONS["geral_2026"] = {
    "ciclo": ELE2026["ciclo"],
    "pleito_1t": ELE2026["pleito_1t"],
    "pleito_2t": ELE2026["pleito_2t"],
    "eleicao_1t": ELE2026["eleicao_1t"],
    "eleicao_2t": ELE2026["eleicao_2t"],
    "cargos": {"presidente": 1},
    "spec_version": ELE2026["spec_version"],
}
PARQUET_DIR = DATA_DIR / "parquet"
PARQUET_2026_DIR = PARQUET_DIR / "2026"

# Todos os estados brasileiros
ESTADOS = [
    "ac", "al", "ap", "am", "ba", "ce", "df", "es", "go", "ma",
    "mt", "ms", "mg", "pa", "pb", "pr", "pe", "pi", "rj", "rn",
    "rs", "ro", "rr", "sc", "sp", "se", "to",
]

# Regiões para amostragem
REGIOES = {
    "norte": ["ac", "am", "ap", "pa", "ro", "rr", "to"],
    "nordeste": ["al", "ba", "ce", "ma", "pb", "pe", "pi", "rn", "se"],
    "centro_oeste": ["df", "go", "ms", "mt"],
    "sudeste": ["es", "mg", "rj", "sp"],
    "sul": ["pr", "rs", "sc"],
}

# Modelos de urna
MODELOS_URNA = {
    9: "UE2009",
    10: "UE2010",
    11: "UE2011",
    13: "UE2013",
    15: "UE2015",
    20: "UE2020",
    22: "UE2022",
}

# Tipos de arquivo
FILE_TYPES_V1 = {
    "bu": ".bu",
    "rdv": ".rdv",
    "log": ".logjez",
    "imgbu": ".imgbu",
    "vscmr": ".vscmr",
}

FILE_TYPES_V2 = {
    "bu": "-bu.dat",
    "rdv": "-rdv.dat",
    "log": "-log.jez",
    "imgbu": "-imgbu.dat",
    "vsc": "-vota.vsc",
}

# Severidades de inconsistência
class Severity:
    CRITICAL = "critica"
    HIGH = "alta"
    MEDIUM = "media"
    INFO = "informativa"

# Códigos de cargo
CARGOS = {
    1: "Presidente",
    3: "Governador",
    5: "Senador",
    6: "Deputado Federal",
    7: "Deputado Estadual",
    11: "Prefeito",
    13: "Vereador",
}

# Offsets de fuso horário em relação a Brasília (UTC-3)
# Logs de urna usam hora local. A votação ocorre das 8h às 17h de Brasília.
# Offset negativo = está atrás de Brasília.
TIMEZONE_OFFSETS = {
    "ac": -2,  # UTC-5 (Acre Time)
    "am": -1,  # UTC-4 (Amazon Time) - exceto leste AM
    "mt": -1,  # UTC-4
    "ms": -1,  # UTC-4
    "ro": -1,  # UTC-4
    "rr": -1,  # UTC-4
    # Fernando de Noronha (PE): +1, mas poucas seções
    # Demais estados: 0 (UTC-3 = Brasília)
}

