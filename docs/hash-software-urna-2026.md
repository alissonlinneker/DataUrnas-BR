# Hash do software da urna: o que os arquivos públicos permitem verificar (2026)

Pergunta: os arquivos que a urna publica (BU, RDV, log e arquivo de assinatura `.vsc`) permitem saber **qual software rodou**, isto é, trazem o hash dos programas para comparar com a lista oficial de resumos digitais lacrada pelo TSE?

Levantamento feito em 27/10/2026 no servidor de processamento, só com arquivos já baixados (nenhum download novo do TSE). Arquivos temporários em memória (`/dev/shm`); nada foi gravado nas pastas de coleta.

## Resposta curta

**Não.** Nenhum arquivo público por seção traz o hash dos programas da urna.

- O `.vsc` assina e lista o SHA-512 de **11 arquivos de resultado** da seção (BU, RDV, log, imagens, biometria, `hash.dat`, `mr.ver`). Nenhum programa (`.vst`) está na lista.
- O log registra que a urna **verificou** a assinatura de 25 pacotes de software na carga e de 28 itens a cada inicialização, sempre com o texto `[SUCESSO]`. O log não traz o hash de nenhum deles: só o nome do pacote e o resultado.
- O BU traz a **versão** (`10.23.0.0 - Praia da Barra do Cahy`) e o **código de carga**, mas nenhum hash do software ou da carga.

O que dá para conferir publicamente é a consistência: a mesma versão, os mesmos pacotes verificados e o mesmo resultado em todas as urnas da amostra. O que não dá para conferir é se os bytes dos programas eram os lacrados. Essa conferência só existe fora dos arquivos públicos: na lista de hashes que a própria urna emite sob demanda e nas cerimônias do TSE.

## Fontes usadas

| Fonte | Conteúdo | Volume |
|---|---|---|
| Partes Parquet dos coletores (`~/dataurnas-mac/versoes/2026/t2*`, `~/dataurnas-versoes-t2`, `~/dataurnas-versoes-t2-nne`), linhas `vota` e `sa` | `.vsc` do 2º turno | 500.802 linhas, 499.207 `.vsc` distintos (o restante são cópias da mesma assinatura em duas pastas) |
| `~/dataurnas-t2/biometria/brutos/t1` e `t2` | `-log.jez` (ZIP com `logd.dat`) | 5.994 logs |
| `~/dataurnas-t2/emissao_tardia/t2` e `bh` | `-log.jez` e `-logsa.jez` | 738 logs |
| `~/dataurnas-t2/rdv_log/brutos` | BU, RDV e `.vsc` (sem log) | usado para decodificar BU de exemplo |
| `~/dataurnas-t2/emissao_tardia/aux` | aux.json (lista do que o TSE publica por seção) | 738 arquivos |

Os 6.732 logs são de 3.729 seções distintas (os logs do 2º turno acumulam os eventos do 1º). Por modelo, conforme a linha `Identificação do Modelo de Urna`: UE2022 2.638, UE2020 2.443, UE2015 1.151, UE2013 386, UE2013 e UE2015 no mesmo pacote (troca de urna) 110, UE2020 e UE2022 no mesmo pacote 4. Nenhum log ilegível.

Decodificação com os parsers do projeto (`src/dataurnas/parsers/signature.py`, `parse_vsc`; `src/dataurnas/parsers/log.py`; `asn1_helper.decode_envelope` para o BU) e especificação `spec/v2/assinatura.asn1`.

## 1. O arquivo de assinatura (`.vsc`)

### Estrutura

Pela especificação publicada (`EntidadeAssinaturaEcourna`), o `.vsc` tem três campos: `modeloEquipamento`, `assinaturaSW` e `assinaturaHW`. Cada uma das duas assinaturas é uma `EntidadeAssinatura` com data e hora, versão do protocolo, um descritor de quem assinou (`nomeUsuario`, `serial`), algoritmos de hash e de assinatura, o hash e a assinatura do próprio conteúdo, o conteúdo assinado (`conteudoAutoAssinado`, uma lista de `nomeArquivo` com hash e assinatura de cada arquivo), o certificado (opcional) e o identificador do conjunto de chaves (opcional).

Valores observados em todos os 499.207 `.vsc` do 2º turno:

| Campo | Parte de software (`assinaturaSW`) | Parte de hardware (`assinaturaHW`) |
|---|---|---|
| Quem assina (`nomeUsuario`) | `SEVIN` em todas | identificador da urna: `UEAO` nas UE2020 e UE2022, `ueao0NNNNNNN` nas UE2013 e UE2015 |
| `serial` do descritor | `20260708` em todas | número da urna (por exemplo `2368507`), diferente em cada urna |
| `conjuntoChave` | `202607021654` em todas | ausente |
| Algoritmo de assinatura | `cepesc`, 256 bits, em todas | `eddsa` (Ed521) nas UE2020 e UE2022; `ecdsa` P-521 nas UE2013 e UE2015 |
| Algoritmo de hash | SHA-512 | SHA-512 |
| Tamanho de cada assinatura | 4.765 bytes | 132 bytes (Ed521) ou 139 bytes (ECDSA) |
| Certificado embutido | nenhum | certificado X.509 da urna, emitido pela AC UE2020, AC UE2022 ou AC URNA |
| Data e hora | 25/10/2026 (dia da eleição) | igual à da parte de software |
| SHA-512 do conteúdo igual ao hash autoassinado | sim, em todas | sim, em todas |

A lista de arquivos e os hashes são os mesmos nas duas partes; as assinaturas de arquivo são diferentes (nenhuma assinatura de software repete a de hardware do mesmo arquivo).

### Arquivos cobertos

| Modelo | `.vsc` | Arquivos listados |
|---|---:|---|
| UE2022 | 199.122 | 11: `-bu.dat`, `-rdv.dat`, `-log.jez`, `-imgbu.dat`, `-imgze.dat`, `-jufa.dat`, `-hash.dat`, `-mr.ver`, `-wsqbio.jez`, `-wsqman.jez`, `-wsqmes.jez` |
| UE2020 | 201.206 | os mesmos 11 |
| UE2015 | 88.002 | os mesmos 11 em 87.713; 8 (sem os três `wsq*`) em 260; 6 (`-busa.dat`, `-imgbusa.dat`, `-logsa.jez`, `-rdv.dat`, `-hash.dat`, `-mr.ver`) nos 29 `.vsc` do tipo `sa` |
| UE2013 | 12.472 | os mesmos 11 em 11.451; 8 em 1.021 |

(Contagens por linha de Parquet, com as cópias entre pastas; os números por seção estão em `docs/certificados-2turno-2026.md`.)

**Nenhum programa aparece na lista.** Todos os nomes começam pelo prefixo da seção (`o03221uf...`) e são arquivos gerados no encerramento. Não há `.vst`, `.vsu`, binário, biblioteca ou módulo.

Dos 11 arquivos, o TSE publica por seção só BU, RDV, log, o próprio `.vsc` e, em algumas seções, a imagem do BU (aux.json, campo `tp`: `bu`, `rdv`, `log`, `vota`, `imgbu`, e `busa`, `logsa`, `sa` no exterior). O `.vsc` traz o SHA-512 de `-hash.dat` e `-mr.ver`, mas esses arquivos não são publicados; pelo nome, `-mr.ver` poderia conter informação de versão, o que **não pode ser conferido** sem o arquivo.

### Exemplos (2 a 3 seções por modelo, 2º turno)

| Seção | Modelo | Assinante HW (CN do certificado) | AC emissora | Certificado emitido em | Parte SW |
|---|---|---|---|---|---|
| `SP/61069/0239/0162` | UE2022 | `UEAO02368507` | AC UE2022 | 17/11/2023 | SEVIN, serial 20260708, conjunto 202607021654, CEPESC |
| `SP/61069/0239/0165` | UE2022 | `UEAO02369141` | AC UE2022 | 17/11/2023 | idem |
| `SP/61069/0239/0167` | UE2022 | `UEAO02369161` | AC UE2022 | 17/11/2023 | idem |
| `SP/61298/0047/0006` | UE2020 | `UEAO02073214` | AC UE2020 | 05/05/2022 | idem |
| `SP/61298/0047/0070` | UE2020 | `UEAO02072145` | AC UE2020 | 05/05/2022 | idem |
| `SP/61298/0047/0167` | UE2020 | `UEAO02072703` | AC UE2020 | 05/05/2022 | idem |
| `SP/61336/0239/0001` | UE2015 | `ueao01806274` | AC URNA | 04/08/2016 | idem |
| `SP/61336/0239/0002` | UE2015 | `ueao01806351` | AC URNA | 04/08/2016 | idem |
| `SP/61336/0239/0003` | UE2015 | `ueao01806883` | AC URNA | 05/08/2016 | idem |
| `SP/61336/0239/0017` | UE2013 | `ueao01668508` | AC URNA | 27/08/2013 | idem |
| `SP/61336/0239/0045` | UE2013 | `ueao01665140` | AC URNA | 22/08/2013 | idem |
| `SP/61573/0294/0075` | UE2013 | `ueao01668132` | AC URNA | 27/08/2013 | idem |

### Chave da parte de hardware

É uma chave por urna: 499.179 certificados distintos e 499.179 chaves públicas distintas para 499.207 seções (as repetições são as 29 seções do exterior apuradas por duas urnas de contingência; ver `docs/certificados-2turno-2026.md`). O certificado é emitido pela AC do modelo, com validade de cerca de 5.000 dias, e foi gerado anos antes da eleição (2013 a 2026). A assinatura de hardware foi conferida em todas as seções e em todos os 5.487.289 arquivos listados, sem nenhuma falha.

Essa assinatura prova que os arquivos de resultado foram assinados por um equipamento que guarda a chave privada de uma urna certificada pelo TSE. **Ela não diz nada sobre o software**: a chave assina o que o programa em execução pedir. Não há no `.vsc` nenhuma medição do software (hash do sistema carregado, atestado de inicialização medida ou valor de registrador de TPM).

### Chave da parte de software

O descritor é o mesmo em todas as urnas, dos quatro modelos: usuário `SEVIN`, serial `20260708`, conjunto de chaves `202607021654`. O nome SEVIN também aparece no log, na mensagem de erro `Falha ao validar assinatura SEVIN` ligada a pacotes da mídia de votação (ver adiante), e é o nome da pasta do TSE onde ficam os certificados no resumo digital do sistema HOLOCRON (`D:\Aplic\SEVIN\Holocron\certificados`, citado em `scripts/ele2026/analisar_certificados.py`). Pelo descritor da especificação, o serial é a data de geração do conjunto de chaves; o identificador `202607021654` lê-se como 02/07/2026 16:54. Por isso a chave de software é, ao que tudo indica, **uma chave do TSE comum a todas as urnas desta eleição**, distribuída com a carga. De onde exatamente ela vem dentro da urna não é dito nos arquivos públicos; o log mostra um pacote `/dsk/fe/estatico/chave/avusrchave.vst` (na carga) e `/dsk/fi/estatico/chave/avusrchave.vst` (a cada inicialização) verificado com sucesso, o que é compatível com essa hipótese, mas não a prova.

A assinatura em si é opaca. Nas 6.005.636 assinaturas de software examinadas (a do conteúdo e a de cada arquivo, em todas as linhas `vota` e `sa`, com as cópias entre pastas), todas têm 4.765 bytes e começam pelos mesmos 8 bytes ASCII `24.01.03`; o resto varia de uma assinatura para outra. Não há certificado nem chave pública embutidos: numa amostra de 583 `.vsc`, só 20 das 4.765 posições de byte são iguais em todas as assinaturas, o que exclui um bloco comum como um certificado ou uma chave. O algoritmo CEPESC é de governo e não é publicado, e o TSE não publica chave pública para conferir essa parte. Por isso **essa assinatura não pode ser verificada** por quem está fora do TSE; só o SHA-512 do conteúdo da parte de software é conferível (e confere em todas).

### O que dá para afirmar a partir do `.vsc`

- Dá para afirmar: os arquivos de resultado publicados são os que uma urna certificada assinou, e a lista de hashes é a mesma nas duas partes.
- **Não** dá para afirmar que o software que assinou era o lacrado. A parte de hardware não mede o software. A parte de software, mesmo se pudesse ser verificada, mostraria só que quem assinou tinha acesso à chave SEVIN, que é a mesma em todas as urnas; não mostraria o hash dos programas.

## 2. Logs da urna

### Eventos sobre versão, carga e assinatura

Textos exatos (com números trocados por `N` onde variam) e cobertura nos 6.732 logs. "Todos" quer dizer 100% dos logs de cada um dos quatro modelos.

| Aplicativo | Texto | Logs |
|---|---|---|
| SCUE, GAP, ATUE, VOTA | `Versão da aplicação: 10.23.0.0 - Praia da Barra do Cahy` | todos; nenhuma outra versão encontrada |
| SCUE, GAP, ATUE | `Identificação do Modelo de Urna: UE20NN` | todos |
| SCUE | `Versão do UEFI: IYEA24_P` | todos os UE2020 (2.443), nenhum outro valor |
| SCUE | `Versão do UEFI: IYEA26_P` | todos os UE2022 (2.638), nenhum outro valor |
| SCUE | (sem linha de UEFI) | UE2013 e UE2015 |
| SCUE | `Código de carga N.N.N.N.N.N.N.N gravado na tabela de correspondência` | todos |
| SCUE | `Mídia de carga gerada pelo computador (nome - tpm - instalação): <nome> - <serial TPM> - <instalação>` | todos |
| SCUE | `Data e hora da geração da mídia de carga: ...`, `Mídia de carga gerada pelo usuário: N` | todos |
| SCUE | `Verificação de assinatura de aplicação por etapa [N] - [Pacote: <caminho>.vst] - [SUCESSO]` | todos; 25 pacotes distintos, o **mesmo conjunto** nos quatro modelos |
| SCUE | `Verificação de assinatura de dado por etapa [N] - [Pacote: ...] - [Arquivo: ...] - [SUCESSO]` | todos; 9 pacotes de dado, que variam só pela UF |
| SCUE | `Identificação de assinatura do arquivo` seguido de `UENUX CFG`, `Tabela de correspondência`, `EG Geral MI`, `EG GAP 1 MI`, `EG VOTA MI`, `EG SA MI`, `EG RED MI` | todos; a linha não traz hash nem resultado |
| SCUE | `Imprimindo extrato de carga`, `Confirmação do extrato de carga` | todos |
| GAP | `Verificação de assinatura - Etapa [N] - [<caminho>] - [SUCESSO]` | todos; 28 etapas por inicialização, mesmo conjunto em todos os modelos a menos dos arquivos de dado da UF (`oNuf-ce.vsc`, `oNuf-ste.vsc`) |
| GAP | `Solicitação ao INIT para executar o aplicativo - SISTEMA DE AUTOTESTE` | todos |
| GAP | `A chave pública (99.pub) foi encontrada na mídia de resultado`, `O número de série da chave pública (99.pub): 36452507285E23E9`, `Iniciando aplicação VERIFICAÇÃO DE ASSINATURAS` | 278 logs (3% a 7% por modelo); o número de série é o **mesmo** em todas as 290 ocorrências, dos quatro modelos |
| VOTA | `Gerando relatório [RESUMO DA ZERÉSIMA] [INÍCIO]` / `[TÉRMINO]`, `Imprimindo relatório [RESUMO DA ZERÉSIMA] via nº [N]` | 6.731 |
| VOTA | `Gerando arquivo de resultado [hash.dat] + [Início]` / `+ [Término]` | 6.728 |
| VOTA | `Preparando para assinatura dos arquivos de resultados`, `Início do procedimento de assinatura dos arquivos de resultados`, `Término do procedimento de assinatura dos arquivos de resultados`, `Copiando arquivo de resultado para ME: [vota.vsc]` | 3.708 (os que chegaram ao encerramento dentro do pacote examinado) |

Pacotes de software verificados na carga (SCUE, os mesmos 25 em todos os modelos): `/bin/avbin.vst`, `/boot/boot/avboot.vst`, `/boot/boot/avbootcfg.vst`, `/lib/avlib.vst`, `/lib/modules/avmod.vst`, `/lib/modules/ue2013/avmodue2013.vst`, `/lib/modules/ue2015/avmodue2015.vst`, `/lib/modules/ue2020/avmodue2020.vst`, `/lib/modules/ue2022/avmodue2022.vst`, `/lib/plugins/generic/avlibqtgeneric.vst`, `/lib/plugins/imageformats/avlibqtimageformats.vst`, `/lib/plugins/platforms/avlibqtplatforms.vst`, `/uenux/bin/avusrbin.vst`, `/uenux/lib/avusrlib.vst`, `/uenux/lib/avusrlibue2013.vst`, `/uenux/lib/avusrlibue2015.vst`, `/uenux/lib/avusrlibue2020.vst`, `/uenux/lib/avusrlibue2022.vst`, `/etc/avetc.vst`, `/etc/RHVoice/avrhvoice.vst`, quatro pacotes de `/share/RHVoice/...` e `/dsk/fe/estatico/chave/avusrchave.vst`. Na mídia de votação também são verificados `/dsk/fe/estatico/jez/vota_apl.vst`, `vota_ofi.vst`, `avpart_ofi.vst` e `avgm.vsc`.

Na inicialização (GAP) entram, além dos pacotes acima na versão do modelo, `/uenux/bin/avpart90.vst`, `avpart91.vst`, `avpart97.vst`, `avpart99.vst`, `/boot/boot/avbootcfg.vsu`, `/dsk/fi/estatico/dadoscarga.vsu`, `infomidia.vsc` e os arquivos de dado da seção e da UF.

### Hash de software no log

**Nenhum.** Em nenhuma linha dos 6.732 logs aparece hash de programa. As únicas sequências hexadecimais longas na descrição dos eventos são:

- número de série do certificado do TPM do computador que gerou a mídia de carga ou de votação (varia por computador);
- serial da mídia de votação (`Serial da MV: ...`);
- nomes de log aninhado (`Arquivo <número>-01.jez referente ao log da ME`);
- número de série da chave pública `99.pub` (`36452507285E23E9`, igual em todas as urnas; é uma chave da mídia de resultado usada pelo aplicativo de verificação, não um hash de software).

A última coluna de cada linha do log é um código de 16 dígitos hexadecimais que muda a cada linha; é um código de integridade da própria linha do log, não um hash do software.

O aplicativo `VERIFICAÇÃO DE ASSINATURAS` (é por ele que a urna pode mostrar ou imprimir a lista de hashes dos seus sistemas, conferida no Teste de Autenticidade) foi iniciado em 278 logs, mas o log só registra a abertura e a finalização; **a lista de hashes não vai para o log**.

### Falhas de verificação registradas

Todas as linhas de verificação de assinatura de pacote de software (`.vst`) terminam em `[SUCESSO]`. As falhas encontradas envolvem só arquivos de dado ou de mídia, nunca um programa:

| Seção | Modelo | Evento (texto do log, resumido) |
|---|---|---|
| `SP/71072/0353/1020`, `SP/71072/0353/1033`, `SP/71072/0422/0333` | UE2022, UE2022, UE2020 | `Falha durante leitura do serial de votação da MV. Falha ao validar assinatura SEVIN \| pacote: (/dsk/fe/estatico/infomidia.vsc...)` |
| `RJ/60011/0125/0335`, `RJ/60011/0123/0054` | UE2020 | `Verificação de assinatura - Etapa [26] - [/dsk/fe/estatico/infomidia.vsc] - [ERRO]` e `Erro na verificação de integridade do sistema. Desligue a urna e faça uma nova carga.` |
| `CE/14117/0013/0418` | UE2020 | `Validando assinaturas da MV (9336) \| Erro na verificação de integridade do sistema` (falta o arquivo `-lo` da seção na mídia de votação) |
| `SC/82198/0034/0167` | UE2015 | `Erro na verificação de assinatura do arquivo - vota.vsu` |
| `RJ/60011/0007/0460` | UE2013 e UE2015 | `Erro na verificação de assinatura do arquivo - bu.vsu` e `Falha ao validar assinatura UE \| pacote: (/dsk/fi/dinamico/trab1/bu.vsu)` |
| `MG/48658/0185/0184`, `SP/71072/0328/0007` | UE2020, UE2015 | `GAP erro 73 \| Validação do VOTA \| Erro verificando assinatura do arquivo turno2.jez em /dsk/mr/turno2.vsc` |
| `BA/38830/0162/0153` | UE2013 | `MSD - MSD com problema ao assinar.: Erro ao inicializar assinatura. - 6` (autoteste) |

São eventos operacionais de mídia (mídia de votação, mídia de resultado, área de trabalho do BU) que a urna detectou e recusou; não indicam software diferente e não trazem hash.

## 3. BU e zerésima

O BU (`EntidadeBoletimUrna`, `spec/v2/bu.asn1`) traz, sobre software e carga, só estes campos em `urna`:

| Campo | Exemplo (`AC/01031/0003/0095`, 2º turno) |
|---|---|
| `versaoVotacao` | `10.23.0.0 - Praia da Barra do Cahy` (igual nas 499.207 seções) |
| `carga.codigoCarga` | `742507921023510426336993` |
| `carga.dataHoraCarga` | `20260923T200300` |
| `carga.numeroInternoUrna` | `2047850` |
| `carga.numeroSerieFC` | 4 bytes (série da mídia de carga) |
| `carga.identificadorGeradorMidia` | `nome` `ZAC001STD25`, `serialCertificadoTPM` `29B7B62AF8A49BD65FD3`, `serialInstalacao` `5372FFE5` |
| `numeroSerieFV` | 4 bytes (série da mídia de votação) |
| `historicoCodigosCarga` | lista de códigos de carga |

Não existe campo de hash do software nem da carga. O código de carga é um número de 24 dígitos próprio de cada carga de urna (499.180 códigos distintos para 499.207 seções; o mesmo número aparece no log como `Código de carga N.N.N.N.N.N.N.N gravado na tabela de correspondência`). Ele identifica **qual carga** foi feita, não **o que** havia nela. O identificador do gerador de mídia aponta o computador e a instalação que gravaram a mídia de carga, não o conteúdo.

A zerésima não é publicada como arquivo; o log só registra que o relatório `[RESUMO DA ZERÉSIMA]` foi gerado e impresso. O relatório impresso fica na seção.

## O que é e o que não é verificável publicamente

| Pergunta | Verificável com arquivos públicos? | Como |
|---|---|---|
| Os arquivos de resultado (BU, RDV, log) são os que a urna assinou? | **Sim** | SHA-512 e assinatura de hardware do `.vsc`, cadeia até a AC do modelo (feito em `docs/certificados-2turno-2026.md`) |
| Qual versão de software a urna declarou? | **Sim**, como texto | `versaoVotacao` no BU e `Versão da aplicação` no log: `10.23.0.0 - Praia da Barra do Cahy` em todas |
| A urna diz ter verificado a assinatura dos seus pacotes? | **Sim**, como registro | log: 25 pacotes na carga e 28 etapas a cada inicialização, todos `[SUCESSO]`, mesmo conjunto em todos os modelos |
| Versão de firmware (UEFI) | **Sim**, nas UE2020 e UE2022 | log: `IYEA24_P` (UE2020) e `IYEA26_P` (UE2022), uniforme |
| Hash dos programas que rodaram, para comparar com os resumos digitais lacrados | **Não** | nenhum arquivo público por seção traz esse hash |
| Assinatura de software (SEVIN, CEPESC) | **Não** | algoritmo e chave pública não publicados |
| A chave de hardware só assina se o software for o lacrado | **Não** | o `.vsc` não traz medição de inicialização nem atestado do TPM |
| Conteúdo de `-hash.dat` e `-mr.ver` | **Não** | listados no `.vsc` com SHA-512, mas não publicados |

## O que seria preciso para fechar a lacuna

1. **Lista oficial de resumos digitais.** O TSE publica os arquivos `path1u13`, `path1u15`, `path1u20` e `path1u22` (ambiente da urna por modelo) na página "Resumos digitais (hashes) das Eleições 2026". Na tentativa registrada em `docs/verificacoes-externas-2turno-2026.md`, o site respondeu 403 e não havia cópia arquivada. A página avisa que `uenux.cfg` e `avbootcfg.vsu` não têm hash publicado por serem gerados pela urna; os dois aparecem no log (`Identificação de assinatura do arquivo UENUX CFG` e a etapa `/boot/boot/avbootcfg.vsu`).
2. **Lista emitida pela urna.** A comparação entre essa lista oficial e a urna em uso só acontece quando a urna emite a própria lista (aplicativo `VERIFICAÇÃO DE ASSINATURAS`, Teste de Autenticidade nas seções sorteadas, auditorias de partidos e entidades). O resultado não vai para o log nem para o `.vsc`. Os relatórios do Teste de Autenticidade do 2º turno não foram encontrados (ver `docs/verificacoes-externas-2turno-2026.md`).
3. **Publicação de `-hash.dat` e `-mr.ver`.** Ambos já são assinados por cada urna; publicá-los permitiria ao menos ver o que contêm.
4. **Meio de verificar a assinatura SEVIN.** Sem a publicação do algoritmo ou de uma chave pública, a parte de software do `.vsc` continua sem conferência independente.

## Limites deste levantamento

- Os logs examinados são uma amostra (3.729 seções, concentradas nas coletas de biometria e de emissão tardia, com peso de SP e RJ), não as 499.207 seções. Os `.vsc` e os BUs cobrem todas as seções do 2º turno.
- As linhas de verificação do log são o que o próprio software da urna escreve. Um software diferente do lacrado poderia escrever as mesmas linhas; por isso elas mostram consistência, não autenticidade.
- A leitura de SEVIN como chave do TSE comum a todas as urnas vem do descritor igual em 100% dos `.vsc` e do uso do nome no log e no resumo digital; a origem exata da chave dentro da urna não é documentada nos arquivos públicos.

## Confronto com a lista oficial de hashes

Levantamento de 27/10/2026, 07h13 a 07h40 UTC. Os arquivos oficiais foram obtidos e estão guardados, sem nenhuma alteração, em `data/hashes-tse-2026/` (32 zips, `SHA256SUMS` e `download-log.txt` com URL, status e horário de cada requisição).

### Como os arquivos foram obtidos

| Data e hora (UTC) | Origem | URL | Resultado |
|---|---|---|---|
| 27/10 07:13:30 | Mac, `curl` com User-Agent de navegador | `https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/hash/resumos-digitais-hashes-das-eleicoes-2026-1o-e-2o-turnos` | 403 (Akamai, "Access Denied") |
| 27/10 07:13:30 | Mac, idem | mesma página sem `www` | 403 |
| 27/10 07:13:39 | servidor de processamento (London), idem | página com e sem `www` | 403 e 403 |
| 27/10 07:14:33 | Internet Archive, índice CDX | página de 2026 | uma captura com conteúdo: 05/10/2026 10:30:12, status 200 |
| 27/10 07:15:11 | Internet Archive | `web.archive.org/web/20261005103012id_/...` | 200; dela saíram os 32 links reais (`.../hash/arquivos/2026/<ambiente>/<nome>`) |
| 27/10 07:16:34 | Internet Archive, índice CDX | prefixo `.../hash/arquivos/2026/` | só 5 capturas, todas com status 204 (corpo vazio) |
| 27/10 07:17:02 | Mac e London, User-Agent de navegador | `.../sistemas-em-ambiente-urna-eletronica/path1u20`, `.../path1u20/@@download/file`, `.../path1u20/@@display-file/file` | 403 nas seis tentativas |
| 27/10 07:17:49 | Mac e London | cópia no TRE-PE (`www.tre-pe.jus.br/eleicoes/eleicoes-2026/resumos-digitais-hashes-das-eleicoes-2026-1o-turno-e-2o-turnos`) e `www.justicaeleitoral.jus.br` | 403 |
| 27/10 07:18:42 | Mac, `curl` com o conjunto completo de cabeçalhos que um navegador envia (`Accept`, `Accept-Language`, `Accept-Encoding`, `sec-ch-ua*`, `Sec-Fetch-*`, `Upgrade-Insecure-Requests`, HTTP/2) | `.../path1u20` | **200**, `application/zip` |
| 27/10 07:18:55 a 07:20:38 | Mac, mesmos cabeçalhos, uma requisição a cada 2 a 4 segundos | a página e os 32 arquivos | 200 em todos |

O bloqueio do site recusa clientes sem os cabeçalhos de navegador; nenhum proxy, VPN ou troca de IP foi usado. Os links da página ao vivo são os mesmos da captura de 05/10, e a página continua com "Última atualização: 04.09.2026 18:08". O cabeçalho `Last-Modified` do `path1u20` é 04/09/2026 19:17:32 GMT.

### Formato

- Cada link devolve um zip com um único HTML (mais uma entrada `__MACOSX/._<nome>.html`, resto do compactador do macOS que só guarda o atributo `com.apple.provenance`). As entradas do zip têm data de 03/09/2026 18:41.
- O HTML é uma tabela `Arquivo | SHA512b64 (radix)`: SHA-512 do arquivo, em base64. Título "Eleições Gerais 2026" e subtítulo com o sistema e a data (`Urna 2020 - 02/09/2026`, `GEDAI-UE - 02/09/2026`; as mídias de verificação VAD-PC têm 01/09/2026).
- **Não há assinatura digital.** O zip não traz `.sig`, `.p7s` nem outro arquivo além do HTML; a página não aponta nenhuma assinatura; o HTML não tem bloco assinado. A única garantia de origem é o HTTPS do site do TSE. As assinaturas das entidades (MP, OAB, CONFEA) aparecem só como **arquivos listados** nas mídias de verificação (`90.pub`, `91.pub`, `97.pub`, `99.pub` e os `.vpe`), não como assinatura da lista.
- Nas listas da urna (`path1u13`, `path1u15`, `path1u20`, `path1u22`) há uma seção `ARQUIVOS BASE` (135, 136, 140 e 140 arquivos) e 28 seções `UF = XX` (27 UFs e ZZ), cada uma com 17 arquivos de `/dsk/fi/estatico/chave/` e uma linha `HASH GERAL UF = XX`. O modo de cálculo do hash geral não é descrito; ele não foi reproduzido com as combinações simples testadas (concatenação dos hashes em base64, binário ou hexadecimal, com e sem a seção base, em ordem original ou alfabética).

### (a) Pacotes verificados no log contra a lista do modelo

Mesma amostra da seção 2 (6.732 logs; por modelo declarado no log: UE2022 2.639, UE2020 2.446, UE2015 1.195, UE2013 452). As 276.748 linhas `Verificação de assinatura de aplicação/dado por etapa` da carga terminam todas em `[SUCESSO]`, assim como as da inicialização. O resultado é o mesmo nos quatro modelos.

**Carga (SCUE, 25 pacotes de aplicação, os mesmos em todos os logs):**

| Situação | Pacotes |
|---|---|
| Na lista do modelo (16) | `/bin/avbin.vst`, `/boot/boot/avboot.vst`, `/etc/avetc.vst`, `/etc/RHVoice/avrhvoice.vst`, `/lib/avlib.vst`, `/lib/modules/avmod.vst`, `/lib/plugins/generic/avlibqtgeneric.vst`, `/lib/plugins/imageformats/avlibqtimageformats.vst`, `/lib/plugins/platforms/avlibqtplatforms.vst`, os quatro `.vst` de `/share/RHVoice/...`, `/uenux/bin/avusrbin.vst`, `/uenux/lib/avusrlib.vst` e `/dsk/fe/estatico/chave/avusrchave.vst` (na lista como `/dsk/fi/estatico/chave/avusrchave.vst`, um hash por UF) |
| **Fora da lista pelo nome (9)** | `/boot/boot/avbootcfg.vst`; `/lib/modules/ue2013/avmodue2013.vst`, `ue2015/avmodue2015.vst`, `ue2020/avmodue2020.vst`, `ue2022/avmodue2022.vst`; `/uenux/lib/avusrlibue2013.vst`, `avusrlibue2015.vst`, `avusrlibue2020.vst`, `avusrlibue2022.vst` |

A lista de cada modelo traz só o nome instalado: `/lib/modules/ue20NN/avmodue.vst` (só a pasta do próprio modelo) e `/uenux/lib/avusrlibue.vst` (um hash diferente em cada modelo). A leitura mais provável é que a mídia de carga leve os pacotes dos quatro modelos com o ano no nome e a urna instale o do seu modelo com o nome genérico, que é o verificado a cada inicialização (abaixo) e está na lista. Isso não está escrito em nenhum documento público, e os hashes dos pacotes com o ano no nome não são publicados. O `avbootcfg.vst` também não está na lista; a página do TSE só justifica a ausência de `uenux.cfg` e `avbootcfg.vsu` (gerados pela urna), não a do `.vst`.

Na mesma etapa de carga a urna verifica, como "dado", os pacotes da mídia de votação `/dsk/fe/estatico/jez/vota_apl.vst`, `vota_ofi.vst` e `avpart_ofi.vst`. Eles **não** estão nas listas da urna, mas estão na lista do GEDAI (`D:\Aplic\SEVIN\GEDAIUE\aplic\uenux\vota_apl.vst`, `vota_ofi.vst`, `avpart_ofi.vst`, com os `.jez` correspondentes), o que é coerente com o GEDAI gerar a mídia de votação. O `avgm.vsc` e os pacotes de dados da eleição (`o<pleito><uf>00000-ca.vsc`, `-fo.vsc`, `-ce.vsc`) não estão em nenhuma lista, o que é esperado para dados.

**Inicialização (GAP, 28 etapas):** os 22 pacotes de programa estão todos na lista do modelo: `/bin/avbin.vst`, `/boot/boot/avboot.vst`, `/etc/avetc.vst`, `/etc/RHVoice/avrhvoice.vst`, `/lib/avlib.vst`, `/lib/modules/avmod.vst`, `/lib/modules/ue20NN/avmodue.vst` (o do próprio modelo, em 100% dos logs de cada modelo), os três plugins Qt, os quatro de RHVoice, `/uenux/bin/avpart90.vst`, `avpart91.vst`, `avpart97.vst`, `avpart99.vst`, `/uenux/bin/avusrbin.vst`, `/uenux/lib/avusrlib.vst`, `/uenux/lib/avusrlibue.vst` e `/dsk/fi/estatico/chave/avusrchave.vst`. Fora da lista ficam só arquivos gerados ou de dados: `/boot/boot/avbootcfg.vsu` (exceção declarada pelo TSE), `/dsk/fi/estatico/dadoscarga.vsu`, `/dsk/fe/estatico/infomidia.vsc`, `<seção>-lo.vsc`, `o00000br-pu.vsc`, `o01219-cp.vsc` e os arquivos da UF `-ce.vsc` e `-ste.vsc`.

**No sentido inverso**, dos 23 pacotes `.vst`/`.vsu`/`.vsc` de cada lista da urna, só um nunca aparece verificado em nenhum log: **`/uenux/bin/avusrbinof.vst`** (nos quatro modelos). Os demais itens das listas (binários, bibliotecas `.so`, módulos `.ko`, arquivos de voz e chaves) não são citados um a um no log; em tese estão cobertos pelos pacotes `.vst` que os assinam, mas o log não permite conferir isso.

### (b) Versão 10.23.0.0

As listas **não trazem número de versão**: só o título, a data e os hashes. O arquivo `/etc/versoes.properties` tem o mesmo SHA-512 (`aGN9HJl4/rSW3piRpoTa...`) nas quatro listas da urna e nas listas do GEDAI, do Sorteio e da Votação (`D:\Aplic\SEVIN\...\aplic\versoes.properties`); o mesmo vale para `dependencias.properties` (`BKTJ72c14pme3oSV...`). Isso mostra que os sistemas lacrados compartilham um único arquivo de versões, mas o conteúdo dele não é publicado. Logo, a versão `10.23.0.0 - Praia da Barra do Cahy` declarada em 100% dos logs e dos BUs **não pode ser ligada a um hash** com o que o TSE publica.

### (c) Chaves e certificados

| Item | Na lista oficial? | Confronto |
|---|---|---|
| `99.pub` (série `36452507285E23E9` no log) | Sim, nas mídias de verificação do TSE (VAD-PC e VAD-JEC), SHA-512 `XM+fsGzYpK2Ftp0v2DiXP2KMD9fu1iHIoeBokZWibI7Te8rztG2xBayGSILnvLRvpT4XB9eOX4uPX21L0almIQ==` | As outras entidades têm chave própria: `91.pub` (MP), `90.pub` (OAB), `97.pub` (CONFEA). Os pacotes `avpart90/91/97/99.vst` da urna, verificados em toda inicialização, seguem a mesma numeração. Nos logs só aparece a `99.pub` (262 logs nesta varredura), nunca 90, 91 ou 97. **Não dá para conferir** o número de série contra o hash: o arquivo `99.pub` não é publicado e o log só traz o número de série. |
| `acue2020.pem` (`data/certificados/ac/`) | Sim, `D:\Aplic\SEVIN\Holocron\certificados\acue2020.cer` (lista HOLOCRON) | **Confere** byte a byte: `LLveJWbhgUEiPfm/WlQL...` |
| `acue2022.pem` | Sim, `acue2022.cer` (HOLOCRON) | **Confere**: `nawawQDNRHwS4X5kYuMN...` |
| `acurna.pem` (AC URNA) | Não, em nenhuma das 32 listas | Sem confronto (SHA-512 do nosso arquivo: `rMtCT745kgM9uj0IY6x5...`) |
| `acraiz-ue.pem`, `acraizuev2.cer`, `acurnav2.cer` | Sim (HOLOCRON), com os mesmos hashes já registrados em `data/certificados/README.md` | Os arquivos continuam não obtidos |
| Outros certificados | `uedadoschaves.cer`, `ACHSM-DesktopJE-RegistroAssinatura.cer`, `ACHSM-DesktopJE-RegistroSigilo.cer` (HOLOCRON); `acraiz-je.pem` (GEDAI, Sorteio e Votação, mesmo hash) | Não temos os arquivos |

Nenhuma lista da urna traz certificado (`.cer`, `.pem`, `.crt`). As chaves da urna aparecem por UF em `/dsk/fi/estatico/chave/` (17 arquivos, inclusive `.pri`): `sevin.ber.pub`, `pu.ber.pub`, `sc.ber.pub`, `secad.ber.pub`, `secinp.ber.pub` e `seint.ber.pub` têm **um único hash** nas 28 UFs e nos quatro modelos; os outros 11 (`ue.ber.pri`, `ue.ber.pub`, `tse.ber.pub`, `log.ber.pri`, `cv.ber.pri`, `sc.ber.pri`, `bu.pk1`, `bio.sk1`, `jufa.pk1`, `wsq.pk1`, `avusrchave.vst`) mudam de UF para UF e são iguais entre modelos. O `sevin.ber.pub` único reforça a leitura da seção 1 de que a chave SEVIN é comum a todas as urnas, mas o arquivo não é publicado, então a assinatura de software do `.vsc` continua sem conferência.

### (d) GEDAI

A lista `pc1geda` ("GEDAI-UE - 02/09/2026", 69 arquivos) traz `gedai-ue.exe`, `gedai-ue.vst`, bibliotecas, chaves e os pacotes da mídia de votação; não traz versão. Nos logs de preparação (`~/dataurnas-t2/gedai/`, pacotes de 03/10, 04/10, 24/10 e 25/10):

| Evento no log | 1º turno (56 zips) | 2º turno, 24/10 | 2º turno, 25/10 |
|---|---:|---:|---:|
| `Abertura do GEDAI-UE - Versão 8.23.0.0 - Praia da Barra do Cahy` | 108.956 | 84.463 | 86.086 |
| `Serviço Holocron em execução - Versão 4.20.0.0 - Praia da Barra do Cahy` | 108.921 | 84.407 | 86.030 |
| `Serviço HotSwapFlash em execução - Versão 8.12.0.0` | 247.944 | 194.201 | 197.324 |
| `Serviço HotSwapFlash em execução - Versão 8.10.0.0` | 66 | 73 | 73 |
| `Verificação de Assinatura \| Envelope: D:/Aplic/SEVIN/GEDAIUE/Aplic/gedai-ue.vst` | 108.708 | 84.233 | 85.853 |
| `Verificação de Assinatura \| Envelope: D:/Aplic/SEVIN/GEDAIUE/Aplic/app.ini.vsc` | 108.642 | 84.158 | 85.778 |

- O GEDAI-UE tem uma só versão (8.23.0.0) em todas as estações, e o envelope que ele verifica ao abrir (`gedai-ue.vst`) está na lista. O log não traz hash, então a versão não pode ser ligada ao hash publicado.
- **`app.ini.vsc` é verificado em toda abertura e não está na lista do GEDAI.**
- **Duas versões do HotSwapFlash.** No pacote de 25/10, quatro estações registraram a versão 8.10.0.0 entre 18/09 e 17/10/2026: `ZBA056WKS01` (BA, 11 registros, todos em 13/10; a estação também tem 52 registros da 8.12.0.0), `ZBA168WKS01` (BA, 31 registros de 18/09 a 17/10 e nenhum da 8.12.0.0), `ZPA052STD92` (PA, 12 registros de 29/09 a 16/10; 10 da 8.12.0.0) e `ZPI006STD01` (PI, 19 registros de 28/09 a 13/10; 21 da 8.12.0.0). A lista `pc1hsfg` publica um único conjunto de hashes (`HotSwapFlash.exe`, `NotificadorHSF.exe` e 5 bibliotecas) sem versão; duas versões em uso significam que ao menos uma delas não corresponde a esse conjunto. É ponto a esclarecer com o TSE; o log não mostra qual versão foi lacrada.

### Divergências, em resumo

1. Pacotes verificados na carga e ausentes da lista pelo nome: `/boot/boot/avbootcfg.vst`, `avmodue2013/2015/2020/2022.vst` e `avusrlibue2013/2015/2020/2022.vst` (nos quatro modelos).
2. Pacote da lista nunca verificado nos logs: `/uenux/bin/avusrbinof.vst` (nos quatro modelos).
3. Pacotes da mídia de votação (`vota_apl.vst`, `vota_ofi.vst`, `avpart_ofi.vst`) estão na lista do GEDAI, não nas da urna; `avgm.vsc` não está em nenhuma.
4. GEDAI: `app.ini.vsc` verificado e ausente da lista; HotSwapFlash 8.10.0.0 em quatro estações, ao lado da 8.12.0.0.
5. Nenhuma lista traz versão; a ligação entre `10.23.0.0`/`8.23.0.0` e os hashes depende do conteúdo de `versoes.properties`, que não é publicado.
6. As listas não são assinadas digitalmente.
7. Certificado da AC URNA (`acurna.pem`) e arquivo `99.pub` sem possibilidade de confronto (o primeiro não está nas listas; o segundo não é publicado).

Com isso, o item 1 de "O que seria preciso para fechar a lacuna" fica atendido em parte: a lista oficial foi obtida, mas ela confere arquivos que estão dentro da urna e do GEDAI, e os arquivos públicos por seção continuam sem hash de software. O confronto acima é de **nomes** (o log não traz hash); o confronto de bytes continua dependendo da lista emitida pela própria urna.

### Pedidos a fazer ao TSE

- Explicação para os nove pacotes da carga ausentes da lista (`avbootcfg.vst` e os `avmodue20NN.vst`/`avusrlibue20NN.vst`) e os hashes deles; papel do `avusrbinof.vst`.
- Inclusão de `app.ini.vsc` na lista do GEDAI ou explicação de por que não entra; versão do HotSwapFlash lacrada e motivo das estações com 8.10.0.0.
- Publicação de `versoes.properties`, `99.pub` (e `90`, `91`, `97`), `acurna` (certificado renovado, se houver) e das raízes `acraiz-ue`, `acraizuev2`, `acurnav2`.
- Assinatura digital das listas de resumos, e descrição do cálculo do `HASH GERAL UF`.
- Acesso aos arquivos sem bloqueio para clientes automatizados (o mesmo endereço responde 403 sem os cabeçalhos de navegador).

Scripts usados (não versionados): extração das tabelas e varredura dos logs em `/dev/shm/hashconf/` no servidor de processamento, removidos ao final.
