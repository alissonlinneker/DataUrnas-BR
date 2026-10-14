# Investigação: seções com status "Recebida" (Presidente, 1º turno de 2026)

Data da investigação: 14/10/2026 (consultas ao TSE entre 02:38 e 02:50, horário local).
Base local: `data/parquet/2026/secoes_2026.parquet` (consolidado em 13/10/2026 21:53) e
`data/parquet/2026/resultado_uf.parquet` / `resultado_municipio.parquet` (baixados em 13/10/2026 14:31).
Lista completa das seções: `data/parquet/2026/secoes_recebidas_2026.csv` (2.677 linhas).

## Resumo

- 2.677 seções têm `st = "Recebida"` no `aux.json` (hash com `st = "Recebido"`), em 8 UFs e 60 municípios.
  Todas foram recebidas **depois** da geração do resultado oficial (05/10/2026 12:51:05): a primeira às
  05/10/2026 12:54:35 e a última às 07/10/2026 15:00:09.
- Os BUs dessas seções foram emitidos pela urna no dia da eleição (04/10/2026, entre 17:00:38 e 20:58:33),
  todos com origem `bu` (urna), nenhum `busa` (Sistema de Apuração), tipo `secao` (2.665) ou
  `reservaSecao` (12), fase `oficial`.
- O resultado oficial (arquivos `-u.json` de BR, UFs e municípios) **não mudou** desde 05/10/2026:
  `dg/hg` = 05/10/2026 12:51-12:52, `dt/ht` = 05/10/2026 12:51:05, `Last-Modified` = 05/10/2026 (BR: 07/10/2026 23:35 GMT,
  mesmo conteúdo). Todos os arquivos indicam 100% das seções totalizadas.
- A soma dos BUs **incluindo** as seções "Recebida" bate exatamente com o oficial, por UF e por município
  (comparecimento, brancos, nulos e votos por candidato). **Excluindo** essas seções, faltam exatamente os votos
  delas (ex.: PA -429.664 de comparecimento). Ou seja: os votos dessas seções **estão** nos totais oficiais
  de 05/10, com os mesmos números do BU publicado hoje.
- Diferença estrutural observada: nas 57 seções "Recebida" amostradas, o `aux.json` lista 5 arquivos
  (`bu`, `rdv`, `log`, `vota`, `imgbu`), e o `imgbu` retorna HTTP 404 em **todas** (57/57); os outros 4 retornam 200.
  Nas 118 seções "Totalizada" de controle, o `aux.json` lista só 4 arquivos (sem `imgbu`), todos 200.
  O `aux.json` das "Recebida" também não tem o campo `idg` e traz `f = "O"` (maiúsculo), enquanto o das
  "Totalizada" tem `idg` e `f = "o"`.
- Todas as seções (Recebida e Totalizada) têm um único hash no `aux.json` (`n_hashes = 1`): o histórico de
  versões anteriores não é publicado.

**Interpretação mais provável (não confirmada pelo TSE):** o pacote publicado hoje para essas seções é um
reenvio posterior à totalização (05 a 07/10), contendo o mesmo BU já totalizado em 04-05/10 mais o arquivo
`imgbu`. Como a seção já estava totalizada, o novo pacote ficou com status "Recebido" e substituiu o anterior
no `aux.json`, que só mostra o hash mais recente. Isso explica por que a data de recebimento é posterior ao
resultado e, ainda assim, os votos batem. O que **não** podemos afirmar sem o TSE: que o BU deste pacote é
byte a byte o mesmo que foi totalizado (o hash do pacote anterior não é publicado), nem o motivo do reenvio.

## 1. A reconciliação inclui as seções "Recebida"?

Sim. `scripts/ele2026/reconcile.py` soma todas as linhas com `status = 'ok'`, sem filtrar `st_secao`.
Em `scripts/ele2026/fetch_secoes.py`, `status = 'ok'` significa apenas "BU baixado e decodificado".
A escolha do hash (`escolher_hash` em `src/dataurnas/downloader/ele2026.py`) prefere o hash `Totalizado`;
na falta dele usa o último hash não nulo, que nessas 2.677 seções é o único hash, com `st = "Recebido"`.

Distribuição na base local:

| st_secao | st_hash | status | origem_bu | seções |
|---|---|---|---|---:|
| Totalizada | Totalizado | ok | bu | 483.592 |
| Totalizada | Totalizado | ok | (nulo) | 12.907 |
| Totalizada | Totalizado | ok | busa | 31 |
| Recebida | Recebido | ok | bu | 2.677 |
| (nulo) | (nulo) | agregada | (nulo) | 17.931 |
| Nao instalada | (nulo) | nao_instalada | (nulo) | 41 |

Observação lateral: as 12.907 seções com `origem_bu` nulo são de lotes gravados antes de a coluna existir
(todas `Totalizada`, recebidas em 04/10); não afetam esta investigação.

Data de recebimento das seções com BU:

| dt_recebimento | Totalizada | Recebida |
|---|---:|---:|
| 04/10/2026 | 496.231 | 0 |
| 05/10/2026 | 219 | 598 |
| 06/10/2026 | 78 | 1.241 |
| 07/10/2026 | 2 | 838 |

Nenhuma "Recebida" foi recebida antes das 12:51:05 de 05/10 (a primeira é 05/10 12:54:35).

### Recontagem por UF excluindo as "Recebida"

| UF | Recebida | comparecimento sem Recebida | com todas | oficial | dif. com todas | dif. sem Recebida |
|---|---:|---:|---:|---:|---:|---:|
| BA | 135 | 9.023.819 | 9.053.601 | 9.053.601 | 0 | -29.782 |
| MA | 403 | 4.053.795 | 4.160.343 | 4.160.343 | 0 | -106.548 |
| PA | 1.613 | 4.636.840 | 5.066.504 | 5.066.504 | 0 | -429.664 |
| PI | 19 | 2.236.481 | 2.240.883 | 2.240.883 | 0 | -4.402 |
| PR | 500 | 6.708.699 | 6.841.457 | 6.841.457 | 0 | -132.758 |
| RS | 2 | 6.702.448 | 6.702.903 | 6.702.903 | 0 | -455 |
| SC | 1 | 4.647.964 | 4.648.159 | 4.648.159 | 0 | -195 |
| SP | 4 | 26.431.009 | 26.431.992 | 26.431.992 | 0 | -983 |

O número de seções com BU também só bate com `secoes_instaladas` oficial quando as "Recebida" entram
(ex.: PA 20.827 com todas, 19.214 sem).

Nos 60 municípios com seções "Recebida", a soma dos BUs com todas as seções bate com o resultado municipal
oficial em comparecimento, brancos, nulos e número de seções (60/60), e em votos por candidato (720/720
pares município x candidato). Sem as "Recebida", nenhum dos 60 bate. Exemplo extremo: Ibitiara (BA) tem
46 seções, todas "Recebida" no `aux.json`, e o resultado oficial do município (gerado 05/10/2026 12:52:32)
mostra 46/46 seções totalizadas e 9.506 comparecimentos, igual à soma dos 46 BUs.

### Resultado oficial atual x armazenado

Consulta em 14/10/2026 02:38 aos `-u.json` atuais:

| arquivo | Last-Modified (HTTP) | dg hg | dt ht | seções tot./total | comparecimento |
|---|---|---|---|---|---:|
| br | Wed, 07 Oct 2026 23:35:43 GMT | 05/10/2026 12:51:47 | 05/10/2026 12:51:05 | 499.248/499.248 | 125.275.835 |
| pa | Mon, 05 Oct 2026 15:52:17 GMT | 05/10/2026 12:51:45 | 05/10/2026 12:51:05 | 20.827/20.827 | 5.066.504 |
| pr | Mon, 05 Oct 2026 15:52:46 GMT | 05/10/2026 12:51:50 | 05/10/2026 12:51:05 | 27.142/27.142 | 6.841.457 |
| ma | Mon, 05 Oct 2026 15:53:42 GMT | 05/10/2026 12:51:45 | 05/10/2026 12:51:05 | 18.093/18.093 | 4.160.343 |
| ba | Mon, 05 Oct 2026 15:52:13 GMT | 05/10/2026 12:51:55 | 05/10/2026 12:51:05 | 35.476/35.476 | 9.053.601 |
| pi | Mon, 05 Oct 2026 15:53:18 GMT | 05/10/2026 12:51:46 | 05/10/2026 12:51:05 | 10.225/10.225 | 2.240.883 |
| sp | Mon, 05 Oct 2026 15:52:19 GMT | 05/10/2026 12:51:59 | 05/10/2026 12:51:05 | 103.656/103.656 | 26.431.992 |
| rs | Mon, 05 Oct 2026 15:53:18 GMT | 05/10/2026 12:51:50 | 05/10/2026 12:51:05 | 27.547/27.547 | 6.702.903 |
| sc | Mon, 05 Oct 2026 15:53:19 GMT | 05/10/2026 12:51:45 | 05/10/2026 12:51:05 | 17.326/17.326 | 4.648.159 |
| pa04278 (Belém) | Mon, 05 Oct 2026 15:53:49 GMT | 05/10/2026 12:52:20 | 05/10/2026 12:51:05 | 2.989/2.989 | 866.529 |
| pr75353 (Curitiba) | Mon, 05 Oct 2026 15:52:55 GMT | 05/10/2026 12:52:27 | 05/10/2026 12:51:05 | 4.056/4.056 | 1.136.092 |
| ma09210 (São Luís) | Mon, 05 Oct 2026 15:54:08 GMT | 05/10/2026 12:52:22 | 05/10/2026 12:51:05 | 2.273/2.273 | 642.000 |
| ba35610 (Ibitiara) | Mon, 05 Oct 2026 15:54:07 GMT | 05/10/2026 12:52:32 | 05/10/2026 12:51:05 | 46/46 | 9.506 |
| ba38490 (Salvador) | Mon, 05 Oct 2026 15:54:32 GMT | 05/10/2026 12:52:29 | 05/10/2026 12:51:05 | 5.124/5.124 | 1.561.593 |
| pa05339 (Santana do Araguaia) | Mon, 05 Oct 2026 15:54:00 GMT | 05/10/2026 12:52:19 | 05/10/2026 12:51:05 | 83/83 | 18.830 |

Os totais e as datas de geração são os mesmos já armazenados (`resultado_uf.parquet`, `resumo_br.json`
com `data_geracao_tse = 05/10/2026 12:51:47`). O arquivo BR foi regravado no servidor em 07/10 (Last-Modified),
mas com a mesma data de geração e os mesmos números. Não há resultado por seção no diretório `dados/`
(o nível mais fino publicado é o município); o BU da seção é a fonte por seção.

## 2. Amostra de `aux.json` e arquivos

Amostra: até 10 seções "Recebida" por UF (57 no total: BA 10, MA 10, PA 10, PI 10, PR 10, SP 4, RS 2, SC 1)
e três grupos de controle "Totalizada": 10 vizinhas das mesmas zonas (Belém 0001, Salvador 0005, Curitiba 0001,
São Luís 0001, Tambaú 0116), as 88 "Totalizada" com recebimento após 05/10 12:51:05 e 20 aleatórias de 04/10.
Para cada seção: GET do `aux.json` e HEAD de cada arquivo listado. Concorrência máxima de 4 requisições.

| grupo | seções | st (aux) | f | idg | hashes | arquivos listados | HTTP |
|---|---:|---|---|---|---:|---|---|
| Recebida | 57 | Recebida | O | ausente | 1 (st Recebido) | bu, rdv, log, vota, imgbu | 200 em 4; **imgbu 404 em 57/57** |
| Totalizada (mesma zona) | 10 | Totalizada | o | presente | 1 (st Totalizado) | bu, rdv, log, vota | 200 em todos |
| Totalizada recebida após 12:51 | 88 | Totalizada | o | presente | 1 (st Totalizado) | bu, rdv, log, vota | 200 em todos |
| Totalizada aleatória (04/10) | 20 | Totalizada | o | presente | 1 (st Totalizado) | bu, rdv, log, vota | 200 em todos |

Exemplo de `aux.json` "Recebida" (SP, Tambaú, zona 0116, seção 0107):

```json
{"dg": "06/10/2026", "hg": "18:09:02", "f": "O", "st": "Recebida",
 "hashes": [{"hash": "4f625455...", "dr": "06/10/2026", "hr": "18:09:02", "st": "Recebido",
   "arq": [{"nm": "o03220sp7167601160107-vota.vsc", "tp": "vota"}, {"nm": "o03220sp7167601160107-log.jez", "tp": "log"},
           {"nm": "o03220sp7167601160107-bu.dat", "tp": "bu"}, {"nm": "o03220sp7167601160107-rdv.dat", "tp": "rdv"},
           {"nm": "o03220sp7167601160107-imgbu.dat", "tp": "imgbu"}]}]}
```

Exemplo "Totalizada" (MA, São Luís, zona 0001, seção 0087):

```json
{"dg": "05/10/2026", "hg": "12:52:43", "idg": "2866469", "f": "o", "st": "Totalizada",
 "hashes": [{"hash": "57735756...", "dr": "04/10/2026", "hr": "17:41:36", "st": "Totalizado",
   "arq": [{"nm": "...-rdv.dat", "tp": "rdv"}, {"nm": "...-vota.vsc", "tp": "vota"},
           {"nm": "...-bu.dat", "tp": "bu"}, {"nm": "...-log.jez", "tp": "log"}]}]}
```

No `aux.json` das "Recebida", `dg/hg` coincide com `dr/hr` do hash, e o `Last-Modified` HTTP do arquivo
(em GMT; `dr/hr` está em horário de Brasília, UTC-3) fica entre cerca de 1 e 10 horas depois do recebimento,
sempre entre 05 e 07/10. Nenhum `aux.json` amostrado mostra versão anterior do pacote.

Achado paralelo: 88 seções "Totalizada" também têm `dr/hr` posterior a 05/10 12:51:05 (PE 76, PA 8, AM 3, RJ 1;
a maioria em 06/10 entre 11:45 e 12:58, uma em 06/10 14:40). Elas também já estão nos totais de 05/10.
Isso reforça que `dr/hr` no `aux.json` é a data do pacote **publicado agora**, não necessariamente a do
primeiro recebimento usado na totalização.

## 3. Caracterização das 2.677 seções

Por UF:

| UF | seções | municípios | zonas | primeiro recebimento | último recebimento | comparecimento |
|---|---:|---:|---:|---|---|---:|
| PA | 1.613 | 22 | 28 | 05/10/2026 12:54:35 | 07/10/2026 10:57:41 | 429.664 |
| PR | 500 | 14 | 14 | 07/10/2026 12:15:32 | 07/10/2026 15:00:09 | 132.758 |
| MA | 403 | 4 | 4 | 06/10/2026 07:59:40 | 07/10/2026 11:08:50 | 106.548 |
| BA | 135 | 12 | 12 | 06/10/2026 14:46:08 | 07/10/2026 14:39:27 | 29.782 |
| PI | 19 | 3 | 3 | 06/10/2026 09:59:36 | 07/10/2026 09:02:20 | 4.402 |
| SP | 4 | 3 | 3 | 06/10/2026 18:06:30 | 07/10/2026 12:40:05 | 983 |
| RS | 2 | 1 | 1 | 07/10/2026 14:44:31 | 07/10/2026 14:48:11 | 455 |
| SC | 1 | 1 | 1 | 07/10/2026 14:25:10 | 07/10/2026 14:25:10 | 195 |

Municípios com mais seções "Recebida":

| UF | município | seções |
|---|---|---:|
| PA | Belém | 1.099 |
| PR | Curitiba | 360 |
| MA | São Luís | 360 |
| PA | Santana do Araguaia | 83 |
| PA | Porto de Moz | 83 |
| PA | Capanema | 63 |
| PA | Terra Santa | 61 |
| PA | Oeiras do Pará | 61 |
| BA | Ibitiara | 46 (todas as do município) |
| MA | Nina Rodrigues | 40 |
| BA | Novo Horizonte | 38 (todas as da zona 0088 no município) |

A concentração é por zona eleitoral: há zonas em que todas as seções estão "Recebida" (Ibitiara e Novo Horizonte,
zona 0088/BA) e os horários de recebimento formam blocos contínuos por zona (ex.: Curitiba zona 0178 em 07/10
das 13:29 às 14:54). O padrão é compatível com reenvio feito pelo cartório eleitoral, zona a zona.

Modelo da urna (extraído do `-vota.vsc`), comparado com o total de seções com BU:

| modelo | Recebida | % | todas com BU | % |
|---|---:|---:|---:|---:|
| UE2020 | 1.202 | 44,9 | 200.463 | 40,2 |
| UE2022 | 986 | 36,8 | 198.759 | 39,8 |
| UE2015 | 392 | 14,6 | 88.064 | 17,6 |
| UE2013 | 97 | 3,6 | 11.921 | 2,4 |

Sem desvio relevante de modelo. Por UF o mix segue o parque local (MA concentra UE2015/UE2013; PR, UE2022; PA, UE2020).

Outros atributos:

- `origem_bu`: 2.677 `bu` (urna); 0 `busa`. Não são apuração por cédula nem BU do Sistema de Apuração.
- `tipo_urna`: 2.665 `secao`, 12 `reservaSecao` (urna de contingência que substituiu a original na seção).
- `fase`: todas `oficial`.
- `data_hora_emissao` do BU: todas em 04/10/2026, entre 17:00:38 e 20:58:33.
- `hora_encerramento`: média 17:19 (Totalizada: 17:12); 261 encerradas após 18h (9,7%, contra 8,2% nas Totalizada).
- `imgbu`: listado e indisponível (404) em 57/57 da amostra; o registro `data/parquet/2026/integridade/ocorrencias_publicacao.jsonl`
  já acumula casos do mesmo tipo vindos da coleta nacional.

## 4. Conclusão

**Certo (verificado):**

1. Os votos das 2.677 seções "Recebida" estão contidos no resultado oficial gerado em 05/10/2026 12:51:05,
   por UF, por município e por candidato. A soma dos BUs publicados hoje reproduz esses totais exatamente;
   sem eles, os totais não fecham.
2. O resultado oficial não foi alterado depois de 05/10 (datas de geração e números iguais).
3. O BU publicado de cada uma dessas seções foi emitido pela urna em 04/10, com origem urna (não Sistema de Apuração).
4. O pacote publicado para elas foi recebido entre 05/10 12:54 e 07/10 15:00, depois da totalização, e é
   diferente em forma do pacote das seções totalizadas: inclui `imgbu`, que não está disponível (404),
   e o `aux.json` não tem `idg` e usa `f = "O"`.
5. O `aux.json` publica apenas um hash por seção; versões anteriores não ficam visíveis.

**Provável (inferência a confirmar):** essas seções foram totalizadas em 04-05/10 com um pacote anterior e,
de 05 a 07/10, os cartórios reenviaram os arquivos (por exemplo, para completar o conjunto com a imagem do BU,
ou por recuperação de mídia), substituindo o pacote publicado. O novo pacote recebeu status "Recebido" porque
a seção já estava totalizada.

**Incerto:**

- Se o BU deste pacote é idêntico, byte a byte, ao BU que foi totalizado (só sabemos que os números batem).
- O motivo do reenvio e por que o `imgbu` listado não foi publicado.
- Por que o status ficou "Recebida" e não "Totalizada", e se ele mudará.

**Perguntas ao TSE:**

1. Qual foi o hash (e o conjunto de arquivos) do pacote efetivamente usado na totalização dessas 2.677 seções,
   e em que data e hora foi recebido?
2. Por que os pacotes foram reenviados entre 05 e 07/10 nessas zonas, e por qual meio (transmissão, mídia recuperada)?
3. O status "Recebida" com hash "Recebido" indica pacote não usado na totalização? Haverá atualização para "Totalizada"?
4. Por que o `imgbu.dat` listado no `aux.json` retorna HTTP 404? Ele será publicado?
5. O que significam os campos `f` ("o" x "O") e `idg` (ausente nas "Recebida") do `aux.json`?
6. O histórico de versões de cada seção (todos os hashes recebidos) pode ser publicado?

## Como reproduzir

Ambiente: `.venv` do projeto (duckdb) para as consultas; `python3` (urllib) para a rede.

### Consultas locais

```python
import duckdb
c = duckdb.connect()
c.sql("create view s as select * from read_parquet('data/parquet/2026/secoes_2026.parquet')")
c.sql("create view ru as select * from read_parquet('data/parquet/2026/resultado_uf.parquet')")
c.sql("create view m as select * from read_parquet('data/parquet/2026/resultado_municipio.parquet')")

# distribuição de status
c.sql("select st_secao, st_hash, status, origem_bu, count(*) n from s group by all order by n desc")
c.sql("select dt_recebimento, st_secao, count(*) from s where status='ok' group by all order by 1,2")

# recontagem por UF sem as 'Recebida'
c.sql("""with a as (select uf,
          sum(comparecimento) filter (where st_secao='Totalizada') comp_sem_rec,
          sum(comparecimento) comp_todas,
          count(*) filter (where status='ok' and st_secao='Totalizada') sec_sem_rec,
          count(*) filter (where status='ok') sec_todas
        from s group by 1)
      select a.*, ru.comparecimento oficial, ru.secoes_instaladas,
             comp_todas - oficial dif_todas, comp_sem_rec - oficial dif_sem_rec
      from a join ru using (uf) where sec_todas <> sec_sem_rec order by 1""")

# municípios com 'Recebida': com todas x sem
c.sql("""with mu as (select distinct uf, cd_mun from s where st_secao='Recebida'),
      a as (select s.uf, s.cd_mun, sum(comparecimento) comp,
                   sum(comparecimento) filter (where st_secao='Totalizada') comp_sem,
                   sum(votos_brancos) vb, sum(votos_nulos) vn, count(*) filter (where status='ok') n
            from s join mu using (uf, cd_mun) group by all)
      select count(*) municipios,
             count(*) filter (where a.comp=m.comparecimento and a.vb=m.votos_brancos
                              and a.vn=m.votos_nulos and a.n=m.secoes_instaladas) batem_com_todas,
             count(*) filter (where a.comp_sem=m.comparecimento) batem_sem_recebidas
      from a join m using (uf, cd_mun)""")

# votos por candidato nos municípios com 'Recebida' (colunas v_<numero> de resultado_municipio)
cols = [r[0] for r in c.sql("describe m").fetchall() if r[0].startswith('v_')]
of = " union all ".join(f"select uf, cd_mun, {k[2:]} numero, {k} vap from m" for k in cols)
c.sql(f"""with mu as (select distinct uf, cd_mun from s where st_secao='Recebida'),
       bu as (select uf, cd_mun, numero, sum(votos) votos
              from read_parquet('data/parquet/2026/votos_presidente_2026.parquet')
              join mu using (uf, cd_mun) where tipo_voto='nominal' group by all),
       of as ({of})
       select count(*) linhas, count(*) filter (where coalesce(bu.votos,0)=of.vap) iguais
       from of join mu using (uf, cd_mun) left join bu using (uf, cd_mun, numero)""")

# caracterização
c.sql("select uf, count(*), min(dt_recebimento||' '||hr_recebimento), max(dt_recebimento||' '||hr_recebimento), sum(comparecimento) from s where st_secao='Recebida' group by 1 order by 2 desc")
c.sql("select modelo_urna, count(*) from s where st_secao='Recebida' group by 1 order by 2 desc")
c.sql("select tipo_urna, origem_bu, fase, count(*) from s where st_secao='Recebida' group by all")
c.sql("select uf, nm_mun, cd_mun, count(*) n from s where st_secao='Recebida' group by all order by n desc limit 20")
c.sql("""select uf, nm_mun, zona, count(*) total, count(*) filter (where st_secao='Recebida') rec
      from s where status='ok' group by all having rec > 0 order by uf, rec desc""")

# CSV entregue
c.sql("""copy (select uf, cd_mun, nm_mun, zona, secao, st_secao, st_hash, dt_recebimento, hr_recebimento,
                origem_bu, modelo_urna, tipo_urna, data_hora_emissao, hora_encerramento, comparecimento, n_hashes
         from s where st_secao='Recebida' order by uf, cd_mun, zona, secao)
      to 'data/parquet/2026/secoes_recebidas_2026.csv' (header)""")
```

### Consultas ao TSE (máximo 4 em paralelo)

```python
import json, urllib.request
from concurrent.futures import ThreadPoolExecutor

B = "https://resultados.tse.jus.br/oficial/ele2026"
UA = {"User-Agent": "Mozilla/5.0"}

def get(url, head=False):
    req = urllib.request.Request(url, headers=UA, method="HEAD" if head else "GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, dict(r.headers), (b"" if head else r.read())
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), b""

# resultado oficial (abr = 'br', 'pa', 'pa04278', ...)
def resultado(abr):
    st, h, b = get(f"{B}/6257/dados/{abr[:2]}/{abr}-c0001-e006257-u.json")
    d = json.loads(b)
    return abr, h.get("Last-Modified"), d["dg"], d["hg"], d["dt"], d["ht"], d["s"]["st"], d["s"]["ts"], d["e"]["c"]

# aux.json e HEAD de cada arquivo listado
def secao(uf, mun, zona, sec):
    base = f"{B}/arquivo-urna/3220/dados/{uf}/{mun}/{zona}/{sec}"
    st, h, b = get(f"{base}/p003220-{uf}-m{mun}-z{zona}-s{sec}-aux.json")
    aux = json.loads(b)
    arqs = [(a["tp"], get(f"{base}/{hh['hash']}/{a['nm']}", head=True)[0])
            for hh in aux["hashes"] for a in hh["arq"]]
    return aux.get("st"), aux.get("f"), "idg" in aux, len(aux["hashes"]), arqs

with ThreadPoolExecutor(4) as ex:
    print(list(ex.map(resultado, ["br", "pa", "pr", "ma", "ba", "ba35610"])))
    print(list(ex.map(lambda t: secao(*t), [("sp", "71676", "0116", "0107"), ("ma", "09210", "0001", "0087")])))
```

A amostra usada foi: `row_number() over (partition by uf order by hash(cd_mun||zona||secao)) <= 10` entre as
"Recebida"; as duas primeiras "Totalizada" de cada zona de controle; todas as "Totalizada" com
`dt_recebimento > '05/10/2026' or (dt_recebimento = '05/10/2026' and hr_recebimento > '12:51:05')`; e
20 "Totalizada" de 04/10 ordenadas por `hash(secao||cd_mun||zona||'x')`.
