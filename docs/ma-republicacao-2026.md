# Republicação do zip do 1º turno do MA (03/11/2026)

**Resumo.** O arquivo `bu_imgbu_logjez_rdv_vscmr_2026_1t_MA.zip` foi trocado pelo TSE no mesmo endereço em 03/11/2026 às 19:59:01 GMT, poucas horas depois de a versão anterior ter sido lida aqui (16:14 UTC do mesmo dia). A versão nova foi baixada inteira e conferida membro a membro. **Nenhum voto, nenhuma assinatura e nenhum arquivo de seção mudou** em relação a tudo o que havia sido guardado antes: os 72.371 arquivos que o catálogo de 13/10 tem são idênticos byte a byte, as 18.093 assinaturas de urna são válidas, os 90.465 arquivos de seção conferem com o SHA-512 que a urna assinou e a releitura das 18.093 seções repete exatamente os 94 campos da leitura anterior. Como a versão anterior do zip não foi guardada, não é possível dizer qual byte do arquivo mudou; o que a conferência mostra é que, se algo mudou, não foi o conteúdo de nenhum arquivo de urna.

## O que se sabia antes

- A leitura nacional (`pacote_nacional.py`) baixou o zip do MA 1º turno em 03/11/2026 às 16:14 UTC (3.266 MB, valor arredondado no log), processou as 18.093 seções em 8 segundos e apagou o arquivo, como faz com todos. Nem o zip nem o diretório dele foram guardados; ficou só o resultado por seção (`secoes_ma_1.parquet`).
- O diretório lido depois da troca (`cd_republicados.parquet`, de 04/11) não mostra nenhum membro com data posterior a 20/10. Nos outros dois zips republicados a mudança aparecia no diretório (MG 1º turno: um `-imgbu.dat` a menos; SP 2º turno: dois arquivos regravados em 03/11).
- Os demais zips do 1º turno têm data de 22/10/2026, entre 19:42 e 20:53 GMT, gerados em ordem alfabética de UF (GO às 19:56, MS às 20:05). A versão anterior do MA era, muito provavelmente, a desse lote; o horário exato dela não foi registrado.

## Versão atual (consulta de 04/11/2026)

| Campo | Valor |
|---|---|
| Tamanho | 3.266.353.465 bytes |
| `Last-Modified` | Tue, 03 Nov 2026 19:59:01 GMT |
| `ETag` | `"c2b09939-65f64b1958b40"` (tamanho em hexadecimal e data de modificação em microssegundos; os dois batem com o tamanho e com o `Last-Modified`) |
| Membros | 90.466: 18.093 seções com os cinco arquivos (`-bu.dat`, `-imgbu.dat`, `-log.jez`, `-rdv.dat`, `-vota.vsc`) e o `leiame.pdf` |

O tamanho registrado da versão anterior (3.266 MB, arredondado) é compatível com o atual: a versão anterior tinha no máximo 0,15 MB a mais ou 0,85 MB a menos. A diferença, se houver, cabe em poucos arquivos pequenos.

## Referências usadas

1. **Catálogo de hashes do 1º turno** (`arquivos_ma.parquet` da versão v0.2.1, SHA-256 `9cd49f05...567117`, igual ao do manifesto): tamanho, MD5, SHA-256 e SHA-512 de cada `-bu.dat`, `-rdv.dat`, `-log.jez` e `-vota.vsc` do MA, baixados um a um do site de resultados em 13/10/2026. As imagens do BU (`-imgbu.dat`) não estavam publicadas nesse site e não têm hash no catálogo.
2. **Leitura anterior do próprio zip** (`secoes_ma_1.parquet`): 94 campos por seção, tirados do BU, da imagem do BU e do log.
3. **Diretório lido em 04/11** (`cd_republicados.parquet`), para confirmar que o zip conferido aqui é o mesmo visto depois da troca.
4. **A assinatura de cada urna** (`-vota.vsc`), que traz o SHA-512 de cada arquivo da seção, inclusive da imagem do BU.

## Resultado

| Conferência | Resultado |
|---|---|
| Estrutura do zip: cabeçalho local de cada membro contra o diretório (nome, método, data, CRC, tamanhos) | 90.466 de 90.466 iguais |
| Bytes fora dos membros (lacunas, sobreposições, dados entre o último membro e o diretório, comentário do arquivo, nomes repetidos) | nenhum |
| CRC-32 recalculado do conteúdo de cada membro | 90.466 de 90.466 conferem |
| Contra o diretório de 04/11 (CRC, tamanho e data) | 90.465 de 90.465 iguais; o único a mais é o `leiame.pdf`, que aquela tabela não guarda |
| Contra o catálogo de 13/10 (tamanho, MD5, SHA-256 e SHA-512) | **72.371 de 72.371 idênticos**, nenhum diferente, nenhum ausente |
| Fora do catálogo | 18.093 `-imgbu.dat` (não publicados no site de resultados) e 1 `-rdv.dat` (abaixo) |
| Assinatura da urna (`verificar_vsc`, Ed521 ou ECDSA P-521) | **18.093 de 18.093 válidas**, nenhuma falha |
| SHA-512 de cada arquivo contra o valor assinado pela urna | BU, RDV, log e imagem do BU: 18.093 de 18.093 em cada tipo; assinatura individual de cada arquivo válida em todos |
| Releitura das 18.093 seções (`processar_secao`, 94 campos: votos do BU, imagem do BU, comparecimento, habilitações, métricas do log e linha do tempo) | **0 valores diferentes** da leitura anterior |

Os metadados do zip seguem o mesmo padrão do zip do 1º turno do PI, que não foi republicado: campos extras de data (UT) e de dono (ux) em todos os membros, usuário 1001 em todos, grupo 1001 em 18.097 membros (os 18.089 datados de 04/10, seis de 05/10 e os dois de 20/10) e 65534 nos outros 72.368 de 05/10 (no PI: 1001 nos de 04/10 e 65534 nos de 05/10), seis membros sem compressão e os demais em deflate. Nenhum campo de data dos membros (data do zip, data de modificação e de acesso no campo extra) passa de 20/10/2026.

## O RDV da seção MA/07846/0074/0228 está no pacote

Os dois membros com data posterior a 05/10 são da mesma seção, Lagoa Grande do Maranhão (município 07846), zona 0074, seção 0228, ambos com data de 20/10/2026 16:18:32:

- `o03220ma0784600740228-vota.vsc`, na posição original dentro do zip, com conteúdo idêntico ao baixado do site de resultados em 13/10 (mesmo SHA-512);
- `o03220ma0784600740228-rdv.dat`, o **último** membro do zip, logo antes do diretório. É o RDV que a urna assinou e que o site de resultados não publicou (item 2 do [relatório de ocorrências](relatorio-tse-ocorrencias-2026.md) e do [relatório de integridade](relatorio-integridade-2026.md)).

A posição dos dois indica que o zip foi atualizado em 20/10: o `.vsc` foi regravado no lugar, com o mesmo conteúdo, e o RDV foi acrescentado no fim.

Conferência do RDV:

| Item | Resultado |
|---|---|
| SHA-512 do arquivo | `ef182803995b07a03896bc5c5e5d2be9fbe41721fbf30ff239f5a6c777a916de0de450c7f02f51705233b81a289f928ff8be71329de9ddfed80f217ea33f126d`, **igual ao assinado no `.vsc`** e ao registrado como pendente em 14/10 |
| Assinatura Ed521 do arquivo e da urna | válidas |
| Recontagem (`rdv_recontagem.processar_secao`) | 1.314 registros, 5 cargos, estrutura íntegra, **RDV igual ao BU em todos os cargos** |
| Presidente no RDV | 13 = 158, 22 = 52, 14 = 1, 70 = 2, brancos 2, nulos 4 (219 votos) |
| Presidente no BU | 13 = 158, 22 = 52, 14 = 1, 70 = 2, brancos 2, nulos 4; comparecimento 219, igual ao número de votos no log |

Com isso, o RDV que faltava na publicação seção a seção pode ser conferido pelo pacote, e confere. Não dá para saber se ele já estava na versão de 22/10 do zip ou se entrou só na de 03/11: a data do membro (20/10) é anterior às duas, e a leitura anterior não registrava a presença do RDV.

## O que não dá para afirmar

- **Qual byte mudou.** A versão anterior não foi guardada, nem o diretório dela, e nenhuma cópia pública foi encontrada (a consulta ao índice do Internet Archive não retornou captura desses endereços). A troca pode ter sido só de bytes do zip (ordem, compressão, campos extras), de presença de algum membro que a leitura anterior não lia (RDV ou `.vsc`), ou nenhuma: um novo envio do mesmo arquivo também muda o `Last-Modified`.
- **O que está excluído.** Pelas conferências acima, a versão nova não tem nenhum BU, imagem do BU, log, RDV ou `.vsc` de conteúdo diferente do que a urna assinou, nem conteúdo diferente do que foi baixado em 13/10, nem nenhuma seção ou arquivo de BU, imagem do BU ou log a mais ou a menos do que a versão lida antes. Uma eventual diferença ficou restrita ao invólucro do zip ou ao RDV e ao `.vsc` da seção 07846/0074/0228, cujo conteúdo é autêntico.

## Como reproduzir

No servidor de análise, com o zip atual baixado para a memória (`/dev/shm`):

```
uv run python scripts/ele2026/ma_republicado.py \
    --zip /dev/shm/ma-republicado-zip/ma_1t.zip \
    --catalogo ~/dataurnas-ma-republicado/arquivos_ma.parquet \
    --antigo ~/dataurnas-pacote-nacional/secoes_ma_1.parquet \
    --cd ~/dataurnas-pacote-nacional/cd_republicados.parquet \
    --saida ~/dataurnas-ma-republicado
```

O script consulta o cabeçalho HTTP, confere a estrutura do zip, calcula CRC-32, MD5, SHA-256 e SHA-512 de cada membro, compara com o catálogo e com o diretório de 04/11, reconta o RDV de qualquer seção que o catálogo não tenha, verifica todas as assinaturas e relê todas as seções. A saída fica em `~/dataurnas-ma-republicado/`: `resumo.json`, `membros.parquet` (uma linha por membro, com hashes e campos do zip), `assinaturas.parquet`, `secoes_novas.parquet` e `diferencas_secoes.csv` (vazio nesta execução). A execução de 04/11/2026 levou 3 minutos e 10 segundos no servidor, com o download do zip (3,27 GB) feito antes em cerca de 6 minutos.
