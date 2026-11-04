"""Parser of the printed BU image (-imgbu.dat)."""

from dataurnas.parsers.imgbu import parse_imgbu, parse_imgbu_texto

# Excerpt of a real 2026 2nd round -imgbu.dat text (AC, Bujari, zone 9, section 1).
TEXTO = """\
 Justiça Eleitoral
   Tribunal Regional Eleitoral [AC]

           Boletim de Urna

Município                        01007
                BUJARI

Zona Eleitoral                    0009
Local de Votação                  1104
Seção Eleitoral                   0001

Eleitores aptos                   0308
          Originais da seção      0307
          Temporários na seção    0001
Comparecimento                    0232
        Habilitação biométrica    0210
        Habilitação biográfica    0014
        Habilitação sem biometria 0008
Eleitores faltosos                0076

Código identificação UE       02468149
Data de abertura da UE      25/10/2026
Horário de abertura           06:00:01
Data de fechamento da UE    25/10/2026
Horário de fechamento         15:01:33

======================================
    Eleições Gerais Estaduais 2026
======================================

--------------GOVERNADOR--------------
Nome do candidato       Num cand Votos

  ALAN RICK                   10  0049
  MAILZA ASSIS                11  0154

--------------------------------------
Eleitores aptos                   0308
Total de votos Nominais           0203
Brancos                           0005
Nulos                             0024
Total Apurado                     0232

======================================
      Eleição Geral Federal 2026
======================================

--------------PRESIDENTE--------------
Nome do candidato       Num cand Votos

  LULA                        13  0068
  FLAVIO BOLSONARO            22  0149

--------------------------------------
Eleitores aptos                   0308
          Originais da seção      0307
          Temporários na seção    0001
Total de votos Nominais           0217
Brancos                           0002
Nulos                             0013
Total Apurado                     0232

Código Verificador: 0.003.143.276

============= BU DIGITAL =============
--------------PRESIDENTE--------------
  LIXO                        13  9999
"""


def test_header():
    cab = parse_imgbu_texto(TEXTO)["cabecalho"]
    assert cab["municipio"] == 1007 and cab["zona"] == 9 and cab["secao"] == 1
    assert cab["aptos"] == 308 and cab["comparecimento"] == 232
    assert (cab["hab_biometrica"], cab["hab_biografica"], cab["hab_sem_biometria"]) == (210, 14, 8)
    assert cab["faltosos"] == 76 and cab["codigo_ue"] == 2468149
    assert cab["hora_fechamento"] == "15:01:33"


def test_office_blocks_stop_at_digital_bu():
    cargos = parse_imgbu_texto(TEXTO)["cargos"]
    assert len(cargos["PRESIDENTE"]) == 1  # the block after "BU DIGITAL" is ignored
    p = cargos["PRESIDENTE"][0]
    assert p["candidatos"] == {13: 68, 22: 149}
    assert (p["aptos"], p["nominais"], p["brancos"], p["nulos"], p["total_apurado"]) == (
        308, 217, 2, 13, 232)
    assert cargos["GOVERNADOR"][0]["candidatos"] == {10: 49, 11: 154}


def test_bare_text_bytes_fall_back():
    r = parse_imgbu(TEXTO.encode("latin-1"))
    assert r["cargos"]["PRESIDENTE"][0]["candidatos"][22] == 149
