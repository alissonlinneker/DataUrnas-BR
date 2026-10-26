# Verificações externas do 2º turno de 2026 (25/10/2026)

Levantamento de fontes feito em 25/10/2026, entre 21h e 22h40 (horário de Brasília), sobre quatro mecanismos de verificação do 2º turno presidencial de 2026 (pleito 3221, eleição 6258): teste de integridade, resumos digitais (hashes) do software, fontes de boletim de urna (BU) impresso ou lido por QR Code e inspeção do código-fonte. O texto é descritivo: cada afirmação traz a fonte entre colchetes, com o número da lista "Fontes" no fim. Não há conclusão além do que as fontes dizem.

Marcação usada em cada item:

- **[oficial]**: documento ou página de órgão público (TSE, TRE, TCU, MPF, STF).
- **[terceiro]**: reportagem, site de partido ou projeto da sociedade civil.
- **lido**: página aberta na íntegra neste levantamento (diretamente ou por cópia no Internet Archive).
- **não lido**: página que respondeu HTTP 403 ou não foi aberta; o conteúdo citado vem do resumo do buscador ou de reportagem que a cita, e assim está indicado.

Observação de método: todas as páginas de `tse.jus.br` e dos TREs consultados (`tre-ba.jus.br`, `tre-sp.jus.br`, `tre-pe.jus.br`, `tre-se.jus.br`, `tre-mt.jus.br`) responderam **HTTP 403** a acesso automatizado, tanto pela ferramenta de leitura quanto por `curl` com agente de navegador. Algumas páginas do TSE foram lidas por cópias do Internet Archive (`web.archive.org`), indicadas com a data da captura. O portal de dados abertos do TSE (`dadosabertos.tse.jus.br`), o portal do TCU e o do MPF responderam normalmente.

Contexto do dia (prorrogação da votação até 19h por decisão do STF na Rcl 101.673/BA): ver `docs/prorrogacao-votacao-2turno-2026.md`.

## 1. Teste de integridade (votação paralela) do 2º turno de 2026

### 1.1 Como funciona e quem audita

- O TSE descreve o teste assim: na véspera, em cerimônia pública, são escolhidas ou sorteadas seções cujas urnas, já preparadas e lacradas, são recolhidas e levadas a locais públicos com câmeras; no dia da eleição, das 8h às 17h, cédulas de papel preenchidas por voluntários e fiscais são lidas em voz alta e digitadas na urna; às 17h a urna emite o BU e o total é confrontado com o papel. Os votos simulados não entram na apuração. O procedimento é regido pelas Resoluções TSE 23.673/2021 e 23.758/2026 [4] [oficial, lido por cópia arquivada].
- Há duas modalidades em 2026: com e sem biometria de eleitores voluntários [2] [oficial, lido].
- **TCU:** o Acórdão 2558/2026, Plenário, sessão de 16/09/2026 (TC 019.754/2026-4, relator Odair Cunha), autorizou ação de controle para "avaliar a regularidade dos procedimentos relativos aos testes de integridade, com e sem biometria, realizados nas urnas eletrônicas pelos Tribunais Regionais Eleitorais", com equipe de auditores "em cada uma das unidades da federação", com base no Acordo de Cooperação Técnica 51/2026 (vigência 11/09/2026 a 31/12/2031) [2] [oficial, lido; cópia hospedada pelo Poder360]. A notícia do TCU de 02/10/2026 cita o processo TC 020.282/2026-5, cobertura das 27 UFs no 1º turno e, no 2º turno, nas UFs com nova votação, e diz que o relatório consolidado vai ao TSE "em até 30 dias corridos após o 2º turno" [1] [oficial, lido]. A mesma informação aparece em notícia do TSE [3] [oficial, não lido].

### 1.2 Urnas auditadas no 2º turno

- **Seleção:** sábado, 24/10/2026, em todos os TREs [11] [terceiro, lido]; [20] [terceiro, lido]. Em SP, representantes das entidades fiscalizadoras participaram da escolha das urnas [9] [oficial, não lido; título e resumo do buscador].
- **Quantidades por UF (Agência Brasil, 24/10/2026 16h13)** [11] [terceiro, lido]:

| Grupo de UFs | Teste de integridade | Teste de autenticidade | Total |
|---|---|---|---|
| SP, MG, RJ, BA | 33 | 10 | 43 |
| PR, RS, PE, CE | 27 | 8 | 35 |
| RR | 20 | 3 | 23 |
| Demais UFs | não informado | não informado | não informado |

  O total nacional não foi informado. Parte das urnas é auditada com biometria; a quantidade não foi informada [11].
- **Bahia:** 43 urnas, 33 no teste de integridade e 10 no teste de autenticidade; escolha na Sala de Sessões do TRE-BA, em Salvador, no sábado 24/10; a auditoria de integridade ocorre na sede do TRE-BA, em Salvador, no domingo 25/10; as urnas retiradas das seções são substituídas por urnas de contingência preparadas pelos cartórios; transmissão anunciada no canal do TRE-BA no YouTube [12] [16] [terceiro, lido; o próprio texto traz data divergente na seção "Serviço"]. Não foi informado quais seções nem quais municípios foram sorteados, e não há menção a Lauro de Freitas [12].
- **Santa Catarina:** 27 urnas sorteadas, auditoria na Alesc, Florianópolis [19] [terceiro, lido].
- **Distrito Federal:** 20 urnas (16 na Câmara Legislativa, 2 no Museu do Voto do TSE e 2 na Escola Canadense de Brasília, estas no teste com biometria) [18] [17] [terceiro, lidos].
- **Páginas oficiais do TRE-BA localizadas pelo buscador, não lidas (403, sem cópia arquivada):** "Auditoria da Votação Eletrônica - Eleições 2026" [13], "TRE-BA intensifica preparativos para o 2º turno ... neste sábado (24/10)" [14] e a do 1º turno [15].

### 1.3 Resultado do 2º turno (o que foi encontrado até 22h40 de 25/10)

| Local | Resultado divulgado | Fonte |
|---|---|---|
| TSE (Brasília) | Sem divergência entre 389 votos em papel e nas urnas | [5] [oficial, não lido; texto conhecido pelo resumo do buscador] |
| TSE, Museu do Voto | Notícia de realização do teste; resultado não consta no trecho indexado | [6] [oficial, não lido] |
| SP | Teste "concluído sem divergências", 33 urnas | [7] [oficial, não lido; resumo do buscador] |
| MT | Notícia de realização em 25/10; juiz afirma que "nunca houve divergência" desde 2002 | [8] [oficial, não lido; resumo do buscador] |
| DF (CLDF) | Uma divergência atribuída pela comissão a "erro humano de digitação"; trabalhos declarados concluídos "com pleno êxito"; a reportagem não diz qual voto nem como foi resolvida | [17] [terceiro, lido; publicado 25/10 18h45] |
| BA | **Não encontrado.** Nenhuma nota ou reportagem com o resultado da auditoria no TRE-BA | buscas em [13] [14] e imprensa baiana |
| Demais UFs | Não encontrado | |

- Não foi encontrada informação sobre efeito da prorrogação até 19h nos testes de integridade. A reportagem do Museu do Voto cita apenas o encerramento previsto às 17h [18] [terceiro, lido].
- Não foi encontrado relatório (ata, relatório da empresa de auditoria ou do TCU) do 2º turno. Nada de relatório consolidado do 1º turno também.

### 1.4 Quando e onde os relatórios costumam sair

- **2022:** o TSE publica numa página própria os "relatórios elaborados pela empresa de auditoria externa contratada referentes aos testes de integridade", em dois arquivos ZIP (1º e 2º turnos), com base no art. 66, § 2º, da Res. TSE 23.673/2021 [24] [25] [26] [oficial, página lida por cópia arquivada; ZIPs não baixados]. A data de publicação não aparece na página; a captura mais antiga no Internet Archive é de 30/01/2023, o que só indica que a página existia nessa data. No próprio 1º turno de 2022, o TSE anunciou em 06/10/2022 que as 641 urnas do teste tradicional não tiveram divergência e que o teste com biometria (58 urnas, 493 participantes) teve "100% de aprovação" [27] [terceiro, lido]. Em 30/10/2022 o TCU concluiu a análise de 4.161 BUs do 1º turno, sem divergência, com painel em `eleicoes.tcu.gov.br` [28] [oficial, lido].
- **2022, Bahia:** o TRE-BA publicou nota prévia sobre o teste do 2º turno [29] [oficial, não lido].
- **1º turno de 2026:** o calendário eleitoral fixou 14/10/2026 (dez dias após o 1º turno) para os TREs enviarem ao TSE "os relatórios individuais de auditoria referentes ao primeiro turno" [23] [terceiro, lido]. Não foi encontrada a publicação desses relatórios. No dia, o TSE informou que 55 auditores do TCU acompanhavam os testes "sem nenhuma intercorrência" até as 10h, e houve pela primeira vez teste de integridade na própria sede do TSE, com 2 urnas [22] [terceiro, lido].
- **2º turno de 2026:** o único prazo encontrado com fonte é o do relatório consolidado do TCU, até 30 dias corridos após 25/10/2026, ou seja, até cerca de 24/11/2026 [1]. O prazo do envio dos relatórios individuais dos TREs ao TSE para o 2º turno não foi localizado; por analogia com o 1º turno seria de cerca de dez dias, mas isso não foi confirmado em norma ou calendário. Um resumo de buscador mencionou prazos de 30 dias (TREs) e 90 dias (TSE) atribuídos à Res. 23.758/2026, mas nenhuma página que contenha esses prazos foi encontrada, por isso eles não são considerados aqui.

## 2. Resumos digitais (hashes) e autenticidade do software de 2026

### 2.1 Versão do software de votação

- Nenhuma fonte web consultada informa o número da versão do software de votação de 2026. As reportagens citam só o sistema operacional Uenux e o programa "Vota".
- **Dado do próprio projeto (não é fonte externa):** o campo de versão dos BUs publicados pelo TSE traz `10.23.0.0 - Praia da Barra do Cahy` em todas as 499.207 seções com BU do 1º turno (`data/parquet/2026/secoes_2026.parquet`) e em todas as 105.453 seções do 2º turno processadas até 25/10/2026 22h27 (`data/parquet/2026/t2/software/resumo.json`), sem seção com versão diferente e sem mudança de versão entre turnos nessas seções.
- **Modelos de urna em 2026** (TSE, agosto de 2026, via resumo do buscador): UE2022 (217.145), UE2020 (222.323), UE2015 (95.065) e UE2013 (29.377) [39] [oficial, não lido]. A página de hashes de 2026 lista arquivos para os mesmos quatro modelos [30].

### 2.2 Cerimônia de assinatura digital e lacração (04/09/2026)

- Notícia do TSE de 04/09/2026 11h53, atualizada 13h23 [33] [oficial, lido por cópia arquivada em 07/10/2026]:
  - A cerimônia ocorreu na sexta-feira, 04/09/2026, conduzida pelo presidente do TSE, ministro Kassio Nunes Marques. Foram feitas "as assinaturas digitais do arquivo que reúne os resumos digitais dos sistemas eleitorais"; as mídias foram acondicionadas em envelopes lacrados e guardadas na Sala Cofre.
  - Os programas foram compilados durante aquela semana e receberam assinaturas de representantes técnicos das entidades fiscalizadoras.
  - Assinaram digitalmente: Confea (Bruno Taves Pereira da Silva), Polícia Federal (diretor-geral Andrei Rodrigues), CNMP (Fabiana Costa Oliveira Barrato), Conselho Federal da OAB (Délio Lins e Silva Júnior) e Defensoria Pública da União (Tarcijany Linhares).
  - Foram gravados três conjuntos de mídias: dois ficam na Sala Cofre e um com a Secretaria de Tecnologia da Informação, para apresentação a entidades fiscalizadoras.
  - O secretário de TI, Júlio Valente, cita "40 oportunidades de auditoria e fiscalização" no ciclo.
- O MPF registra a assinatura pelo MP Eleitoral (vice-PGE Alexandre Espinosa) e diz que a cerimônia deve ocorrer até 20 dias antes da eleição, conforme a Lei 9.504/1997 [34] [oficial, lido].

### 2.3 Publicação dos resumos digitais

- Página oficial: "Resumos digitais (hashes) das Eleições 2026, 1º turno e 2º turnos" [30] [oficial, lida por cópia arquivada em 05/10/2026; "Última atualização: 04.09.2026 18:08"]. A página explica que os hashes "são gerados a cada eleição, na Cerimônia de Assinatura Digital e Lacração dos Sistemas" e lista os arquivos (cada um é um link próprio):
  - Ambiente PC: `pc1sis1`, `pc1TRAN`, `pc1GEDA`, `pc1CRIP`, `pc1HSFG`, `pc1HOLO`, `pc1SORT` (Apoio ao Sorteio de Auditoria), `pc1VOTA` (Apoio à Auditoria de Votação).
  - Ambiente Linux Web: `itnm1NFM`, `itnm1RECM`, `Itnm1TRAW`, `itnm1STOT`, `Itnm1TOTL`, `Itnm1STCO`, `Itnm1STSE`, `Itnm1STCA`, `Itnm1STCT`, `Itnm1STRE` (módulos do Sistema de Gerenciamento da Totalização e receptor).
  - Ambiente Linux JEC: `itnm1TRAN` (Transportador, JE-Connect) e `Itnm1JECN` (JE-Connect).
  - Ambiente da urna: `path1u13`, `path1u15`, `path1u20`, `path1u22` (modelos 2013, 2015, 2020 e 2022).
  - Arquivos de verificação VAD (PC e JEC): `HASH_MP`, `HASH_OAB`, `HASH_TSE`, `HASH_CONFEA`.
  - Aviso literal da página: ao emitir a lista de hashes pela urna aparecem dois arquivos sem hash publicado, `uenux.cfg` e `avbootcfg.vsu` (assinatura do primeiro), usados pelas UE2020 e UE2022, "por se tratar de arquivos gerados pela urna".
- Os arquivos de hash em si **não foram obtidos**: o site do TSE respondeu 403 e não há cópia deles no Internet Archive (404). O algoritmo de hash não é dito no texto da página.
- O índice de hashes de todas as eleições (2002 a 2026) está em [31] [oficial, lido por cópia arquivada]. Há cópia da página de 2026 no TRE-PE [32] [oficial, não lido].

### 2.4 Verificação de autenticidade no TSE e teste de autenticidade nas seções

- **Véspera do 1º turno (03/10/2026):** cerimônia no TSE de verificação da integridade e autenticidade dos sistemas de transmissão, recebimento e totalização, com conferência de assinaturas e resumos digitais dos quatro sistemas e emissão da zerésima do sistema de totalização para Presidente [35] [oficial, não lido; resumo do buscador]. O MPF acompanhou e informou que os softwares "são os mesmos lacrados em setembro" [36] [oficial, não lido; trecho indexado]. O O Liberal registra a mesma informação [22] [terceiro, lido].
- **Véspera do 2º turno (24/10/2026):** não foi encontrada notícia de cerimônia equivalente no TSE.
- **Teste de Autenticidade dos Sistemas Eleitorais (dia da eleição):** feito na própria seção, antes do início da votação, para mostrar que a urna tem os mesmos sistemas compilados, assinados e lacrados [37] [oficial, não lido; resumo do buscador]. No 2º turno, segundo o TRE-SP, ocorre em 10 zonas não selecionadas para o teste de integridade, com urnas escolhidas na véspera [10] [oficial, não lido].
  - 1º turno de 2026: SP, 10 urnas [37]; AL, 3 urnas (e 20 no teste de integridade) [38] [oficial, não lido].
  - 2º turno de 2026: 10 urnas em BA, SP, MG e RJ; 8 em PR, RS, PE e CE; 3 em RR [11] [terceiro, lido]. **Resultado do teste de autenticidade do 2º turno: não encontrado em nenhuma UF.**
- **Preparação das urnas para o 2º turno na Bahia:** de 14/10 a 22/10/2026, no Centro de Apoio Técnico do TRE-BA (Porto Seco Pirajá, Salvador), 39.744 urnas, das quais 5.141 para Salvador. Nas urnas do 1º turno é inserida nova Mídia de Resultado; sistemas e dados armazenados são mantidos; o lacre do compartimento da mídia é trocado e os demais lacres do 1º turno permanecem; "a carga, a conferência por amostragem e a lacração são procedimentos públicos" [21] [terceiro, lido].

## 3. Fontes de BU impresso ou lido por QR Code do 2º turno de 2026

Nenhum download em massa foi feito. Foram consultadas apenas listagens e metadados.

| Fonte | Tipo | O que oferece | Formato e acesso | 2º turno, Salvador e Lauro de Freitas |
|---|---|---|---|---|
| Totalização Paralela (CMInd) [43] | [terceiro] projeto da sociedade civil | Leituras de QR Code de BUs afixados nas seções, enviadas por voluntários | API JSON pública, sem login: `https://totalizacaoparalela.com.br/api/public-bu?page=1&pageSize=25&_tp_mode=oficial` (lista, campos `id`, `uf`, `municipio`, `zona`, `secao`, `turno`, `status`, `submetido_em`, `municipality_name`) e `/api/public-bu/<id>?_tp_mode=oficial` (detalhe com o texto bruto dos QR Codes, campo `qr_raw`, segundo `docs/confronto-fontes-externas.md`). API não documentada | Consulta às 22h30 de 25/10: 97 BUs no total, **59 do 2º turno**: SP 31 (Lindóia 18, Guararapes 10, Jaguariúna 2, Limeira 1), SC 9 (Içara), AL 7 (Maceió), RS 6 (Esteio), RN 3 (Patu), DF 2, MG 1 (Belo Horizonte). **Nenhum BU da Bahia.** O campo `submetido_em` vai de `2026-10-25 20:04:52` a `2026-10-26 00:31:13`; como o maior valor é posterior ao horário da consulta, os carimbos parecem estar em UTC (17h04 a 21h31 de Brasília), mas o site não declara o fuso |
| Boletim na Mão / e-Título [41] [46] [47] | [oficial] aplicativo do TSE | Lê o QR Code do BU sem internet, guarda e compartilha vários BUs; em 2026 a função também está no e-Título, menu "mais opções" | Aplicativo Android/iOS. **Não há base pública agregada das leituras** | Não se aplica: não publica coleção |
| Manual do QR Code no BU, 2026 [42] | [oficial] | Especificação para criação de aplicativos de leitura | PDF no site do TSE. **403**, não obtido. O formato de 2026 está descrito e verificado empiricamente em `docs/confronto-fontes-externas.md` | Não se aplica |
| Fiscais do PL [44] | [terceiro] partido | Plataforma de cadastro de fiscais que recebe "registros de ocorrências e boletins de urna" (cl. 1.1) | Uso interno. Os termos dizem que registros "não serão publicados em redes sociais, grupos abertos ou contas pessoais" (cl. 7.2) e que não haverá "listas públicas". Nenhuma API ou dado aberto | Sem dados públicos |
| Orientação do PL no 2º turno [45] | [terceiro] reportagem | O partido pediu que fiscais permanecessem até a emissão do BU e recolhessem as cópias físicas dos BUs para conferência paralela com os dados oficiais (paráfrase da reportagem) | Não há publicação das cópias | Não informado |
| Federação Brasil da Esperança (PT, PCdoB, PV) | [terceiro] | Nenhum aplicativo ou coleção de BUs encontrado | | Não encontrado |
| Portal de Dados Abertos do TSE, "Resultados - 2026 - Boletim de Urna" [40] | [oficial] | BU de todas as seções, por UF, licença CC BY | CSV zipado por UF com `.sha512` ao lado, em `https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb/bweb_1t_<UF>_051020261403.zip`. Metadados via API CKAN: `https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-2026-boletim-de-urna` | Em 25/10 22h30, só o 1º turno (recursos criados em 06/10/2026, última modificação 06/10/2026 20h14). **2º turno ainda não publicado.** Não é fonte independente: deriva dos arquivos do TSE |
| Portal Resultados do TSE (`resultados.tse.jus.br`) | [oficial] | Arquivos de urna por seção (BU, RDV, log, imagem do BU) | Já coletado pelo projeto (ver `docs/roteiro-2turno-2026.md`) | Não é fonte independente |

- O TSE informa que os BUs usados na totalização ficam na internet para comparação em tempo real com os obtidos nas seções, e que depois da totalização vão para o Portal de Dados Abertos [46] [oficial, não lido; resumo do buscador].
- Ferramentas de código aberto para ler QR Code de BU (sem coleção de dados) estão listadas em `docs/confronto-fontes-externas.md`.
- **Salvador e Lauro de Freitas:** não foi encontrada nenhuma coleção pública de fotos ou leituras de QR Code de BUs do 2º turno de 2026 desses municípios, nem de partidos, nem de imprensa, nem de projetos de cidadãos. A única reportagem localizada sobre BUs em Lauro de Freitas trata da eleição municipal de 2024 e não foi usada.

## 4. Inspeção do código-fonte para 2026

### 4.1 Período e regras

- Códigos-fonte abertos desde 02/10/2025 (abertura do Ciclo de Transparência Democrática); inspeção pré-agendada na Sala Multiúso, no subsolo do edifício-sede do TSE, com ofício à Presidência ao menos 10 dias antes, até a cerimônia de lacração; entidades legitimadas pelo art. 6º da Res. TSE 23.673/2021, entre elas partidos, federações e coligações, OAB, Polícia Federal, Ministério Público, Defensoria Pública, Congresso Nacional, CGU, TCU e Sociedade Brasileira de Computação [48] [oficial, lido por cópia arquivada; notícia de 14/04/2026].
- **Forças Armadas:** checagem de 28/08/2026 afirma que participaram da inspeção em 2022 e que em 2023 o TSE as retirou da lista de entidades fiscalizadoras; a lista de 2026 citada não as inclui [55] [terceiro, lido].

### 4.2 Quem inspecionou

Lista oficial dada pelo secretário de TI do TSE na cerimônia de 04/09/2026: "Ao todo, oito entidades inspecionaram os códigos-fonte: União Brasil, Senado Federal, Confederação Nacional do Comércio de Bens, Serviços e Turismo (CNC), Sociedade Brasileira de Computação (SBC), Conselho Nacional do Ministério Público (CNMP), Partido Verde (PV), Ministério Público Federal (MPF) e Controladoria-Geral da União (CGU)" [33] [oficial, lido por cópia arquivada].

| Entidade | Data | Fonte | Relatório publicado |
|---|---|---|---|
| União Brasil | maio de 2026 (uma fonte diz 25/05; reportagem de 18/06 fala em "semana passada") | [54] [terceiro, lido]; [49] [oficial, não lido] | Não encontrado |
| Senado Federal | 10/06/2026 | [49] [oficial, não lido] | Não encontrado |
| SBC | 24 e 25/06/2026 | [50] [oficial, não lido] | Não encontrado |
| CNMP | 06/07/2026 (1ª visita) | [51] [oficial, não lido] | Não encontrado |
| MP Eleitoral (servidores da Sppea/PGR) | 05 a 13/08/2026 | [53] [oficial, lido] | Não. A notícia descreve o processo e não traz achados |
| CGU | 20 e 21/08/2026 | [52] [oficial, não lido] | Não encontrado |
| CNC | não informada | [33] | Não encontrado |
| PV | não informada | [33] | Não encontrado |

- **Polícia Federal e OAB:** assinaram digitalmente os sistemas na lacração [33] [34]; **não constam** da lista das oito entidades que inspecionaram os códigos-fonte [33]. Nenhum relatório de inspeção da PF ou da OAB foi encontrado.
- **TCU:** não aparece como inspetor do código. Integra a Comissão Avaliadora do Teste Público de Segurança 2025, com MPF, PF, Congresso, OAB e SBC [56] [oficial, lido], e audita os testes de integridade [2].
- **Partidos:** segundo reportagem de 18/06/2026, até então o União Brasil era o único partido a ter inspecionado no ciclo; a mesma reportagem diz que o PL, no ciclo de 2024, compareceu a uma apresentação técnica e "desistiu de prosseguir com a análise detalhada" [54] [terceiro, lido]. O PV aparece apenas na lista do TSE de 04/09 [33].
- **Universidades:** nenhuma inspeção por universidade foi encontrada; a única entidade acadêmica ou técnica listada é a SBC.

### 4.3 Achados

- **Nenhum relatório de entidade fiscalizadora sobre a inspeção do código-fonte de 2026 foi encontrado.** As notícias oficiais e reportagens descrevem datas, participantes e declarações, sem achados técnicos.
- O MPF diz que os técnicos do MP Eleitoral "propuseram melhorias" durante o ciclo, sem detalhar quais [34] [oficial, lido].
- O TSE afirma que, na etapa de confirmação concluída em maio de 2026, nenhuma verificação apontou falha capaz de comprometer o sigilo do voto ou alterar resultado (conteúdo de reportagem que cita o TSE, via resumo do buscador; página não lida).
- **Teste Público de Segurança 2025 (01 a 05/12/2025), etapa ligada ao ciclo de 2026:** o TSE noticiou 38 planos aprovados após recursos [58] e 35 planos executados [59] [oficiais, não lidos; títulos indexados]. Um resumo de imprensa fala em 29 planos executados e 6 com "achados mitigáveis", e na conclusão das comissões de que nenhum achado representou risco efetivo à integridade, ao sigilo do voto ou ao resultado [61] [terceiro, não lido]. Os números divergem entre fontes; o relatório oficial [57] não foi lido (403). O Teste de Confirmação ocorreu de 13 a 15/05/2026 [60] [oficial, não lido].

## 5. Linha do tempo de publicação versus totalização (dados coletados pelo projeto)

Diferente das seções anteriores, esta parte não vem de fontes externas: usa os arquivos públicos do 2º turno versionados pelos coletores do projeto (aux.json, BU e totais por abrangência), com a coleta nacional completa de 26/10/2026. O texto é descritivo e não atribui causa. Script: `scripts/ele2026/linha_tempo_t2.py` (testes em `tests/ele2026/test_linha_tempo_t2.py`); saídas no servidor de análise em `~/dataurnas-t2/linha_tempo-nacional/` e listas em CSV copiadas para `data/parquet/2026/t2/linha_tempo/nacional/` (fora do git). Versão anterior desta análise: 112.493 seções, só Norte e Nordeste.

### 5.1 Horários usados

| Horário | Fonte | Fuso | Uso |
|---|---|---|---|
| Emissão do BU (`dataHoraEmissao`) e encerramento | BU | horário local da urna, convertido para Brasília pelo fuso do município | momento em que o BU existiu |
| Recebimento (`dr`/`hr` do pacote) | aux.json da seção | Brasília (testado abaixo) | recebimento que o TSE publica |
| Geração do aux.json (`dg`/`hg`) | aux.json | Brasília | quando o arquivo foi gerado |
| Totalização da versão (`dt`/`ht`) | JSON de totais da abrangência | horário local da abrangência, convertido para Brasília | quando a versão foi totalizada |
| Geração da versão (`dg`/`hg`) | JSON de totais | Brasília | quando a versão foi publicada |
| `Last-Modified` do `bu.dat` | cabeçalho HTTP do CDN | GMT | só numa amostra (5.4) |

- Teste do fuso de `hr`: lido como Brasília, o menor atraso entre emissão e recebimento é de 2,3 min nas seções em UTC-5 e de -0,6 min em UTC-4; lido como horário local, o menor atraso seria de 122 min em UTC-5 e de 59 min em UTC-4. A leitura como Brasília é a coerente.
- 17 seções têm recebimento de 0,1 a 2,5 minutos antes da emissão gravada no BU (15 no PA, 11 delas em Jacareacanga, zona 0102; 1 no AM; 1 no PR). É compatível com relógio da urna adiantado em relação ao do TSE; lista em `secoes_recebimento_antes_emissao.csv`.
- Em 80.541 seções (status "Recebida") a geração do aux.json coincide com o recebimento; nas 418.666 com status "Totalizada" o aux.json foi gerado de novo depois. O `dr`/`hr` marca o registro do pacote no sistema de divulgação, que pode não ser o instante exato da chegada ao TSE.

### 5.2 Cobertura e consistência dos totais

- 499.248 seções vistas no aux.json, 499.207 com BU (as 41 restantes "Não instalada"), nenhum BU ilegível, nenhuma seção com mais de um pacote ou mais de uma versão de BU.
- Totais: 15.682 versões de 5.786 abrangências, nenhuma regressão entre versões e nenhuma versão em que o total de votos difira da soma interna.
- A soma dos 499.207 BUs bate exatamente com a última versão do Brasil (gerada às 23:27:02 de 25/10): comparecimento 128.236.074, 13 com 64.256.232, 22 com 59.826.041, brancos 1.430.496 e nulos 2.723.305. Nenhuma UF e nenhum dos 4.145 municípios comparáveis tem diferença. Em 1.572 municípios a última versão municipal gravada é anterior aos BUs, e a comparação fica para o total da UF.
- Pausa: 1.193 seções têm recebimento entre 17:06 e 19:00, todas até 17:08:53; não há recebimento entre 17:08:53 e 19:03:37. A última totalização antes das 19h é de 17:07:35, e 8 versões foram totalizadas depois de 17:06 (de 17:06:15 a 17:07:35): 7 municipais (MT 99058 e 98990, MA 07242, SC 80926 e 80942, PR 76996, RO 00795) e a do AM.

### 5.3 BU emitido ou publicado depois de já totalizado

Três verificações, da mais direta à mais ampla:

1. **Emissão depois da totalização completa do município.** Nos 3.999 municípios em que há BU de todas as seções e uma versão com 100% das seções totalizadas (388.431 seções), compara-se a emissão de cada BU, em Brasília, com o `ht` da primeira versão completa. **Nenhuma seção tem BU emitido depois da totalização** (a emissão mais próxima ficou 232 s antes). O mesmo vale para o encerramento da seção: nenhuma depois da totalização.
2. **Curva de emissão.** Em cada uma das 11.932 versões de 4.767 abrangências (município, UF e Brasil) com cobertura completa de BU, conta-se quantas seções tinham BU emitido até o `ht` da versão. **Em nenhuma versão o número de seções totalizadas passa do número de BUs já emitidos.**
3. **Recebimento publicado depois da totalização completa.** Nos mesmos 3.999 municípios, compara-se o `dr`/`hr` de cada seção com o `ht` da primeira versão completa. 16.574 seções, em 1.494 municípios, têm recebimento publicado depois de o município já aparecer 100% totalizado: mediana de 93 s, percentil 90 de 167 s, percentil 99 de 1.933 s, máximo de 6.130 s. 11.546 passam de 1 minuto, 691 de 5 minutos, 392 de 15 minutos e 50 de 1 hora. Por UF (todas): BA 5.813, PE 2.151, PI 1.693, CE 1.623, SE 1.478, PB 1.166, AL 802, MA 685, PA 450, MG 292, AM 189, AC 89, RR 76, SP 38, AP 27, TO 2. Lista completa em `secoes_recebimento_apos_totalizacao.csv`.

O conjunto dos três resultados é o seguinte: nenhum BU foi totalizado antes de existir, mas em parte das seções o horário de recebimento que o TSE publica no aux.json é posterior à totalização que já as incluía. A diferença típica, de 1 a 3 minutos, é compatível com o recebimento ser carimbado no registro do pacote para divulgação, logo depois de totalizado. Os casos acima de 15 minutos não se explicam só por isso e ficam para conferência.

Seções com recebimento publicado mais de 15 minutos depois da totalização completa do município (392, em 45 municípios):

| UF | Município | Seções | Totalização completa | Recebimento publicado | Diferença (s) |
|---|---|---|---|---|---|
| PA | 04057 Afuá | 99 | 20:15:39 | 20:45:30 a 20:49:53 | 1.791 a 2.054 |
| PB | 21393 Pitimbu | 42 | 20:50:34 | 21:12:33 a 21:13:44 | 1.319 a 1.390 |
| PB | 19496 Bonito de Santa Fé | 27 | 19:44:02 | 20:44:02 a 20:51:36 | 3.600 a 4.054 |
| PI | 10286 Jacobina do Piauí | 19 | 20:52:34 | 21:09:25 a 21:13:30 | 1.011 a 1.256 |
| PB | 19038 Aguiar | 17 | 20:54:35 | 21:12:47 a 21:13:35 | 1.092 a 1.140 |
| PB | 20931 Monte Horebe | 15 | 19:29:14 | 20:22:35 a 20:27:48 | 3.201 a 3.514 |
| PE | 25895 Surubim | 13 | 20:26:42 | 20:49:10 a 20:50:50 | 1.348 a 1.448 |
| PB | 21571 Riacho dos Cavalos | 11 | 19:51:30 | 20:09:21 a 20:12:07 | 1.071 a 1.237 |
| PB | 20290 Gurinhém | 10 | 20:54:15 | 21:12:45 a 21:13:27 | 1.110 a 1.152 |
| PB | 19410 Belém do Brejo do Cruz | 10 | 20:26:13 | 21:12:06 a 21:13:02 | 2.753 a 2.809 |
| PE | 23000 Quixaba | 10 | 20:28:02 | 20:43:48 a 20:44:18 | 946 a 976 |
| CE | 13129 Barreira | 9 | 20:49:03 | 21:06:59 a 21:09:12 | 1.076 a 1.209 |
| PB | 19828 Riacho de Santo Antônio | 9 | 19:45:35 | 21:08:07 a 21:08:54 | 4.952 a 4.999 |
| PB | 19836 Carrapateira | 9 | 19:37:37 | 20:44:13 a 20:44:52 | 3.996 a 4.035 |
| PA | 04898 Melgaço | 8 | 20:21:22 | 20:39:17 a 20:52:05 | 1.075 a 1.843 |
| MA | 07560 Formosa da Serra Negra | 7 | 20:11:16 | 20:39:43 a 20:41:10 | 1.707 a 1.794 |
| PB | 21490 Puxinanã | 7 | 19:31:43 | 20:10:45 a 20:16:11 | 2.342 a 2.668 |
| PB | 20672 Lagoa Seca | 6 | 20:00:56 | 20:47:58 a 20:49:53 | 2.822 a 2.937 |
| AM | 02992 Caapiranga | 6 | 20:16:30 | 20:45:45 a 20:46:05 | 1.755 a 1.775 |
| outros 26 municípios | AC, AM, CE, PA, PB, PE, PI | 58 | | | 902 a 6.130 |

- Na PB, 193 seções passam de 15 minutos, e 87 delas têm recebimento publicado entre 21:12 e 21:13:59; outro grupo de 34 cai às 20:44. O recebimento chega em blocos, para municípios totalizados em horários diferentes.
- Em Bonito de Santa Fé, 20 das 27 seções têm recebimento publicado entre 3.600 e 3.636 s depois da totalização completa (as duas primeiras exatamente 3.600 s).
- Maior diferença: Santo André (PB 19267), zona 0056, seção 0066: BU emitido às 17:02:51, município 100% totalizado às 19:24:56, recebimento publicado às 21:07:06 (6.130 s depois).

Conferência independente no banco ClickHouse, com o horário de geração da versão (`totalizado_em`, que é o `dg`/`hg` do JSON, e não o `ht`) no lugar do `ht`: nas mesmas 388.431 seções, 12.582 têm recebimento depois da primeira versão completa, 380 mais de 15 minutos depois, e nenhuma tem emissão depois. Como `hg` vem depois de `ht`, os números são menores que os do script, e o resultado sobre a emissão é o mesmo:

```sql
WITH comp AS (
  SELECT uf, cd_mun, min(totalizado_em) AS tot
  FROM totais_versoes FINAL
  WHERE nivel = 'municipio' AND st = ts AND st > 0
  GROUP BY uf, cd_mun
),
bu AS (
  SELECT uf, cd_mun, zona, secao, recebimento,
    data_hora_emissao + toIntervalHour(multiIf(cd_mun IN ('02020','02054','02135','02291',
          '02313','02399','02496','02755','02917','98370','98477'), 2,
          cd_mun = '30015', -1, uf = 'ac', 2, uf IN ('am','mt','ms','ro','rr'), 1, 0)) AS emissao_bsb
  FROM v_bu_ultima WHERE uf != 'zz'
)
SELECT count() AS secoes,
  countIf(recebimento > tot) AS rec_depois,
  countIf(dateDiff('second', tot, recebimento) > 900) AS rec_depois_15min,
  countIf(emissao_bsb > toDateTime(toString(tot), 'UTC')) AS emissao_depois
FROM bu INNER JOIN comp USING (uf, cd_mun);
-- 388431  12582  380  0
```

### 5.4 Curva de recebimento por versão (todas as versões)

Para cada versão dos totais de cada abrangência com BU de todas as seções (4.913 abrangências, 12.085 versões), conta-se quantas seções tinham recebimento publicado até a geração da versão (`hg`). Em 4.637 versões de 1.746 abrangências o TSE já tinha totalizado mais seções do que o aux.json mostrava como recebidas naquele instante. O menor conjunto de seções que explica esses excessos (as de recebimento mais cedo depois de `hg`) soma 117.656 seções distintas; em 54 s de mediana o recebimento aparece depois de `hg`, e 978 seções ficam mais de 15 minutos depois. A versão parcial desta análise, só com Norte e Nordeste, registrava 895 abrangências com excesso. Lista em `curva_excesso_secoes_distintas.csv`; essas seções são as que explicariam a contagem, não necessariamente as seções totalizadas.

Por emissão, a mesma curva não tem excesso em nenhuma versão (5.3, item 2).

### 5.5 Outras marcas de horário

- **`Last-Modified` do `bu.dat`:** medido só numa amostra de 225 seções na primeira execução (madrugada de 26/10), sem repetir em escala nacional para não fazer requisições em massa ao TSE. Na mediana, o arquivo foi gravado de 2 a 3 s depois do `dr`/`hr`; os maiores intervalos foram de 1.105 a 5.384 s, em seções do AM, AP, MA, PA e do excesso da curva. Em 5 seções regravadas depois da coleta, o MD5 informado pelo CDN era igual ao do arquivo guardado.
- **`mtime` do `log.jez`:** os coletores versionam aux.json, BU e assinatura; o log da urna só foi baixado numa amostra do estudo de impacto, sem registrar o horário interno do arquivo. Esta marca não entra na análise nacional.
- **Bahia (recebimento menos emissão, minutos):** Salvador 5.124 seções, mediana 202,6, 41,4% recebidas depois das 21h; Lauro de Freitas 413, 237,6 e 74,6%; Feira de Santana 1.218, 234,1 e 52,3%; resto da BA 28.721, 216,5 e 17,6%.

Reprodução (no servidor de análise; `--sem-download` impede qualquer requisição ao TSE):

```sh
python3 scripts/ele2026/linha_tempo_t2.py \
  --parts ~/dataurnas-versoes-t2/bus/parts --parts ~/dataurnas-versoes-t2-nne/bus/parts \
  --parts ~/dataurnas-mac/versoes/2026/t2/bus/parts --parts ~/dataurnas-mac/versoes/2026/t2-sseco/bus/parts \
  --totais ~/dataurnas-versoes-t2-nne/totais --totais ~/dataurnas-mac/versoes/2026/t2/totais \
  --saida <saida> --workers 48 --sem-download --limite-lista 5000
```

A execução leu 675.765 versões de aux.json e 501.454 de BU e levou cerca de 4 minutos. As colunas `m_emissao_apos_totalizacao`, `emissao_menos_totalizacao_s` e o arquivo `curva_emissao_totalizacao.parquet` foram acrescentados ao script nesta versão.

## Limitações

- **Bloqueio do TSE e TREs:** todas as páginas de `tse.jus.br` e `tre-*.jus.br` responderam 403. Os conteúdos marcados "não lido" vêm de trechos de buscador ou de reportagens e podem estar incompletos ou desatualizados. Só foram lidas na íntegra as páginas do TSE com cópia no Internet Archive: hashes de 2026 [30], índice de hashes [31], lacração [33], teste de integridade [4], códigos-fonte [48] e relatórios de 2022 [24].
- **Seção 5 (linha do tempo):** usa só os arquivos públicos coletados; o `ht` dos totais depende da conversão de fuso da abrangência e o `dr`/`hr` do aux.json é o horário publicado, não necessariamente o da chegada ao TSE. `Last-Modified` foi medido só numa amostra e o `mtime` do `log.jez` não foi coletado.
- **Resultados do dia:** o levantamento terminou por volta das 22h40 de 25/10/2026. Atas e relatórios dos testes do 2º turno, em especial do TRE-BA, podem ser publicados depois.
- **Hashes:** os valores dos resumos digitais de 2026 não foram obtidos (403 no TSE, ausentes no Internet Archive), portanto não foram comparados com nada.
- **Versão do software:** veio dos BUs processados pelo projeto, não de fonte oficial textual do TSE.
- **Totalização Paralela:** amostra pequena e não aleatória; foram lidos só os metadados da listagem, sem conferir conteúdo nem assinatura dos 59 BUs do 2º turno. O fuso de `submetido_em` é inferido.
- **Resumos de buscador:** em várias consultas o resumo trazia datas ou números que não se confirmaram nas páginas abertas (por exemplo, prazos de 30 e 90 dias para relatórios dos testes). Esses números foram descartados quando não havia página que os contivesse.
- **Nada foi encontrado** sobre: resultado do teste de integridade e de autenticidade na Bahia no 2º turno; seções sorteadas na Bahia; cerimônia de verificação no TSE na véspera do 2º turno; relatório de qualquer entidade sobre a inspeção do código-fonte de 2026; coleção pública de BUs de Salvador ou Lauro de Freitas.

## Fontes

Data de acesso de todas as fontes: 25/10/2026, salvo indicação.

1. [oficial, lido] TCU, "Eleições 2026: TCU acompanha testes de integridade das urnas eletrônicas", 02/10/2026: https://portal.tcu.gov.br/imprensa/noticias/eleicoes-2026-tcu-acompanha-testes-de-integridade-das-urnas-eletronicas
2. [oficial, lido] TCU, Acórdão 2558/2026, Plenário, TC 019.754/2026-4, sessão de 16/09/2026 (cópia hospedada pelo Poder360; autenticidade verificável em www.tcu.gov.br/autenticidade, código 81067682): https://static.poder360.com.br/uploads/2026/09/019.754-2026-4-OJC-Proposta-de-Fiscalizacao-Integridade-das-Urnas.pdf
3. [oficial, não lido] TSE, "Eleições de 2026 terão acompanhamento do TCU nos testes de integridade das urnas eletrônicas": https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/eleicoes-de-2026-terao-acompanhamento-do-tcu-nos-testes-de-integridade-das-urnas-eletronicas
4. [oficial, lido por cópia de 04/10/2026] TSE, "Como funciona o Teste de Integridade, 'a prova dos nove' da urna eletrônica", 06/08/2026, atualizada 20/08/2026: https://www.tse.jus.br/comunicacao/noticias/2026/Agosto/como-funciona-o-teste-de-integridade-a-prova-dos-nove-da-urna-eletronica (cópia: https://web.archive.org/web/20261004065015/https://www.tse.jus.br/comunicacao/noticias/2026/Agosto/como-funciona-o-teste-de-integridade-a-prova-dos-nove-da-urna-eletronica)
5. [oficial, não lido] TSE, "Teste de integridade no TSE confirma correspondência entre cédulas e votos registrados nas urnas": https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/teste-de-integridade-no-tse-confirma-correspondencia-entre-cedulas-e-votos-registrados-nas-urnas
6. [oficial, não lido] TSE, "TSE realiza Teste de Integridade das urnas eletrônicas no Museu do Voto": https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/tse-realiza-teste-de-integridade-das-urnas-eletronicas-no-museu-do-voto
7. [oficial, não lido] TRE-SP, "Teste de Integridade das urnas no 2º turno é concluído sem divergências em São Paulo": https://www.tre-sp.jus.br/comunicacao/noticias/2026/Outubro/teste-de-integridade-das-urnas-no-2o-turno-e-concluido-sem-divergencias-em-sao-paulo
8. [oficial, não lido] TRE-MT, "Teste de Integridade reforça segurança e confiabilidade da urna eletrônica no 2º turno": https://www.tre-mt.jus.br/comunicacao/noticias/2026/Outubro/teste-de-integridade-reforca-seguranca-e-confiabilidade-da-urna-eletronica-no-2o-turno
9. [oficial, não lido] TRE-SP, "Eleições 2026: fiscalizadores definem urnas para os Testes de Integridade e de Autenticidade do 2º turno": https://www.tre-sp.jus.br/comunicacao/noticias/2026/Outubro/eleicoes-2026-fiscalizadores-definem-urnas-para-os-testes-de-integridade-e-de-autenticidade-do-2o-turno
10. [oficial, não lido] TRE-SP, "Eleições 2026: urnas eletrônicas serão submetidas a novas auditorias para o 2º turno em SP": https://www.tre-sp.jus.br/comunicacao/noticias/2026/Outubro/eleicoes-2026-urnas-eletronicas-serao-submetidas-a-novas-auditorias-para-o-2o-turno-em-sp
11. [terceiro, lido] Agência Brasil, "Tribunais eleitorais definem urnas que serão auditadas no 2º turno", 24/10/2026 16h13: https://agenciabrasil.ebc.com.br/justica/noticia/2026-10/tribunais-eleitorais-definem-urnas-que-serao-auditadas-no-2o-turno
12. [terceiro, lido] Bahia Na Política, "2º turno: TRE-BA define no sábado (24/10) as seções eleitorais cujas urnas passarão por auditoria", 23/10/2026: https://bahianapolitica.com.br/2o-turno-tre-ba-define-no-sabado-24-10-as-secoes-eleitorais-cujas-urnas-passarao-por-auditoria/
13. [oficial, não lido] TRE-BA, "Auditoria da Votação Eletrônica - Eleições 2026": https://www.tre-ba.jus.br/eleicoes/eleicoes-2026-1/auditoria-da-votacao-eletronica
14. [oficial, não lido] TRE-BA, "TRE-BA intensifica preparativos para o 2º turno das Eleições Gerais 2026 neste sábado (24/10)": https://www.tre-ba.jus.br/comunicacao/noticias/2026/Outubro/tre-ba-intensifica-preparativos-para-o-2o-turno-das-eleicoes-gerais-2026-neste-sabado-24-10
15. [oficial, não lido] TRE-BA, "TRE-BA define no próximo sábado (3/10) urnas que passarão por Auditoria da Votação Eletrônica": https://www.tre-ba.jus.br/comunicacao/noticias/2026/Setembro/tre-ba-define-no-proximo-sabado-3-10-urnas-que-passarao-por-auditoria-da-votacao-eletronica
16. [oficial, não acessado; citado em 12] Canal do TRE-BA no YouTube: https://www.youtube.com/@tvtreba
17. [terceiro, lido] Bomba Bomba, "Urnas eletrônicas são aprovadas em teste de integridade realizado na CLDF no 2º turno", 25/10/2026 18h45: https://bombabomba.com.br/urnas-eletronicas-sao-aprovadas-em-teste-de-integridade-realizado-na-cldf-no-2o-turno/
18. [terceiro, lido] Mix Vale, "Teste de Integridade do TSE audita urnas no Museu do Voto em Brasília durante o 2º turno das Eleições 2026", 25/10/2026: https://www.mixvale.com.br/2026/10/25/teste-de-integridade-do-tse-audita-urnas-no-museu-do-voto-em-brasilia-durante-o-2o-turno-das-eleicoes-2026/
19. [terceiro, lido] ND Mais, "Urnas eletrônicas de SC passam por teste de integridade no segundo turno das Eleições 2026", 24/10/2026 17h28: https://ndmais.com.br/politica/eleicoes-2026-urnas-eletronicas-de-sc-passam-por-teste-de-integridade-no-segundo-turno/
20. [terceiro, lido] CNN Brasil, "TREs sorteiam neste sábado urnas que passarão por auditoria no 2º turno", 24/10/2026: https://www.cnnbrasil.com.br/eleicoes/tres-sorteiam-neste-sabado-urnas-que-passarao-por-auditoria-no-2o-turno/
21. [terceiro, lido] Muita Informação, "TRE-BA prepara 39,7 mil urnas para o 2º turno das eleições na Bahia", outubro de 2026: https://muitainformacao.com.br/eleicoes/tre-ba-prepara-397-mil-urnas-para-o-2o-turno-das-eleicoes-na-bahia/
22. [terceiro, lido] O Liberal, "TSE: 55 auditores do TCU acompanham teste de integridade no Brasil; não há intercorrências", 04/10/2026 10h18: https://www.oliberal.com/eleicoes/tse-55-auditores-do-tcu-acompanham-teste-de-integridade-no-brasil-nao-ha-intercorrencias-1.1176812
23. [terceiro, lido] Midiamax, "Confira prazos do calendário eleitoral que vencem nesta semana, às vésperas do 2º turno", 13/10/2026 07h59: https://midiamax.com.br/politica/2026/confira-prazos-calendario-eleitoral-vencem-nesta-semana-vesperas-2o-turno/
24. [oficial, lido por cópia de 09/02/2026] TSE, "Testes de Integridade - Relatórios referentes ao 1º e 2º turnos" (Eleições 2022): https://www.tse.jus.br/eleicoes/eleicoes-2022/testes-de-integridade-relatorios-referentes-ao-1o-e-2o-turnos (cópia: https://web.archive.org/web/20260209210703/https://www.tse.jus.br/eleicoes/eleicoes-2022/testes-de-integridade-relatorios-referentes-ao-1o-e-2o-turnos)
25. [oficial, não baixado] TSE, relatórios de auditoria dos testes de integridade, 1º turno de 2022 (ZIP): https://www.tse.jus.br/eleicoes/eleicoes-2022/arquivos/relatorios-de-auditoria-dos-testes-de-integridade-1o-turno-2022
26. [oficial, não baixado] TSE, relatório de auditoria dos testes de integridade, 2º turno de 2022 (ZIP): https://www.tse.jus.br/eleicoes/eleicoes-2022/arquivos/relatorio-de-auditoria-dos-testes-de-integridade-2o-turno-arquivo-zip-2022
27. [terceiro, lido] Agência Brasil, "Urnas têm 100% de aprovação em novo teste de integridade, diz TSE", 06/10/2022 13h30: https://agenciabrasil.ebc.com.br/politica/noticia/2022-10/urnas-tem-100-de-aprovacao-em-novo-teste-de-integridade-diz-tse
28. [oficial, lido] TCU, "TCU finaliza análise de boletins de urna do 1º turno das eleições", 30/10/2022 (painel citado: https://eleicoes.tcu.gov.br/, não acessado): https://portal.tcu.gov.br/imprensa/noticias/tcu-finaliza-analise-de-boletins-de-urna-do-1%C2%BA-turno-das-eleicoes
29. [oficial, não lido] TRE-BA, "Faltam 4 dias: TRE-BA realizará Teste de Integridade nas urnas eletrônicas durante o 2º turno" (2022): https://www.tre-ba.jus.br/comunicacao/noticias/2022/Outubro/faltam-4-dias-tre-ba-realizara-teste-de-integridade-nas-urnas-eletronicas-durante-o-2o-turno
30. [oficial, lido por cópia de 05/10/2026] TSE, "Resumos digitais (hashes) das Eleições 2026, 1º turno e 2º turnos", última atualização 04/09/2026 18h08: https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/hash/resumos-digitais-hashes-das-eleicoes-2026-1o-e-2o-turnos (cópia: https://web.archive.org/web/20261005103012/https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/hash/resumos-digitais-hashes-das-eleicoes-2026-1o-e-2o-turnos)
31. [oficial, lido por cópia de 05/10/2026] TSE, índice "Hash dos sistemas eleitorais": https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/hash (cópia: https://web.archive.org/web/20261005102936/https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/hash)
32. [oficial, não lido] TRE-PE, cópia da página de resumos digitais de 2026: https://www.tre-pe.jus.br/eleicoes/eleicoes-2026/resumos-digitais-hashes-das-eleicoes-2026-1o-turno-e-2o-turnos
33. [oficial, lido por cópia de 07/10/2026] TSE, "Sistemas das Eleições Gerais de 2026 são assinados digitalmente e lacrados pelo TSE", 04/09/2026 11h53, atualizada 13h23: https://www.tse.jus.br/comunicacao/noticias/2026/Setembro/sistemas-das-eleicoes-gerais-de-2026-sao-assinados-digitalmente-e-lacrados-pelo-tse (cópia: https://web.archive.org/web/20261007192254/https://www.tse.jus.br/comunicacao/noticias/2026/Setembro/sistemas-das-eleicoes-gerais-de-2026-sao-assinados-digitalmente-e-lacrados-pelo-tse)
34. [oficial, lido] MPF/PGR, "MP Eleitoral atesta segurança dos sistemas de votação e apuração que serão usados nas Eleições 2026", 04/09/2026 12h03: https://www.mpf.mp.br/o-mpf/unidades/procuradoria-geral-da-republica-pgr/noticias/mp-eleitoral-atesta-seguranca-dos-sistemas-de-votacao-e-apuracao-que-serao-usados-nas-eleicoes-2026
35. [oficial, não lido] TSE, "TSE verifica integridade dos sistemas eleitorais na véspera do 1º turno": https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/tse-verifica-integridade-dos-sistemas-eleitorais-na-vespera-do-1o-turno
36. [oficial, não lido] MPF/PGR, "MPF atesta a integridade e a segurança dos sistemas que serão usados nas Eleições 2026", 03/10/2026: https://www.mpf.mp.br/o-mpf/unidades/procuradoria-geral-da-republica-pgr/noticias/mpf-atesta-a-integridade-e-a-seguranca-dos-sistemas-que-serao-usados-nas-eleicoes-2026
37. [oficial, não lido] TRE-SP, "Urnas eletrônicas passam por teste de autenticidade no 1º turno das Eleições 2026 em São Paulo": https://www.tre-sp.jus.br/comunicacao/noticias/2026/Outubro/urnas-eletronicas-passam-por-teste-de-autenticidade-no-1o-turno-das-eleicoes-2026-em-sao-paulo
38. [oficial, não lido] MPF/PR-AL, "MP Eleitoral acompanha sorteio de urnas para auditoria nas eleições em Alagoas": https://www.mpf.mp.br/o-mpf/unidades/pr-al/noticias/mp-eleitoral-acompanha-sorteio-de-urnas-para-auditoria-nas-eleicoes-em-alagoas
39. [oficial, não lido] TSE, "Veja os modelos de urna que serão utilizados nas Eleições Gerais 2026", agosto de 2026: https://tse.jus.br/comunicacao/noticias/2026/Agosto/veja-os-modelos-de-urna-que-serao-utilizados-nas-eleicoes-gerais-2026
40. [oficial, lido] TSE, Portal de Dados Abertos, "Resultados - 2026 - Boletim de Urna", consultado às 22h30: https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna (API: https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-2026-boletim-de-urna)
41. [terceiro, lido] Agência Brasil, "Boletim de Urna permite conferir totalização dos votos; entenda", 04/10/2026 14h33: https://agenciabrasil.ebc.com.br/politica/noticia/2026-10/boletim-de-urna-permite-conferir-totalizacao-dos-votos-entenda
42. [oficial, não obtido, 403] TSE, "Manual do QR Code no Boletim de Urna" (2026): https://www.tse.jus.br/eleicoes/eleicoes-2026-content/arquivos/manual-do-qr-code-no-boletim-de-urna/@@display-file/file/manual-do-qr-code-no-boletim-de-urna.pdf
43. [terceiro, lido] CMInd, Totalização Paralela, listagem pública consultada às 22h30: https://totalizacaoparalela.com.br/ (API: https://totalizacaoparalela.com.br/api/public-bu?page=1&pageSize=25&_tp_mode=oficial)
44. [terceiro, lido] Fiscais do PL 2026, "Termo de uso, adesão e Aviso de privacidade": https://fiscaisdopl.com.br/politica-de-privacidade
45. [terceiro, lido] ABC do ABC, "PL convoca fiscais a monitorar fim do segundo turno", 25/10/2026 19h15: https://www.abcdoabc.com.br/pl-convoca-fiscais-monitorar-segundo-turno/
46. [oficial, não lido] TSE, "Faltam 4 dias: é possível acompanhar em tempo real a totalização dos votos", setembro de 2026: https://www.tse.jus.br/comunicacao/noticias/2026/Setembro/faltam-4-dias-e-possivel-acompanhar-em-tempo-real-a-totalizacao-dos-votos
47. [oficial, não lido] TSE, "Faltam 17 dias: baixe os aplicativos da Justiça Eleitoral e tenha tudo o que precisa para votar na palma da mão": https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/faltam-17-dias-baixe-os-aplicativos-da-justica-eleitoral-e-tenha-tudo-o-que-precisa-para-votar-na-palma-da-mao
48. [oficial, lido por cópia de 15/04/2026] TSE, "Eleições 2026: códigos-fonte dos sistemas eleitorais continuam abertos para inspeções", 14/04/2026 15h09: https://www.tse.jus.br/comunicacao/noticias/2026/Abril/eleicoes-2026-codigos-fonte-dos-sistemas-eleitorais-continuam-abertos-para-inspecao (cópia: https://web.archive.org/web/20260415002416/https://www.tse.jus.br/comunicacao/noticias/2026/Abril/eleicoes-2026-codigos-fonte-dos-sistemas-eleitorais-continuam-abertos-para-inspecao)
49. [oficial, não lido] TSE, "Eleições 2026: Senado inspeciona códigos-fonte dos sistemas eleitorais no TSE", junho de 2026: https://www.tse.jus.br/comunicacao/noticias/2026/Junho/eleicoes-2026-senado-inspeciona-codigos-fonte-dos-sistemas-eleitorais-no-tse
50. [oficial, não lido] TSE, "Sociedade Brasileira de Computação inspeciona códigos-fonte dos sistemas das Eleições 2026", junho de 2026: https://www.tse.jus.br/comunicacao/noticias/2026/Junho/sociedade-brasileira-de-computacao-inspeciona-codigos-fonte-dos-sistemas-das-eleicoes-2026
51. [oficial, não lido] TSE, "CNMP realiza 1ª visita ao TSE para inspecionar códigos-fonte dos sistemas das Eleições 2026", julho de 2026: https://www.tse.jus.br/comunicacao/noticias/2026/Julho/cnmp-realiza-1a-visita-ao-tse-para-inspecionar-codigos-fonte-dos-sistemas-das-eleicoes-2026
52. [oficial, não lido] TSE, "CGU conclui inspeção dos códigos-fonte dos sistemas eleitorais para as Eleições 2026", agosto de 2026: https://www.tse.jus.br/comunicacao/noticias/2026/Agosto/cgu-conclui-inspecao-dos-codigos-fonte-dos-sistemas-eleitorais-para-as-eleicoes-2026
53. [oficial, lido] MPF/PGR, "MP Eleitoral realiza inspeção nos códigos-fonte da urna eletrônica e sistemas utilizados nas Eleições 2026", 13/08/2026 12h00: https://www.mpf.mp.br/o-mpf/unidades/procuradoria-geral-da-republica-pgr/noticias/mp-eleitoral-realiza-inspecao-nos-codigos-fonte-da-urna-eletronica-e-sistemas-utilizados-nas-eleicoes-2026
54. [terceiro, lido] Agora RN (crédito: O Correio de Hoje), "Só um partido fiscalizou código-fonte das urnas no TSE em oito meses", 18/06/2026 15h07: https://agorarn.com.br/ultimas/so-um-partido-fiscalizou-codigo-fonte-das-urnas-no-tse-em-oito-meses/
55. [terceiro, lido] TNH1, "Viralizou: é falso que Forças Armadas não inspecionaram o código-fonte das urnas", 28/08/2026 13h37: https://www.tnh1.com.br/noticia/nid/viralizou-e-falso-que-forcas-armadas-nao-inspecionaram-o-codigo-fonte-das-urnas/
56. [oficial, lido] TCU, "Eleições 2026: TCU participa de teste de urnas eletrônicas", 26/01/2026: https://portal.tcu.gov.br/imprensa/noticias/eleicoes-2026-tcu-participa-de-teste-de-urnas-eletronicas
57. [oficial, não lido] TSE, catálogo de publicações, "Teste Público de Segurança dos Sistemas Eleitorais 2025": https://www.tse.jus.br/institucional/catalogo-de-publicacoes/arquivos/tse-teste-publico-de-seguranca-dos-sistemas-eleitorais-2025
58. [oficial, não lido] TSE, "Teste da Urna 2025 tem 38 planos aprovados após fase de recursos", novembro de 2025: https://www.tse.jus.br/comunicacao/noticias/2025/Novembro/teste-da-urna-2025-tem-38-planos-aprovados-apos-fase-de-recursos
59. [oficial, não lido] TSE, "Teste da Urna 2025: veteranos e calouros colocam em prática 35 planos de ataque", dezembro de 2025: https://www.tse.jus.br/comunicacao/noticias/2025/Dezembro/teste-da-urna-2025-veteranos-e-calouros-colocam-em-pratica-35-planos-de-ataque
60. [oficial, não lido] TSE, "Eleições 2026: Teste de Confirmação começa nesta quarta (13) e valida melhorias nos sistemas eleitorais", maio de 2026: https://www.tse.jus.br/comunicacao/noticias/2026/Maio/eleicoes-2026-teste-de-confirmacao-comeca-nesta-quarta-13-e-valida-melhorias-nos-sistemas-eleitorais
61. [terceiro, não lido] Jornal Opção, página do marcador "teste público de segurança": https://www.jornalopcao.com.br/assunto/teste-publico-de-seguranca/

Documentos do próprio projeto citados: `docs/prorrogacao-votacao-2turno-2026.md`, `docs/confronto-fontes-externas.md`, `docs/roteiro-2turno-2026.md`, `data/parquet/2026/secoes_2026.parquet`, `data/parquet/2026/t2/software/resumo.json`.
