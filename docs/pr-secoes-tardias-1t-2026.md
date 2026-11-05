# As últimas seções do Paraná no 1º turno de 2026 (recebimento em 07/10)

Data da verificação: 04/11/2026.
Script: `scripts/ele2026/pr_tardias_1t.py` (subcomandos `export`, `pacote` e `analisar`, rodados no servidor de processamento).
Saídas: `data/parquet/2026/pr_tardias/` (`resumo.json`, `secoes_pr_tardias.csv`, `ultimas_499.csv`, `controle_t2.csv`, `mensagens_log.csv`).

## Pergunta

No 1º turno (04/10/2026), o recebimento publicado no `aux.json` das últimas seções do Paraná é de 07/10/2026, três dias depois da eleição (ver [chegada dos BUs](chegada-bus-2026.md), item 5). Esses BUs chegaram e foram totalizados com três dias de atraso? Há algo diferente nos arquivos dessas seções?

## Resposta curta

**Não houve totalização atrasada.** O horário de 07/10 é o de um **reenvio** do mesmo pacote de arquivos, feito depois que a seção já estava totalizada. O `aux.json` mostra só o recebimento mais recente, e por isso essas seções parecem as últimas a chegar.

- O resultado oficial do PR, gerado em 05/10/2026 às 12:51:05, já tinha 27.142 de 27.142 seções totalizadas e o mesmo comparecimento da soma dos BUs, incluindo as 500 seções com recebimento em 07/10. Sem elas, faltam exatamente os 132.758 comparecimentos delas ([investigação das seções "Recebida"](investigacao-secoes-recebidas-2026.md)).
- No 2º turno, o coletor do projeto guardou o histórico do `aux.json` e flagrou o mesmo fenômeno: 1.341 seções com recebimento publicado depois de 25/10 tinham sido totalizadas na noite da eleição (a última às 21:24:35), com o **mesmo hash de pacote** e o **mesmo BU**, e depois reapareceram como "Recebida" com nova data de recebimento, entre 26/10 08:09 e 28/10 09:44.
- Nos arquivos do pacote nacional, as 500 seções tardias do PR não diferem das outras: assinatura válida em todas, hash assinado confere para BU, RDV, log e imagem do BU, recontagem do RDV igual ao BU em todas, log terminando no próprio dia 04/10, nenhuma urna de contingência a mais, nenhuma apuração pelo Sistema de Apuração.
- **Nenhuma divergência de votos e nenhuma falha de assinatura foi encontrada.**

O que continua sem explicação oficial: **por que** os cartórios dessas zonas reenviaram os pacotes em 07/10 e em que horário cada seção foi recebida pela primeira vez. Isso vai como pendência ao TSE (seção 7).

## 1. Quais são as seções

Base: tabela das seções do 1º turno com BU (`ref_secoes_2026_t1`, a mesma de `data/parquet/2026/secoes_2026.parquet`), 499.207 seções com recebimento publicado.

- As 499 últimas do país foram recebidas entre 07/10 12:19:03 e 07/10 15:00:09: **481 do PR**, 14 da BA, 2 do RS, 1 de SP e 1 de SC. Todas com status "Recebida" (`ultimas_499.csv`).
- Contando todas as seções com recebimento depois da geração do resultado oficial (05/10 12:51:05), o PR tem **500** (a primeira às 12:15:32 de 07/10, por isso só 481 entram nas últimas 499). No país são 2.765: PA 1.621, PR 500, MA 403, BA 135, PE 76, PI 19, SP 4, AM 3, RS 2, SC 1 e RJ 1. Dessas, 2.677 têm status "Recebida" e 88 "Totalizada".
- As 500 do PR somam 132.758 comparecimentos, em 14 municípios e 8 zonas eleitorais. Lista completa, com zona, seção, município, local de votação e horário: `secoes_pr_tardias.csv`.

| Zona | Município | Seções tardias | Seções da zona no município | Locais de votação | Recebimento em 07/10 |
|---|---|---:|---:|---:|---|
| 0203 | Candói | 5 | 43 | 4 | 12:15:32 a 12:22:53 |
| 0203 | Goioxim | 8 | 20 | 3 | 12:15:49 a 12:20:52 |
| 0203 | Cantagalo | 14 | 35 | 6 | 12:16:20 a 12:23:09 |
| 0203 | Virmond | 4 | 12 | 4 | 12:19:58 a 12:22:43 |
| 0178 | Curitiba | 360 | 415 | 43 | 12:18:01 a 15:00:09 |
| 0076 | Califórnia | 25 | 25 | 4 | 13:31:34 a 13:40:37 |
| 0076 | Marilândia do Sul | 28 | 28 | 5 | 13:44:20 a 13:51:46 |
| 0076 | Mauá da Serra | 25 | 25 | 5 | 13:54:23 a 14:01:16 |
| 0076 | Rio Bom | 11 | 11 | 3 | 14:02:21 a 14:04:27 |
| 0157 | Londrina | 1 | 290 | 1 | 14:01:03 |
| 0068 | Cascavel | 1 | 372 | 1 | 14:03:28 |
| 0130 | Santa Izabel do Oeste | 1 | 29 | 1 | 14:33:25 |
| 0024 | Jacarezinho | 15 | 102 | 3 | 14:42:59 a 14:54:28 |
| 0033 | União da Vitória | 2 | 139 | 1 | 14:50:39 a 14:57:56 |

Padrão: os horários formam blocos contínuos **por zona eleitoral**, e na zona 0076 os municípios aparecem um depois do outro (Califórnia, Marilândia do Sul, Mauá da Serra, Rio Bom), cada um inteiro. Na zona 0178 de Curitiba são 360 das 415 seções, em 43 locais de votação. Isso é o desenho de um reenvio feito no cartório, zona a zona e município a município, e não de seções que ficaram sem transmitir por um problema local (uma enchente ou falha de transmissão atingiria locais de votação, não municípios inteiros em sequência).

## 2. Esses votos estavam no resultado de 05/10

Já verificado em [investigacao-secoes-recebidas-2026.md](investigacao-secoes-recebidas-2026.md) com os arquivos oficiais (`-u.json`) do TSE:

- PR: resultado gerado em 05/10/2026 12:51:50 (totalização de 12:51:05), 27.142 de 27.142 seções totalizadas, comparecimento 6.841.457. A soma dos 27.142 BUs dá 6.841.457; sem as 500 seções tardias, 6.708.699 (diferença de 132.758, exatamente o comparecimento delas).
- Curitiba (75353): 4.056 de 4.056 seções totalizadas no resultado de 05/10 12:52:27.
- Nos municípios com seções "Recebida", os votos por candidato da soma dos BUs batem com o resultado municipal oficial só quando essas seções entram.

Ou seja: os BUs dessas seções já tinham sido totalizados, com os mesmos números, antes de 05/10 12:51, quase dois dias antes do recebimento publicado.

Uma busca na web indica que o relatório de totalização do TRE-PR (SISTOT) do 1º turno, para os cargos estaduais, foi emitido em 04/10/2026 às 22:51 com 27.142 seções apuradas e nenhuma seção não apurada [1]. **Não consegui abrir o documento** (o site do TRE-PR respondeu HTTP 403 tanto do computador local quanto do servidor), então esse dado vem só do resumo do buscador e não foi conferido aqui. Se confirmado, as 500 seções estavam totalizadas na própria noite da eleição.

## 3. O mesmo fenômeno, observado por inteiro no 2º turno

No 2º turno o coletor (`versionar_t2.py`) gravou cada versão do `aux.json` e cada arquivo no momento em que apareceu (tabelas `aux_versoes` e `versoes_arquivo`). Isso permite ver o que o `aux.json` final esconde. Resultado (`controle_t2.csv`):

| | 2º turno |
|---|---:|
| Seções com recebimento publicado depois do dia da eleição | 1.341 (PE 447, BA 344, PA 216, MA 191, AM 77, RS 62, RJ 2, PI 1, SP 1) |
| Com uma versão "Totalizada" anterior, guardada pelo coletor | 1.341 |
| Recebimento da versão totalizada | todas até 25/10 21:24:35 |
| Mesmo hash de pacote em todas as versões | 1.341 |
| Mesmo BU (SHA-512) em todas as versões | 1.341 |
| Recebimento publicado no fim | 26/10 08:09:39 a 28/10 09:44:50 |
| Status final no `aux.json` | "Recebida" (`f = "O"`, com `imgbu` na lista) em todas |

Exemplo (AM, 02658, zona 0035, seção 0093): na noite da eleição o `aux.json` mostrou o pacote como "Recebida" às 19:51:04 e, depois, como "Totalizada" (recebido às 19:51:00, sem `imgbu` na lista). Em 26/10 às 18:38:39 o mesmo hash voltou como "Recebida", com `imgbu` na lista e nova data de recebimento. O BU guardado nas duas ocasiões é o mesmo.

É a mesma assinatura das 500 seções do PR no 1º turno: status "Recebida", `f = "O"`, sem `idg`, `imgbu` listado, um único hash visível e recebimento dias depois da totalização. No 1º turno o projeto ainda não guardava o histórico, por isso só a versão final é conhecida; o 2º turno mostra que esse padrão é um reenvio do mesmo pacote, e não uma primeira chegada.

No PR, no 2º turno, não houve reenvio tardio: as mesmas 500 seções foram recebidas em 25/10 entre 17:05:39 e 21:12:10, e o último recebimento do PR foi às 21:21:07.

## 4. O pacote nacional dessas seções

Fonte: `bu_imgbu_logjez_rdv_vscmr_2026_1t_PR.zip` (5.175.339.811 bytes, Last-Modified 22/10/2026 20:21:43 GMT), lido por requisições HTTP Range, no máximo 4 conexões simultâneas. Diretório central completo (135.710 arquivos, 27.142 seções) e leitura de BU, RDV, log, imagem do BU e `.vsc` das 500 seções tardias e de 307 seções de controle recebidas a tempo nas mesmas zonas (até 40 por zona e município, as primeiras pela numeração).

| Verificação | Tardias (500) | Controle (307) |
|---|---|---|
| Assinatura do `.vsc` válida (`verificar_vsc`) | 500 | 307 |
| SHA-512 assinado confere: BU, RDV, log, imagem do BU | 500 em cada | 307 em cada |
| Recontagem do RDV igual ao BU (todos os cargos) | 500 | 307 |
| RDV de Presidente: 13 e 22 iguais aos do BU usado no projeto | 500 | não comparado |
| Última linha do log | 04/10 entre 17:02:16 e 18:31:51 | 04/10 entre 17:01:52 e 18:11:48 |
| Log com mais de uma urna (troca de urna) | 3 | 2 |
| Linhas com "conting", "substitu" | 4 e 0 | 2 e 1 |
| Linhas com "recupera", "Sistema de Apuração", "transmi" | 0 | 0 |
| Imagem do BU no pacote | 500 | todas as 26.642 seções a tempo também |
| Data do `-bu.dat` dentro do zip | 05/10 em todas | 05/10 em todas |

- **Nenhum log tem linha depois de 04/10.** Se a urna tivesse sido religada para gerar nova mídia ou recuperar dados nos dias 05 a 07/10, isso apareceria no log. As linhas fora do dia da eleição são todas da preparação (carga e testes, antes de 04/10), igual ao controle.
- **Tipo de BU**: 497 `secao` e 3 `reservaSecao` (urna de reserva, 0,6%, contra 1,0% no PR inteiro), todas com origem `bu` (urna), nenhuma `busa` (Sistema de Apuração, voto em cédula). As 3 de reserva são de Curitiba, zona 0178 (seções 0357, 0403 e 0671); são justamente as 3 com log de mais de uma urna.
- **Emissão do BU**: 04/10 entre 17:01:31 e 18:29:26 (horário local, que no PR é o de Brasília). Encerramento entre 17:00:19 e 18:25:54; 129 das 500 (25,8%) encerraram depois de 17:05, contra 21,7% das outras seções do PR. Nada que explique três dias de diferença.
- **Modelo**: 481 UE2022, 15 UE2015 e 4 UE2020. A concentração em UE2022 acompanha a zona 0178 de Curitiba, não indica um defeito de modelo.
- As mensagens do log com maior diferença de frequência entre tardias e controle (`mensagens_log.csv`) são identificadores do computador que gerou a mídia de carga (próprios de cada zona) e eventos de bateria; refletem a composição das zonas (a zona 0178 pesa 72% das tardias), não um evento comum às tardias.
- A imagem do BU (`-imgbu.dat`) dessas seções, que dava HTTP 404 no portal de resultados em 14/10, está no pacote nacional, assinada e conferindo com o hash da urna.

## 5. Votos

| Grupo | Seções | 13 | 22 | Fatia do 13 (13 + 22) |
|---|---:|---:|---:|---:|
| Tardias | 500 | 37.441 | 76.535 | 32,85% |
| Mesmas zonas, a tempo | 1.046 | 76.170 | 160.151 | 32,23% |
| Mesmos municípios, a tempo | 5.932 | 454.920 | 924.663 | 32,98% |
| Resto do PR | 26.642 | 2.017.156 | 3.868.810 | 34,27% |

- Na zona 0178 de Curitiba, que concentra 360 das 500: 31,29% nas tardias e 30,70% nas 55 seções a tempo da mesma zona.
- Nas zonas com 1 a 15 seções tardias a diferença varia para os dois lados (Jacarezinho 58,0% contra 43,4%; Cascavel, 1 seção, 16,5% contra 29,7%), como se espera de grupos pequenos. Detalhe por zona em `resumo.json`.
- Do 1º para o 2º turno, a fatia do 13 nessas seções subiu 2,86 pontos (32,85% para 35,71%), contra 3,19 pontos no resto do PR.

Os votos das seções tardias seguem o lugar em que elas ficam. E, como estavam no resultado de 05/10, o horário publicado de 07/10 não mexeu em nenhum total.

## 6. Fontes oficiais consultadas

- Nenhuma nota do TSE ou do TRE-PR sobre atraso de transmissão, enchente ou problema em zona eleitoral do PR no 1º turno foi encontrada. A notícia do TRE-PR do dia da eleição diz que a votação transcorreu de forma pacífica em todo o estado [2].
- A Comissão Apuradora do TRE-PR (Resolução TRE-PR nº 988/2026) publicou os relatórios de resultado da totalização do 1º turno, inclusive um "parcial" de Presidente [3] [4]. As páginas responderam HTTP 403 aos acessos deste estudo; o conteúdo citado na seção 2 vem do resumo do buscador e fica como não conferido.
- Nenhuma fonte oficial encontrada explica o reenvio de pacotes de seções já totalizadas, nem por que eles reaparecem com status "Recebida".

## 7. Conclusão

**Explicação operacional plausível, com evidência forte; motivo do reenvio não confirmado pelo TSE.**

1. **Verificado:** as 500 seções do PR com recebimento em 07/10 (481 delas entre as últimas 499 do país) já estavam no resultado oficial de 05/10 12:51:05, com os mesmos números do BU publicado. O horário de 07/10 não é o da totalização.
2. **Verificado:** os arquivos dessas seções no pacote nacional têm assinatura válida, hashes conferindo, RDV igual ao BU e log encerrado em 04/10. Nada indica BU produzido ou alterado depois da eleição.
3. **Verificado no 2º turno, inferido para o 1º:** o `aux.json` publica só o último recebimento de cada seção. Quando o cartório reenvia o mesmo pacote depois da totalização, a seção volta para "Recebida" com a nova data. No 2º turno isso foi observado diretamente em 1.341 seções, sempre com o mesmo hash e o mesmo BU.
4. **Não explicado:** por que os cartórios das zonas 0178, 0076, 0203, 0024 e de outras quatro seções isoladas reenviaram os pacotes em 07/10, entre 12:15 e 15:00, e qual foi o primeiro recebimento de cada seção.

### Pendência candidata ao TSE (redação sugerida)

> No 1º turno de 2026, 500 seções do Paraná (zonas 0178 de Curitiba, 0076, 0203, 0024 e quatro seções isoladas nas zonas 0033, 0068, 0130 e 0157) aparecem no `aux.json` com status "Recebida" e recebimento em 07/10/2026, entre 12:15:32 e 15:00:09, embora seus votos já constem do resultado gerado em 05/10/2026 às 12:51:05. Solicitamos: (a) a data e a hora do primeiro recebimento e da totalização de cada uma dessas seções; (b) o hash do pacote usado na totalização, para confirmar que é o mesmo publicado; (c) o motivo do reenvio feito pelos cartórios em 07/10 e o meio usado (transmissão ou mídia); (d) a publicação do histórico de recebimentos de cada seção no `aux.json`, para que o horário publicado não seja confundido com o da totalização.

Essa pendência é um caso particular das perguntas 1 a 3 já listadas em [investigacao-secoes-recebidas-2026.md](investigacao-secoes-recebidas-2026.md) e em [relatorio-tse-ocorrencias-2026.md](relatorio-tse-ocorrencias-2026.md).

### Controle de 2022

A base do projeto para 2022 não tem horário de recebimento por seção (só a emissão do BU), então não dá para dizer se o mesmo reenvio ocorreu em 2022. O controle usado foi o 2º turno de 2026, que tem o histórico completo.

## Limitações

- O histórico de versões do `aux.json` só existe a partir do 2º turno. Para o 1º turno, a ligação entre o recebimento de 07/10 e um reenvio é inferida pelo padrão idêntico ao do 2º turno e pelo resultado de 05/10, não observada diretamente.
- O pacote nacional do PR foi publicado em 22/10/2026 (Last-Modified). Ele confirma o conteúdo dos arquivos, mas não diz quando cada um chegou ao TSE: as datas internas do zip são de 05/10 para todas as 27.142 seções, tardias ou não.
- O controle do pacote cobre 307 seções das mesmas zonas, não o PR inteiro. Para o PR inteiro, as verificações de assinatura e de imagem do BU contra o BU estão em [pacote nacional](pacote-nacional-imgbu-logs-2026.md).

## Como reproduzir

No servidor de processamento, no clone do repositório:

```sh
uv run python scripts/ele2026/pr_tardias_1t.py export   --work ~/dataurnas-pr-tardias
uv run python scripts/ele2026/pr_tardias_1t.py pacote   --work ~/dataurnas-pr-tardias
uv run python scripts/ele2026/pr_tardias_1t.py analisar --work ~/dataurnas-pr-tardias --out ~/dataurnas-pr-tardias/out
```

O passo `pacote` leva cerca de 7 minutos com 4 conexões.

## Referências

1. [resumo de buscador, documento não aberto: HTTP 403] TRE-PR, "Relatório Resultado da Totalização, Eleições Gerais Estaduais 2026, Paraná, 1º turno": https://www.tre-pr.jus.br/eleicoes/eleicoes-2026/arquivos/tre-pr-relatorio-resultado-da-totalizacao-eleicoes-gerais-estaduais-2026-parana-1o-turno-para-governador-senador-deputados-federais-e-estaduais
2. [oficial, título e resumo do buscador] TRE-PR, "Primeiro turno das Eleições 2026 transcorre de forma pacífica em todo o Paraná": https://www.tre-pr.jus.br/comunicacao/noticias/2026/Outubro/primeiro-turno-das-eleicoes-2026-transcorre-de-forma-pacifica-em-todo-o-parana
3. [oficial, título e resumo do buscador] TRE-PR, "Eleições 2026: Resultados da Totalização do 1º turno no Paraná": https://www.tre-pr.jus.br/comunicacao/noticias/2026/Outubro/eleicoes-2026-resultados-da-totalizacao-do-1o-turno-no-parana
4. [oficial, título do buscador, documento não aberto: HTTP 403] TRE-PR, "Relatório Resultado da Totalização, Eleição Geral Federal 2026, Paraná, 1º turno (parcial), Presidente": https://www.tre-pr.jus.br/eleicoes/eleicoes-2026/arquivos/tre-pr-relatorio-resultado-da-totalizacao-eleicao-geral-federal-2026-parana-1o-turno-parcial-para-presidente
