# Veredicto da auditoria independente: eleição presidencial de 2026 (1º e 2º turnos)

Auditoria feita sobre os arquivos públicos das urnas e da totalização (BU, RDV, log, assinaturas `.vsc`, `aux.json`, totais `.json`/`.jws`, dados abertos, logs de preparação GEDAI e listas oficiais de hashes), sem partir de nenhuma premissa sobre a confiabilidade do TSE nem sobre o resultado político. Cada conclusão abaixo remete ao documento com o método, as consultas e os números completos.

Resultado oficial do 2º turno (25/10/2026, totalização final às 23:22): Lula (13) 64.256.232; Flávio (22) 59.826.041; margem de 4.430.191 votos; brancos 1.430.496; nulos 2.723.305; 499.248 seções, das quais 41 não instaladas no exterior.

## Veredicto

**Não foi encontrada nenhuma evidência de manipulação, de contagem errada de votos ou de dado impossível nos arquivos públicos, em nenhum dos dois turnos.** O resultado divulgado é exatamente a soma dos boletins assinados pelas urnas; o registro digital de cada voto (RDV), recontado em todas as seções dos dois turnos, dá exatamente os mesmos números; os boletins são coerentes por dentro e com o log de cada eleitor, e nenhum padrão estatístico de 2026 foge do que se observou em 2022 com a mesma metodologia.

Isso não equivale a provar que o software da urna é honesto. Os arquivos públicos não permitem ligar o programa que rodou em cada urna à lista de hashes lacrada; essa ligação só é feita por amostragem, em cerimônias cujos relatórios não são publicados. Esse é o limite real da auditoria, descrito na seção "O que não pode ser verificado".

Foram encontrados pontos de transparência e de registro que pedem esclarecimento (lista no fim). Nenhum deles, isolado ou somado, mexe na contagem ou chega perto da margem.

## O que foi verificado e o resultado

| # | Verificação | Escopo | Resultado | Documento |
|---|---|---|---|---|
| 1 | Coleta versionada de todos os arquivos das seções, com reconferência periódica (ETag/MD5) para detectar troca posterior | 499.207 seções do 2º turno, 8 voltas completas em cada coletor (25/10 a 27/10) | 0 arquivos alterados ou removidos até a última volta; nenhum BU com segunda versão | `docs/verificacoes-externas-2turno-2026.md` |
| 2 | Assinatura digital de todos os arquivos de cada seção e cadeia de certificados | 499.207 seções, 5.487.289 assinaturas | 0 inválidas; SHA-512 do BU confere com o assinado em todas | `docs/certificados-2turno-2026.md` |
| 3 | Soma dos BUs x resultado oficial | Brasil, UFs e 5.757 municípios, dois turnos | Igual voto a voto (13, 22, brancos, nulos, comparecimento) | `docs/auditoria-consistencia-bu-2026.md` |
| 4 | Totais divulgados ao longo da noite | 12 mil versões coletadas | Nunca diminuíram; sempre fecharam | `docs/verificacoes-externas-2turno-2026.md` |
| 5 | Valores impossíveis no BU (comparecimento > aptos, total ≠ comparecimento, horários fora do dia, urna repetida, aptos que mudam) | 998.414 BUs | 0 impossíveis; repetições e zeros explicados e comparados com 2022 | `docs/auditoria-consistencia-bu-2026.md` |
| 6 | Recontagem voto a voto pelo RDV x BU | Todas as seções dos dois turnos: 499.206 no 1º e 499.205 no 2º (as 2 restantes do exterior tiveram comparecimento 0) | 0 divergências; soma nacional do RDV do 2º turno igual ao resultado oficial (13: 64.256.232; 22: 59.826.041); assinatura e hash do RDV válidos em todas | `docs/rdv-log-2026.md` |
| 7 | Log eleitor a eleitor x BU | 2.997 seções, dois turnos | Votos no log = comparecimento em todas; 0 votos fora do horário; ritmo plausível | `docs/rdv-log-2026.md` |
| 8 | Encerramento tardio (prorrogação até 19h) e impacto na margem | 497.897 seções; logs de 21.317 | 5.129 votos depois das 17h nas tardias; total estimado 31.792; margem nunca inverte (pior cenário 4.398.399) | `docs/encerramento-tardio-2turno-2026.md` |
| 9 | 368 BUs emitidos mais de 1 h depois do encerramento | logs das 368 e de 368 controles | 0 votos depois do encerramento, 0 reabertura; urna parada na tela de registro de mesários | `docs/auditoria-consistencia-bu-2026.md` |
| 10 | Viradas por seção 1º para 2º turno, com modelo de 2022 | 497.897 seções | 31.341 viradas para o 13 contra 32.604 esperadas; contabilidade fecha em todas | `docs/viradas-1t-2t-2026.md` |
| 11 | Estatística forense (impressão digital eleitoral, dígitos, swing, transferência, dispersão) com 2022 de controle | todas as seções, 2022 e 2026 | Nenhum padrão de 2026 maior que o de 2022 | `docs/forense-estatistica-2026.md` |
| 12 | Efeito do modelo de urna, troca, recarga, reserva e contingência | 499 mil seções, efeito fixo de local | Nenhum efeito capaz de mover a margem; maior pior caso 3.957 votos | `docs/efeito-urna-2026.md` |
| 13 | Biometria 1º x 2º turno (BU e log) | 497.895 seções; logs de 2.997 | Variações de décimos de ponto; sem relação com o voto | `docs/biometria-1t-2t-2026.md` |
| 14 | Cargas das urnas x logs de preparação GEDAI | 499.207 BUs | 99,83% conferem em todos os campos; 862 sem log | `docs/gedai-2turno-2026.md` |
| 15 | Linha do tempo: emissão, recebimento e totalização | todas as seções | Nenhum BU emitido depois de totalizado | `docs/verificacoes-externas-2turno-2026.md` |
| 16 | Produtos de dados abertos (votação por seção, detalhe, BU web, correspondências) x BU | dois turnos, todas as seções | 0 divergências de voto; divergências de registro de urna (ver pendências) | `docs/confronto-dados-abertos-2026.md` |
| 17 | Lista oficial de hashes lacrados x programas verificados nos logs | 32 listas; 6.732 logs | Todos os programas de inicialização estão na lista; divergências de nome e versão (ver pendências) | `docs/hash-software-urna-2026.md` |
| 18 | Assinatura JWS dos resultados divulgados x soma dos BUs | 5.786 arquivos por turno (Brasil, 28 UFs, 5.757 municípios), dois turnos | 11.572 assinaturas válidas, 0 inválidas; payload idêntico ao `.json`; 0 divergências com a soma dos BUs | `docs/jws-totalizacao-2026.md` |
| 19 | Alegações externas (vídeo sobre "virada única" e "vales igualmente espaçados") | 2022 e 2026 | Explicadas pela ordem geográfica de chegada; ordem aleatória não produz o padrão alegado | `docs/ordem-de-envio-viradas-2022-2026.md` |
| 20 | Pacote oficial do 2º turno (zips por UF de 26/10) x BUs e assinaturas guardados na noite da eleição; totais de novo em 03/11 | 998.356 arquivos; Brasil, UFs e municípios | 998.356 idênticos à última versão guardada; nenhum total novo depois de 25/10 23:27:02 | `docs/verificacoes-externas-2turno-2026.md` |
| 21 | Pacote oficial completo dos dois turnos: imagem do BU x BU e log eleitor a eleitor x BU | 499.207 seções por turno (56 zips, 219 GB) | Votos iguais entre imagem do BU e BU em todas; log = comparecimento salvo 16 seções com log faltando ou sobrando no pacote (RDV igual ao BU nelas); log republicado em 03/11 confere com a assinatura da urna | `docs/pacote-nacional-imgbu-logs-2026.md` |
| 22 | Ordem e horário de chegada dos BUs x voto | 499.205 seções; 2022 de controle | Nenhum sinal de injeção; curva da noite reproduzida pela geografia de chegada | `docs/chegada-bus-2026.md` |
| 23 | Plausibilidade da virada: base histórica (454 disputas), pesquisas, transferências, simulação de fraude e eleitorado x população | Brasil 1994 a 2026 e 31 casos internacionais | Virada com chance perto de 50% pela margem do 1º turno; fraude concentrada capaz de inverter apareceria; eleitorado inflado não favoreceu o 13 | `docs/virada-2026-probabilidades.md` |
| 24 | Zerésima (relatório de zero votos) em todas as urnas: presença, horário e ordem em relação à abertura e ao primeiro voto | 998.354 logs, dois turnos (143,8 GB) | Nenhum voto antes da zerésima e nenhuma zerésima depois da abertura, fora do dia ou antes das 7h de Brasília; mais de uma zerésima em 383 (1º) e 298 (2º) seções, quase sempre troca de urna antes de qualquer voto; 2 seções sem zerésima no log publicado (SP 71072/0002/0035 no 1º e MA 08893/0047/0609 no 2º), ambas com o log da urna que abriu a votação ausente do pacote | `docs/zeresima-2026.md` |
| 25 | Coerência entre cargos no mesmo BU (todos os cargos no 1º turno; Presidente x Governador no 2º) e voto dividido, com 2022 de controle | 499.207 BUs do 1º turno, 39.739 do 2º turno de governador (AC, AM, DF, ES, RN, TO) e 249.040 de 2022 | 0 BUs com cargo que não fecha, comparecimento ou aptos diferentes entre cargos; diferença Presidente x cargos estaduais explicada pelo voto em trânsito e no exterior; seções atípicas no voto dividido em 0,40% (2026) contra 0,24% (2022), dentro da faixa por UF de 2022 | `docs/coerencia-cargos-2026.md` |
| 26 | Últimas seções recebidas no 1º turno (PR, 07/10) | 500 seções do PR e 2.765 no país com recebimento depois do resultado oficial | Já somadas no resultado oficial do PR de 05/10 (27.142 de 27.142 seções); o horário de 07/10 é reenvio do mesmo pacote; assinaturas válidas e RDV igual ao BU nas 500; voto no 13 igual ao das seções da mesma zona | `docs/pr-secoes-tardias-1t-2026.md` |

## O que não pode ser verificado com dados públicos

A explicação completa (quem garante o quê, quais assinaturas existem, o que é impossível sem código-fonte e compilação reproduzível, e alertas) está em `docs/cadeia-de-confianca-2026.md`.

1. **Qual software rodou em cada urna.** O `.vsc` assina só os arquivos de resultado; o log registra o nome de cada pacote verificado e "SUCESSO", nunca o hash; a assinatura de software (chave SEVIN, algoritmo CEPESC) não é verificável fora do TSE. A ligação entre a urna e a lista lacrada existe só nas verificações por amostragem (AVPART/VPP na preparação e Teste de Autenticidade no dia), cujos relatórios ficam em ata e não são publicados.
2. **Adulteração idêntica em todas as urnas.** Os testes comparativos (modelo, troca, região, 2022) não detectam uma alteração aplicada igualmente a todas as urnas, porque ela não deixa diferença entre grupos. A proteção contra isso é o Teste de Integridade (votação paralela), cujo relatório do 2º turno só sai até cerca de 24/11 (TREs) e 23/01/2027 (TSE).
3. **O que aconteceu na seção fora do arquivo**, como a razão de uma mesa esperar uma hora para emitir o BU. Isso está nas atas, não nos arquivos.

## Pendências para esclarecimento do TSE

Ordem de relevância; nenhuma altera contagem.

1. Publicar, por seção, a lista de hashes emitida pela urna nas verificações de autenticidade e os relatórios do Teste de Autenticidade; publicar `-hash.dat` e `-mr.ver`, que o `.vsc` assina mas o TSE não divulga.
2. Listas oficiais de hashes sem assinatura digital (HTML com SHA-512, garantidas só pelo HTTPS do site), ao contrário do que diz a notícia sobre a cerimônia.
3. Divergências entre lista de hashes e logs: `avbootcfg.vst`, `avmodue20XX.vst` e `avusrlibue20XX.vst` verificados na carga e ausentes da lista pelo nome; `avusrbinof.vst` na lista e nunca verificado; `app.ini.vsc` (GEDAI) e `acurna.pem` fora das listas; HotSwapFlash 8.10.0.0 em 4 estações ao lado da 8.12.0.0, com um só conjunto de hashes publicado; `versoes.properties` não publicado, o que impede ligar a versão 10.23.0.0 a um hash.
4. 3 seções assinadas por urna diferente da que recebeu a carga (SP 64777/0393/0312, RJ 58696/0027/0139, ES 57932/0009/0085); as urnas que assinaram são de contingência da própria zona.
5. Correspondência esperada do 2º turno com `ST_CORRESP_ALTERADA=N` em 372 seções que mudaram; 35 seções votaram com urna diferente da esperada, 8 delas com urna que não aparece em nenhum produto; 108 urnas de reserva vindas de fora da contingência da zona; correspondência efetivada e BU web do 2º turno ainda não publicados.
6. 862 cargas sem log GEDAI (Parauapebas zona 0106, Guarulhos zona 0176, zona 0339 de MG, Juruá, Monte Alegre); 5 urnas carregadas em 25/10; 2 estações geradoras sem log publicado.
7. Erro "Problema ao desmontar a MR" (aplicação GAP) em 2.993 de 2.997 urnas da amostra no dia do 2º turno e em nenhuma no 1º; na leitura do pacote completo, 531.983 ocorrências em 497.702 seções do 2º turno, fora da lista de erros mais frequentes do 1º.
8. 11 seções com falha de verificação de arquivos de dados no log (`infomidia.vsc`, `vota.vsu`, `bu.vsu`, `turno2.vsc`).
9. 368 seções com BU emitido mais de 1 hora depois do encerramento (urna parada na tela de registro de mesários) e Belo Horizonte 0039/0168 no 1º turno (apuração mista no Sistema de Apuração; log e BU da urna original não publicados).
10. Horário de recebimento publicado (`aux.json`) posterior à totalização completa do município em 16.574 seções; o carimbo não representa a chegada real.
11. Certificado da AC URNA publicado vencido em 18/07/2026, com 53 certificados de urna emitidos depois dessa data.
12. 187 arquivos de resultado do 1º turno no exterior regerados em 24/10/2026 (mesmos números da totalização de 05/10), sem explicação; lista de certificados revogados da AC de totalização (`actot.tse.jus.br`) inacessível (403), o que impede conferir revogação da chave que assina os resultados.
13. Pacote oficial republicado em 03/11/2026 sem aviso, em três zips: MG 1º turno (retirada do `-imgbu.dat` da urna na seção 50075/0047/0041, de apuração em cédula), SP 2º turno (`-log.jez` e `-vota.vsc` da seção 64777/0395/0298 regravados; conteúdo igual ao assinado pela urna) e MA 1º turno (nenhum arquivo de urna mudou: os 72.371 arquivos são iguais ao catálogo de hashes de 13/10; o zip passou a trazer o RDV da seção 07846/0074/0228, que confere com a assinatura da urna e com o BU; o byte exato alterado não pode ser identificado porque a versão anterior não foi guardada; ver `docs/ma-republicacao-2026.md`). Pedir registro público de versões do pacote, com data e motivo.

## Correções feitas no próprio projeto durante a auditoria

- `analyzer/timezones.py` não tinha 4 municípios do oeste do AM em UTC-5 (Jutaí, São Paulo de Olivença, Amaturá e Itamarati). Os 11 municípios em UTC-5 foram confirmados pelos BUs de 2026, que abrem às 6h locais; a tabela foi corrigida com teste. Análises anteriores que usaram a tabela antiga tinham erro de 1 hora só nessas seções, sem efeito nas conclusões.
- O campo `hora_encerramento` da view `v_bu_ultima` guarda a hora local rotulada como UTC; não deve ser convertido com `toTimeZone`.
