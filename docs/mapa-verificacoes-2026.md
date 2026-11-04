# Mapa das verificações da eleição de 2026: o que foi feito, o que está em andamento e o que falta

Lista única de tudo o que uma auditoria independente da eleição presidencial de 2026 precisa conferir, com o estado de cada item neste projeto. Serve para quem quiser continuar o trabalho, repetir uma verificação ou cobrar dados do TSE.

Estados: **feito** (com documento e números), **em andamento**, **falta** (possível com dados públicos, ainda não feito), **depende do TSE** (o dado não é público), **impossível hoje** (nenhum dado existente permite).

Atualizado em 03/11/2026.

## 1. Arquivos das urnas (BU, RDV, log, imagem do BU, assinaturas)

| Verificação | Estado | Resultado ou próximo passo | Documento |
|---|---|---|---|
| Assinatura de hardware de todos os arquivos de todas as seções, 2º turno | feito | 5.487.289 assinaturas, 0 inválidas | `certificados-2turno-2026.md` |
| Cadeia de certificados até a AC intermediária | feito | amostra de 5% sem falha; raízes não publicadas | `README.md`, `certificados-2turno-2026.md` |
| Lista de revogação (LCR) das AC de urna e de totalização | depende do TSE | a LCR da AC de totalização respondeu 403 | `veredicto-auditoria-2026.md` |
| RDV x BU, voto a voto, todas as seções, dois turnos | feito | 0 divergências | `rdv-log-2026.md` |
| Imagem do BU (`-imgbu.dat`, o texto do boletim impresso) x BU binário, todas as seções, dois turnos | feito em 04/11 | votos iguais em 499.176 pares no 1º turno e 499.178 no 2º; 9 seções de contingência com código de urna diferente e votos idênticos | `pacote-nacional-imgbu-logs-2026.md` |
| Log eleitor a eleitor x BU, todas as seções | feito em 04/11 | votos no log = comparecimento em 499.167 seções (1º) e 499.171 (2º); 16 com log faltando ou sobrando no pacote, todas com RDV igual ao BU | `rdv-log-2026.md`, `pacote-nacional-imgbu-logs-2026.md` |
| Liberações sem biometria, sequências rápidas de votos e votos na última hora, todas as seções | feito em 04/11 | nenhum intervalo abaixo de 10 s; 1 sequência rápida só sem biometria no Brasil (6 votos); sem relação com o voto | `biometria-1t-2t-2026.md`, `pacote-nacional-imgbu-logs-2026.md` |
| Pacote oficial do 2º turno x arquivos publicados na noite | feito | 998.356 de 998.356 idênticos | `verificacoes-externas-2turno-2026.md`, seção 6 |
| Reconferência periódica dos arquivos publicados (troca no mesmo endereço) | feito até 27/10 e de novo em 03/11 | 0 alterações, 0 remoções, 0 BU com segunda versão em 989.290 arquivos conferidos | idem |
| Coerência entre cargos no mesmo BU (Presidente x Governador no 2º turno; todos os cargos no 1º) | feito em 04/11 | 0 BUs com cargo que não fecha ou comparecimento diferente entre cargos em 787.986 BUs (1º turno de 2026, 2º turno de governador de 2026 e de 2022); voto dividido dentro da faixa de 2022 | `coerencia-cargos-2026.md` |
| Zerésima de cada urna (relatório de zero votos antes da abertura) | feito em 04/11 | 998.354 logs: nenhum voto antes da zerésima; 2 seções sem zerésima no log publicado, ambas sem o log da urna que abriu a votação | `zeresima-2026.md` |
| Pacote do MA 1º turno republicado em 03/11 | feito em 04/11 | nenhum arquivo de urna mudou (72.371 iguais ao catálogo de 13/10); entrou o RDV de MA 07846/0074/0228, que confere com a assinatura | `ma-republicacao-2026.md` |
| `-hash.dat` e `-mr.ver` (assinados pela urna, não publicados) | depende do TSE | pedir publicação | `hash-software-urna-2026.md` |

## 2. Software, carga e lacração

| Verificação | Estado | Resultado ou próximo passo | Documento |
|---|---|---|---|
| Programas verificados no log x lista oficial de hashes | feito na amostra de logs | todos na lista; divergências de nome e versão | `hash-software-urna-2026.md` |
| Cargas das urnas x logs de preparação GEDAI | feito | 99,83% conferem; 862 sem log | `gedai-2turno-2026.md` |
| Lista de hashes assinada digitalmente | depende do TSE | publicada sem assinatura | `cadeia-de-confianca-2026.md` |
| Hash do software em execução, assinado pela urna | impossível hoje | a urna não publica essa medição | idem |
| Compilação reproduzível (código inspecionado = binário lacrado) | impossível hoje | o TSE não publica ambiente nem passos | idem |
| Relatórios das entidades que inspecionaram o código | depende do TSE e das entidades | nenhum publicado; 8 entidades inspecionaram | `verificacoes-externas-2turno-2026.md`, seção 4 |
| Relatórios do Teste de Autenticidade (hashes emitidos por urnas sorteadas) | depende do TSE | não publicados por seção; pedir pela Lei de Acesso à Informação | `cadeia-de-confianca-2026.md` |
| **Relatórios do Teste de Integridade do 2º turno** | depende do TSE, com data | TREs até cerca de 24/11/2026 e TSE até 23/01/2027. É a principal proteção contra adulteração igual em todas as urnas: conferir urna a urna se o BU bate com as cédulas de teste | `veredicto-auditoria-2026.md` |

## 3. Totalização e divulgação

| Verificação | Estado | Resultado ou próximo passo | Documento |
|---|---|---|---|
| Soma dos BUs = resultado oficial (Brasil, UF, município), dois turnos | feito | igual voto a voto | `auditoria-consistencia-bu-2026.md` |
| Assinatura JWS dos resultados divulgados | feito | 11.572 válidas | `jws-totalizacao-2026.md` |
| Totais divulgados ao longo da noite nunca caíram | feito | 12 mil versões | `verificacoes-externas-2turno-2026.md` |
| Totais depois da noite da eleição | feito em 03/11 | nenhuma versão nova desde 25/10 23:27:02 | idem, seção 6 |
| Ordem de chegada das seções e cruzamentos da curva acumulada | feito | explicado pela ordem geográfica de chegada | `ordem-de-envio-viradas-2022-2026.md` |
| Últimas seções recebidas no 1º turno (PR, 07/10) | feito em 04/11 | já somadas no resultado oficial de 05/10; o horário de 07/10 é reenvio do mesmo pacote; o motivo do reenvio vai ao TSE | `pr-secoes-tardias-1t-2026.md` |
| Voto por seção x horário de chegada (injeção tardia) | feito | curva reproduzida pela geografia de chegada; desvios de centésimos de ponto, abaixo de 1,5% da margem | `chegada-bus-2026.md` |
| Logs do sistema de totalização e da transmissão (JE-Connect) | depende do TSE | não publicados | |

## 4. Estatística e probabilidade

| Verificação | Estado | Resultado ou próximo passo | Documento |
|---|---|---|---|
| Valores impossíveis no BU (comparecimento acima de aptos e outros) | feito | 0 | `auditoria-consistencia-bu-2026.md` |
| Viradas por seção 1º para 2º turno com modelo de 2022 | feito | dentro do esperado | `viradas-1t-2t-2026.md` |
| Forense estatística (Klimek, dígitos, swing, transferência, dispersão) | feito | nada maior que em 2022 | `forense-estatistica-2026.md` |
| Tamanho e forma de uma fraude capaz de inverter o resultado | feito | ver `virada-2026-probabilidades.md` | `virada-2026-probabilidades.md` |
| Base histórica: com que frequência o líder do 1º turno perde o 2º, por tamanho da vantagem | feito | 454 disputas de 1994 a 2024, 116 viradas; margem abaixo de 3 pontos (presidente e governador): 12 de 23; 31 casos internacionais | `virada-2026-probabilidades.md` |
| Pesquisas de véspera x resultado, comparado com o erro histórico | feito | ver `virada-2026-probabilidades.md` | idem |
| Eleitorado por município x população com 16 anos ou mais (Censo 2022) | feito | 2.866 municípios acima da população de 12 anos ou mais; virada para o 13 menor neles (2,05 x 3,15 pontos) | `virada-2026-probabilidades.md` |
| Eleitores falecidos que votaram | depende do TSE | o cruzamento com óbitos (SIRC) exige dado individual não público; o teste indireto (votos de eleitores sem biometria) não achou favorecimento | `biometria-1t-2t-2026.md` |

## 5. Verificações que só a sociedade pode fazer

| Verificação | Estado | Como fazer |
|---|---|---|
| **BU impresso de cada seção x arquivo publicado** | falta, sem dados | fotos dos boletins afixados ou leitura do QR code (aplicativo Boletim na Mão) em muitas seções de várias regiões. É o teste independente mais forte contra fraude na totalização ou na raiz de chaves do TSE |
| Atas das mesas (ocorrências, horários, troca de urna) | falta, sem dados | as atas ficam nos cartórios; pedir cópias das seções listadas como atípicas nos documentos |
| Fiscalização das cerimônias de carga e do Teste de Integridade | depende de presença física | partidos e entidades podem acompanhar e registrar |

## 6. Pedidos ao TSE que fechariam lacunas

1. Relatórios do Teste de Autenticidade e do Teste de Integridade por urna, com os hashes emitidos.
2. Listas de hashes assinadas digitalmente, com as assinaturas das entidades.
3. Publicação de `-hash.dat` e `-mr.ver` de cada seção.
4. Certificados das AC raiz e lista de revogação acessível.
5. Ambiente e passos de compilação para reprodução independente.
6. Logs da transmissão e da totalização.
7. Correspondência efetivada e BU em planilha do 2º turno.

A lista completa de pendências com números está em `veredicto-auditoria-2026.md`.
