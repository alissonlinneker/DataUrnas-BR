# Acervo dos BUs assinados de 2026

> **O que é:** uma segunda cópia, datada, do Boletim de Urna binário de **todas as 499.207 seções de cada turno de 2026**, tirada dos zips oficiais do TSE entre 04/11/2026 às 23:51 e 05/11/2026 às 00:55 (UTC). Cada BU vem com o SHA-512 calculado, o SHA-512 que a urna assinou para ele e o resultado da conferência da assinatura. Se o TSE republicar ou trocar um zip, qualquer pessoa pode provar o que estava publicado nessa data.
>
> **Resultado da conferência feita na montagem:** nas 998.414 seções (499.207 por turno), o SHA-512 de cada BU é igual ao valor assinado pela urna, a assinatura individual de cada BU é válida e todos os 998.414 arquivos de assinatura (`-vota.vsc` e `-sa.vsc`) são válidos. Nenhuma falha, nenhum BU sem assinatura.
>
> **Onde baixar:** anexos da versão [acervo-bu-2026](https://github.com/alissonlinneker/DataUrnas-BR/releases/tag/acervo-bu-2026), 61 arquivos, 5,26 GB no total.

## Por que este acervo existe

Os BUs do pacote nacional ficam em zips publicados no mesmo endereço, e o TSE já trocou alguns depois da publicação: em 03/11/2026 foram regravados os zips do MA e de MG do 1º turno e o de SP do 2º turno (ver [Republicação do pacote do MA](ma-republicacao-2026.md)). Quando um arquivo é trocado no mesmo endereço, a versão anterior some. Este acervo guarda a versão lida em 04/11 e 05/11, com o `ETag`, o `Last-Modified` e o tamanho de cada zip de origem, para que uma troca futura possa ser detectada e medida arquivo a arquivo.

O BU é o arquivo que importa para a prova: é ele que tem os votos de cada seção, e é ele que a urna assina. A cópia de cada BU vale como prova porque o SHA-512 dele está dentro do arquivo de assinatura da urna, assinado com a chave daquela urna. Quem tiver o BU e o `.vsc` original consegue refazer a conferência sem depender deste projeto.

## Origem

Para cada turno e UF (27 UFs mais `ZZ`, o exterior), o zip oficial:

```
https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/arqurnatot/bu_imgbu_logjez_rdv_vscmr_2026_<1t|2t>_<UF>.zip
```

Do zip foram lidos só quatro tipos de membro, por requisições HTTP Range, sem baixar o resto (imagem do BU, log e RDV ficam de fora):

| Membro | O que é | Assinado por |
|---|---|---|
| `-bu.dat` | BU da urna eletrônica | `-vota.vsc` da mesma seção |
| `-busa.dat` | BU do Sistema de Apuração (seções apuradas fora da urna) | `-sa.vsc` da mesma seção |
| `-vota.vsc` | Assinatura da urna | |
| `-sa.vsc` | Assinatura do Sistema de Apuração | |

Os 56 zips somam 95,07 GB no 1º turno e 124,14 GB no 2º turno; foram lidos 88,36 GB e 118,01 GB, respectivamente. Cada requisição foi presa ao `ETag` do zip (`If-Range`) e o `ETag` foi lido de novo no fim, de modo que um zip trocado durante a leitura seria detectado. Cada membro foi conferido contra o CRC-32 do diretório central do zip.

Data de modificação (`Last-Modified`) dos zips lidos:

| `Last-Modified` | Zips |
|---|---|
| 22/10/2026 | 26 do 1º turno |
| 26/10/2026 | 27 do 2º turno |
| 03/11/2026 | 3: MA e MG do 1º turno, SP do 2º turno |

## O que há em cada arquivo

### `acervo_bu_2026_<1t|2t>_<UF>.tar.zst` (56 arquivos)

Um tar por turno e UF, compactado com zstd (nível 19, janela longa de 2^27), com os BUs da UF (`-bu.dat` e, quando houver, `-busa.dat`) em ordem de nome. O tar é determinístico: cada membro tem modo 0644 e a data do membro no zip do TSE. Nenhum arquivo passou de 2 GB, então nenhuma UF precisou ser dividida em partes.

Os arquivos de assinatura (`-vota.vsc` e `-sa.vsc`) **não** estão dentro dos tar.zst. Cada um tem cerca de 62 KB, quase todo em doze assinaturas de partes do software que não se compactam; juntos somam 31,2 GB por turno, contra 6,26 GB de BU no 1º turno e 0,50 GB no 2º. Todos foram lidos e conferidos na montagem, e o SHA-512 de cada um está no manifesto. O script tem a opção `--com-vsc` para incluí-los, se um dia for preciso.

Os nomes seguem o padrão do TSE, `o0322<turno><uf><município><zona><seção>-bu.dat` (turno `0` = 1º, `1` = 2º).

| UF | Seções por turno | 1º turno: BU (MB) | 1º turno: tar.zst (MB) | 2º turno: BU (MB) | 2º turno: tar.zst (MB) |
|---|---|---|---|---|---|
| AC | 2.270 | 24,1 | 18,4 | 3,4 | 2,0 |
| AL | 7.101 | 65,0 | 49,1 | 6,7 | 3,4 |
| AM | 8.157 | 99,5 | 75,9 | 12,4 | 7,2 |
| AP | 1.914 | 24,6 | 18,8 | 1,7 | 0,9 |
| BA | 35.476 | 393,6 | 301,2 | 33,4 | 16,9 |
| CE | 23.765 | 257,1 | 196,2 | 22,5 | 11,3 |
| DF | 6.969 | 108,2 | 83,2 | 10,7 | 6,2 |
| ES | 9.844 | 109,7 | 83,8 | 15,0 | 8,8 |
| GO | 15.686 | 197,1 | 150,8 | 15,1 | 7,5 |
| MA | 18.093 | 180,6 | 137,8 | 16,7 | 8,4 |
| MG | 52.062 | 588,8 | 451,4 | 49,1 | 24,9 |
| MS | 7.106 | 70,6 | 53,5 | 6,8 | 3,3 |
| MT | 8.287 | 83,8 | 63,7 | 8,0 | 4,0 |
| PA | 20.827 | 222,8 | 170,1 | 19,3 | 9,7 |
| PB | 10.712 | 101,4 | 77,1 | 10,0 | 5,1 |
| PE | 21.418 | 259,9 | 199,0 | 20,3 | 10,2 |
| PI | 10.225 | 88,0 | 66,6 | 9,6 | 4,8 |
| PR | 27.142 | 335,8 | 257,6 | 25,6 | 13,0 |
| RJ | 37.675 | 644,7 | 498,0 | 35,8 | 18,2 |
| RN | 8.115 | 71,1 | 53,8 | 12,3 | 7,2 |
| RO | 4.698 | 50,2 | 38,2 | 4,4 | 2,2 |
| RR | 1.519 | 17,9 | 13,7 | 1,4 | 0,7 |
| RS | 27.547 | 337,3 | 258,8 | 26,2 | 13,2 |
| SC | 17.326 | 197,0 | 150,6 | 16,6 | 8,3 |
| SE | 5.923 | 61,9 | 47,1 | 5,5 | 2,8 |
| SP | 103.656 | 1.627,5 | 1.254,8 | 99,1 | 49,9 |
| TO | 4.384 | 40,4 | 30,6 | 6,7 | 3,9 |
| ZZ | 1.310 | 1,8 | 1,1 | 1,2 | 0,6 |
| **Total** | **499.207** | **6.260,5** | **4.801,1** | **495,5** | **254,6** |

Cada seção tem exatamente um BU por turno. Os `-busa.dat` são 31 no 1º turno (29 no exterior e 2 em MG) e 29 no 2º turno (todos no exterior); as demais seções têm `-bu.dat`.

### `manifesto_bu_2026_<1t|2t>.csv.gz` (2 arquivos, 100,0 MB cada)

Uma linha por arquivo lido (BU e assinatura), 998.414 linhas por turno, com estas colunas:

| Coluna | Conteúdo |
|---|---|
| `turno`, `uf`, `cd_mun`, `zona`, `secao` | Identificação da seção |
| `arquivo`, `tipo` | Nome do membro no zip e tipo (`bu`, `busa`, `vota`, `sa`) |
| `tamanho`, `crc32`, `data_zip` | Tamanho, CRC-32 e data do membro no zip |
| `sha512` | SHA-512 do arquivo |
| `par` | No BU, o arquivo de assinatura que o assina; na assinatura, os BUs que ela assina |
| `sha512_assinado` | No BU, o SHA-512 que a urna assinou para ele |
| `hash_confere` | No BU, `true` quando `sha512` é igual a `sha512_assinado` |
| `assinatura_arquivo` | No BU, `true` quando a assinatura individual do arquivo é válida |
| `vsc_valida`, `vsc_falhas`, `vsc_motivos` | Na assinatura, o resultado de `verificar_vsc` (`src/dataurnas/parsers/signature.py`) |
| `asset` | O tar.zst que guarda o arquivo (vazio nas assinaturas) |

### `resumo_bu_2026_<1t|2t>.json` (2 arquivos)

Contagens por tipo, bytes por tipo, seções com assinatura conferida, lista de falhas (vazia nos dois turnos), tamanho de cada tar.zst e, para cada zip de origem, URL, `ETag`, `Last-Modified`, tamanho, número de membros, hora da leitura, bytes lidos e número de requisições.

### `SHA512SUMS`

SHA-512 dos 60 arquivos acima (56 tar.zst, 2 manifestos e 2 resumos), no formato do `sha512sum`.

## Resultado da conferência na montagem

| Turno | Seções | BU com SHA-512 igual ao assinado e assinatura válida | Assinaturas (`.vsc`) válidas | Falhas |
|---|---|---|---|---|
| 1º | 499.207 | 499.207 (499.176 `-bu.dat` e 31 `-busa.dat`) | 499.207 (499.176 `-vota.vsc` e 31 `-sa.vsc`) | 0 |
| 2º | 499.207 | 499.207 (499.178 `-bu.dat` e 29 `-busa.dat`) | 499.207 (499.178 `-vota.vsc` e 29 `-sa.vsc`) | 0 |

Depois de publicado, o acervo foi conferido de novo a partir dos próprios arquivos, com o script abaixo: o `SHA512SUMS` confere nos 60 arquivos, e cada um dos 998.414 BUs dos 56 tar.zst tem o SHA-512 igual ao valor assinado registrado no manifesto, sem nenhum arquivo faltando ou sobrando. A leitura do zip do exterior do 2º turno direto do TSE (`--tse`) também refez a conferência das 1.310 assinaturas da UF sem nenhum problema.

## Como conferir

Requisitos: Python 3.10 ou superior com as dependências do projeto (`pip install -e .`), e a ferramenta de linha de comando `zstd` para ler os tar.zst.

1. Baixar os anexos para uma pasta (todos, ou só os de interesse mais os dois manifestos, os dois resumos e o `SHA512SUMS`):

   ```sh
   mkdir acervo && cd acervo
   gh release download acervo-bu-2026 -R alissonlinneker/DataUrnas-BR
   # ou, arquivo a arquivo:
   curl -LO https://github.com/alissonlinneker/DataUrnas-BR/releases/download/acervo-bu-2026/SHA512SUMS
   curl -LO https://github.com/alissonlinneker/DataUrnas-BR/releases/download/acervo-bu-2026/acervo_bu_2026_1t_AC.tar.zst
   ```

2. Conferir a integridade dos arquivos baixados:

   ```sh
   sha512sum -c SHA512SUMS               # Linux
   shasum -a 512 -c SHA512SUMS           # macOS
   sha512sum -c --ignore-missing SHA512SUMS   # se baixou só uma parte
   ```

3. Conferir cada BU contra o manifesto e contra o hash assinado pela urna:

   ```sh
   python scripts/ele2026/conferir_acervo_bu.py conferir --acervo acervo
   python scripts/ele2026/conferir_acervo_bu.py conferir --acervo acervo --ufs AC --turnos 1
   ```

   O script confere primeiro o `SHA512SUMS` (todos os arquivos listados nele precisam estar na pasta; para uma parte, gere um `SHA512SUMS` só com as linhas baixadas). Depois lê cada tar.zst sem gravar nada em disco e, para cada BU, recalcula tamanho, CRC-32 e SHA-512 e exige que o SHA-512 seja igual ao `sha512_assinado` do manifesto. Arquivos faltando, sobrando ou diferentes são listados; `--saida problemas.csv` grava todos. O código de saída é 0 só quando não há nenhum problema.

4. Refazer a conferência da assinatura direto dos zips do TSE (precisa só dos manifestos e dos resumos):

   ```sh
   python scripts/ele2026/conferir_acervo_bu.py conferir --acervo acervo --tse --ufs ZZ --turnos 2
   ```

   Aqui o BU e o `.vsc` vêm do zip publicado hoje, a assinatura é verificada de novo e o resultado é comparado com o manifesto. Um `ETag` diferente do registrado é avisado.

5. Detectar uma republicação silenciosa, de forma barata:

   ```sh
   python scripts/ele2026/conferir_acervo_bu.py confrontar --acervo acervo --saida diferencas.csv
   ```

   Compara `ETag`, `Last-Modified` e tamanho de cada zip e o CRC-32 e o tamanho de cada `-bu.dat`, `-busa.dat`, `-vota.vsc` e `-sa.vsc` com o manifesto, lendo só o diretório central (poucas requisições por zip). Com `--baixar`, os membros diferentes ou novos são baixados e o SHA-512 deles é registrado.

O script nunca faz mais de 4 requisições simultâneas ao TSE.

## Como o acervo foi montado

```sh
uv run python scripts/ele2026/acervo_bu.py construir --saida ~/dataurnas-acervo-bu/out
uv run python scripts/ele2026/acervo_bu.py fechar --saida ~/dataurnas-acervo-bu/out
```

`construir` lê cada zip, confere as assinaturas, grava o tar.zst e um manifesto parcial por turno e UF (os pares prontos são pulados numa nova execução). `fechar` junta os manifestos, grava os resumos e o `SHA512SUMS`. A montagem completa dos 56 pares levou cerca de uma hora no servidor de análise.

## Limites

- O acervo prova o que estava publicado nos zips no momento da leitura (04/11 e 05/11/2026). Ele não diz nada sobre versões anteriores dos três zips regravados em 03/11; para o MA, essa comparação está em [Republicação do pacote do MA](ma-republicacao-2026.md).
- Os arquivos de assinatura não estão nos tar.zst. Sem eles, a conferência a partir do acervo se apoia no SHA-512 assinado registrado no manifesto; a verificação criptográfica completa de uma seção exige o `.vsc` do TSE (passo 4).
- A assinatura prova que o BU saiu da urna com aquela chave. Ela não prova qual software rodou na urna; esse limite está em [Cadeia de confiança 2026](cadeia-de-confianca-2026.md).
