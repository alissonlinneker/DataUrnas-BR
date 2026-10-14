# Pedido de esclarecimentos ao TSE: arquivos de urna do 1º turno de 2026

**Assunto:** pedido de esclarecimento sobre a publicação de arquivos de urna e sobre certificados da cadeia de certificação das urnas, Eleições Gerais de 2026, Presidente, 1º turno (eleição 6257, pleito 3220).

**Origem:** projeto DataUrnas-BR, auditoria independente dos arquivos públicos da urna eletrônica (<https://github.com/alissonlinneker/DataUrnas-BR>).

**Data de referência:** 14/10/2026.

## 1. Contexto

Entre 13 e 14/10/2026, o projeto baixou do portal de resultados do TSE (`https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/`) os arquivos de urna de todas as 499.207 seções instaladas e conferiu, seção a seção, o SHA-512 do Boletim de Urna (BU), do Registro Digital do Voto (RDV) e do log com o valor assinado pela urna no arquivo de assinatura (`-vota.vsc`), além da assinatura de hardware de cada urna.

O resultado foi integralmente coerente: 1.497.620 SHA-512 iguais ao valor assinado, nenhum divergente; 499.207 assinaturas válidas, nenhuma inválida; votos de cada BU assinado iguais aos do BU da coleta de resultados; soma dos BUs igual ao resultado oficial em todas as UFs e no exterior. Os detalhes estão no [relatório de integridade](relatorio-integridade-2026.md).

Os itens abaixo **não indicam divergência de conteúdo** em nenhum arquivo. Referem-se a arquivos listados ou assinados que não estão disponíveis para download e a certificados da cadeia de certificação que não estão publicados. Solicita-se esclarecimento para que a conferência pública possa ser completada.

Convenção dos endereços: cada seção tem um `aux.json` em `.../dados/<uf>/<município>/<zona>/<seção>/p003220-<uf>-m<município>-z<zona>-s<seção>-aux.json`; os arquivos ficam no subdiretório cujo nome é o campo `hash` desse `aux.json`.

## 2. RDV assinado pela urna e não publicado

| Campo | Valor |
|---|---|
| Seção | MA, Lagoa Grande do Maranhão (município 07846), zona 0074, seção 0228 |
| Arquivo | `o03220ma0784600740228-rdv.dat` |
| SHA-512 assinado no `.vsc` | `ef182803995b07a03896bc5c5e5d2be9fbe41721fbf30ff239f5a6c777a916de0de450c7f02f51705233b81a289f928ff8be71329de9ddfed80f217ea33f126d` |
| Token do conjunto | `61myyYeKY7IonxHc6++8r7RavxWF3yY0KkouBRSLERU=` |
| Status no `aux.json` | seção "Totalizada", conjunto "Totalizado", recebido em 04/10/2026 20:28:55 |

Endereços:

```
https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados/ma/07846/0074/0228/p003220-ma-m07846-z0074-s0228-aux.json
https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados/ma/07846/0074/0228/36316d797959654b5937496f6e784863362b2b387237526176785746337959304b6b6f754252534c4552553d/o03220ma0784600740228-rdv.dat
```

O arquivo de assinatura da seção traz o SHA-512 do `rdv.dat`, mas o `aux.json` lista apenas o log, o `.vsc` e o BU, e o endereço do RDV responde HTTP 404 (consulta de 14/10/2026). O BU e o log publicados conferem com os valores assinados, a assinatura da urna é válida e os votos do BU coincidem com os da totalização. É o único caso desse tipo entre as 499.207 seções.

**Pedidos:**

1. Informar se o RDV dessa seção foi recebido pelo TSE e por que não consta do `aux.json`.
2. Publicar o arquivo, caso disponível, para que o SHA-512 possa ser conferido com o valor assinado pela urna.

## 3. Imagens do BU listadas e indisponíveis em seções com status "Recebida"

Em 2.658 seções, o `aux.json` lista a imagem do BU (`-imgbu.dat`) e o endereço do arquivo responde HTTP 404. Todas têm status de seção "Recebida" e status de conjunto "Recebido", com data de recebimento entre 05 e 07/10/2026, posterior à geração do resultado oficial (05/10/2026 12:51:05). O BU, o RDV, o log e o `.vsc` dessas seções estão publicados e conferem com o que a urna assinou, e os votos delas estão contidos no resultado oficial.

| UF | Seções |
|---|---:|
| PA | 1.613 |
| PR | 500 |
| MA | 403 |
| BA | 135 |
| SP | 4 |
| RS | 2 |
| SC | 1 |
| **Total** | **2.658** |

Exemplo (Tambaú, SP, município 71676, zona 0116, seção 0112, recebida em 06/10/2026 18:06:30):

```
https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados/sp/71676/0116/0112/p003220-sp-m71676-z0116-s0112-aux.json
https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados/sp/71676/0116/0112/7534794c4958686541667a64674973447049436753397a4e377773796d415a4571673254686f48527174593d/o03220sp7167601160112-imgbu.dat
```

A relação completa, com UF, município, zona, seção, nome do arquivo, endereço da seção, status e data de recebimento informados no `aux.json`, está em `data/parquet/2026/integridade/ocorrencias_publicacao.jsonl` no repositório do projeto. Esse registro tem 2.677 entradas: além das 2.658 acima, 19 seções do PI (municípios 11770, 10685 e 12190) apresentaram a mesma situação e, em consulta de 14/10/2026, passaram a constar com status "Totalizada", `aux.json` gerado em 14/10/2026 e sem a imagem do BU na lista; em 3 delas a data de recebimento do conjunto também mudou. Em amostra de 20 seções das demais, o status continuava "Recebida" com a imagem listada.

Nessas seções o `aux.json` difere do das seções "Totalizada" também na forma: não traz o campo `idg` e usa `f = "O"` (maiúsculo). A análise completa está em [investigacao-secoes-recebidas-2026.md](investigacao-secoes-recebidas-2026.md).

**Pedidos:**

1. Informar o hash e o conjunto de arquivos do pacote efetivamente usado na totalização dessas seções, com a data e a hora de recebimento.
2. Informar o motivo e o meio (transmissão ou mídia recuperada) do reenvio dos pacotes entre 05 e 07/10/2026 nessas zonas.
3. Esclarecer se o status "Recebida", com conjunto "Recebido", indica pacote não usado na totalização, e se haverá atualização para "Totalizada", como ocorreu nas 19 seções do PI em 14/10/2026.
4. Esclarecer por que a imagem do BU listada no `aux.json` responde HTTP 404 e se ela será publicada.
5. Esclarecer o significado dos campos `f` ("o" e "O") e `idg` (ausente nas seções "Recebida") do `aux.json`.
6. Avaliar a publicação do histórico de versões de cada seção (todos os hashes recebidos), já que o `aux.json` mostra apenas o mais recente.

## 4. Validade do certificado publicado da AC URNA

Os certificados de urna dos modelos UE2013 e UE2015 são emitidos pela AC URNA. O certificado dessa AC disponível publicamente (pacote oficial com a especificação dos arquivos de assinatura, `formato-arquivos-bu-rdv-ass-digital-v2.zip`) tem as seguintes características:

| Campo | Valor |
|---|---|
| Titular | AC URNA |
| Emissor | AC RAIZ UE |
| Número de série | 3 |
| Validade | 22/07/2011 a 18/07/2026 |
| SHA-256 do certificado (DER) | `dc20a4c3b8aef01794b80efe8e143e1fbf719707e00bb0d4ba8865191dc2731d` |

Esse certificado venceu antes da eleição (04/10/2026). Mesmo assim, a assinatura dos certificados de urna emitidos pela AC URNA confere com a chave pública dele, inclusive a de um certificado de urna emitido depois do vencimento: seção SP, Marília (município 66818), zona 0400, seção 0141, certificado emitido em 03/08/2026. Na amostra de 24.846 seções em que a cadeia foi validada, as 4.957 seções com urna UE2013 ou UE2015 têm certificado conferido pela AC URNA, cuja validade publicada não cobre o dia da eleição. A explicação mais provável é a existência de um certificado renovado da AC URNA, com a mesma chave, que não foi publicado.

**Pedidos:**

1. Confirmar se há certificado renovado da AC URNA válido em 04/10/2026 e publicá-lo, com o respectivo resumo digital.
2. Publicar os certificados da AC RAIZ UE, da AC RAIZ UE v2 e da AC URNA v2, cujos resumos SHA-512 constam do resumo digital oficial, para permitir a validação da cadeia até a raiz.

## 5. Certificado da urna diferente do número interno registrado na carga do BU

Em 14 seções, o CN do certificado que assina o `.vsc` não é igual ao número interno da urna registrado no BU, no campo `correspondenciaResultado.carga.numeroInternoUrna`. Em todas, o SHA-512 dos arquivos e a assinatura conferem com o certificado que acompanha o `.vsc`, e os votos coincidem com a totalização. A hipótese é que a urna que votou tenha sido outra que não aquela para a qual a carga foi gerada (troca de equipamento depois da carga).

| UF | Município | Zona | Seção | CN do certificado | Número interno na carga do BU |
|---|---|---|---|---|---|
| AL | Arapiraca (27057) | 0022 | 0581 | UEAO02072552 | 02073355 |
| BA | São Gonçalo dos Campos (38857) | 0108 | 0148 | ueao01672673 | 01768711 |
| ES | Guarapari (56472) | 0024 | 0100 | ueao01771857 | 01840092 |
| ES | Serra (56995) | 0053 | 0028 | ueao01656698 | 01677012 |
| ES | Vitória (57053) | 0001 | 0046 | UEAO02353044 | 02036425 |
| ES | Vitória (57053) | 0001 | 0413 | UEAO02036277 | 02036420 |
| MS | Sidrolândia (91570) | 0031 | 0007 | UEAO02152596 | 02150794 |
| PR | Corumbataí do Sul (75280) | 0133 | 0034 | UEAO02077196 | 02081583 |
| PR | Ivaiporã (76236) | 0093 | 0083 | UEAO02056331 | 02060632 |
| RN | Tibau do Sul (18813) | 0009 | 0144 | UEAO02052038 | 02348402 |
| SE | Aracaju (31054) | 0001 | 0346 | ueao01791133 | 01751434 |
| SE | Simão Dias (32417) | 0022 | 0133 | UEAO02273651 | 02044616 |
| SP | São Paulo (71072) | 0418 | 0073 | UEAO02276282 | 02001951 |
| SP | São Paulo (71072) | 0418 | 0418 | UEAO02403160 | 02087618 |

**Pedido:** confirmar se essas divergências correspondem a substituição de urna depois da carga e, se for o caso, onde esse registro é publicado (ata da mesa ou relatório da zona eleitoral).

## 6. Como reproduzir

Os dados e o código que fundamentam este documento estão no repositório do projeto. O catálogo com MD5, SHA-256 e SHA-512 de cada um dos 1.999.485 arquivos baixados está nos anexos da versão [v0.3.0](https://github.com/alissonlinneker/DataUrnas-BR/releases/tag/v0.3.0), com `SHA256SUMS` para conferência. O [relatório de integridade](relatorio-integridade-2026.md) descreve o passo a passo para conferir qualquer seção com ferramentas comuns (`curl` e `shasum`).
