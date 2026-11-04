# Cadeia de confiança do software e dos dados da eleição de 2026

O que se consegue verificar, o que não se consegue com dados públicos e o que é impossível sem o código-fonte e a reprodução das compilações.

Este documento responde, em linguagem direta, às perguntas mais frequentes sobre o software das urnas e dos sistemas do TSE. Cada afirmação vem marcada com a origem:

- **[verificado]**: conferido por este projeto com arquivos públicos, com o método no documento citado;
- **[TSE]**: dito pelo próprio TSE em resolução, notícia ou página oficial, e não verificado de forma independente;
- **[limite]**: algo que não pode ser conferido de fora do TSE.

## Resposta curta

1. **A contagem é verificável e foi verificada.** O resultado divulgado é exatamente a soma dos boletins de urna (BU) assinados. Nenhum BU foi alterado depois de publicado. A recontagem pelo registro digital do voto (RDV) bate em todas as seções dos dois turnos. **[verificado]**
2. **O software não é verificável por quem está fora do TSE.** Nenhum arquivo público prova que o programa que rodou em cada urna é o mesmo que foi lacrado. A assinatura do BU prova que ele saiu de uma urna certificada, não qual programa a urna executava. **[limite]**
3. **Quem garante a ligação entre software e resultado é o próprio TSE**, com a participação de entidades fiscalizadoras em etapas e amostras definidas por ele. Os relatórios dessas amostras não são publicados por seção. **[TSE] [limite]**
4. **Não há como validar o ecossistema de ponta a ponta sem o código-fonte e sem compilação reproduzível.** Mesmo com o código, falta um elo: a urna não publica uma medição assinada do software que executou. **[limite]**

Isso não é evidência de fraude. É a descrição do ponto em que a confiança deixa de ser verificável e passa a depender da instituição.

## 1. Como o processo funciona, segundo o TSE

| Etapa | O que o TSE diz que acontece | Data em 2026 |
|---|---|---|
| Código-fonte | Aberto às entidades legitimadas pelo art. 6º da Res. TSE 23.673/2021 (partidos, federações, OAB, PF, MP, Defensoria, Congresso, CGU, TCU, SBC e outras) para inspeção **dentro do TSE**, em sala agendada e ambiente controlado, sem poder levar o código. Em 2026, só 8 entidades inspecionaram (União Brasil, Senado, CNC, SBC, CNMP, PV, MPF e CGU), e nenhuma publicou relatório técnico. As Forças Armadas deixaram a lista em 2023 | de 02/10/2025 até a compilação **[TSE]**, detalhes em `docs/verificacoes-externas-2turno-2026.md`, seção 4 |
| Compilação | Os programas são compilados no TSE na presença das entidades | 31/08 a 04/09/2026 **[TSE]** |
| Assinatura e lacração | O TSE e as entidades assinam digitalmente os programas; os resumos digitais (hashes) são gerados, as mídias são lacradas e guardadas na sala-cofre | 04/09/2026 **[TSE]** |
| Impugnação | As entidades têm 5 dias para impugnar | até cerca de 09/09/2026 **[TSE]** |
| Publicação dos hashes | Listas de SHA-512 dos programas, por sistema e modelo de urna, no site do TSE | listas datadas de 01 e 02/09/2026, página atualizada em 04/09/2026 **[verificado]** |
| Carga das urnas | Os TREs geram as mídias (sistema GEDAI) e carregam as urnas; o software da urna verifica a assinatura de cada pacote | setembro e outubro **[TSE]**, com log público **[verificado]** |
| Dia da eleição | Teste de Autenticidade (conferência de hashes em urnas sorteadas) e Teste de Integridade (votação paralela filmada em urnas sorteadas) | 04/10 e 25/10 **[TSE]** |
| Encerramento | A urna imprime o BU, grava os arquivos na mídia de resultado e assina tudo no arquivo `.vsc` | 04/10 e 25/10 **[verificado]** |
| Transmissão | A mídia é lida nos locais de votação ou nos cartórios (JE-Connect, Coletor), que transmitem os arquivos ao TSE; a assinatura é conferida na recepção | noite da eleição **[TSE]** |
| Totalização | O TSE soma os BUs e publica o resultado em arquivos assinados (JWS) | noite da eleição **[verificado]** |
| Arquivos de urna | BU, RDV, log e `.vsc` de cada seção ficam públicos no portal de resultados e, depois, em pacotes por UF | 25/10 em diante; pacote completo do 2º turno em 26/10/2026 **[verificado]** |

## 2. As perguntas, uma a uma

### 2.1 O TSE publica algum hash do software que as equipes testaram?

**Sim, em parte.** O TSE publica as listas de resumos digitais (SHA-512 em base64) dos programas lacrados. Este projeto guardou as 32 listas oficiais, sem alteração, em `data/hashes-tse-2026/`, com o registro de cada download. **[verificado]**

O que falta:

- **As listas não têm assinatura digital.** São um HTML dentro de um zip, garantido só pelo HTTPS do site. Não há como provar depois que a lista de hoje é a mesma do dia da lacração, a não ser por cópias guardadas por terceiros. **[verificado]**
- **O hash é dos binários compilados no TSE, não do código que as entidades leram.** Quem inspecionou o código não consegue, fora do TSE, compilar o mesmo código e chegar ao mesmo hash. O TSE não publica compilação reproduzível (*reproducible build*): ambiente, compilador e passos que permitam a qualquer pessoa gerar bit a bit o mesmo binário. **[limite]**
- **Parte dos arquivos não tem hash publicado**, porque são gerados na própria urna (`uenux.cfg`, `avbootcfg.vsu`). Há também pacotes verificados na carga que não aparecem na lista pelo nome, e um que está na lista e nunca é verificado. O detalhe está em `docs/hash-software-urna-2026.md`. **[verificado]**

### 2.2 Como se atesta que o software antes, durante e depois da eleição é o mesmo?

| Mecanismo | Quem faz | O que prova | Publicado? |
|---|---|---|---|
| Verificação de assinatura dos pacotes na carga e a cada inicialização | o próprio software da urna | que o software se declarou íntegro | só como linha de log (`[SUCESSO]`), sem hash. O log público mostra 25 pacotes na carga e 28 itens por inicialização, todos com sucesso, nas 6.732 amostras **[verificado]** |
| Teste de Autenticidade | TSE e TREs, com entidades convidadas, em urnas sorteadas | que, naquelas urnas, os hashes emitidos batem com a lista | relatórios em ata, não publicados por seção **[limite]** |
| Teste de Integridade (votação paralela) | TREs, filmado, em urnas sorteadas | que, naquelas urnas, o BU bate com votos conhecidos | relatório do 2º turno previsto para até 24/11 (TREs) e 23/01/2027 (TSE) **[TSE]** |
| Verificações a pedido depois da eleição | entidades fiscalizadoras, conforme resolução | idem, nas urnas pedidas | não localizamos relatórios públicos de 2026 **[limite]** |

O problema estrutural é este: **a verificação contínua é feita pelo próprio software que se quer verificar.** Um programa adulterado pode escrever no log as mesmas linhas de sucesso. As verificações independentes do software (Autenticidade e Integridade) são por amostragem, organizadas pela Justiça Eleitoral, e o resultado não vira dado público por seção.

### 2.3 Quem garante que o software da urna é o mesmo que assina o BU, e vice-versa?

**Ninguém, com dados públicos.** O arquivo `.vsc` de cada seção tem duas assinaturas: **[verificado]**

1. **Assinatura de hardware:** uma chave por urna (499.179 certificados distintos), emitida pela autoridade certificadora do TSE, com algoritmo público (ECDSA P-521 nas UE2013 e UE2015, Ed521 nas UE2020 e UE2022). Este projeto conferiu as 5.487.289 assinaturas do 2º turno: nenhuma inválida (`docs/certificados-2turno-2026.md`). Essa chave assina o que o programa em execução mandar assinar. Ela não mede o software: o `.vsc` não traz hash do sistema carregado nem atestado de inicialização medida (como o de um TPM).
2. **Assinatura de software:** uma chave comum a todas as urnas (descritor `SEVIN`, conjunto `202607021654`), com algoritmo de governo (CEPESC) não publicado e sem chave pública divulgada. **Não pode ser verificada** fora do TSE. Mesmo que pudesse, provaria só que quem assinou tinha a chave, não qual programa rodava.

Conclusão: o BU prova **de qual urna** saiu, não **qual software** o produziu.

### 2.4 Quem garante que os sistemas do TSE não alteram os dados recebidos, nos cartórios ou na totalização?

**Essa parte é verificável e foi verificada.** **[verificado]**

- Cada BU é assinado pela urna antes de sair dela. Quem altera o arquivo depois (no pendrive, na leitura do cartório, na transmissão ou no banco do TSE) quebra a assinatura. As assinaturas de todos os arquivos publicados estão válidas.
- A soma de todos os BUs publicados é igual, voto a voto, ao resultado divulgado em todos os níveis: Brasil, 28 UFs e 5.757 municípios, nos dois turnos. Os 11.572 arquivos de resultado assinados (JWS) também conferem (`docs/jws-totalizacao-2026.md`).
- Os arquivos foram versionados durante a apuração e conferidos 8 vezes até 27/10, sem nenhuma troca. Em 03/11/2026 foram conferidos de novo e comparados com o pacote oficial publicado em 26/10 (seção 5).

**O que fica em aberto:** o TSE é ao mesmo tempo desenvolvedor do software, emissor dos certificados das urnas (AC URNA), operador da totalização e quem publica os arquivos. A assinatura protege contra alteração no caminho. **Não protege contra quem controla a emissão de chaves.** Um BU falso, assinado com um certificado emitido pela própria AC, passaria na conferência. A única defesa independente contra isso é o **BU impresso**: ele é afixado na seção e entregue aos fiscais, e o QR code permite comparar papel e arquivo publicado. Essa comparação em larga escala é a verificação mais forte ao alcance de partidos e cidadãos. Este projeto não a fez, porque não tem as fotos.

Também foram encontrados 53 certificados de urna emitidos depois do vencimento publicado da AC URNA (18/07/2026). Isso é uma pendência de esclarecimento, não indício de BU falso: as urnas desses certificados têm carga, log e votos coerentes. **[verificado]**

### 2.5 Dá para validar tudo de ponta a ponta sem o código-fonte?

**Não.** E, como está hoje, nem com o código-fonte. Para fechar a cadeia seriam necessários, todos juntos:

1. **Código-fonte auditável fora do TSE**, por tempo suficiente, por qualquer equipe técnica qualificada, e não só dentro de uma sala controlada.
2. **Compilação reproduzível**, com a publicação do ambiente, do compilador e dos passos, para que qualquer pessoa chegue ao mesmo hash publicado.
3. **Listas de hashes assinadas digitalmente** pelo TSE e pelas entidades, com as assinaturas publicadas.
4. **Medição do software em execução, assinada pelo hardware.** O `.vsc` precisaria levar o hash do software carregado, medido pelo módulo de segurança no boot, para comparação com a lista lacrada. Hoje essa ligação não existe nos arquivos públicos.
5. **Publicação, por seção, dos relatórios do Teste de Autenticidade** e da lista de hashes emitida pelas urnas verificadas, além dos arquivos `-hash.dat` e `-mr.ver`, que já são assinados mas não são publicados.
6. **Independência de software:** um registro físico do voto conferido pelo eleitor (voto impresso auditável) e recontável por amostragem. Sem isso, toda verificação do voto depende de algum software. O RDV, por exemplo, é escrito pelo mesmo programa que escreve o BU.

## 3. O que foi detectável, o que não é verificável e o que é impossível

### 3.1 Verificado por este projeto (nada anormal na contagem)

| Item | Resultado | Documento |
|---|---|---|
| Assinatura de hardware de todos os arquivos de todas as seções | 0 inválidas | `docs/certificados-2turno-2026.md` |
| Soma dos BUs = resultado oficial (Brasil, UF, município), nos dois turnos | igual voto a voto | `docs/auditoria-consistencia-bu-2026.md` |
| Resultados assinados (JWS) = soma dos BUs | 11.572 válidos, 0 divergências | `docs/jws-totalizacao-2026.md` |
| RDV = BU, em todas as seções, nos dois turnos | 0 divergências | `docs/rdv-log-2026.md` |
| Arquivos trocados depois de publicados | 0 em 8 voltas, de 25/10 a 27/10 | `docs/verificacoes-externas-2turno-2026.md` |
| Pacote oficial do 2º turno (26/10) x arquivos guardados na noite da eleição | 998.356 de 998.356 BUs e assinaturas idênticos | idem, seção 6 |
| Totais divulgados nunca caíram | 12 mil versões | idem |
| Votos de eleitores sem biometria favorecendo um lado | mesma proporção dos com biometria | `docs/biometria-1t-2t-2026.md` |
| Padrões estatísticos de 2026 x 2022 | nenhum padrão maior que o de 2022 | `docs/forense-estatistica-2026.md` |
| Programas verificados no log x lista oficial de hashes | todos na lista; divergências de nome e versão registradas | `docs/hash-software-urna-2026.md` |

### 3.2 Não verificável com dados públicos (só com acesso a dados que o TSE tem e não publica)

- Qual programa rodou em cada urna: os hashes emitidos pelas urnas e os relatórios do Teste de Autenticidade não são publicados.
- O resultado dos testes de integridade antes da data de divulgação.
- A assinatura de software (SEVIN e CEPESC).
- O conteúdo de `-hash.dat` e `-mr.ver`.
- Os logs e certificados da autoridade certificadora: quem emitiu cada certificado, quando, e se algum foi revogado. A lista de revogação da AC de totalização respondeu 403.
- Se a lista de hashes publicada hoje é a mesma do dia da lacração. Não há assinatura; dependemos de cópias de terceiros, como a do Internet Archive de 05/10/2026.

### 3.3 Impossível, mesmo com acesso, sem código-fonte aberto e compilação reproduzível

- Provar que o binário lacrado corresponde ao código inspecionado.
- Provar a ausência de comportamento malicioso no próprio código, por exemplo um desvio que só age em condições específicas, como data, volume ou modelo de urna.
- Detectar uma adulteração idêntica em todas as urnas. Testes comparativos entre grupos não veem uma alteração que não cria diferença entre grupos. Sobram as amostras do Teste de Integridade e o confronto com algo fora do software: o BU impresso, que é gerado pelo mesmo software, e um registro físico do voto, que não existe.

## 4. Alertas sobre a confiabilidade do processo

1. **Raiz de confiança única.** Desenvolvimento, compilação, emissão de chaves, operação da totalização, publicação dos dados e julgamento das impugnações estão na mesma instituição. A participação das entidades acontece em etapas e locais definidos por essa instituição.
2. **Sem independência de software.** Nenhum registro do voto existe fora do software da urna. O RDV e o BU vêm do mesmo programa; a recontagem pelo RDV confirma a coerência interna, não a fidelidade ao voto digitado.
3. **Inspeção de código pequena e sem relatório.** Em 2026, 8 entidades inspecionaram o código, em sala do TSE. Nenhum relatório técnico foi publicado. A Polícia Federal e a OAB assinaram os sistemas na lacração, mas não constam entre as que inspecionaram o código.
4. **Amostras sem dado público por seção.** Os testes que ligam software e resultado (Autenticidade e Integridade) são amostrais e os relatórios saem semanas ou meses depois.
5. **Hashes sem assinatura e sem compilação reproduzível.** A lista publicada só vale enquanto se confia no site e na cerimônia.
6. **O que é forte:** a cadeia **depois da urna**. Do momento em que o BU é assinado até o resultado divulgado, qualquer alteração seria detectável, e nenhuma foi encontrada. Uma fraude teria de acontecer **dentro da urna**, antes da assinatura, de forma idêntica em todas as urnas e sem deixar padrão estatístico; ou **na raiz de chaves do TSE**, o que seria exposto pelo confronto com os BUs impressos.

## 5. O que qualquer pessoa pode fazer

- **Fotografar o BU impresso da sua seção**, ou ler o QR code com o aplicativo Boletim na Mão, e comparar com o arquivo publicado da mesma seção no portal de resultados. Um conjunto grande dessas fotos, de várias regiões, é o teste independente mais forte disponível hoje contra fraude na totalização ou na raiz de chaves.
- **Pedir ao TSE**, pelos canais de transparência, a publicação dos itens das seções 2.5 e 3.2.
- **Guardar cópias com data** das listas de hashes e dos arquivos de urna. O versionamento deste projeto é um exemplo: `scripts/ele2026/versionar_t2.py`.

## Fontes

- Notícias do TSE sobre a lacração de 2026: [Sistemas das Eleições Gerais de 2026 são assinados digitalmente e lacrados pelo TSE](https://www.tse.jus.br/comunicacao/noticias/2026/Setembro/sistemas-das-eleicoes-gerais-de-2026-sao-assinados-digitalmente-e-lacrados-pelo-tse) e [Clica e Confirma: como funciona a lacração](https://www.tse.jus.br/comunicacao/noticias/2026/Setembro/clica-e-confirma-mostra-como-funciona-a-lacracao-dos-sistemas-eleitorais).
- Resolução TSE nº 23.673/2021 e alterações (fiscalização, auditoria e procedimentos de segurança): [texto no TRE-CE](https://www.tre-ce.jus.br/eleicao/eleicoes-2024/arquivos-mlep-2024/resolucao-tse-n-o-23-673-de-14-de-dezembro-de-2021).
- Totalização e transmissão: [Totalização dos votos é aberta, auditável e segura, diz TSE](https://www.diariodepernambuco.com.br/brasil/2026/08/11721101-totalizacao-dos-votos-e-aberta-auditavel-e-segura-diz-tse.html).
- Verificações deste projeto: documentos citados nas tabelas e `docs/veredicto-auditoria-2026.md`.
