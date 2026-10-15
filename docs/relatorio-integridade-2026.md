# Relatório de integridade dos arquivos de urna: 1º turno de 2026

> **Concluída** a conferência de hashes e assinaturas em 499.207 de 499.207 seções instaladas (100,00%), sem erros pendentes, e a auditoria do BU e do log de 2026. A validação da cadeia de certificados, numa amostra, tem a situação própria indicada em [Certificados das urnas](#certificados-das-urnas). Relatório gerado em 15/10/2026 07:09 por `scripts/docs/gerar_relatorio_integridade.py`.

Registro da coleta: gerado em: 2026-10-14T13:41:17.

<p align="center">
  <img src="assets/2026-integridade.svg" alt="Cobertura da verificação de integridade por UF: 499.207 seções verificadas, 1.497.620 SHA-512 iguais ao assinado e 0 divergentes" width="100%">
</p>

## Resultado

- **0 SHA-512 divergentes** em 1.497.620 comparados (BU, RDV e log de cada seção): todo arquivo publicado tem o conteúdo que a urna resumiu e assinou.
- **0 assinaturas inválidas**: 499.207 assinaturas de urna válidas (Ed521: 399.222; ECDSA P-521: 99.985).
- **Votos do BU assinado iguais aos do BU da coleta** em 499.207 seções; 0 diferentes.
- **1 arquivo assinado pela urna e não publicado**: ver [Divergências](#divergências).
- **2.658 arquivos listados e indisponíveis** (HTTP 404), todos fora da conferência de BU, RDV e log: ver [Arquivos listados e indisponíveis](#arquivos-listados-e-indisponíveis-no-servidor-do-tse).
- **Auditoria do BU e do log:** nenhuma ocorrência do grupo 1; ver [Auditoria do BU e do log](#auditoria-do-bu-e-do-log-de-2026).

Os pontos que dependem de esclarecimento do TSE estão reunidos em [relatorio-tse-ocorrencias-2026.md](relatorio-tse-ocorrencias-2026.md).

## Como funciona o mecanismo

Ao encerrar a votação, cada urna grava o Boletim de Urna (`bu.dat`), o Registro Digital do Voto (`rdv.dat`) e o log (`log.jez`). Ela calcula o resumo **SHA-512** de cada um desses arquivos e grava os resumos num arquivo de assinatura (`.vsc`), assinado com a chave privada da própria urna. O TSE publica todos esses arquivos por seção, junto com um `aux.json` que lista os nomes e o diretório de publicação.

A verificação feita pelo projeto, para cada seção:

1. baixa os arquivos publicados e calcula MD5, SHA-256 e SHA-512 de cada um;
2. lê do `.vsc` o SHA-512 assinado de cada arquivo coberto e compara com o calculado (`hash_confere`);
3. verifica a assinatura do `.vsc` com a chave pública do certificado que o acompanha e registra algoritmo, titular, emissor, número de série e SHA-256 do certificado;
4. compara os votos do BU assinado com os do BU lido na coleta de resultados (`votos_conferem`);
5. registra o token do `aux.json` (32 bytes em base64url) e a data e hora informadas pelo TSE.

MD5 e SHA-256 não fazem parte do mecanismo da urna: ficam no catálogo para facilitar conferências com outras fontes. O token do `aux.json` identifica o conjunto publicado e não é o hash de nenhum arquivo isolado; por isso é registrado e não comparado.

## O que fica comprovado e o que não fica

**Comprovado, para cada seção verificada sem divergência:** os arquivos `bu.dat`, `rdv.dat` e `log.jez` publicados pelo TSE têm exatamente o conteúdo cujo SHA-512 está no arquivo de assinatura, e esse arquivo de assinatura foi assinado pela chave correspondente ao certificado que o acompanha.

**Não comprovado por esta verificação:**

- que o software da urna é o oficial, nem que funcionou corretamente;
- que o certificado pertence à urna física daquela seção além do que os campos dele declaram e do que a conferência com a AC emissora mostra (ver [Certificados das urnas](#certificados-das-urnas));
- que os votos registrados correspondem à intenção dos eleitores;
- nada sobre os demais arquivos cujo SHA-512 o `.vsc` também traz (imagem do BU, biometria e outros), que o TSE não publica, nem sobre o próprio `.vsc` além da assinatura.

Uma divergência indica que o arquivo publicado não corresponde ao que a urna assinou e merece investigação; não é, por si só, prova de adulteração (pode haver falha de publicação, de download ou de leitura). Ausência de divergência também não prova a lisura da eleição.

## Totais

| Métrica | Valor |
|---|---:|
| Seções instaladas (oficial) | 499.207 |
| Seções verificadas | 499.207 (100,00%) |
| Seções agregadas a outra | 17.931 |
| Seções não instaladas | 41 |
| Seções sem arquivos publicados | 0 |
| Linhas no resumo por seção | 517.179 |
| Arquivos catalogados | 1.999.485 |
| SHA-512 comparados (BU, RDV e log) | 1.497.620 |
| SHA-512 iguais ao assinado | 1.497.620 (100,00%) |
| SHA-512 diferentes do assinado | 0 |
| Arquivos sem SHA-512 a comparar (o próprio `.vsc`) | 499.207 |
| Arquivos listados e indisponíveis (HTTP 404) | 2.658 |
| Arquivos assinados e não publicados | 1 |
| Assinaturas válidas | 499.207 |
| Assinaturas inválidas | 0 |
| Assinaturas não verificadas | 0 |
| Votos do BU assinado diferentes do BU da coleta | 0 |
| Seções com hash divergente, assinatura inválida ou votos diferentes | 0 |
| Seções com erro pendente na coleta | 0 |

Algoritmo da assinatura de hardware: Ed521: 399.222; ECDSA P-521 com SHA-512: 99.985.

## Por UF

| UF | Nome | Instaladas | Verificadas | Cobertura | SHA-512 conferem | SHA-512 divergem | Assinaturas válidas | Seções divergentes |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| AC | Acre | 2.270 | 2.270 | 100,0% | 6.810 | 0 | 2.270 | 0 |
| AL | Alagoas | 7.101 | 7.101 | 100,0% | 21.303 | 0 | 7.101 | 0 |
| AM | Amazonas | 8.157 | 8.157 | 100,0% | 24.471 | 0 | 8.157 | 0 |
| AP | Amapá | 1.914 | 1.914 | 100,0% | 5.742 | 0 | 1.914 | 0 |
| BA | Bahia | 35.476 | 35.476 | 100,0% | 106.428 | 0 | 35.476 | 0 |
| CE | Ceará | 23.765 | 23.765 | 100,0% | 71.295 | 0 | 23.765 | 0 |
| DF | Distrito Federal | 6.969 | 6.969 | 100,0% | 20.907 | 0 | 6.969 | 0 |
| ES | Espírito Santo | 9.844 | 9.844 | 100,0% | 29.532 | 0 | 9.844 | 0 |
| GO | Goiás | 15.686 | 15.686 | 100,0% | 47.058 | 0 | 15.686 | 0 |
| MA | Maranhão | 18.093 | 18.093 | 100,0% | 54.278 | 0 | 18.093 | 0 |
| MG | Minas Gerais | 52.062 | 52.062 | 100,0% | 156.186 | 0 | 52.062 | 0 |
| MS | Mato Grosso do Sul | 7.106 | 7.106 | 100,0% | 21.318 | 0 | 7.106 | 0 |
| MT | Mato Grosso | 8.287 | 8.287 | 100,0% | 24.861 | 0 | 8.287 | 0 |
| PA | Pará | 20.827 | 20.827 | 100,0% | 62.481 | 0 | 20.827 | 0 |
| PB | Paraíba | 10.712 | 10.712 | 100,0% | 32.136 | 0 | 10.712 | 0 |
| PE | Pernambuco | 21.418 | 21.418 | 100,0% | 64.254 | 0 | 21.418 | 0 |
| PI | Piauí | 10.225 | 10.225 | 100,0% | 30.675 | 0 | 10.225 | 0 |
| PR | Paraná | 27.142 | 27.142 | 100,0% | 81.426 | 0 | 27.142 | 0 |
| RJ | Rio de Janeiro | 37.675 | 37.675 | 100,0% | 113.025 | 0 | 37.675 | 0 |
| RN | Rio Grande do Norte | 8.115 | 8.115 | 100,0% | 24.345 | 0 | 8.115 | 0 |
| RO | Rondônia | 4.698 | 4.698 | 100,0% | 14.094 | 0 | 4.698 | 0 |
| RR | Roraima | 1.519 | 1.519 | 100,0% | 4.557 | 0 | 1.519 | 0 |
| RS | Rio Grande do Sul | 27.547 | 27.547 | 100,0% | 82.641 | 0 | 27.547 | 0 |
| SC | Santa Catarina | 17.326 | 17.326 | 100,0% | 51.978 | 0 | 17.326 | 0 |
| SE | Sergipe | 5.923 | 5.923 | 100,0% | 17.769 | 0 | 5.923 | 0 |
| SP | São Paulo | 103.656 | 103.656 | 100,0% | 310.968 | 0 | 103.656 | 0 |
| TO | Tocantins | 4.384 | 4.384 | 100,0% | 13.152 | 0 | 4.384 | 0 |
| ZZ | Exterior | 1.310 | 1.310 | 100,0% | 3.930 | 0 | 1.310 | 0 |

## Divergências

Nenhuma seção com SHA-512 divergente, assinatura inválida ou votos diferentes nas 499.207 seções verificadas.

O registro `divergencias.jsonl` tem 1 entrada (`arquivo_ausente_tse`: 1), que não alteram o hash de nenhum arquivo publicado e por isso não entram na contagem acima.

### RDV da seção MA/07846/0074/0228: arquivo listado no .vsc, mas não publicado pelo TSE

| Campo | Valor |
|---|---|
| Categoria | `arquivo_ausente_tse` (grupo de leitura 1) |
| Arquivo | `o03220ma0784600740228-rdv.dat` |
| SHA-512 assinado pela urna | `ef182803995b07a03896bc5c5e5d2be9fbe41721fbf30ff239f5a6c777a916de0de450c7f02f51705233b81a289f928ff8be71329de9ddfed80f217ea33f126d` |
| SHA-512 calculado | não calculado (arquivo não publicado) |
| Motivo registrado | arquivo listado no .vsc, mas ausente no aux.json do TSE |
| Token do conjunto (aux.json) | `61myyYeKY7IonxHc6++8r7RavxWF3yY0KkouBRSLERU=` |
| Registrado em | 2026-10-14T06:33:17 |

Endereços para conferência:

```
https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados/ma/07846/0074/0228/p003220-ma-m07846-z0074-s0228-aux.json
https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados/ma/07846/0074/0228/36316d797959654b5937496f6e784863362b2b387237526176785746337959304b6b6f754252534c4552553d/o03220ma0784600740228-rdv.dat
```

Demais arquivos publicados da seção:

| Arquivo | Tipo | SHA-512 x assinado |
|---|---|---|
| `o03220ma0784600740228-bu.dat` | BU | confere |
| `o03220ma0784600740228-log.jez` | log | confere |
| `o03220ma0784600740228-vota.vsc` | arquivo de assinatura (.vsc) | fora da assinatura |

O `aux.json` da seção não lista o arquivo e o endereço dele responde HTTP 404. O BU e o log publicados conferem com o que a urna assinou, a assinatura da urna é válida e os votos do BU assinado são os mesmos do BU da coleta. O que falta é o próprio arquivo na publicação, de modo que ele não pode ser conferido. A categoria pertence ao grupo 1 por definição (a urna assinou um arquivo que não aparece na publicação), mas o quadro é de lacuna de publicação a ser informada ao TSE, sem indício de alteração de conteúdo.

## Arquivos listados e indisponíveis no servidor do TSE

Na passagem final, 2.658 arquivos listados no `aux.json` responderam HTTP 404 (2.658 imagem do BU), em 2.658 seções. O BU, o RDV e o log dessas seções foram baixados e conferidos normalmente. A imagem do BU tem SHA-512 no `.vsc`, como outros arquivos que a urna grava, mas o TSE não a publica nas demais seções e a conferência do projeto cobre o BU, o RDV e o log; nessas seções ela aparece no `aux.json` e o servidor responde 404. Esses arquivos ficam no catálogo com `disponivel = false` e `http_status = 404`. Não é divergência de hash nem de assinatura: o arquivo não pôde ser verificado porque não estava publicado.

| UF | Nome | Arquivos indisponíveis |
|---|---|---:|
| PA | Pará | 1.613 |
| PR | Paraná | 500 |
| MA | Maranhão | 403 |
| BA | Bahia | 135 |
| SP | São Paulo | 4 |
| RS | Rio Grande do Sul | 2 |
| SC | Santa Catarina | 1 |

O registro `ocorrencias_publicacao.jsonl` guarda 2.677 ocorrências, uma por arquivo, anotadas no momento em que o 404 foi visto pela primeira vez, com o status da seção no `aux.json` (Recebida: 2.677) e a data de recebimento informada pelo TSE (05/10/2026: 598; 06/10/2026: 1.241; 07/10/2026: 838). Destas, 2.658 continuavam indisponíveis na passagem final. As outras 19 (PI 19) deixaram de constar no `aux.json`: quando a seção foi verificada de novo, o arquivo já não era listado, e o catálogo registra apenas os quatro arquivos da urna (BU, RDV, log e `.vsc`), todos conferidos. Numa consulta de 14/10/2026 a uma dessas seções, o `aux.json` aparece com status "Totalizada" e sem a imagem do BU. A diferença entre 2.677 e 2.658 é, portanto, de arquivos retirados da lista, não de arquivos que passaram a ser servidos.

Todas as seções afetadas aparecem com status "Recebida" e foram republicadas entre 05 e 07/10/2026. O caso está descrito na [investigação das seções "Recebida"](investigacao-secoes-recebidas-2026.md) e consta da [relação de ocorrências para o TSE](relatorio-tse-ocorrencias-2026.md). Trata-se de lacuna de publicação a ser informada ao TSE, não de evidência de adulteração.

## Auditoria do BU e do log de 2026

> **Concluída.** 499.207 seções com BU e log analisados. 256.306 ocorrências em 159.777 seções. Dados em `data/parquet/2026/auditoria/` (`issues_2026.parquet` e `secoes_log_2026.parquet`).

Cada código pertence a um dos três [grupos de leitura](metodologia.md#grupos-de-leitura), conforme o que pode dizer sobre manipulação. A severidade indica a prioridade de investigar; o grupo, o tipo de conclusão que o achado admite.

| Grupo | Códigos encontrados | Ocorrências | Seções |
|---|---|---:|---:|
| 1. Indício direto de adulteração | nenhum | 0 | 0 |
| 2. Inconsistência a investigar | A03, M03 | 33 | 33 |
| 3. Operacional ou estatístico | A04, A05, C06, I01, I02, I03, I04, I05, I06, M02, M04, M05, M06 | 256.273 | 159.777 |

**Grupo 1 (indício direto de adulteração).** Nenhuma ocorrência de A02, A06, C01, C05 no BU e no log de 2026: nenhum BU com votos acima dos aptos ou do comparecimento, nenhum comparecimento diferente entre cargos e nenhum SHA-512 divergente. Na conferência dos arquivos, as categorias do grupo 1 somam 1 registro: o RDV assinado e não publicado descrito em [Divergências](#divergências).

**Grupo 2 (inconsistência a investigar).** A03 (divergência de votos no log vs bu): 2; M03 (abertura não encontrada no log): 31. Nenhuma ocorrência de A01. As ocorrências de A03 são de seções em que o pacote publicado não traz o log da urna que recebeu parte dos votos; o RDV dessas seções é igual ao BU (ver [investigação log x BU](investigacao-log-bu-2026.md)). As 31 ocorrências de M03 são todas de seções cujo BU veio do sistema de apuração (`busa.dat`, votação por cédula): o log dessas seções é o do equipamento de apuração, que não registra a abertura de votação de uma urna.

**Grupo 3 (operacional ou estatístico).** Descreve como o dia de votação transcorreu (reinícios, horários, proporção de brancos e nulos, abstenção, urna de reserva, liberação sem biometria). Sozinho, não é evidência de manipulação.

| Código | Descrição | Severidade | Grupo | Ocorrências | Seções |
|---|---|---|:---:|---:|---:|
| M03 | Abertura não encontrada no log | média | 2 | 31 | 31 |
| A03 | Divergência de votos no log vs BU | alta | 2 | 2 | 2 |
| I04 | Proporção elevada de brancos | informativa | 3 | 177.616 | 110.757 |
| I03 | Proporção elevada de nulos | informativa | 3 | 35.631 | 33.850 |
| C06 | Reinício durante votação | média | 3 | 23.488 | 23.488 |
| C06 | Reinício durante votação | alta | 3 | 4.767 | 4.767 |
| I05 | Abstenção acima de 40% | informativa | 3 | 3.794 | 2.532 |
| I06 | Urna não padrão (reservaSeção) | informativa | 3 | 3.064 | 3.064 |
| I01 | Eventos de substituição/contingência | informativa | 3 | 2.902 | 2.902 |
| I02 | Alertas de mesário elevados | informativa | 3 | 2.693 | 2.693 |
| A04 | Abertura muito tardia | alta | 3 | 1.015 | 1.015 |
| M04 | Número elevado de erros no log | média | 3 | 563 | 563 |
| M06 | Alta taxa de liberação sem biometria | média | 3 | 533 | 533 |
| A05 | Encerramento antes do horário | alta | 3 | 88 | 88 |
| M05 | Ajustes de hora detectados | média | 3 | 86 | 86 |
| M02 | Encerramento muito tarde | média | 3 | 33 | 33 |

## Certificados das urnas

Cada `.vsc` traz o certificado de hardware da urna que o assinou. A coerência desses certificados entre si e com o BU é conferida em todas as seções verificadas, a partir do catálogo. A validação da cadeia (a assinatura de cada certificado de urna conferida com a chave pública da autoridade certificadora, AC, emissora) é feita por `scripts/ele2026/analisar_certificados.py`. Os certificados públicos das AC usados estão em [`data/certificados/`](../data/certificados/README.md).

### Coerência dos certificados em todas as seções (499.207)

> **Concluída.** Calculada a partir de `secoes.parquet` (SHA-256, titular, emissor e número de série do certificado de cada seção) e do número interno da urna registrado no BU (`secoes_2026.parquet`).

| Métrica | Valor |
|---|---:|
| Seções verificadas com certificado | 499.207 |
| Certificados distintos (SHA-256 do DER) | 499.179 |
| Pares emissor e número de série distintos | 499.179 |
| CN no padrão `UEAO` + 8 dígitos | 499.207 de 499.207 |
| Urnas (número interno do BU) com mais de um certificado | 0 |
| Certificados usados por urnas diferentes | 0 |
| CN igual ao número interno da urna no BU | 499.193 de 499.207 |

| Modelo | AC emissora | Algoritmo da assinatura | Seções |
|---|---|---|---:|
| UE2013 | AC URNA | ECDSA P-521 com SHA-512 | 11.921 |
| UE2015 | AC URNA | ECDSA P-521 com SHA-512 | 88.064 |
| UE2020 | AC UE2020 | Ed521 | 200.463 |
| UE2022 | AC UE2022 | Ed521 | 198.759 |

Cada modelo de urna tem uma única AC emissora e um único algoritmo.

**Certificado em mais de uma seção:** 1 certificado, em 29 seções (ZZ). Todas essas seções têm BU do sistema de apuração (`busa.dat`, votação por cédula), que é emitido e assinado por uma mesma urna de apuração para várias seções; por isso o mesmo certificado aparece em mais de uma seção.

**CN diferente do número interno do BU:** 14 seções. O número interno comparado é o do campo `correspondenciaResultado.carga.numeroInternoUrna` do BU assinado, isto é, a urna para a qual a carga foi gerada. Em todas elas o hash dos arquivos e a assinatura conferem com o certificado que acompanha o `.vsc`. A explicação provável é a urna que votou ser outra que não a da carga original (troca de equipamento antes da votação); é um ponto a confirmar com o TSE, não uma falha de assinatura.

| UF | Código do município | Zona | Seção | CN do certificado | Número interno no BU |
|---|---|---|---|---|---|
| AL | 27057 | 0022 | 0581 | UEAO02072552 | 02073355 |
| BA | 38857 | 0108 | 0148 | ueao01672673 | 01768711 |
| ES | 56472 | 0024 | 0100 | ueao01771857 | 01840092 |
| ES | 56995 | 0053 | 0028 | ueao01656698 | 01677012 |
| ES | 57053 | 0001 | 0046 | UEAO02353044 | 02036425 |
| ES | 57053 | 0001 | 0413 | UEAO02036277 | 02036420 |
| MS | 91570 | 0031 | 0007 | UEAO02152596 | 02150794 |
| PR | 75280 | 0133 | 0034 | UEAO02077196 | 02081583 |
| PR | 76236 | 0093 | 0083 | UEAO02056331 | 02060632 |
| RN | 18813 | 0009 | 0144 | UEAO02052038 | 02348402 |
| SE | 31054 | 0001 | 0346 | ueao01791133 | 01751434 |
| SE | 32417 | 0022 | 0133 | UEAO02273651 | 02044616 |
| SP | 71072 | 0418 | 0073 | UEAO02276282 | 02001951 |
| SP | 71072 | 0418 | 0418 | UEAO02403160 | 02087618 |

### Validação da cadeia de certificados

> **Concluída na amostra de 5%, sorteio determinístico.** Critério do sorteio: SHA-256 da chave uf/cd_mun/zona/secao abaixo do limiar. 24.846 seções processadas, 4,98% das 499.207 seções verificadas no país, em todas as UFs. Situação registrada em `certificados_resumo.json` (gerado em 2026-10-14T13:49:28): "concluído (amostra de 5%)".

**Seções processadas** (`certificados.parquet`): 24.846; assinatura do certificado conferida pela AC: sim: 24.846; nível da cadeia: AC intermediária: 24.846; certificado da urna válido no dia da eleição: sim: 24.846; CN igual ao usuário da assinatura de hardware: sim: 24.846; chaves públicas em urnas diferentes: 0; problemas: 0.

| AC emissora | Modelo | Seções | Emitidos entre | Conferido pela AC | AC válida no dia |
|---|---|---:|---|---|---|
| AC UE2020 | UE2020 | 9.915 | 23/04/2022 a 29/09/2026 | sim: 9.915 | sim: 9.915 |
| AC UE2022 | UE2022 | 9.974 | 19/05/2023 a 09/09/2026 | sim: 9.974 | sim: 9.974 |
| AC URNA | UE2013 | 576 | 30/07/2013 a 19/08/2024 | sim: 576 | não: 576 |
| AC URNA | UE2015 | 4.381 | 14/06/2016 a 17/07/2026 | sim: 4.381 | não: 4.381 |

**Amostra estratificada de arquivos `.vsc`** (400 arquivos): validade no dia da eleição: válidos: 400; chaves públicas em urnas diferentes: 0; cadeia: conferida: 400.

| AC | Emitida por | Validade | Válida em 04/10/2026 | Confere com o resumo digital do TSE |
|---|---|---|---|---|
| AC UE2020 | AC URNA v2 | 05/07/2021 a 01/07/2037 | sim | acue2020.cer |
| AC UE2022 | AC URNA v2 | 28/02/2023 a 24/02/2039 | sim | acue2022.cer |
| AC URNA | AC RAIZ UE | 22/07/2011 a 18/07/2026 | não | não consta |

**Até onde vai a cadeia.** A conferência chega à AC intermediária (AC URNA, AC UE2020 e AC UE2022). Os certificados das raízes (AC RAIZ UE e AC RAIZ UE v2) e da AC URNA v2 não estão disponíveis publicamente para download; o SHA-512 deles, publicado pelo TSE, já está no script, que sobe até a raiz assim que os arquivos forem colocados em `data/certificados/ac/`.

**Observação sobre a AC URNA.** O certificado publicado da AC URNA tem validade até 18/07/2026, antes da eleição, e há certificado de urna emitido depois dessa data cuja assinatura confere com a chave dessa AC (por exemplo, seção `sp-66818-0400-0141`: emitido em 2026-08-03; AC URNA válida de 2011-07-22 a 2026-07-18). A explicação mais provável é um certificado renovado da AC URNA, com a mesma chave, que não foi publicado. É um ponto a esclarecer com o TSE (ver [ocorrências para o TSE](relatorio-tse-ocorrencias-2026.md)), não indício de adulteração.

**Assinatura de software (CEPESC).** O `.vsc` traz também uma assinatura de software feita com algoritmo de governo não publicado; ela não pode ser verificada com informação pública. A conferência acima usa a assinatura de hardware de cada urna.

## Catálogo de hashes por arquivo

O catálogo completo (MD5, SHA-256, SHA-512 calculado, SHA-512 assinado, token e situação de cada arquivo) com 1.999.485 arquivos catalogados não fica no git. Ele está publicado como anexos da versão [v0.2.1](https://github.com/alissonlinneker/DataUrnas-BR/releases/tag/v0.2.1) do projeto, um Parquet por UF (`arquivos_<uf>.parquet`) e um `SHA256SUMS` (28 arquivos Parquet, 359 MB no total).

Baixar e conferir a integridade dos anexos:

```bash
mkdir -p catalogo-2026 && cd catalogo-2026
gh release download v0.2.1 --repo alissonlinneker/DataUrnas-BR --pattern 'arquivos_*.parquet' --pattern SHA256SUMS
sha256sum -c SHA256SUMS            # macOS: shasum -a 256 -c SHA256SUMS
```

Sem o `gh`, baixe só a UF desejada e confira apenas ela:

```bash
curl -LO https://github.com/alissonlinneker/DataUrnas-BR/releases/download/v0.2.1/arquivos_ac.parquet
curl -LO https://github.com/alissonlinneker/DataUrnas-BR/releases/download/v0.2.1/SHA256SUMS
sha256sum -c --ignore-missing SHA256SUMS   # macOS: shasum -a 256 -c --ignore-missing SHA256SUMS
```

Consulta de exemplo com DuckDB:

```python
import duckdb
duckdb.sql("""
    SELECT tipo, count(*) AS arquivos,
           count(*) FILTER (WHERE hash_confere) AS sha512_confere,
           count(*) FILTER (WHERE NOT disponivel) AS indisponiveis
    FROM 'arquivos_*.parquet' GROUP BY tipo ORDER BY tipo
""").show()
```

O painel, na página **Integridade dos arquivos (2026)**, baixa sob demanda o anexo da UF consultada e confere o SHA-256 com o manifesto `data/parquet/2026/integridade/catalogo_manifest.json`.

## Como conferir uma seção por conta própria

Exemplo com a seção 0001 da zona 0009, município 01007 (AC). Troque os códigos para conferir qualquer outra.

1. Baixe o `aux.json` da seção. O campo `hash` é o nome do diretório do conjunto publicado (o token em base64url, escrito em hexadecimal) e `arq` lista os arquivos:

```bash
curl -sO https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados/ac/01007/0009/0001/p003220-ac-m01007-z0009-s0001-aux.json
```

2. Baixe o BU e o arquivo de assinatura (`-vota.vsc`) desse diretório:

```bash
curl -sO https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados/ac/01007/0009/0001/59694651676c4e325569574e6a4c544c39527a6f2b536b496d584a4c676b4e504571677553374f712d506b3d/o03220ac0100700090001-bu.dat
curl -sO https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados/ac/01007/0009/0001/59694651676c4e325569574e6a4c544c39527a6f2b536b496d584a4c676b4e504571677553374f712d506b3d/o03220ac0100700090001-vota.vsc
```

3. Calcule o SHA-512 do arquivo (sem dependências além do Python):

```bash
python3 -c "import hashlib,sys; print(hashlib.sha512(open(sys.argv[1],'rb').read()).hexdigest())" o03220ac0100700090001-bu.dat
# alternativa: shasum -a 512 o03220ac0100700090001-bu.dat
```

4. Leia o SHA-512 que a urna assinou e verifique a assinatura, com o leitor do projeto (`pip install -e .` na raiz do repositório), e compare:

```bash
python3 -c "from dataurnas.parsers.signature import verificar_vsc; r = verificar_vsc(open('o03220ac0100700090001-vota.vsc', 'rb').read()); print('assinatura válida:', r['assinatura_valida'], r['algoritmo'], r['cert_subject']); [print(k, v.hex()) for k, v in r['hashes'].items()]"
```

Para esta seção, o valor assinado do BU registrado no catálogo é:

```
ed99d17488e9ad3c20f4d28e41c2421aff89e91e5c554fbc644f67a88d2fd40bd6fa756193cfc525d6f10e324fc13c8785494fe32eec01c5da09df24df46ad8f
```

O resultado do passo 3 deve ser idêntico ao do passo 4 e ao valor do catálogo (coluna `sha512_assinado` de `arquivos_<uf>.parquet`, ver [Catálogo de hashes por arquivo](#catálogo-de-hashes-por-arquivo)). O painel, na página **Integridade dos arquivos (2026)**, mostra os mesmos valores para qualquer seção.

## Reproduzir este relatório

```bash
python scripts/docs/gerar_relatorio_integridade.py
```

Os dados de entrada ficam em `data/parquet/2026/integridade` (`arquivos_<uf>.parquet`, `secoes.parquet`, `resumo.json`, `divergencias.jsonl`, `ocorrencias_publicacao.jsonl` e `certificados_resumo.json`) e em `data/parquet/2026/auditoria`; o número de seções instaladas vem de `data/parquet/2026/resultado_uf.parquet`. Veja também a [metodologia](metodologia.md#integridade-em-2026) e as [perguntas frequentes](faq.md).
