# Horário de encerramento da urna x votos no 2º turno de 2026

Conferência feita em 05/11/2026 de uma alegação que circulou no X entre 29/10 e 05/11/2026 (perfil `urna_2026`, "Urna Eletrônica"; o post principal, de 03/11, passou de 1 milhão de visualizações). Os posts foram lidos na íntegra em 05/11/2026: 37 próprios e 82 repostagens, com as 14 imagens anexas. O próprio perfil anunciou que apagaria o conteúdo no dia seguinte, e por isso este texto resume cada afirmação com o número que ela traz.

Em 09/11/2026 o perfil não existia mais no X (a consulta devolve "User not found") e o post principal aparece como apagado pelo próprio autor. O Internet Archive não tem cópia da página do perfil. O projeto guarda a cópia feita em 05/11/2026, com os 119 posts e as 14 imagens, fora do repositório por conter texto e imagens de terceiros. O SHA-256 do arquivo com os posts (`statuses.json`) é `bfb5cb9a93a2e73ac086b0eb89d0cd929b67725ecab3a8e93e2fa6f7554bb52b`, o que permite provar depois que a cópia não foi alterada.

Script: `scripts/ele2026/encerramento_minuto_t2.py` (testes em `tests/ele2026/test_encerramento_minuto_t2.py`). Saída: `data/parquet/2026/t2/encerramento_minuto/resumo.json` e `tabelas.md`.

## Conclusão

**A tabela do perfil está certa, e a conclusão dela está errada.** As seções que encerraram mais tarde deram mais votos ao 13, mas esses mesmos locais já votavam mais no 13 antes. Dentro do mesmo prédio de votação, encerrar às 17:00 ou às 17:03 não muda nada. Cinco testes independentes apontam a mesma coisa:

1. **Os números se reproduzem.** Com os 497.897 BUs do Brasil, ordenados pelo encerramento (horário de Brasília) e cortados em 10 grupos iguais, o 13 vai de 47,93% no primeiro grupo a 56,36% no último. O perfil mostra 47,76% e 56,37%. Até 17:01:00 encerraram 125.624 seções, com 49,01% para o 13 (o perfil diz 129.061 seções e 49,03%). Em SP, 41,86% a 53,19% (perfil: 41,87% a 53,19%).
2. **O mesmo degrau já estava no 1º turno.** Ordenando as mesmas seções pelo horário em que encerraram no 2º turno, e contando os votos que elas deram em 04/10, o 13 vai de 45,15% a 53,47%. Uma rotina que agisse depois das 17:01 de 25/10 não alcança votos apurados três semanas antes. As seções que encerraram depois das 17:01 no 2º turno já davam 3,60 pontos a mais ao 13 no 1º turno; no 2º turno a diferença é de 3,68 pontos.
3. **A variação do 1º para o 2º turno é a mesma em todos os grupos.** Na mesma seção, o 13 ganhou 2,78 pontos no grupo das primeiras a encerrar e 2,89 no das últimas, e nos grupos do meio ficou entre 2,71 e 2,85. Em SP a variação até cai nas que encerraram tarde (3,85 para 3,30). A alegação prevê o contrário: a variação teria de crescer grupo a grupo.
4. **Dentro do mesmo local de votação o efeito some.** Seções do mesmo prédio (mesmo município, zona e local) têm o mesmo perfil de eleitor. Medindo cada seção contra a média do seu próprio local, o resíduo fica entre -0,03 e +0,01 ponto em todos os 10 grupos (Brasil), entre -0,10 e 0,00 no estado de SP e entre -0,09 e +0,10 na capital paulista.
5. **No minuto das 17:01 não há salto.** Em 40.803 locais que tiveram seção encerrada entre 17:00:00 e 17:00:59 e seção encerrada entre 17:01:00 e 17:01:59, a diferença dentro do local é de **+0,026 ponto** (IC 95%: -0,014 a +0,065). A inclinação dentro do local, até 17:10, é de -0,006 ponto por minuto. Para criar a margem final, uma alteração a partir de 17:01 nas 75% das urnas que encerraram depois disso precisaria passar 2,2 milhões de votos do 22 para o 13, ou seja, 2,4 pontos da fatia do 13 nessas urnas (93,1 milhões de votos válidos). Isso apareceria dentro dos locais como um salto ou uma rampa de alguns pontos. O observado é 0,03 ponto no corte e -0,006 ponto por minuto.

**O padrão também existe em 2022.** No 2º turno de 2022 (Lula x Bolsonaro, outra versão do software), o 13 vai de 48,03% no primeiro grupo a 53,37% no último; em SP, de 42,26% a 50,20%. No 1º turno de 2026, pelo horário daquele dia, vai de 40,96% a 63,08%.

**Por que as seções de fim de fila votam mais no 13.** Os grupos que encerraram mais tarde têm mais eleitores por seção (310 no primeiro grupo, 336 no último) e mais seções do Nordeste (23% no primeiro, 33% no último). Seções maiores demoram mais a encerrar, porque o último eleitor sai mais tarde e o procedimento leva mais tempo. Elas ficam em centros urbanos mais populosos e em regiões onde o 13 vai melhor. É a mesma composição em 2022 (23% a 29,4% de Nordeste e 322 a 348 eleitores por seção).

## Afirmação por afirmação

| Afirmação do perfil | O que os dados mostram |
|---|---|
| Urnas encerradas até 17:01 dão vitória a Flávio (129 mil seções, 15 milhões de votos) | Correto como número: 125.624 seções, 50,99% para o 22. Não indica fraude, porque as mesmas seções já davam mais ao 22 no 1º turno (53,73%) |
| Quanto mais tarde a urna fecha, maior a diferença para o 13, "sempre" | Correto como descrição. Some dentro do mesmo local de votação (itens 4 e 5) e já existia no 1º turno e em 2022 |
| Não é geografia, porque o padrão também aparece em SP e na capital paulista | Dentro de SP ainda há geografia: periferia e centro, seções grandes e pequenas. Dentro do mesmo prédio, em SP, o resíduo fica entre -0,10 e 0,00 ponto |
| A rotina rouba votos já dados, a partir de 17:01 | Não há salto no minuto 17:01 nem variação 1º para 2º turno que cresça com o horário. O RDV (registro de cada voto, embaralhado) confere com o BU em todas as seções do 2º turno (ver `rdv-log-2026.md`) |
| "Não se deve ajustar pela localização, porque o local é efeito da fraude" | A comparação dentro do mesmo prédio não depende de qual local é mais do 13. Ela compara seções vizinhas que encerraram em minutos diferentes, e uma rotina disparada pelo horário teria de separá-las |
| 2018 x 2022 x 2026: "demorou a encerrar, o PT ganha" | O gráfico do perfil mostra só a velocidade de encerramento, não votos. Em 2022 o mesmo degrau de votos aparece com o software de 2022 |
| Cruzeiro do Sul (AC), zona 0004, seção 0457: 0 voto para Flávio na "primeira urna finalizada"; governador de 59 para 4 | Os números do BU estão corretos: 137 x 0 no 2º turno e 151 x 0 no 1º. A seção encerrou às 17:00:13, antes das 17:01, ou seja, pela própria tese do perfil seria uma urna limpa. A outra seção do mesmo local (0301) deu 118 x 2 no 2º turno, 127 x 1 no 1º e 227 x 2 em 2022. Para governador, a 0301 foi de 35 x 35 (e 27 no 40) para 12 x 106, a mesma virada da 0457. É um local que vota em bloco há pelo menos duas eleições. Não foi a primeira urna recebida do município: chegou às 19:53, e a primeira às 19:09 |
| O teste de integridade termina às 17h em ponto | Correto: art. 69 da Res. TSE 23.673/2021 ("Às 17 horas, será encerrada a votação, mesmo que a totalidade das cédulas não tenha sido digitada") |
| Os BUs das urnas do teste de integridade não são divulgados | Correto: art. 66-J, incluído pela Res. TSE 23.758/2026, veda o fornecimento da imagem do BU, do RDV e dos logs dessas urnas |
| O teste de integridade termina até 17:00:40 | Não verificado. Não há arquivo público com esse horário |

## O que a alegação acerta, e o que fica pendente

O desenho do teste de integridade tem um ponto cego verdadeiro: se as urnas do teste sempre encerram logo às 17h, uma rotina que só agisse em urnas encerradas depois de certo minuto não seria vista por ele. Esta conferência não fecha esse ponto pelo teste de integridade; fecha pelo efeito que a rotina deixaria nos votos. Uma alteração disparada pelo horário de encerramento separaria seções vizinhas encerradas em minutos diferentes, e essa separação não existe (itens 4 e 5).

Continua fora do alcance de qualquer comparação estatística uma alteração aplicada igualmente a todas as urnas, sem depender do horário (ressalva já registrada em `veredicto-auditoria-2026.md`). E o art. 66-J impede que um auditor externo confira por conta própria os BUs, RDVs e logs das urnas do teste. Por isso o pedido ao TSE (`relatorio-tse-ocorrencias-2026.md`) passa a incluir o horário de encerramento de cada urna do teste de integridade do 2º turno e o resultado urna a urna.

## Método

- **Dados:** `data/parquet/2026/t2/impacto/secoes_t1_t2.parquet` (as 497.897 seções do Brasil com BU do 2º turno, horário de encerramento convertido para Brasília pelo fuso do município e par no 1º turno), `data/parquet/2026/secoes_2026.parquet` (local de votação de cada seção) e, para 2022, `data/parquet/secoes.parquet` e `votos_t2.parquet` (horário do BU convertido pelo fuso da UF). Fatia do 13 sobre 13 + 22, nos dois turnos.
- **Grupos:** seções ordenadas pelo horário de encerramento e cortadas em 10 grupos de tamanho igual (7 na capital paulista, como no post do perfil).
- **Resíduo do local:** fatia do 13 na seção menos a média simples das seções do mesmo local de votação (UF, município, zona e local), só em locais com 2 ou mais seções (475.801 seções). O mesmo para a variação do 1º para o 2º turno. Média por grupo ponderada pelos votos válidos.
- **Corte 17:01:** seções encerradas entre 17:00:00 e 17:00:59 contra 17:01:00 a 17:01:59, só em locais que têm os dois lados. Diferença média por local, IC 95% por bootstrap dos locais (2.000 repetições).
- **Inclinação:** regressão da fatia do 13 no minuto de encerramento, com efeito fixo de local, para as seções encerradas até 17:10.

## Como reproduzir

```sh
uv run python scripts/ele2026/encerramento_minuto_t2.py --data data/parquet \
    --out data/parquet/2026/t2/encerramento_minuto
```
