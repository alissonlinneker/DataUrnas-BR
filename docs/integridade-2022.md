# Integridade dos arquivos de urna: eleições de 2022 (1º e 2º turnos)

> **Concluída** a conferência de hashes e assinaturas em 944.051 seções dos dois turnos (56 de 56 pacotes de dados abertos do TSE), com 0 erros pendentes. Relatório gerado em 15/10/2026 07:16 por `scripts/docs/gerar_relatorio_integridade_2022.py`.

Registro da coleta: gerado em 2026-10-15T01:26:15.

## Resultado

- **0 SHA-512 divergentes** em 3.776.042 comparados (BU, RDV, log e imagem do BU de cada seção, ou o BU do sistema de apuração): todo arquivo publicado tem o conteúdo que a urna resumiu e assinou.
- **0 assinaturas inválidas**: 944.051 assinaturas de urna válidas (ECDSA P-521 com SHA-512: 558.715; Ed521: 385.336); 3.776.042 assinaturas por arquivo válidas e 0 inválidas.
- **Votos de Presidente do BU iguais aos da base de 2022** em 941.653 seções; 0 diferentes e 2.398 não conferidas (ver [Observações](#observações)).
- **173 arquivos assinados pela urna e ausentes do pacote do TSE**, em 64 seções: ver [Arquivos assinados e ausentes do pacote do TSE](#arquivos-assinados-e-ausentes-do-pacote-do-tse).
- **Divergências graves** (hash divergente, assinatura inválida ou arquivo sem hash assinado): 0.
- **33 ocorrências de publicação**, todas seções presentes no pacote e ausentes do banco de 2022: ver [Ocorrências de publicação](#ocorrências-de-publicação).

## Fonte e método

Fonte: zips de arquivos de urna do portal de dados abertos do TSE, lidos por faixas de bytes; a API de resultados não serve mais os arquivos de 2022 (HTTP 404). Padrão de URL:

```
https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2022/arqurnatot/bu_imgbu_logjez_rdv_vscmr_2022_<turno>t_<UF>.zip
```

Pleitos: 1º turno 406 (02/10/2022), 2º turno 407 (30/10/2022). Cada zip é lido por faixas de bytes; cada entrada tem o CRC-32 conferido na extração. Para cada seção:

- **SHA-512:** SHA-512 do arquivo publicado comparado ao hash da lista de arquivos assinados no .vscmr (partes SW e HW).
- **Assinatura de hardware:** ECDSA P-521 com SHA-512 (ou Ed521, se o certificado trouxer a chave Ed521); a mensagem assinada é o hash SHA-512 do arquivo. Verificados o autoAssinado (lista inteira) e cada arquivo publicado. r e s vêm como INTEGER de 66 bytes (BER não mínimo) e são recodificados em DER antes da verificação.
- **Assinatura de software:** CEPESC (algoritmo de governo não publicado): não verificada.
- **Cadeia do certificado:** não validada aqui; registramos subject, issuer, serial e SHA-256 do certificado da urna.
- **CRC-32:** CRC-32 de cada entrada do zip conferido na extração.
- **Votos:** votos de Presidente do BU comparados com data/parquet/votos_t*.parquet

O que fica comprovado e o que não fica segue o mesmo raciocínio do [relatório de 2026](relatorio-integridade-2026.md#o-que-fica-comprovado-e-o-que-não-fica): ausência de divergência mostra que o arquivo publicado é o que a urna assinou, e não prova, sozinha, a lisura da eleição; uma divergência pede investigação e não é, por si só, prova de adulteração.

## Totais

| Métrica | 1º turno | 2º turno | Total |
|---|---:|---:|---:|
| Seções verificadas | 472.024 | 472.027 | 944.051 |
| Seções fora do banco de 2022 | 1.038 | 1.026 | 2.064 |
| Arquivos catalogados | 2.359.960 | 2.360.133 | 4.720.093 |
| SHA-512 iguais ao assinado | 1.887.936 | 1.888.106 | 3.776.042 |
| SHA-512 divergentes | 0 | 0 | 0 |
| Arquivos sem SHA-512 a comparar (o próprio .vscmr) | 472.024 | 472.027 | 944.051 |
| Assinaturas de urna válidas | 472.024 | 472.027 | 944.051 |
| Assinaturas de urna inválidas | 0 | 0 | 0 |
| Assinaturas não verificadas | 0 | 0 | 0 |
| Assinaturas por arquivo válidas | 1.887.936 | 1.888.106 | 3.776.042 |
| Assinaturas por arquivo inválidas | 0 | 0 | 0 |
| Votos de Presidente conferem | 470.819 | 470.834 | 941.653 |
| Votos de Presidente divergem | 0 | 0 | 0 |
| Votos não conferidos | 1.205 | 1.193 | 2.398 |

Pacotes processados: 56 de 56 (11 execuções registradas). Seções com status `ok`: 944.051 de 944.051.

### Por tipo de arquivo

| Tipo | Arquivos | Tamanho |
|---|---:|---:|
| arquivo de assinatura (.vscmr) | 944.051 | 58,4 GB |
| log (.logjez) | 944.001 | 100,0 GB |
| RDV | 943.995 | 8,0 GB |
| BU | 943.892 | 6,4 GB |
| imagem do BU | 943.836 | 10,3 GB |
| BU do sistema de apuração | 159 | 0,3 MB |
| outros (sistema de apuração) | 159 | 0,6 MB |

### Algoritmo de assinatura e modelo de urna

| Turno | Item | Valor | Seções |
|---|---|---|---:|
| 1º turno | algoritmo | ECDSA P-521 com SHA-512 | 279.379 |
| 1º turno | algoritmo | Ed521 | 192.645 |
| 1º turno | modelo | UE2009 | 46.690 |
| 1º turno | modelo | UE2010 | 94.368 |
| 1º turno | modelo | UE2011 | 27.537 |
| 1º turno | modelo | UE2013 | 24.987 |
| 1º turno | modelo | UE2015 | 85.797 |
| 1º turno | modelo | UE2020 | 192.645 |
| 1º turno | emissor do certificado | AC UE2020 | 192.645 |
| 1º turno | emissor do certificado | AC URNA | 279.379 |
| 2º turno | algoritmo | ECDSA P-521 com SHA-512 | 279.336 |
| 2º turno | algoritmo | Ed521 | 192.691 |
| 2º turno | modelo | UE2009 | 48.246 |
| 2º turno | modelo | UE2010 | 93.794 |
| 2º turno | modelo | UE2011 | 26.889 |
| 2º turno | modelo | UE2013 | 24.672 |
| 2º turno | modelo | UE2015 | 85.735 |
| 2º turno | modelo | UE2020 | 192.691 |
| 2º turno | emissor do certificado | AC UE2020 | 192.691 |
| 2º turno | emissor do certificado | AC URNA | 279.336 |

## Por UF

### 1º turno

| UF | Seções | Fora do banco | Arquivos | SHA-512 iguais | SHA-512 divergentes | Assinaturas válidas | Assinaturas inválidas | Arquivos ausentes do pacote |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| AC | 2.124 | 0 | 10.620 | 8.496 | 0 | 2.124 | 0 | 0 |
| AL | 6.626 | 0 | 33.130 | 26.504 | 0 | 6.626 | 0 | 0 |
| AM | 7.453 | 4 | 37.267 | 29.814 | 0 | 7.453 | 0 | 0 |
| AP | 1.740 | 0 | 8.700 | 6.960 | 0 | 1.740 | 0 | 0 |
| BA | 34.424 | 2 | 172.120 | 137.696 | 0 | 34.424 | 0 | 1 |
| CE | 22.796 | 2 | 113.981 | 91.185 | 0 | 22.796 | 0 | 0 |
| DF | 6.748 | 0 | 33.740 | 26.992 | 0 | 6.748 | 0 | 0 |
| ES | 9.239 | 0 | 46.195 | 36.956 | 0 | 9.239 | 0 | 0 |
| GO | 14.620 | 0 | 73.100 | 58.480 | 0 | 14.620 | 0 | 0 |
| MA | 16.423 | 0 | 82.113 | 65.690 | 0 | 16.423 | 0 | 2 |
| MG | 49.981 | 2 | 249.904 | 199.923 | 0 | 49.981 | 0 | 1 |
| MS | 6.912 | 1 | 34.561 | 27.649 | 0 | 6.912 | 0 | 0 |
| MT | 7.652 | 1 | 38.260 | 30.608 | 0 | 7.652 | 0 | 0 |
| PA | 18.235 | 1 | 91.175 | 72.940 | 0 | 18.235 | 0 | 0 |
| PB | 9.602 | 0 | 48.010 | 38.408 | 0 | 9.602 | 0 | 0 |
| PE | 20.572 | 2 | 102.860 | 82.288 | 0 | 20.572 | 0 | 0 |
| PI | 8.963 | 0 | 44.815 | 35.852 | 0 | 8.963 | 0 | 0 |
| PR | 25.721 | 3 | 128.605 | 102.884 | 0 | 25.721 | 0 | 0 |
| RJ | 34.068 | 0 | 170.340 | 136.272 | 0 | 34.068 | 0 | 0 |
| RN | 7.674 | 1 | 38.369 | 30.695 | 0 | 7.674 | 0 | 1 |
| RO | 4.198 | 0 | 20.990 | 16.792 | 0 | 4.198 | 0 | 0 |
| RR | 1.268 | 0 | 6.340 | 5.072 | 0 | 1.268 | 0 | 0 |
| RS | 27.201 | 1 | 136.005 | 108.804 | 0 | 27.201 | 0 | 0 |
| SC | 16.242 | 2 | 81.210 | 64.968 | 0 | 16.242 | 0 | 0 |
| SE | 5.498 | 0 | 27.490 | 21.992 | 0 | 5.498 | 0 | 0 |
| SP | 101.073 | 2 | 505.367 | 404.294 | 0 | 101.073 | 0 | 0 |
| TO | 3.957 | 0 | 19.785 | 15.828 | 0 | 3.957 | 0 | 0 |
| ZZ (exterior) | 1.014 | 1.014 | 4.908 | 3.894 | 0 | 1.014 | 0 | 162 |
| **Total** | 472.024 | 1.038 | 2.359.960 | 1.887.936 | 0 | 472.024 | 0 | 167 |

### 2º turno

| UF | Seções | Fora do banco | Arquivos | SHA-512 iguais | SHA-512 divergentes | Assinaturas válidas | Assinaturas inválidas | Arquivos ausentes do pacote |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| AC | 2.124 | 0 | 10.620 | 8.496 | 0 | 2.124 | 0 | 0 |
| AL | 6.626 | 0 | 33.130 | 26.504 | 0 | 6.626 | 0 | 0 |
| AM | 7.453 | 0 | 37.265 | 29.812 | 0 | 7.453 | 0 | 0 |
| AP | 1.740 | 0 | 8.700 | 6.960 | 0 | 1.740 | 0 | 0 |
| BA | 34.424 | 1 | 172.121 | 137.697 | 0 | 34.424 | 0 | 0 |
| CE | 22.796 | 0 | 113.980 | 91.184 | 0 | 22.796 | 0 | 0 |
| DF | 6.748 | 1 | 33.741 | 26.993 | 0 | 6.748 | 0 | 0 |
| ES | 9.239 | 0 | 46.195 | 36.956 | 0 | 9.239 | 0 | 0 |
| GO | 14.620 | 0 | 73.100 | 58.480 | 0 | 14.620 | 0 | 0 |
| MA | 16.423 | 0 | 82.115 | 65.692 | 0 | 16.423 | 0 | 0 |
| MG | 49.981 | 0 | 249.905 | 199.924 | 0 | 49.981 | 0 | 0 |
| MS | 6.912 | 0 | 34.560 | 27.648 | 0 | 6.912 | 0 | 0 |
| MT | 7.652 | 0 | 38.260 | 30.608 | 0 | 7.652 | 0 | 0 |
| PA | 18.235 | 4 | 91.170 | 72.935 | 0 | 18.235 | 0 | 5 |
| PB | 9.602 | 0 | 48.010 | 38.408 | 0 | 9.602 | 0 | 0 |
| PE | 20.572 | 1 | 102.860 | 82.288 | 0 | 20.572 | 0 | 0 |
| PI | 8.963 | 0 | 44.815 | 35.852 | 0 | 8.963 | 0 | 0 |
| PR | 25.721 | 0 | 128.605 | 102.884 | 0 | 25.721 | 0 | 0 |
| RJ | 34.068 | 0 | 170.340 | 136.272 | 0 | 34.068 | 0 | 0 |
| RN | 7.674 | 0 | 38.369 | 30.695 | 0 | 7.674 | 0 | 1 |
| RO | 4.198 | 0 | 20.990 | 16.792 | 0 | 4.198 | 0 | 0 |
| RR | 1.268 | 0 | 6.340 | 5.072 | 0 | 1.268 | 0 | 0 |
| RS | 27.201 | 1 | 136.006 | 108.805 | 0 | 27.201 | 0 | 0 |
| SC | 16.242 | 1 | 81.211 | 64.969 | 0 | 16.242 | 0 | 0 |
| SE | 5.498 | 0 | 27.490 | 21.992 | 0 | 5.498 | 0 | 0 |
| SP | 101.073 | 0 | 505.365 | 404.292 | 0 | 101.073 | 0 | 0 |
| TO | 3.957 | 0 | 19.785 | 15.828 | 0 | 3.957 | 0 | 0 |
| ZZ (exterior) | 1.017 | 1.017 | 5.085 | 4.068 | 0 | 1.017 | 0 | 0 |
| **Total** | 472.027 | 1.026 | 2.360.133 | 1.888.106 | 0 | 472.027 | 0 | 6 |

## Divergências

### Por categoria

| Categoria | Descrição | Arquivos |
|---|---|---:|
| `hash_diverge` | SHA-512 calculado diferente do assinado | 0 |
| `assinatura_invalida` | assinatura da urna inválida | 0 |
| `hash_assinado_ausente` | arquivo publicado sem SHA-512 no .vscmr | 0 |
| `arquivo_ausente_tse` | arquivo listado no .vscmr e ausente do pacote do TSE | 173 |

### Por UF e turno

| Turno | UF | Arquivos | Seções |
|---|---|---:|---:|
| 1º | BA | 1 | 1 |
| 1º | MA | 2 | 1 |
| 1º | MG | 1 | 1 |
| 1º | RN | 1 | 1 |
| 1º | ZZ (exterior) | 162 | 54 |
| 2º | PA | 5 | 5 |
| 2º | RN | 1 | 1 |

Por tipo de arquivo: `.logjez`: 61; `.rdv`: 56; `.imgbu`: 56.

## Arquivos assinados e ausentes do pacote do TSE

Cada linha é um arquivo que a urna listou e assinou no `.vscmr` (com o SHA-512 abaixo) e que não está no zip de dados abertos do TSE da UF e do turno. São 173 arquivos em 64 seções. O arquivo de assinatura dessas seções foi verificado e é válido; o que falta é o próprio arquivo, então não há como conferir o conteúdo. Esta tabela é a base do pedido de esclarecimento ao TSE: publicação dos arquivos ou explicação da ausência. A coluna SHA-512 mostra os 16 primeiros caracteres; o valor completo está em `data/parquet/2022/integridade/divergencias.jsonl` (campo `sha512_assinado`).

| # | Turno | UF | Município | Zona | Seção | Arquivo | SHA-512 assinado (início) |
|---:|---|---|---|---|---|---|---|
| 1 | 1º | BA | 33197 | 0036 | 0015 | `o00406-3319700360015.rdv` | `63bca2ddf61965cf` |
| 2 | 1º | MA | 09237 | 0084 | 0215 | `o00406-0923700840215.imgbu` | `9225a679b5c19bd8` |
| 3 | 1º | MA | 09237 | 0084 | 0215 | `o00406-0923700840215.rdv` | `1cd9a44717a6619f` |
| 4 | 1º | MG | 51390 | 0244 | 0091 | `o00406-5139002440091.logjez` | `b613ea2c7a17237f` |
| 5 | 1º | RN | 16918 | 0054 | 0090 | `o00406-1691800540090.logjez` | `ae829c762c481168` |
| 6 | 1º | ZZ (exterior) | 29955 | 0001 | 0531 | `o00406-2995500010531.imgbu` | `99e3af1090bf8819` |
| 7 | 1º | ZZ (exterior) | 29955 | 0001 | 0531 | `o00406-2995500010531.logjez` | `00a2774045731b44` |
| 8 | 1º | ZZ (exterior) | 29955 | 0001 | 0531 | `o00406-2995500010531.rdv` | `6bf34000fee5e060` |
| 9 | 1º | ZZ (exterior) | 29955 | 0001 | 0535 | `o00406-2995500010535.imgbu` | `acfb487170a7cd24` |
| 10 | 1º | ZZ (exterior) | 29955 | 0001 | 0535 | `o00406-2995500010535.logjez` | `9875de13b08853be` |
| 11 | 1º | ZZ (exterior) | 29955 | 0001 | 0535 | `o00406-2995500010535.rdv` | `3a147498797110c1` |
| 12 | 1º | ZZ (exterior) | 29955 | 0001 | 0538 | `o00406-2995500010538.imgbu` | `16a6e02ca20ba0a1` |
| 13 | 1º | ZZ (exterior) | 29955 | 0001 | 0538 | `o00406-2995500010538.logjez` | `22facd5b303f116f` |
| 14 | 1º | ZZ (exterior) | 29955 | 0001 | 0538 | `o00406-2995500010538.rdv` | `0e4618b1bde01228` |
| 15 | 1º | ZZ (exterior) | 29955 | 0001 | 0539 | `o00406-2995500010539.imgbu` | `332553652f3b2a84` |
| 16 | 1º | ZZ (exterior) | 29955 | 0001 | 0539 | `o00406-2995500010539.logjez` | `aaad3618da949697` |
| 17 | 1º | ZZ (exterior) | 29955 | 0001 | 0539 | `o00406-2995500010539.rdv` | `eb5f38fb79a67045` |
| 18 | 1º | ZZ (exterior) | 29955 | 0001 | 0542 | `o00406-2995500010542.imgbu` | `aa48970110f947d6` |
| 19 | 1º | ZZ (exterior) | 29955 | 0001 | 0542 | `o00406-2995500010542.logjez` | `fb9915bb21506eec` |
| 20 | 1º | ZZ (exterior) | 29955 | 0001 | 0542 | `o00406-2995500010542.rdv` | `0669098fc98e4f62` |
| 21 | 1º | ZZ (exterior) | 29955 | 0001 | 0544 | `o00406-2995500010544.imgbu` | `2896971953e1f0dc` |
| 22 | 1º | ZZ (exterior) | 29955 | 0001 | 0544 | `o00406-2995500010544.logjez` | `f5114ba193072bb3` |
| 23 | 1º | ZZ (exterior) | 29955 | 0001 | 0544 | `o00406-2995500010544.rdv` | `bd54a7cfa09e6bfa` |
| 24 | 1º | ZZ (exterior) | 29955 | 0001 | 0553 | `o00406-2995500010553.imgbu` | `9dc5dd24a57d1135` |
| 25 | 1º | ZZ (exterior) | 29955 | 0001 | 0553 | `o00406-2995500010553.logjez` | `da5f305fe847d5d9` |
| 26 | 1º | ZZ (exterior) | 29955 | 0001 | 0553 | `o00406-2995500010553.rdv` | `946a3ee02cae6836` |
| 27 | 1º | ZZ (exterior) | 29955 | 0001 | 0554 | `o00406-2995500010554.imgbu` | `27d9ee38ff1ddc5e` |
| 28 | 1º | ZZ (exterior) | 29955 | 0001 | 0554 | `o00406-2995500010554.logjez` | `993abdc0bbcdf820` |
| 29 | 1º | ZZ (exterior) | 29955 | 0001 | 0554 | `o00406-2995500010554.rdv` | `276a6fac53dee832` |
| 30 | 1º | ZZ (exterior) | 29955 | 0001 | 0557 | `o00406-2995500010557.imgbu` | `13a4332b9f5e4cc5` |
| 31 | 1º | ZZ (exterior) | 29955 | 0001 | 0557 | `o00406-2995500010557.logjez` | `e8acbfff2f6711b8` |
| 32 | 1º | ZZ (exterior) | 29955 | 0001 | 0557 | `o00406-2995500010557.rdv` | `60d4052ea36429d2` |
| 33 | 1º | ZZ (exterior) | 29955 | 0001 | 0559 | `o00406-2995500010559.imgbu` | `1dfb7a274a3919ac` |
| 34 | 1º | ZZ (exterior) | 29955 | 0001 | 0559 | `o00406-2995500010559.logjez` | `cf5affb3f113ebb9` |
| 35 | 1º | ZZ (exterior) | 29955 | 0001 | 0559 | `o00406-2995500010559.rdv` | `5539cb0da4c9f835` |
| 36 | 1º | ZZ (exterior) | 29955 | 0001 | 0560 | `o00406-2995500010560.imgbu` | `21b4da26c2a63de5` |
| 37 | 1º | ZZ (exterior) | 29955 | 0001 | 0560 | `o00406-2995500010560.logjez` | `3bb32e0f49ac8f90` |
| 38 | 1º | ZZ (exterior) | 29955 | 0001 | 0560 | `o00406-2995500010560.rdv` | `89de7e8002479727` |
| 39 | 1º | ZZ (exterior) | 29955 | 0001 | 0562 | `o00406-2995500010562.imgbu` | `331bc5f8b4ba9f57` |
| 40 | 1º | ZZ (exterior) | 29955 | 0001 | 0562 | `o00406-2995500010562.logjez` | `d7090f360a46bc68` |
| 41 | 1º | ZZ (exterior) | 29955 | 0001 | 0562 | `o00406-2995500010562.rdv` | `c7c9a934c9dbbdae` |
| 42 | 1º | ZZ (exterior) | 29955 | 0001 | 0566 | `o00406-2995500010566.imgbu` | `2b6ad10a0c5c0e61` |
| 43 | 1º | ZZ (exterior) | 29955 | 0001 | 0566 | `o00406-2995500010566.logjez` | `a91dbbc594174ac1` |
| 44 | 1º | ZZ (exterior) | 29955 | 0001 | 0566 | `o00406-2995500010566.rdv` | `f7b004664e5d0e64` |
| 45 | 1º | ZZ (exterior) | 29955 | 0001 | 0567 | `o00406-2995500010567.imgbu` | `a4263d418b041c89` |
| 46 | 1º | ZZ (exterior) | 29955 | 0001 | 0567 | `o00406-2995500010567.logjez` | `7472a64eb05d211a` |
| 47 | 1º | ZZ (exterior) | 29955 | 0001 | 0567 | `o00406-2995500010567.rdv` | `807bf4d6986d51d7` |
| 48 | 1º | ZZ (exterior) | 29955 | 0001 | 0569 | `o00406-2995500010569.imgbu` | `5243f0d5e56d70c3` |
| 49 | 1º | ZZ (exterior) | 29955 | 0001 | 0569 | `o00406-2995500010569.logjez` | `16a7f18d5cfe7b6b` |
| 50 | 1º | ZZ (exterior) | 29955 | 0001 | 0569 | `o00406-2995500010569.rdv` | `dc6003488668bb28` |
| 51 | 1º | ZZ (exterior) | 29955 | 0001 | 0570 | `o00406-2995500010570.imgbu` | `ca4cd2f9f2d0d4fc` |
| 52 | 1º | ZZ (exterior) | 29955 | 0001 | 0570 | `o00406-2995500010570.logjez` | `0d621eaaf31c8bb6` |
| 53 | 1º | ZZ (exterior) | 29955 | 0001 | 0570 | `o00406-2995500010570.rdv` | `ad59de8197d554d5` |
| 54 | 1º | ZZ (exterior) | 29955 | 0001 | 0573 | `o00406-2995500010573.imgbu` | `c79d03fa0747de34` |
| 55 | 1º | ZZ (exterior) | 29955 | 0001 | 0573 | `o00406-2995500010573.logjez` | `2b88ea6c3fa85b60` |
| 56 | 1º | ZZ (exterior) | 29955 | 0001 | 0573 | `o00406-2995500010573.rdv` | `4ef7b2734d0bf4bc` |
| 57 | 1º | ZZ (exterior) | 29955 | 0001 | 0576 | `o00406-2995500010576.imgbu` | `76fba2ff676a31e6` |
| 58 | 1º | ZZ (exterior) | 29955 | 0001 | 0576 | `o00406-2995500010576.logjez` | `1e0d92b152c3d5be` |
| 59 | 1º | ZZ (exterior) | 29955 | 0001 | 0576 | `o00406-2995500010576.rdv` | `47d1c6a0e880df07` |
| 60 | 1º | ZZ (exterior) | 29955 | 0001 | 0579 | `o00406-2995500010579.imgbu` | `c51354eeafc19093` |
| 61 | 1º | ZZ (exterior) | 29955 | 0001 | 0579 | `o00406-2995500010579.logjez` | `91899eca3f760a4c` |
| 62 | 1º | ZZ (exterior) | 29955 | 0001 | 0579 | `o00406-2995500010579.rdv` | `9331e56981def87b` |
| 63 | 1º | ZZ (exterior) | 29955 | 0001 | 0581 | `o00406-2995500010581.imgbu` | `f6de61c34012666b` |
| 64 | 1º | ZZ (exterior) | 29955 | 0001 | 0581 | `o00406-2995500010581.logjez` | `2eaf36bcd468c3a7` |
| 65 | 1º | ZZ (exterior) | 29955 | 0001 | 0581 | `o00406-2995500010581.rdv` | `9ebcdf8db8b77dcc` |
| 66 | 1º | ZZ (exterior) | 29955 | 0001 | 0582 | `o00406-2995500010582.imgbu` | `2539a3b5a854f968` |
| 67 | 1º | ZZ (exterior) | 29955 | 0001 | 0582 | `o00406-2995500010582.logjez` | `518c16475b9a4e96` |
| 68 | 1º | ZZ (exterior) | 29955 | 0001 | 0582 | `o00406-2995500010582.rdv` | `8ec82a48be9e7436` |
| 69 | 1º | ZZ (exterior) | 29955 | 0001 | 0592 | `o00406-2995500010592.imgbu` | `1695019c30be0769` |
| 70 | 1º | ZZ (exterior) | 29955 | 0001 | 0592 | `o00406-2995500010592.logjez` | `86487ddb93522d7f` |
| 71 | 1º | ZZ (exterior) | 29955 | 0001 | 0592 | `o00406-2995500010592.rdv` | `a314900267e76511` |
| 72 | 1º | ZZ (exterior) | 29955 | 0001 | 0594 | `o00406-2995500010594.imgbu` | `e4a785b24d5a3a02` |
| 73 | 1º | ZZ (exterior) | 29955 | 0001 | 0594 | `o00406-2995500010594.logjez` | `d231dfc9080a226f` |
| 74 | 1º | ZZ (exterior) | 29955 | 0001 | 0594 | `o00406-2995500010594.rdv` | `3ba23d5a77bee9ef` |
| 75 | 1º | ZZ (exterior) | 29955 | 0001 | 0598 | `o00406-2995500010598.imgbu` | `27b8dc3eaa7d58b4` |
| 76 | 1º | ZZ (exterior) | 29955 | 0001 | 0598 | `o00406-2995500010598.logjez` | `84c06a75d8ac064f` |
| 77 | 1º | ZZ (exterior) | 29955 | 0001 | 0598 | `o00406-2995500010598.rdv` | `b76950210a288ede` |
| 78 | 1º | ZZ (exterior) | 29955 | 0001 | 0599 | `o00406-2995500010599.imgbu` | `2f1b41657bc03e3c` |
| 79 | 1º | ZZ (exterior) | 29955 | 0001 | 0599 | `o00406-2995500010599.logjez` | `fa63a7edd518e837` |
| 80 | 1º | ZZ (exterior) | 29955 | 0001 | 0599 | `o00406-2995500010599.rdv` | `b46d0c0a669f9401` |
| 81 | 1º | ZZ (exterior) | 29955 | 0001 | 0600 | `o00406-2995500010600.imgbu` | `ca01935b35e7f21c` |
| 82 | 1º | ZZ (exterior) | 29955 | 0001 | 0600 | `o00406-2995500010600.logjez` | `2688ebe53803f40c` |
| 83 | 1º | ZZ (exterior) | 29955 | 0001 | 0600 | `o00406-2995500010600.rdv` | `460f7f63b156574b` |
| 84 | 1º | ZZ (exterior) | 29955 | 0001 | 0605 | `o00406-2995500010605.imgbu` | `d4fc5162f1adf0d0` |
| 85 | 1º | ZZ (exterior) | 29955 | 0001 | 0605 | `o00406-2995500010605.logjez` | `bf8289a608b427e7` |
| 86 | 1º | ZZ (exterior) | 29955 | 0001 | 0605 | `o00406-2995500010605.rdv` | `4fcee4029826916d` |
| 87 | 1º | ZZ (exterior) | 29955 | 0001 | 0606 | `o00406-2995500010606.imgbu` | `482b662972f4d96f` |
| 88 | 1º | ZZ (exterior) | 29955 | 0001 | 0606 | `o00406-2995500010606.logjez` | `c61b94f788780d5e` |
| 89 | 1º | ZZ (exterior) | 29955 | 0001 | 0606 | `o00406-2995500010606.rdv` | `cafb43e3bce95a7f` |
| 90 | 1º | ZZ (exterior) | 29955 | 0001 | 0612 | `o00406-2995500010612.imgbu` | `7723c1c9612932a9` |
| 91 | 1º | ZZ (exterior) | 29955 | 0001 | 0612 | `o00406-2995500010612.logjez` | `8e5fcc179e25332b` |
| 92 | 1º | ZZ (exterior) | 29955 | 0001 | 0612 | `o00406-2995500010612.rdv` | `35eaed54859dc62e` |
| 93 | 1º | ZZ (exterior) | 29955 | 0001 | 0613 | `o00406-2995500010613.imgbu` | `904207a8be48d1fd` |
| 94 | 1º | ZZ (exterior) | 29955 | 0001 | 0613 | `o00406-2995500010613.logjez` | `8738e77caaa4b2f3` |
| 95 | 1º | ZZ (exterior) | 29955 | 0001 | 0613 | `o00406-2995500010613.rdv` | `f25c86814cfd426a` |
| 96 | 1º | ZZ (exterior) | 29955 | 0001 | 0617 | `o00406-2995500010617.imgbu` | `9b5ab1bd62782e3a` |
| 97 | 1º | ZZ (exterior) | 29955 | 0001 | 0617 | `o00406-2995500010617.logjez` | `f952c1a355bd5fea` |
| 98 | 1º | ZZ (exterior) | 29955 | 0001 | 0617 | `o00406-2995500010617.rdv` | `af20ab977eb10022` |
| 99 | 1º | ZZ (exterior) | 29955 | 0001 | 0618 | `o00406-2995500010618.imgbu` | `087b084e7225af88` |
| 100 | 1º | ZZ (exterior) | 29955 | 0001 | 0618 | `o00406-2995500010618.logjez` | `769e5c9c15576493` |
| 101 | 1º | ZZ (exterior) | 29955 | 0001 | 0618 | `o00406-2995500010618.rdv` | `61f78ae34ab9aa0a` |
| 102 | 1º | ZZ (exterior) | 29955 | 0001 | 0620 | `o00406-2995500010620.imgbu` | `46a4534b2a163a93` |
| 103 | 1º | ZZ (exterior) | 29955 | 0001 | 0620 | `o00406-2995500010620.logjez` | `04cf169794e5cdb0` |
| 104 | 1º | ZZ (exterior) | 29955 | 0001 | 0620 | `o00406-2995500010620.rdv` | `46cdb2a304193ca9` |
| 105 | 1º | ZZ (exterior) | 29955 | 0001 | 0621 | `o00406-2995500010621.imgbu` | `68b4f4e1d0c946ed` |
| 106 | 1º | ZZ (exterior) | 29955 | 0001 | 0621 | `o00406-2995500010621.logjez` | `49ed2d191427fc8a` |
| 107 | 1º | ZZ (exterior) | 29955 | 0001 | 0621 | `o00406-2995500010621.rdv` | `3523c8d6ba3816ed` |
| 108 | 1º | ZZ (exterior) | 29955 | 0001 | 0623 | `o00406-2995500010623.imgbu` | `d3294e81a557b72f` |
| 109 | 1º | ZZ (exterior) | 29955 | 0001 | 0623 | `o00406-2995500010623.logjez` | `4dd6e54e4804ad75` |
| 110 | 1º | ZZ (exterior) | 29955 | 0001 | 0623 | `o00406-2995500010623.rdv` | `32fe9b21590b1e46` |
| 111 | 1º | ZZ (exterior) | 29955 | 0001 | 0626 | `o00406-2995500010626.imgbu` | `ed7f27f3534f1882` |
| 112 | 1º | ZZ (exterior) | 29955 | 0001 | 0626 | `o00406-2995500010626.logjez` | `e67694085b5f7329` |
| 113 | 1º | ZZ (exterior) | 29955 | 0001 | 0626 | `o00406-2995500010626.rdv` | `d2ebe3e2bca3c981` |
| 114 | 1º | ZZ (exterior) | 29955 | 0001 | 0628 | `o00406-2995500010628.imgbu` | `e0360c7d2e9af94a` |
| 115 | 1º | ZZ (exterior) | 29955 | 0001 | 0628 | `o00406-2995500010628.logjez` | `a07ab9910f82b395` |
| 116 | 1º | ZZ (exterior) | 29955 | 0001 | 0628 | `o00406-2995500010628.rdv` | `2ad13c1e87ed6a36` |
| 117 | 1º | ZZ (exterior) | 29955 | 0001 | 0632 | `o00406-2995500010632.imgbu` | `3080deb91f34bbc9` |
| 118 | 1º | ZZ (exterior) | 29955 | 0001 | 0632 | `o00406-2995500010632.logjez` | `12cc225c61148665` |
| 119 | 1º | ZZ (exterior) | 29955 | 0001 | 0632 | `o00406-2995500010632.rdv` | `fb1980100754fbc4` |
| 120 | 1º | ZZ (exterior) | 29955 | 0001 | 0634 | `o00406-2995500010634.imgbu` | `d6dd95ed6729ff4e` |
| 121 | 1º | ZZ (exterior) | 29955 | 0001 | 0634 | `o00406-2995500010634.logjez` | `2814aa06ed7c3c6b` |
| 122 | 1º | ZZ (exterior) | 29955 | 0001 | 0634 | `o00406-2995500010634.rdv` | `891506d5710c5165` |
| 123 | 1º | ZZ (exterior) | 29955 | 0001 | 0635 | `o00406-2995500010635.imgbu` | `1b817a3600ae5edc` |
| 124 | 1º | ZZ (exterior) | 29955 | 0001 | 0635 | `o00406-2995500010635.logjez` | `1c3d96896186ac4d` |
| 125 | 1º | ZZ (exterior) | 29955 | 0001 | 0635 | `o00406-2995500010635.rdv` | `35671492f5a7a71e` |
| 126 | 1º | ZZ (exterior) | 29955 | 0001 | 0636 | `o00406-2995500010636.imgbu` | `639d4afea0b961ac` |
| 127 | 1º | ZZ (exterior) | 29955 | 0001 | 0636 | `o00406-2995500010636.logjez` | `3eff4a049b5d83b4` |
| 128 | 1º | ZZ (exterior) | 29955 | 0001 | 0636 | `o00406-2995500010636.rdv` | `ee41bfb570c06d4c` |
| 129 | 1º | ZZ (exterior) | 29955 | 0001 | 0639 | `o00406-2995500010639.imgbu` | `983154eb8589be4e` |
| 130 | 1º | ZZ (exterior) | 29955 | 0001 | 0639 | `o00406-2995500010639.logjez` | `fc2fe4206d95c1cf` |
| 131 | 1º | ZZ (exterior) | 29955 | 0001 | 0639 | `o00406-2995500010639.rdv` | `b23b193876823066` |
| 132 | 1º | ZZ (exterior) | 29955 | 0001 | 1420 | `o00406-2995500011420.imgbu` | `40c600834cfefc45` |
| 133 | 1º | ZZ (exterior) | 29955 | 0001 | 1420 | `o00406-2995500011420.logjez` | `b5dd75802f8941fb` |
| 134 | 1º | ZZ (exterior) | 29955 | 0001 | 1420 | `o00406-2995500011420.rdv` | `66558b282835d821` |
| 135 | 1º | ZZ (exterior) | 29955 | 0001 | 3041 | `o00406-2995500013041.imgbu` | `ae37633296f9677c` |
| 136 | 1º | ZZ (exterior) | 29955 | 0001 | 3041 | `o00406-2995500013041.logjez` | `58f2248000abe238` |
| 137 | 1º | ZZ (exterior) | 29955 | 0001 | 3041 | `o00406-2995500013041.rdv` | `7f4a632f063fd709` |
| 138 | 1º | ZZ (exterior) | 29955 | 0001 | 3073 | `o00406-2995500013073.imgbu` | `2417352c5159ed42` |
| 139 | 1º | ZZ (exterior) | 29955 | 0001 | 3073 | `o00406-2995500013073.logjez` | `a4082591022cca6c` |
| 140 | 1º | ZZ (exterior) | 29955 | 0001 | 3073 | `o00406-2995500013073.rdv` | `009df8825a12642b` |
| 141 | 1º | ZZ (exterior) | 29955 | 0001 | 3080 | `o00406-2995500013080.imgbu` | `277053899e7b5947` |
| 142 | 1º | ZZ (exterior) | 29955 | 0001 | 3080 | `o00406-2995500013080.logjez` | `9218f315f7151387` |
| 143 | 1º | ZZ (exterior) | 29955 | 0001 | 3080 | `o00406-2995500013080.rdv` | `e15d381714bae417` |
| 144 | 1º | ZZ (exterior) | 29955 | 0001 | 3163 | `o00406-2995500013163.imgbu` | `ab7c0ff8a598516f` |
| 145 | 1º | ZZ (exterior) | 29955 | 0001 | 3163 | `o00406-2995500013163.logjez` | `c1b8306e8fde155a` |
| 146 | 1º | ZZ (exterior) | 29955 | 0001 | 3163 | `o00406-2995500013163.rdv` | `514fac9f2a54895c` |
| 147 | 1º | ZZ (exterior) | 29955 | 0001 | 3170 | `o00406-2995500013170.imgbu` | `9b0a55344fde3620` |
| 148 | 1º | ZZ (exterior) | 29955 | 0001 | 3170 | `o00406-2995500013170.logjez` | `3256bb300fe9d9fd` |
| 149 | 1º | ZZ (exterior) | 29955 | 0001 | 3170 | `o00406-2995500013170.rdv` | `bf2d0b027ebc0926` |
| 150 | 1º | ZZ (exterior) | 29955 | 0001 | 3176 | `o00406-2995500013176.imgbu` | `27cc4b9efb4b41cd` |
| 151 | 1º | ZZ (exterior) | 29955 | 0001 | 3176 | `o00406-2995500013176.logjez` | `64c2c7c653b02860` |
| 152 | 1º | ZZ (exterior) | 29955 | 0001 | 3176 | `o00406-2995500013176.rdv` | `b552131a0df8ba4b` |
| 153 | 1º | ZZ (exterior) | 29955 | 0001 | 3363 | `o00406-2995500013363.imgbu` | `d3e7c2b75c6714bc` |
| 154 | 1º | ZZ (exterior) | 29955 | 0001 | 3363 | `o00406-2995500013363.logjez` | `501506d0c7724f34` |
| 155 | 1º | ZZ (exterior) | 29955 | 0001 | 3363 | `o00406-2995500013363.rdv` | `c7836c00fb0476a7` |
| 156 | 1º | ZZ (exterior) | 29955 | 0001 | 3374 | `o00406-2995500013374.imgbu` | `dabd64c7d719ca92` |
| 157 | 1º | ZZ (exterior) | 29955 | 0001 | 3374 | `o00406-2995500013374.logjez` | `9c6db6890372e73c` |
| 158 | 1º | ZZ (exterior) | 29955 | 0001 | 3374 | `o00406-2995500013374.rdv` | `5046c4d18ade0d9d` |
| 159 | 1º | ZZ (exterior) | 29955 | 0001 | 3386 | `o00406-2995500013386.imgbu` | `0ca71a407e88d11a` |
| 160 | 1º | ZZ (exterior) | 29955 | 0001 | 3386 | `o00406-2995500013386.logjez` | `7c9aee57776b30fa` |
| 161 | 1º | ZZ (exterior) | 29955 | 0001 | 3386 | `o00406-2995500013386.rdv` | `fbc2cbbf58e82981` |
| 162 | 1º | ZZ (exterior) | 29955 | 0001 | 3390 | `o00406-2995500013390.imgbu` | `1f873b6afe32ffdd` |
| 163 | 1º | ZZ (exterior) | 29955 | 0001 | 3390 | `o00406-2995500013390.logjez` | `a9156d05acd533bc` |
| 164 | 1º | ZZ (exterior) | 29955 | 0001 | 3390 | `o00406-2995500013390.rdv` | `81302fde38dafe78` |
| 165 | 1º | ZZ (exterior) | 29955 | 0001 | 3394 | `o00406-2995500013394.imgbu` | `6889b3b67ef7715f` |
| 166 | 1º | ZZ (exterior) | 29955 | 0001 | 3394 | `o00406-2995500013394.logjez` | `1b8388f87ace9d77` |
| 167 | 1º | ZZ (exterior) | 29955 | 0001 | 3394 | `o00406-2995500013394.rdv` | `df29c873e578616d` |
| 168 | 2º | PA | 04650 | 0006 | 0059 | `o00407-0465000060059.logjez` | `738c2f690fb194f9` |
| 169 | 2º | PA | 04650 | 0006 | 0060 | `o00407-0465000060060.logjez` | `dc59b0df21e97e9a` |
| 170 | 2º | PA | 04650 | 0006 | 0072 | `o00407-0465000060072.logjez` | `7e401e1beb24b06d` |
| 171 | 2º | PA | 04650 | 0006 | 0109 | `o00407-0465000060109.logjez` | `ad9996a434335015` |
| 172 | 2º | PA | 04650 | 0006 | 0111 | `o00407-0465000060111.logjez` | `d8406812ff0068bd` |
| 173 | 2º | RN | 17655 | 0012 | 0114 | `o00407-1765500120114.imgbu` | `845b9bd8f0615ceb` |

## Ocorrências de publicação

| Categoria | Descrição | Ocorrências |
|---|---|---:|
| `secao_sem_arquivos_no_pacote` | seção do banco sem arquivos no pacote | 0 |
| `secao_fora_do_banco` | seção do pacote ausente do banco de 2022 | 33 |
| `entrada_fora_do_padrao` | entrada do zip fora do padrão de nomes | 0 |
| `entrada_corrompida` | entrada do zip corrompida | 0 |
| `pacote_indisponivel` | pacote indisponível | 0 |

Há 2.064 seções no pacote e fora do banco de 2022: 2.031 do exterior (o banco de 2022 não traz o exterior; não são registradas como ocorrência) e 33 no Brasil, listadas abaixo. Todas foram verificadas normalmente (hash e assinatura); só não há votos da base para comparar.

| Turno | UF | Município | Zona | Seção |
|---|---|---|---|---|
| 1º | AM | 02011 | 0034 | 0027 |
| 1º | AM | 02259 | 0008 | 0116 |
| 1º | AM | 02550 | 0040 | 0454 |
| 1º | AM | 02690 | 0004 | 0129 |
| 1º | BA | 34070 | 0031 | 0259 |
| 1º | BA | 37478 | 0131 | 0222 |
| 1º | CE | 15270 | 0006 | 0206 |
| 1º | CE | 15873 | 0089 | 0181 |
| 1º | MG | 47872 | 0167 | 0041 |
| 1º | MG | 49050 | 0196 | 0173 |
| 1º | MS | 90735 | 0043 | 0027 |
| 1º | MT | 98191 | 0027 | 0126 |
| 1º | PA | 04839 | 0023 | 0707 |
| 1º | PE | 23493 | 0099 | 0039 |
| 1º | PE | 25313 | 0005 | 0054 |
| 1º | PR | 74039 | 0048 | 0013 |
| 1º | PR | 75043 | 0188 | 0166 |
| 1º | PR | 76678 | 0042 | 0329 |
| 1º | RN | 17434 | 0030 | 0077 |
| 1º | RS | 87378 | 0062 | 0035 |
| 1º | SC | 81744 | 0054 | 0167 |
| 1º | SC | 82210 | 0106 | 0006 |
| 1º | SP | 61557 | 0299 | 0242 |
| 1º | SP | 71838 | 0407 | 0205 |
| 2º | BA | 37877 | 0105 | 0083 |
| 2º | DF | 97012 | 0009 | 0011 |
| 2º | PA | 04898 | 0099 | 0017 |
| 2º | PA | 04898 | 0099 | 0018 |
| 2º | PA | 04898 | 0099 | 0019 |
| 2º | PA | 04898 | 0099 | 0055 |
| 2º | PE | 26212 | 0075 | 0135 |
| 2º | RS | 89192 | 0054 | 0013 |
| 2º | SC | 83011 | 0046 | 0022 |

## Cadeia de certificados (amostra de 5%)

Conferência concluída: 47.230 de 47.230 seções sorteadas (5,00% das 944.051 seções dos dois turnos), 47.230 com certificado lido do arquivo de assinatura (46.104 certificados distintos; 1.126 aparecem em mais de uma seção, 1.125 só porque a mesma urna foi sorteada nos dois turnos, e 1 em seções do mesmo turno: a urna do sistema de apuração (`.vscsa`) que assina várias seções do exterior). Gerado em 2026-10-15T03:16:38 por `scripts/ele2022/analisar_certificados.py`.

- **Amostra:** estratificada por turno e UF (inclusive o exterior), 5% de cada estrato arredondado para cima. Dentro do estrato entram as seções de menor SHA-256 de `<semente>|<turno>|<uf>|<cd_mun>|<zona>|<secao>`, com **semente 20221002**. O sorteio não depende de biblioteca nem de máquina e pode ser refeito por qualquer pessoa.
- **Leitura:** só o arquivo de assinatura de cada seção (`.vscmr`; `.vscsa` nas seções do sistema de apuração), por faixas de bytes do zip de dados abertos, descompactado em memória com o CRC-32 conferido. Nada bruto vai para o disco. `.vscmr`: 47.225; `.vscsa`: 5.
- **Certificado da urna assinado pela AC emissora:** 47.230 de 47.230 (sim: 47.230).
- **Chave pública do certificado valida a assinatura de hardware do `.vscmr`:** 47.230 de 47.230 (sim: 47.230).
- **Certificado da urna válido no dia do turno:** sim: 47.230. **Uso de chave** (digitalSignature, sem keyCertSign, sem CA): sim: 47.230.
- **AC emissora:** válida no dia do turno: sim: 47.230; autoridade com keyCertSign: sim: 47.230; certificado da urna emitido dentro da validade da AC: sim: 47.230.
- **CN igual ao usuário da assinatura:** sim: 47.230. **SHA-256 do certificado igual ao de `secoes.parquet`:** sim: 47.230.
- **Nenhuma falha crítica:** nenhuma cadeia inválida e nenhuma assinatura que deixe de fechar com o certificado da urna.

| AC emissora | Modelo | Chave | Seções | Emissor da AC | Emissão | Validade mínima |
|---|---|---|---:|---|---|---|
| AC UE2020 | UE2020 | Ed521 | 19.258 | AC URNA v2 | 2022-04-23 a 2022-09-29 | 2035-12-31 |
| AC URNA | UE2009 | ECDSA | 4.786 | AC RAIZ UE | 2012-06-28 a 2020-11-04 | 2026-03-07 |
| AC URNA | UE2010 | ECDSA | 9.538 | AC RAIZ UE | 2012-05-23 a 2018-09-26 | 2026-01-30 |
| AC URNA | UE2011 | ECDSA | 2.599 | AC RAIZ UE | 2012-06-19 a 2022-05-17 | 2026-02-26 |
| AC URNA | UE2013 | ECDSA | 2.474 | AC RAIZ UE | 2013-07-30 a 2022-08-02 | 2027-04-08 |
| AC URNA | UE2015 | ECDSA | 8.575 | AC RAIZ UE | 2016-06-14 a 2022-09-19 | 2030-02-21 |

Certificados de AC usados (pasta `data/certificados/ac`, origem e conferência em `data/certificados/README.md`):

| AC | Emissor | Validade | Usada em 2022 | Válida em 2022 | SHA-256 (DER) |
|---|---|---|---|---|---|
| AC UE2020 | AC URNA v2 | 2021-07-05 a 2037-07-01 | sim | 1T: sim, 2T: sim | `77f31bef3d8eb35f0cc969a2b9bba3ff2a498cc339d29a375d3181e0547c0376` |
| AC UE2022 | AC URNA v2 | 2023-02-28 a 2039-02-24 | não (emitida depois de 2022) | 1T: não, 2T: não | `6ae65790dae7cc5d97394e461204744c8e2f7a810d0303af828d4d3dbecfa293` |
| AC URNA | AC RAIZ UE | 2011-07-22 a 2026-07-18 | sim | 1T: sim, 2T: sim | `dc20a4c3b8aef01794b80efe8e143e1fbf719707e00bb0d4ba8865191dc2731d` |

**Raiz não conferida.** Cada `.vscmr` traz só o certificado da urna. As AC superiores (AC RAIZ UE, emissora da AC URNA; AC URNA v2 e AC RAIZ UE v2, acima da AC UE2020) não são publicadas em endereço que se possa baixar, então a cadeia é conferida até a AC intermediária (`nivel_cadeia = intermediaria`). Tentativas em 15/10/2026: `http://dpc.acue2020.tse.jus.br/acraizue.crt` (HTTP 403); `http://dpc.acue2020.tse.jus.br/acurnav2.crt` (HTTP 403); `https://dpc.acue2020.tse.jus.br/acraizue.crt` (sem resposta (HTTPS)); `http://dpc.acraizue.tse.jus.br/` (HTTP 403); `http://lcr.acraizue.tse.jus.br/` (HTTP 403). O TSE publica o SHA-512 desses arquivos no resumo digital do HOLOCRON de 2026, o que permite conferi-los byte a byte quando forem obtidos; basta colocá-los em `data/certificados/ac` e rodar o script de novo.

## Observações

- **Votos não conferidos (2.398):** 2.064 são seções fora do banco; as outras 334 estão no banco, mas a base Parquet (`votos_t*.parquet`) não traz votos de Presidente para elas (traz os demais cargos): 1º turno BA: 167; 2º turno BA: 166; 2º turno GO: 1. É uma lacuna da base do projeto, não do arquivo da urna; o hash e a assinatura dessas seções conferem.
- **Certificado com CN diferente do usuário registrado (2 seções):** a assinatura é válida; o nome comum do certificado difere do identificador de usuário gravado no arquivo de assinatura. Seções: `1T/se/31690/0012/0018` (UE2013: CN do certificado (ueao01654951) difere do usuário (ueao01308856)); `2T/mg/40720/0167/0080` (UE2010: CN do certificado (ueao01221893) difere do usuário (ueao01241440)).
- **Assinatura de software (CEPESC):** algoritmo de governo não publicado; não verificada.
- **Cadeia de certificados:** conferida numa amostra de 5% (ver [Cadeia de certificados](#cadeia-de-certificados-amostra-de-5)); subject, emissor, número de série e SHA-256 do certificado de cada urna ficam em `secoes.parquet`.

## Catálogo de hashes por arquivo

O catálogo por arquivo (4.720.093 linhas em 58 arquivos Parquet, 894,5 MB, um por turno e UF, `arquivos_t<turno>_<uf>.parquet`) não fica no git, como em 2026. Colunas: `turno`, `uf`, `cd_mun`, `zona`, `secao`, `tipo`, `nome`, `tamanho`, `md5`, `sha256`, `sha512`, `sha512_assinado`, `hash_confere`, `assinatura_arquivo_valida`, `crc32`, `data_hora_zip`. O manifesto com o SHA-256 de cada anexo está em `data/parquet/2022/integridade/catalogo_manifest.json`.
Publicado como anexos da versão [v0.2.2](https://github.com/alissonlinneker/DataUrnas-BR/releases/tag/v0.2.2), com `SHA256SUMS` para conferência (`sha256sum -c SHA256SUMS`).

## Pacotes do TSE

| Turno | UF | Seções | Entradas | Tamanho | Last-Modified |
|---|---|---:|---:|---:|---|
| 1º | AC | 2.124 | 10.621 | 311,0 MB | Thu, 06 Oct 2022 20:00:41 GMT |
| 1º | AL | 6.626 | 33.131 | 1,1 GB | Thu, 06 Oct 2022 20:01:58 GMT |
| 1º | AM | 7.453 | 37.268 | 1,2 GB | Thu, 06 Oct 2022 20:02:59 GMT |
| 1º | AP | 1.740 | 8.701 | 273,0 MB | Thu, 06 Oct 2022 20:04:55 GMT |
| 1º | BA | 34.424 | 172.121 | 5,6 GB | Thu, 06 Oct 2022 20:45:11 GMT |
| 1º | CE | 22.796 | 113.982 | 3,5 GB | Thu, 06 Oct 2022 21:10:26 GMT |
| 1º | DF | 6.748 | 33.741 | 1,1 GB | Fri, 07 Oct 2022 05:22:59 GMT |
| 1º | ES | 9.239 | 46.196 | 1,3 GB | Thu, 06 Oct 2022 21:20:18 GMT |
| 1º | GO | 14.620 | 73.101 | 2,4 GB | Thu, 06 Oct 2022 21:37:49 GMT |
| 1º | MA | 16.423 | 82.114 | 2,5 GB | Thu, 06 Oct 2022 21:56:58 GMT |
| 1º | MG | 49.981 | 249.905 | 7,6 GB | Thu, 06 Oct 2022 22:58:37 GMT |
| 1º | MS | 6.912 | 34.562 | 1,0 GB | Thu, 06 Oct 2022 23:06:47 GMT |
| 1º | MT | 7.652 | 38.261 | 1,1 GB | Thu, 06 Oct 2022 23:15:44 GMT |
| 1º | PA | 18.235 | 91.176 | 2,9 GB | Thu, 06 Oct 2022 23:37:25 GMT |
| 1º | PB | 9.602 | 48.011 | 1,5 GB | Thu, 06 Oct 2022 23:48:55 GMT |
| 1º | PE | 20.572 | 102.861 | 3,4 GB | Fri, 07 Oct 2022 00:14:29 GMT |
| 1º | PI | 8.963 | 44.816 | 1,4 GB | Fri, 07 Oct 2022 00:25:07 GMT |
| 1º | PR | 25.721 | 128.606 | 4,1 GB | Fri, 07 Oct 2022 00:55:22 GMT |
| 1º | RJ | 34.068 | 170.341 | 5,8 GB | Fri, 07 Oct 2022 01:39:18 GMT |
| 1º | RN | 7.674 | 38.370 | 1,3 GB | Fri, 07 Oct 2022 01:48:45 GMT |
| 1º | RO | 4.198 | 20.991 | 625,9 MB | Fri, 07 Oct 2022 01:53:35 GMT |
| 1º | RR | 1.268 | 6.341 | 186,4 MB | Fri, 07 Oct 2022 01:55:01 GMT |
| 1º | RS | 27.201 | 136.006 | 4,3 GB | Fri, 07 Oct 2022 02:28:17 GMT |
| 1º | SC | 16.242 | 81.211 | 2,6 GB | Fri, 07 Oct 2022 02:49:23 GMT |
| 1º | SE | 5.498 | 27.491 | 856,0 MB | Fri, 07 Oct 2022 02:56:16 GMT |
| 1º | SP | 101.073 | 505.368 | 16,5 GB | Fri, 07 Oct 2022 05:10:11 GMT |
| 1º | TO | 3.957 | 19.786 | 585,8 MB | Fri, 07 Oct 2022 05:14:47 GMT |
| 1º | ZZ (exterior) | 1.014 | 4.909 | 79,9 MB | Fri, 07 Oct 2022 05:23:37 GMT |
| 2º | AC | 2.124 | 10.621 | 366,8 MB | Wed, 02 Nov 2022 21:41:12 GMT |
| 2º | AL | 6.626 | 33.131 | 1,4 GB | Wed, 02 Nov 2022 21:41:16 GMT |
| 2º | AM | 7.453 | 37.266 | 1,5 GB | Wed, 02 Nov 2022 21:41:23 GMT |
| 2º | AP | 1.740 | 8.701 | 318,0 MB | Wed, 02 Nov 2022 21:41:25 GMT |
| 2º | BA | 34.424 | 172.122 | 7,3 GB | Wed, 02 Nov 2022 21:42:05 GMT |
| 2º | CE | 22.796 | 113.981 | 4,4 GB | Wed, 02 Nov 2022 21:42:22 GMT |
| 2º | DF | 6.748 | 33.742 | 1,3 GB | Wed, 02 Nov 2022 21:48:36 GMT |
| 2º | ES | 9.239 | 46.196 | 1,5 GB | Wed, 02 Nov 2022 21:42:30 GMT |
| 2º | GO | 14.620 | 73.101 | 2,9 GB | Wed, 02 Nov 2022 21:42:42 GMT |
| 2º | MA | 16.423 | 82.116 | 3,1 GB | Wed, 02 Nov 2022 21:42:56 GMT |
| 2º | MG | 49.981 | 249.906 | 9,3 GB | Wed, 02 Nov 2022 21:43:43 GMT |
| 2º | MS | 6.912 | 34.561 | 1,3 GB | Wed, 02 Nov 2022 21:43:50 GMT |
| 2º | MT | 7.652 | 38.261 | 1,4 GB | Wed, 02 Nov 2022 21:43:56 GMT |
| 2º | PA | 18.235 | 91.171 | 3,5 GB | Wed, 02 Nov 2022 21:44:11 GMT |
| 2º | PB | 9.602 | 48.011 | 2,0 GB | Wed, 02 Nov 2022 21:44:19 GMT |
| 2º | PE | 20.572 | 102.861 | 4,3 GB | Wed, 02 Nov 2022 21:44:39 GMT |
| 2º | PI | 8.963 | 44.816 | 1,7 GB | Wed, 02 Nov 2022 21:44:47 GMT |
| 2º | PR | 25.721 | 128.606 | 5,1 GB | Wed, 02 Nov 2022 21:45:11 GMT |
| 2º | RJ | 34.068 | 170.341 | 7,0 GB | Wed, 02 Nov 2022 21:45:45 GMT |
| 2º | RN | 7.674 | 38.370 | 1,6 GB | Wed, 02 Nov 2022 21:45:51 GMT |
| 2º | RO | 4.198 | 20.991 | 790,5 MB | Wed, 02 Nov 2022 21:45:55 GMT |
| 2º | RR | 1.268 | 6.341 | 214,8 MB | Wed, 02 Nov 2022 21:45:56 GMT |
| 2º | RS | 27.201 | 136.007 | 5,5 GB | Wed, 02 Nov 2022 21:46:26 GMT |
| 2º | SC | 16.242 | 81.212 | 3,4 GB | Wed, 02 Nov 2022 21:46:39 GMT |
| 2º | SE | 5.498 | 27.491 | 1,1 GB | Wed, 02 Nov 2022 21:46:45 GMT |
| 2º | SP | 101.073 | 505.366 | 20,2 GB | Wed, 02 Nov 2022 21:48:28 GMT |
| 2º | TO | 3.957 | 19.786 | 720,3 MB | Wed, 02 Nov 2022 21:48:32 GMT |
| 2º | ZZ (exterior) | 1.017 | 5.086 | 108,5 MB | Wed, 02 Nov 2022 21:48:37 GMT |

## Reproduzir este relatório

```bash
python scripts/ele2022/fetch_integridade.py --so-consolidar   # refaz resumo.json a partir das partes
python scripts/ele2022/registrar_metadados_integridade.py --gravar
python scripts/ele2022/analisar_certificados.py --so-consolidar   # cadeia de certificados (amostra)
python scripts/docs/gerar_relatorio_integridade_2022.py
```

Os dados de entrada ficam em `data/parquet/2022/integridade`. Veja também a [metodologia](metodologia.md) e o [relatório de 2026](relatorio-integridade-2026.md).
