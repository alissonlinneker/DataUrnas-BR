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
