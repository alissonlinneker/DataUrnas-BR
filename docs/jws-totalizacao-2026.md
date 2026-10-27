# Resultados assinados (.jws) da totalização de 2026: assinatura e confronto com os BUs

## Resultado em destaque

**Nenhuma assinatura inválida e nenhuma divergência.**

| Item | 2º turno (eleição 6258) | 1º turno (eleição 6257) |
|---|---:|---:|
| Arquivos .jws baixados (Brasil, 28 UFs, 5.757 municípios) | 5.786 de 5.786 | 5.786 de 5.786 |
| Assinatura válida com a chave oficial do TSE | **5.786** | **5.786** |
| Assinatura inválida | **0** | **0** |
| Cabeçalho diferente de `EdDSA` + `kid` oficial | 0 | 0 |
| Payload de abrangência ou eleição trocada | 0 | 0 |
| Payload idêntico, byte a byte, ao .json publicado | 5.786 | 5.786 |
| Divergências com a soma dos BUs (Brasil, UFs, municípios) | **0** | **0** |

Em todos os níveis (Brasil, cada UF e cada um dos 5.757 municípios, inclusive as
cidades do exterior) os números assinados pelo TSE são iguais à soma dos boletins de
urna assinados pelas urnas: votos do 13, do 22, brancos, nulos, comparecimento,
abstenção, eleitorado das seções instaladas e seções. No 1º turno a igualdade vale
com o ajuste conhecido do nulo técnico (5.246 votos digitados no número 28, que não
tinha candidato; ver [Método](#confronto-com-os-bus)).

## O que é o .jws

Desde 2026 o TSE publica cada arquivo de resultado em dois formatos, no mesmo
endereço: `.json` (dados) e `.jws` (os mesmos dados assinados). O `.jws` é um JWS
compacto (RFC 7515) com três partes em Base64URL separadas por ponto:
cabeçalho, payload (o JSON do resultado) e assinatura EdDSA sobre Ed25519
(RFC 8037). Exemplo, Brasil no 2º turno:

```
https://resultados.tse.jus.br/oficial/ele2026/6258/dados/br/br-c0001-e006258-u.jws
cabeçalho: {"kid":"sNbt9Q_fLS65zE1_ZLNV-XRRwPY","typ":"JOSE","alg":"EdDSA"}
```

Endereços (mesmo padrão dos `.json` usados por `versionar_t2.py`):
`<base>/ele2026/<eleição>/dados/<uf>/<abr>-c0001-e<eleição com 6 dígitos>-u.jws`,
com `abr` = `br`, a UF (`sp`, `zz`) ou UF + código TSE do município (`sp71072`).
A lista de municípios vem de `<base>/ele2026/<eleição>/config/mun-e<eleição>-cm.json`
(5.757 municípios, 28 abrangências de UF, nos dois turnos). Os códigos das
eleições estão em `https://resultados.tse.jus.br/oficial/comum/config/ele-c.json`:
6257 (federal, 1º turno, pleito 3220) e 6258 (federal, 2º turno, pleito 3221).

## Chave pública usada

A chave **não** foi tirada do próprio .jws. Ela foi copiada do documento oficial
"Manual de verificação dos arquivos JWS" do TSE (versão de 16/09/2026), Apêndice B
(ambiente oficial), e fixada no script, como o próprio manual recomenda.

| Item | Valor |
|---|---|
| Documento | `https://www.tse.jus.br/eleicoes/eleicoes-2026-content/arquivos/divulgacao-de-resultados/manual-verificacao-jws` |
| Captura usada | Web Archive, `20261009105842` (o endereço direto do TSE respondeu 403 ao acesso automatizado em 27/10/2026) |
| SHA-256 do PDF (8 páginas) | `db1145145e98283689e53d3261c2f9188369d42c9e1e9db351b9e62c38684244` |
| JWK oficial | `{"kty":"OKP","crv":"Ed25519","alg":"EdDSA","use":"sig","key_ops":["verify"],"kid":"sNbt9Q_fLS65zE1_ZLNV-XRRwPY","x":"kWlpNHjuws1csyQZwzn3Fhzbi3RD435RbpThtSr4hMc"}` |
| SHA-256 da chave bruta (32 bytes de `x`) | `8246b7eaa1858ddd9aa77ad3931fd9ce82805ab13adb77d5963eb7aca80f7a5a` |
| Impressão digital RFC 7638 (SHA-256 da JWK canônica) | `e466eb5998d61a42be7e4fe5e28b6ca0c9bc1ca6725de3f2f962e96599cd6ff6` |
| Chave de desenvolvimento (Apêndice A), que não pode aparecer | `kid` `pEGrlis0i8vO2Bz7Ergwr0MnKfg` (nenhum arquivo a usa) |

O manual traz também a cadeia X.509 da mesma chave. O subcomando `chave` do script
confere que as duas formas são a mesma chave e que a cadeia fecha:

| Conferência | Resultado |
|---|---|
| Chave Ed25519 do certificado "ELEICOES 2026 - DIVULGACAO DE RESULTADOS" = `x` da JWK | sim |
| `kid` da JWK = identificador da chave (Subject Key Identifier) do certificado | sim (`b0d6edf50fdf2d2eb9cc4d7f64b355f97451c0f6`) |
| Certificado da entidade final assinado pela AC DIVULGACAO (Ed448) | sim |
| AC DIVULGACAO assinada pela AC TOTALIZACAO (Ed448) | sim |
| AC TOTALIZACAO autoassinada | sim |
| Validade da entidade final | 01/01/2026 a 01/01/2031 |

SHA-256 (DER) dos certificados: entidade final
`8b4cc28a9816ad9a2e9c9278a42fadc1dccfa79805d615ad4ed7556c02410941`, AC DIVULGACAO
`a8ef9896d31c08cfae9b9fe9ec764671d6a14755164ae66e0028f24ace3d7b43`, AC TOTALIZACAO
`367625ddf7b73031fa6b073568b1526aaec1359b4a7791bcce5cf1077276b07f`.

Limite: a Lista de Certificados Revogados indicada nos certificados
(`http://actot.tse.jus.br/totalizacao/oficial/crls/acdivulgacao.crl` e `actot.crl`)
respondeu 403 tanto do Mac quanto do servidor de processamento, por HTTP e HTTPS.
A não revogação do certificado não foi conferida. A raiz da confiança é o manual
publicado pelo TSE em 16/09/2026, antes das duas votações.

## Método

### Download

`scripts/ele2026/verificar_jws.py baixar`: um único processo, sequencial, uma
conexão HTTPS reaproveitada, no máximo 3 requisições por segundo, retomável pelo
`manifesto.jsonl` (abrangência, URL, status HTTP, `Last-Modified`, `ETag`, tamanho,
SHA-256, momento do download). O 2º turno foi baixado do Mac em 27/10/2026 entre
07h19 e 07h55 UTC; o 1º turno começou no Mac e, depois de uma falha de rede local,
foi concluído no servidor de processamento (mesmo teto, um processo). Nenhuma
requisição falhou ao final: 5.786 respostas 200 em cada turno.

Brutos no servidor de processamento, em `~/dataurnas-jws-2026/`:

| Pasta | Conteúdo | SHA-256 do conjunto |
|---|---|---|
| `t2/` | 5.786 .jws do 2º turno, `manifesto.jsonl`, `mun-e006258-cm.json` | `3540e4358b70c39119369007505a7c54c56dc4dd5a9b8d5a3e170dd9b35d5a3e` |
| `t1/` | 5.786 .jws do 1º turno, `manifesto.jsonl`, `mun-e006257-cm.json` | `96ea3e9bfafc64f1ba980d0514b229f859757f1afd97f9f94f6d90dd21ed2406` |
| `t2-json/` | 3.288 .json do 2º turno (os que o coletor não tinha na versão final) | |
| `t1-json/` | 5.786 .json do 1º turno | |
| `verificacao/` | `verif_t1.jsonl`, `verif_t2.jsonl` (uma linha por arquivo), `confronto_t1.csv`, `confronto_t2.csv` (só cabeçalho: sem divergência), `bu_t1.tsv`, `bu_t2.tsv` (soma dos BUs por abrangência) | |
| `manual-verificacao-jws-wayback-20261009105842.pdf` | o manual com a chave | `db1145145e...38684244` |

O SHA-256 do conjunto é `find tN -name '*.jws' | sort | xargs sha256sum | sha256sum`,
rodado dentro de `~/dataurnas-jws-2026`.

### Verificação da assinatura

Para cada arquivo (`verificar`):

1. separa as três partes; decodifica o cabeçalho e exige `alg = EdDSA` e
   `kid = sNbt9Q_fLS65zE1_ZLNV-XRRwPY`;
2. verifica a assinatura Ed25519 sobre `cabeçalho.payload` (ASCII, como está no
   arquivo) com a chave fixada (biblioteca `cryptography` 50.0.2);
3. controle negativo: troca um bit no meio do payload e exige que a mesma
   assinatura seja recusada (5.786 de 5.786 recusadas no 1º turno e 5.786 de 5.786
   no 2º, o que mostra que o verificador não aceita qualquer coisa);
4. confere que o payload é da abrangência, da eleição e do turno do nome do arquivo
   (`cdabr`, `ele`, `t`);
5. extrai o resumo: seções (`ts`, `st`, `si`, `sni`), eleitorado (`te`, `esi`),
   comparecimento, abstenção, votos por candidato (`vap`), brancos, nulos (`vn`),
   nulos técnicos (`vnt`), total de nulos (`tvn`), data e hora de geração e de
   totalização, indicador de totalização final (`tf`).

Conferência independente: o `.jws` do Brasil no 2º turno também foi verificado
com o OpenSSL 4.0.3 (`openssl pkeyutl -verify -rawin`), com a chave montada a partir
do `x` da JWK: assinatura válida, e recusada com um caractere do payload trocado.

### Payload x .json

O payload de cada .jws foi comparado byte a byte com o .json do mesmo endereço:

- **2º turno**: 2.498 payloads são idênticos (mesmo SHA-256) a uma versão do .json
  guardada pelo coletor `versionar_t2.py` (`~/dataurnas-mac/versoes/2026/t2/totais`
  e `~/dataurnas-versoes-t2-nne/totais`). Os outros 3.288 eram de versões geradas
  depois da última coleta (a final, com `tf = s` e o resultado de eleito); para
  eles o .json atual foi baixado (mesmo teto de 3 req/s) e os 3.288 são idênticos
  byte a byte. Total: **5.786 de 5.786 idênticos**.
- **1º turno**: o coletor de versões não existia no 1º turno; os 5.786 .json foram
  baixados agora (27/10/2026, mesmo teto de 3 req/s) e os 5.786 payloads são
  idênticos byte a byte. Total: **5.786 de 5.786 idênticos**.

Observação sobre o `idg` (identificador de geração): ele não cresce com o tempo.
No Brasil, por exemplo, o coletor guardou uma versão das 23:22:22 com `idg`
4247843 e o .jws final, gerado às 23:27:02, tem `idg` 4241309. Para ordenar versões
use `dg` e `hg`, não o `idg`.

### Confronto com os BUs

Soma dos BUs no ClickHouse (`docs/banco-clickhouse.md`), por abrangência (Brasil,
UF, UF + município), em `confrontar`:

- 2º turno: todas as seções de `v_bu_ultima` (última versão de BU de cada seção,
  499.207), com os votos de `v_votos_t2_secao` por junção externa. A junção externa
  importa: `v_votos_t2_secao` não tem linha para seção sem nenhum voto, e há duas
  assim, ambas no exterior, com BU emitido e comparecimento zero
  (`zz29564` zona 0001 seção 0091, 72 aptos; `zz30686` zona 0001 seção 0443, 30
  aptos). Com elas, a contagem de seções e de aptos fecha.
- 1º turno: as 499.207 seções com BU de `ref_secoes_2026_t1` (`status = ok`), com
  os votos de `v_votos_t1_secao` por junção externa (a seção `zz29564/0001/0091`
  também não teve voto no 1º turno).

Correspondência dos campos:

| Soma dos BUs | Campo do .jws | Observação |
|---|---|---|
| seções com BU | `s.si` (seções instaladas) | seção não instalada não tem BU; `st` = `ts` = 499.248 inclui as 41 não instaladas |
| aptos | `e.esi` (eleitorado das seções instaladas) | `te` inclui os 423 eleitores das seções não instaladas |
| comparecimento | `e.c` | |
| aptos menos comparecimento | `e.a` (abstenção) | o TSE calcula a abstenção sobre as seções instaladas |
| votos no 13 e no 22 | `vap` dos candidatos 13 e 22 | |
| brancos | `v.vb` | |
| nulos | `v.vn` | nulos digitados |
| nominais fora de 13 e 22 | `vap` dos demais candidatos + `v.vnt` | no 1º turno, 5.246 votos no 28 (sem candidato) são nulo técnico para o TSE |

Resultado: **0 divergências** em 5.786 abrangências no 2º turno e 0 em 5.786 no 1º
turno, para todos os campos acima. As 40 cidades do exterior sem nenhuma seção
instalada (`si = 0`) têm todos os campos zerados no .jws e nenhuma seção com BU,
o que também confere.

Totais do Brasil (iguais no .jws e na soma dos BUs):

| Campo | 1º turno | 2º turno |
|---|---:|---:|
| Seções totalizadas / instaladas / não instaladas | 499.248 / 499.207 / 41 | 499.248 / 499.207 / 41 |
| Eleitorado / das seções instaladas | 158.745.502 / 158.745.079 | 158.745.502 / 158.745.079 |
| Comparecimento | 125.275.835 | 128.236.074 |
| Abstenção | 33.469.244 | 30.509.005 |
| 13 | 53.879.538 | 64.256.232 |
| 22 | 56.104.503 | 59.826.041 |
| Demais candidatos (10) | 9.316.747 | |
| Brancos | 2.300.798 | 1.430.496 |
| Nulos digitados | 3.669.003 | 2.723.305 |
| Nulos técnicos (número 28) | 5.246 | 0 |

## Outras observações

- Todos os arquivos dos dois turnos trazem `tf = s` (totalização final) e
  `and = f`. No 2º turno, todos foram gerados em 25/10/2026 entre 23:26:56 e
  23:27:44 (horário de Brasília), com `Last-Modified` entre 02:27:18 e 02:30:11 UTC
  de 26/10.
- No 1º turno, 5.599 arquivos foram gerados em 05/10/2026 (a partir de 12:51:40) e
  187, todos do exterior (a UF `zz` e 186 cidades), foram gerados de novo em
  24/10/2026 às 20:12 e 20:13, véspera do 2º turno, mantendo a data e a hora de
  totalização (05/10/2026 12:51:05). O `Last-Modified` dos arquivos do 1º turno
  se distribui em 05/10 (3.385), 07/10 (1.332), 18/10 (236), 21/10 (646) e 24/10
  (187): o TSE regravou os arquivos no servidor depois da eleição. Os números
  regravados continuam iguais aos BUs e ao resultado oficial por município
  coletado em 05/10/2026 (`ref_resultado_municipio_2026_t1`: 5.757 municípios,
  0 diferenças em seções totalizadas, comparecimento, 13, 22, brancos e total de
  nulos). A regeração não mudou resultado, mas o motivo não foi informado.
- O payload assinado inclui a formatação exata do .json (espaços e quebras de
  linha), por isso a comparação byte a byte é possível e foi feita.

## Como reproduzir

```sh
S=scripts/ele2026/verificar_jws.py
python3 $S chave                                    # chave x certificado x cadeia
python3 $S baixar --turno 2 --saida ~/dataurnas-jws-2026 --rps 3
python3 $S baixar --turno 1 --saida ~/dataurnas-jws-2026 --rps 3
python3 $S baixar --turno 2 --formato json --saida ~/dataurnas-jws-2026 --rps 3 \
    [--lista abrangencias.txt]
# soma dos BUs por abrangência (consultas no fim deste documento)
ch.sh < bu_t2.sql > bu_t2.tsv
python3 $S verificar --turno 2 --dir ~/dataurnas-jws-2026 \
    --totais ~/dataurnas-mac/versoes/2026/t2/totais ~/dataurnas-versoes-t2-nne/totais \
    --json-dir ~/dataurnas-jws-2026/t2-json --saida verif_t2.jsonl
python3 $S confrontar --verif verif_t2.jsonl --bu bu_t2.tsv --saida confronto_t2.csv
```

`verificar` grava uma linha JSON por arquivo (assinatura, controle negativo,
abrangência, resumo, comparação com o .json) e imprime as contagens;
`confrontar` grava um CSV só com as divergências (`abr, campo, jws, soma_bu,
diferenca`) e imprime o total. Nos dois turnos o CSV saiu só com o cabeçalho.

Soma dos BUs do 2º turno (no 1º, troque a base por `ref_secoes_2026_t1` com
`status = 'ok'` e `v_votos_t1_secao`, com `votos_outros` como `o_`):

```sql
WITH s AS (
    SELECT u.uf AS uf, u.cd_mun AS cd_mun, ifNull(u.aptos, 0) AS a_,
           ifNull(u.comparecimento, 0) AS c_, v.votos_13 AS v13_, v.votos_22 AS v22_,
           v.brancos AS b_, v.nulos AS n_,
           v.total - v.votos_13 - v.votos_22 - v.brancos - v.nulos AS o_
    FROM v_bu_ultima AS u
    LEFT JOIN v_votos_t2_secao AS v
      ON v.uf = u.uf AND v.cd_mun = u.cd_mun AND v.zona = u.zona AND v.secao = u.secao
)
SELECT abr, count() AS secoes, sum(a_) AS aptos, sum(c_) AS comparecimento,
       sum(a_) - sum(c_) AS abstencao, sum(v13_) AS votos_13, sum(v22_) AS votos_22,
       sum(b_) AS brancos, sum(n_) AS nulos, sum(o_) AS outros
FROM (SELECT arrayJoin(['br', toString(uf), concat(toString(uf), cd_mun)]) AS abr, * FROM s)
GROUP BY abr ORDER BY abr
FORMAT TSVWithNames;
```

## Alcance

A assinatura prova que os arquivos vieram de quem tem a chave privada do
certificado "ELEICOES 2026 - DIVULGACAO DE RESULTADOS" e não foram alterados
depois de assinados. Ela não prova que a totalização esteja certa; isso é o que o
confronto com os BUs (assinados pelas urnas e conferidos em
`docs/auditoria-consistencia-bu-2026.md`) mostra, nível por nível. Juntas, as duas
verificações fecham o caminho urna, BU, totalização e divulgação para Presidente
nos dois turnos de 2026.
