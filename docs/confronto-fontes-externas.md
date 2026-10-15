# Confronto com fontes externas de boletins de urna

Levantamento feito em 14/10/2026. Objetivo: encontrar cópias de boletins de urna (BU) que não tenham vindo dos arquivos publicados pelo TSE e confrontá-las, seção a seção, com os dados do projeto (`data/parquet/2026/secoes_2026.parquet` e `votos_presidente_2026.parquet`, 1º turno de 04/10/2026).

## Resumo

- A única fonte externa e independente com dados de 2026 acessíveis encontrada é a **Totalização Paralela do CMInd** (Comitê Multidisciplinar Independente): voluntários leem o QR Code dos BUs afixados nas seções e enviam o texto bruto para um servidor, que o expõe numa API pública, sem login.
- Em 14/10/2026 a fonte tinha **38 BUs** do 1º turno de 2026 (MG 12, RS 16, SC 1, SP 9), cerca de 0,008% das 499.207 seções com BU. Todos os 38 tiveram a cadeia de hash e a assinatura da própria urna verificadas, com o certificado da urna emitido por uma AC do TSE, e **todos os 38 conferem** com os dados do TSE no projeto: votos de cada candidato a Presidente, brancos, nulos, comparecimento, aptos, número de série da urna e código de carga. Nenhuma divergência.
- A amostra é pequena e não é aleatória (concentrada em seis municípios), portanto serve como verificação de método e não permite conclusão estatística sobre o país.
- Para 2022 não foi encontrado nenhum conjunto público de leituras de QR Code feitas no papel. As fontes de 2022 que existem derivam dos arquivos do TSE.
- O formato do QR Code mudou em 2026 (`VRQR:6.0`): a assinatura passou a ser feita pela própria urna (Ed521 ou ECDSA P-521), com o certificado X.509 impresso em QR Codes adicionais (`QRCE`). Até 2024 a assinatura era Ed25519 com uma chave por UF. O método de verificação está descrito abaixo e implementado em `scripts/externo/confrontar_bu_externo.py`.

## Fontes avaliadas

| Fonte | Quem publica | Cobertura | Formato e acesso | Licença ou termos | Independente do arquivo do TSE? |
|---|---|---|---|---|---|
| [Totalização Paralela](https://totalizacaoparalela.com.br/) (CMInd) | CMInd, sociedade civil, ativo desde 2018 | 2026, 1º turno: 38 seções em 14/10/2026 (MG, RS, SC, SP) | API JSON pública usada pelo próprio site: lista em `/api/public-bu?page=1&pageSize=100&_tp_mode=oficial`, detalhe em `/api/public-bu/<id>?_tp_mode=oficial` (campo `qr_raw` com o texto de todos os QR Codes) | Sem licença declarada. O site afirma que o BU é documento público (Res. TSE 23.554, art. 107, VI) e que não coleta dados pessoais além do QR Code. API não documentada, pode mudar | **Sim.** O texto vem da leitura do papel na seção. A assinatura da urna no QR Code não existe nos arquivos publicados pelo TSE, então uma assinatura válida prova que o conteúdo saiu da impressão da urna |
| Boletim na Mão (agora dentro do e-Título) | TSE | Qualquer BU que o usuário escanear | App Android/iOS. Lê o QR Code sem internet; em 2026 permite compartilhar vários BUs de uma vez. Não há base pública agregada | Termos do app do TSE | Leitura sim (feita do papel pelo próprio cidadão). Não existe conjunto de dados publicado; serve como ferramenta de coleta |
| [urna-validador](https://github.com/lucas-zimerman/urna-validador) | Lucas Zimerman (GitHub) | Ferramenta; não publica BUs coletados | Site e código JavaScript; aceita texto do QR Code ou foto | MIT | Ferramenta de coleta. O README diz que não verifica as assinaturas do QR Code |
| [verificador_boletim_urna](https://github.com/lucas-daniel-sm/verificador_boletim_urna) | Lucas Mendes (GitHub) | Ferramenta; sem dados | App Flutter e backend Kotlin que leem o QR Code | Sem licença | Ferramenta. Não verifica hash nem assinatura |
| [urna_aberta](https://github.com/kterto/urna_aberta) | kterto (GitHub) | Ferramenta; usa só arquivos do TSE | App Dart | Sem licença | Não. Verifica os arquivos do TSE (JWS, `.vsc`, Ed521); o próprio README diz que o confronto com o papel fica a cargo do usuário |
| [doccaz/urnas-br](https://github.com/doccaz/urnas-br) | doccaz (GitHub) | 2022, CSV por UF | CSV no repositório | MIT | Não. Gerado a partir dos arquivos `.bu` do TSE. Útil pelo exemplo de QR Code do manual |
| [Dados Abertos TSE: Boletim de Urna 2022](https://dadosabertos.tse.jus.br/dataset/resultados-2022-boletim-de-urna) | TSE | 2022, todas as seções, 1º e 2º turnos | CSV por UF e listas de hash SHA2 | CC BY | Não. É o próprio TSE |
| Relatório das Forças Armadas sobre 2022 | Ministério da Defesa | Amostra de seções de 2022 | Relatório; sem base pública de leituras de QR Code | n/a | Não há dados publicados para confronto |

Não foram encontrados conjuntos de leituras de QR Code publicados por partidos, por veículos de imprensa, no Kaggle, em portais de dados ou por universidades, nem para 2022 nem para 2026. Partidos e coligações recebem vias impressas do BU, mas não publicam essas coletas.

## O QR Code do boletim de urna

### Especificação oficial

- Manual de 2020, ainda válido em 2022 segundo o TSE: "QR Code no Boletim de Urna: manual para criação de aplicativos de leitura" (`https://www.tse.jus.br/hotsites/catalogo-publicacoes/pdf/Manual_QR_code_SEPREV_OK_final.pdf`). O site do TSE responde 403 a partir do ambiente deste levantamento; a cópia usada veio do Internet Archive (captura de 20/01/2022, 62 páginas).
- Manual de 2026: `https://www.tse.jus.br/eleicoes/eleicoes-2026-content/arquivos/manual-do-qr-code-no-boletim-de-urna/@@display-file/file/manual-do-qr-code-no-boletim-de-urna.pdf`. Não foi possível baixá-lo (403, sem cópia arquivada). As regras do formato 2026 abaixo foram **confirmadas empiricamente** em BUs reais: a verificação só passa com elas.
- Chaves Ed25519 de 2022 (formato antigo): `http://qrcodenobu.tse.jus.br/tse.qrcodebu/20220829/LEGAL/o<uf>qrcode.pub` (32 bytes cada) e a lista oficial de SHA-512 de cada chave (`Anexo_2179302_TSE_lista_hashes_chave_publica_eleicoes_2022.zip`, na página de documentação técnica de 2022). A chave de AC arquivada confere com a lista (`oacqrcode.pub`, SHA-512 `11a30d1d...6946dbda`). Para 2024 a versão das chaves é `20240507`.

### Estrutura

Cada QR Code tem até 1.100 caracteres no modo alfanumérico, com registros `CHAVE:VALOR` separados por espaço, em três seções:

1. Cabeçalho: `QRBU:i:n` (QR Code i de n), `VRQR` (versão do formato) e, até 2024, `VRCH` (versão da chave). Em 2026 o `VRCH` não aparece.
2. Conteúdo: dados da seção (`UNFE`, `MUNI`, `ZONA`, `SECA`, `AGRE`, `IDUE` série da urna, `IDCA` código de carga, `APTO`, `COMP`, `FALT`, horários) e, para cada eleição (`IDEL`) e cargo (`CARG`, 1 = Presidente), os votos `numero:votos`, seguidos de `APTA`, `NOMI`, `LEGC`, `BRAN`, `NULO`, `TOTC`. Em 2026 surgiram `APTS`/`APTT` (aptos da seção e em trânsito), `HIQT`/`HICA` (códigos de carga) e `HBBM`/`HBBG`/`HBSB` (habilitação biométrica).
3. Segurança: `HASH` em todo QR Code e `ASSI` só no último.

Um BU grande se divide em vários QR Codes; a quebra ocorre num espaço, que é removido e precisa ser recolocado ao remontar o conteúdo.

### Cadeia de hash (igual em todas as versões)

O cabeçalho fica fora do cálculo. Sendo `dados_i` o conteúdo do QR Code i (sem cabeçalho e sem `HASH`):

```
hash_1 = SHA-512(dados_1)
conteudo_1 = dados_1 + " HASH:" + hash_1
hash_i = SHA-512(conteudo_(i-1) + " " + dados_i)
conteudo_i = conteudo_(i-1) + " " + dados_i + " HASH:" + hash_i
```

Os hashes são impressos em hexadecimal maiúsculo. Conferido com o exemplo do manual (1 QR Code) e com os 38 BUs de 2026 (de 2 a 5 QR Codes de boletim cada).

### Assinatura

| Formato | Quem assina | Algoritmo | Mensagem assinada | Onde está a chave |
|---|---|---|---|---|
| Até 2024 (VRQR 1.x a 5.x) | Chave da UF gerada pelo TSE | Ed25519 (libsodium), assinatura de 64 bytes | Os 64 bytes do último hash (hex decodificado) | `qrcodenobu.tse.jus.br/tse.qrcodebu/<VRCH>/LEGAL/<fase><uf>qrcode.pub` |
| 2026, urnas UE2020 e UE2022 (VRQR 6.0) | A própria urna | Ed521 (EdDSA na curva E-521, padrão ICP-Brasil), assinatura de 132 bytes | SHA-512 dos 64 bytes do último hash | Certificado X.509 da urna (PEM em hexadecimal) nos QR Codes `QRCE:i:n IDUE:<série> MDUE:<modelo> CERT:<hex>`, emitido pela AC UE2020 ou AC UE2022 |
| 2026, urnas UE2013 e UE2015 (VRQR 6.0) | A própria urna | ECDSA P-521 com SHA-512, assinatura DER (cerca de 139 bytes) | Os 64 bytes do último hash (o ECDSA aplica o SHA-512) | Certificado DER em hexadecimal nos `QRCE`, emitido pela AC URNA |

Vetor de teste oficial (manual de 2020): o BU simulado de 2016 do manual verifica com a chave de exemplo `CF3AF898467A5B7A52D33D53BC037E2642A8DA996903FC252217E9C033E2F291`. O código C++ do manual troca os rótulos dessa chave e da assinatura; o exemplo correto é o do texto do QR Code.

### Como um QR Code do papel se confronta com o BU do TSE

1. Juntar todos os QR Codes do BU (`QRBU` e, em 2026, `QRCE`).
2. Recalcular a cadeia de hash. Hash errado indica leitura com erro ou conteúdo alterado.
3. Verificar `ASSI` com a chave correta. Em 2026, conferir também que o certificado é da mesma urna (`IDUE` e o CN `UEAO0<série>`) e que foi emitido por uma AC do TSE (`data/certificados/ac/`).
4. Só então comparar os números com o BU publicado pelo TSE para a mesma UF, município, zona e seção.

A assinatura do QR Code é diferente da assinatura do arquivo `.bu` (que fica no `-vota.vsc`) e não aparece em nenhum arquivo publicado pelo TSE. Por isso um QR Code com assinatura válida só pode ter vindo da impressão feita pela urna.

## Resultado do confronto (1º turno de 2026)

Comando executado em 14/10/2026 (requisições sequenciais com 1 s de intervalo):

```sh
.venv/bin/python -I scripts/externo/confrontar_bu_externo.py \
    --baixar-cmind /caminho/novo/diretorio --saida-csv confronto_cmind.csv
```

| UF | Município | Zona | Seções | Urnas e assinatura | Resultado |
|---|---|---|---|---|---|
| MG | Itaúna (46752) | 140 | 85, 86, 87, 88, 89, 90, 91, 151, 175, 190, 216, 245 | UE2015, ECDSA P-521, AC URNA | 12 conferem |
| RS | Nova Esperança do Sul (85120) | 26 | 3, 6, 25, 28, 43, 54, 55, 56, 59, 62, 70, 71, 72 | Ed521, AC UE2022 | 13 conferem |
| RS | Passo Fundo (87858) | 33 | 183, 188, 281 | Ed521, AC UE2020 | 3 conferem |
| SC | Benedito Novo (80438) | 32 | 16 | Ed521, AC UE2020 | 1 confere |
| SP | São Paulo (71072) | 250 | 267, 278, 279, 299, 330, 345, 371, 409 | Ed521, AC UE2022 | 8 conferem |
| SP | Uchoa (72133) | 312 | 209 | Ed521, AC UE2022 | 1 confere |

Total: 38 BUs, 38 com cadeia de hash íntegra, 38 com assinatura válida da urna e certificado emitido por AC do TSE, 38 sem nenhuma diferença em relação ao TSE (9.521 votos para Presidente, incluindo brancos e nulos). Campos comparados: votos de cada candidato a Presidente, brancos, nulos, total do cargo, comparecimento, faltosos, aptos, série da urna (`IDUE` contra `numero_interno_urna`) e código de carga (`IDCA` contra `codigo_carga`).

## Limitações

- **Amostra pequena e por conveniência.** 38 seções em seis municípios. Não é amostra aleatória e não estima nada sobre o país.
- **O que o confronto prova.** Que, nessas seções, o resultado impresso na seção é o mesmo publicado e totalizado pelo TSE, ou seja, que não houve alteração entre a impressão e a publicação. Não diz nada sobre o funcionamento interno da urna, porque o QR Code e o arquivo `.bu` são produzidos pela mesma urna.
- **Seleção pelo coletor.** Quem publica escolhe o que enviar. Uma assinatura válida garante a origem de cada BU, mas não garante que os BUs que não foram enviados também confeririam.
- **Fonte sem licença e API sem documentação.** A API da Totalização Paralela pode mudar ou sair do ar. Os arquivos baixados não são redistribuídos neste repositório, exceto dois BUs usados como fixture de teste (documentos públicos afixados na seção).
- **Manual de 2026 não lido.** As regras do formato 2026 foram deduzidas e confirmadas pela verificação em BUs reais. Se o manual trouxer casos não cobertos (por exemplo, urnas de contingência ou BUs do Recuperador de Dados), o script marca a assinatura como não verificada em vez de afirmar resultado.
- **Escopo do script.** Compara só o cargo de Presidente e o 1º turno de 2026, porque são os dados disponíveis no projeto. Com `--sem-escopo`, `--secoes` e `--votos` ele aceita outras tabelas no mesmo esquema.
- **Seções agregadas.** O QR Code traz a seção principal e as agregadas em `AGRE`; o confronto usa a seção principal, como o TSE.

## Como verificar a sua seção

1. Fotografe ou escaneie todos os QR Codes do BU afixado na porta da seção, inclusive os do certificado (`QRCE`, no fim do boletim). Qualquer leitor de QR Code serve, assim como o Boletim na Mão (e-Título) ou o app da Totalização Paralela.
2. Copie o texto de cada QR Code para um arquivo de texto, um QR Code por linha, em qualquer ordem. Exemplo: `scripts/externo/fixtures/qr_sp_72133_0312_0209.txt`.
3. Na raiz do repositório, rode:

   ```sh
   .venv/bin/python -I scripts/externo/confrontar_bu_externo.py --qr minha_secao.txt
   ```

4. Leia o status:
   - `confere`: hash e assinatura válidos e números iguais aos do TSE;
   - `DIVERGE`: BU autêntico com número diferente do TSE (o script lista cada diferença e termina com código 1);
   - `confere_sem_autenticidade` ou `diverge_sem_autenticidade`: números lidos, mas a assinatura não pôde ser confirmada;
   - `qr_invalido_ou_incompleto`: falta QR Code ou o hash não fecha (leia de novo);
   - `ausente_tse`, `fora_escopo`, `nao_oficial`: seção não encontrada, outro pleito ou turno, ou BU de simulação.

Para BUs de 2022 ou 2024 (formato Ed25519), informe as chaves com `--dir-chaves` (arquivos `o<uf>qrcode.pub`) e, de preferência, `--lista-hashes-chaves` com a lista SHA-512 publicada pelo TSE, além de `--sem-escopo --secoes ... --votos ...` com as tabelas daquele pleito.

Autoteste sem rede (vetor oficial do manual, BU sintético com 3 QR Codes, alteração de um voto, chave errada, QR Code faltando, e dois BUs reais de 2026, um UE2022 com Ed521 e um UE2015 com ECDSA):

```sh
.venv/bin/python -I scripts/externo/confrontar_bu_externo.py --autoteste
```

## Como contribuir

- Envie ao projeto o arquivo de texto com os QR Codes da sua seção (o BU é documento público e não contém dados de eleitores). Um BU com assinatura válida dispensa confiança em quem o enviou.
- Prefira coletar todas as seções de um local de votação, o que reduz o viés de seleção.
- Se você tiver acesso ao manual do QR Code de 2026 ou às chaves de 2024, uma cópia ajuda a documentar formalmente o formato `VRQR:6.0`.
- Próximo passo sugerido: comparar o SHA-256 do certificado impresso no QR Code com o certificado do `-vota.vsc` da mesma seção, já verificado por `scripts/ele2026/analisar_certificados.py`.

## Arquivos

- `scripts/externo/confrontar_bu_externo.py`: leitura, verificação de hash e assinatura, download da Totalização Paralela e confronto com os parquets do projeto.
- `scripts/externo/fixtures/qr_sp_72133_0312_0209.txt` e `scripts/externo/fixtures/qr_mg_46752_0140_0089.txt`: textos dos QR Codes de dois BUs reais de 2026, usados no autoteste.
