# Dados abertos do TSE confrontados com os BUs assinados (2026)

Eleição presidencial de 2026, 1º turno em 04/10 e 2º turno em 25/10 (13 x 22).
Pergunta: os produtos do portal de dados abertos do TSE (votação por seção,
detalhe da apuração por seção, BU na web e correspondências urna x seção) batem
entre si e com os boletins de urna (BU) binários assinados, decodificados pelo
projeto?

Script: `scripts/ele2026/confronto_dados_abertos.py`. Dados derivados em
`data/parquet/2026/t2/dados_abertos/` (fora do git). Arquivos brutos no servidor
de processamento em `~/dataurnas-t2/dados_abertos/brutos/`.

## 1. Divergências encontradas

Nenhuma divergência de voto. As divergências abaixo são de cadastro de urna,
de metadado do produto ou de marca de controle, em ordem de relevância.

| # | Achado | Seções | Produto | Natureza |
|---|---|---:|---|---|
| 1 | Correspondência esperada do 2º turno, 2ª geração (25/10, 13h45): `ST_CORRESP_ALTERADA = N` em todas as 499.178 linhas, mas 372 seções mudaram em relação à 1ª geração (24/10): 350 com urna e carga novas, 10 só com carga nova e 12 seções que nem existiam na 1ª geração (deveriam vir com `*`). No 1º turno a marca é coerente (165 `S`, 3 `*`, 499.009 `N` sem mudança) | 372 | CESP 2º turno | Marca de controle errada |
| 2 | 2º turno: BU de urna de seção comum (`tipo_urna = secao`) com urna diferente da esperada na correspondência de 25/10. 18 usaram urna de contingência da própria zona, 3 urna de contingência de outra zona da UF e 14 uma urna que não está em nenhuma correspondência publicada do 2º turno (tabela 4.3). A assinatura `.vsc` de todas confere com a urna do BU | 35 | CESP 2º turno x BU | Troca de urna sem marca de reserva no BU e sem registro na correspondência esperada |
| 3 | 2º turno: urna de reserva (`reservaSecao`) que não está no conjunto de contingência da zona: 98 vieram de outra zona da mesma UF e 10 não aparecem em nenhuma correspondência do 2º turno (tabela 4.4) | 108 | CESP 2º turno x BU | Reserva fora do conjunto esperado |
| 4 | 2º turno: urna igual à esperada, mas código de carga do BU diferente do código esperado. Em 5 seções do PA a correspondência esperada manteve a carga do 1º turno e o BU tem carga nova (recarga entre os turnos não refletida). Em `MG/43710/0313/0046` a esperada trocou de urna e de carga duas vezes em 24/10 e o BU tem uma terceira carga | 6 | CESP 2º turno x BU | Recarga não registrada |
| 5 | 1º turno: correspondência efetivada com urna esperada diferente da efetivada e `TP_DIVERGENCIA` vazio (o leiaute manda marcar `D` ou `C`): 13 urnas de seção comum e 4 de reserva. Em 12 seções (9 comuns e 3 de reserva) a urna que votou não está na geração final da correspondência esperada do 1º turno; 10 reaparecem como esperada da mesma seção no 2º turno. Em `MA/09210/0001/0124` e `0125` a geração de 04/10 trocou a urna (carga nova em 03/10, 15h08 e 15h19), mas votaram as urnas originais (carga de 28/09), nos dois turnos, e a esperada do 2º turno manteve as urnas que não votaram | 17 | CEFT 1º turno | Marca de divergência ausente |
| 6 | Correspondência esperada do 1º turno, 2ª geração (04/10): `MA/07030/0052/0085` e `MT/98817/0033/0040` estavam na 1ª geração (03/10) e sumiram da 2ª. Em 4 seções a urna esperada da CESP difere da urna esperada da CEFT (`PA/04030/0094/0117`, `MG/48852/0190/0107` e as duas acima) | 2 + 4 | CESP x CEFT 1º turno | Omissão e incoerência entre produtos |
| 7 | `detalhe_votacao_secao`: número do local de votação diferente do BU em 7.033 seções no 1º turno e 7.344 no 2º. `votacao_secao`, BU na web e correspondência efetivada batem com o BU em todas essas seções. No detalhe, 431 seções trocam de local entre os turnos; no BU, 2 | 7.033 / 7.344 | detalhe | Metadado do produto |
| 8 | `detalhe_votacao_secao`: modelo da urna diferente do modelo gravado no `.vsc` em 6 seções do 1º turno, todas com BU gerado pelo Recuperador de Dados (RED) | 6 | detalhe | Metadado do produto |
| 9 | `votacao_secao_2026_BR.zip` e `detalhe_votacao_secao_2026.zip` não têm `.sha512` publicado (HTTP 404 em `<arquivo>.zip.sha512`); os outros 168 arquivos têm, e todos conferem | 2 arquivos | CDN | Publicação |
| 10 | Correspondência efetivada e BU na web do 2º turno ainda não publicados (CKAN consultado em 27/10/2026) | | CKAN | Publicação pendente |

Diferenças explicadas, que não são divergência:

- O BU do Sistema de Apuração (`busa`, 29 seções do exterior e 2 de MG no 1º
  turno) registra local de votação 1; os produtos trazem o local real (30 seções
  no `votacao_secao` do 1º turno, 27 no 2º, 30 no BU na web, 31 na correspondência
  efetivada).
- Sem linha no produto quando a seção não tem voto: `ZZ/29564/0001/0091`
  (1º e 2º turnos) e `ZZ/30686/0001/0443` (2º turno), com comparecimento zero, não
  aparecem no `votacao_secao` nem no BU na web.
- O detalhe lista as 41 seções não instaladas (origem "Totalização", instalada
  "Não"); por isso tem 1.351 seções no exterior contra 1.310 BUs.
- A correspondência esperada não lista as seções do exterior apuradas por urna de
  contingência (28 no 1º turno, 29 no 2º).
- Data e hora de recebimento do BU (ver 3.4): fontes de relógio diferentes.

## 2. Votos, aptos e comparecimento: nenhuma divergência

Seção a seção, comparando valor por valor (votável sem voto não aparece no
produto e conta como zero):

| Confronto | Turno | Seções comparadas | Campos | Divergências |
|---|---|---:|---|---:|
| `votacao_secao` x BU | 1º | 499.206 | votos no 13, no 22, nos demais candidatos, brancos, nulos, total | 0 |
| `votacao_secao` x BU | 2º | 499.205 | votos no 13, no 22, brancos, nulos, total | 0 |
| `detalhe_votacao_secao` x BU | 1º | 499.207 | aptos, comparecimento, abstenção, nominais, brancos, nulos, legenda, anulados e apurados em separado | 0 |
| `detalhe_votacao_secao` x BU | 2º | 499.207 | idem | 0 |
| detalhe x `votacao_secao` | 1º e 2º | 499.206 / 499.205 | nominais, brancos, nulos | 0 |
| BU na web x BU | 1º | 499.206 | aptos, comparecimento, abstenção, votos por candidato, brancos, nulos, total, número da urna, código de carga, abertura, encerramento, emissão do BU | 0 |
| correspondência efetivada x BU | 1º | 499.207 | número da urna, código de carga | 0 |

Totais nacionais (Presidente), iguais nos quatro produtos:

| Turno | 13 | 22 | Demais | Brancos | Nulos | Aptos (BU) | Comparecimento |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1º | 53.879.538 | 56.104.503 | 9.321.993 | 2.300.798 | 3.669.003 | 158.745.079 | 125.275.835 |
| 2º | 64.256.232 | 59.826.041 | 0 | 1.430.496 | 2.723.305 | 158.745.079 | 128.236.074 |

Margem do 2º turno: 4.430.191 votos. Os aptos do detalhe somam 158.745.502; a
diferença de 423 são os aptos das 41 seções não instaladas.

## 3. Método

### 3.1 Arquivos

Descobertos pela API CKAN (`package_show`) dos pacotes `resultados-2026`,
`resultados-2026-boletim-de-urna` e `resultados-2026-correspondencias-esperadas-e-efetivadas-{1,2}-turno`:

| Produto | Arquivos | Conteúdo usado |
|---|---|---|
| `votacao_secao_2026_BR.zip` (241.891.087 bytes, gerado em 26/10) | 1 | votos de Presidente por seção e votável, os dois turnos |
| `detalhe_votacao_secao_2026.zip` (234.357.769 bytes) | 1 | arquivo `_BR` (Presidente): aptos, comparecimento, abstenção, nominais, brancos, nulos, legenda, local, recebimento, origem do voto, modelo |
| `bweb_1t_<UF>_051020261403.zip` | 28 | BU na web do 1º turno, só a pergunta Presidente |
| `CEFT_1t_<UF>_051020261049.zip` | 28 | correspondência efetivada do 1º turno (esperada e efetivada lado a lado) |
| `CESP_1t_<UF>_*.zip` | 56 | correspondência esperada do 1º turno, gerações de 03/10 15h34 e 04/10 12h59 |
| `CESP_2t_<UF>_*.zip` | 56 | correspondência esperada do 2º turno, gerações de 24/10 12h31 e 25/10 13h45 |

Total: 170 arquivos, 5.727.665.371 bytes. Baixados num único processo, no máximo
3 requisições por segundo, a partir do Mac; o restante foi completado no servidor
de processamento a 2 requisições por segundo. O SHA-512 de cada arquivo foi
calculado nas duas máquinas (170 de 170 iguais) e conferido com o `.sha512`
publicado ao lado (168 conferem; os 2 sem `.sha512` estão na tabela 1). Registro
em `manifesto.jsonl` e `ckan.json`.

A correspondência esperada traz dois arquivos por UF: `csec` (urna esperada de
cada seção) e `ccont` (urnas de contingência esperadas de cada zona).

### 3.2 Referência (BU)

ClickHouse do servidor (`docs/banco-clickhouse.md`):

- 2º turno: `v_bu_ultima` (última versão do BU de cada seção) com os votos de
  `bu_votos` e o modelo do `.vsc` em `versoes_arquivo`; 499.207 seções.
- 1º turno: `ref_secoes_2026_t1` e `ref_votos_2026_t1`; 517.179 linhas, das
  quais 499.207 com BU (`status = ok`), 17.931 agregadas e 41 não instaladas.

Chave: UF, município (5 dígitos), zona e seção (4 dígitos). O código de carga é
comparado com 24 dígitos: a correspondência efetivada grava o código como número
e perde o zero à esquerda em 50.016 seções.

### 3.3 Etapas

```sh
python3 -I scripts/ele2026/confronto_dados_abertos.py baixar --brutos <pasta>
# no servidor (temporários em /dev/shm):
uv run --no-project --with duckdb python -I confronto_dados_abertos.py extrair \
    --brutos ~/dataurnas-t2/dados_abertos/brutos --dir /dev/shm/dados_abertos
python3 -I confronto_dados_abertos.py bu --dir /dev/shm/dados_abertos
uv run --no-project --with duckdb python -I confronto_dados_abertos.py confrontar \
    --dir /dev/shm/dados_abertos --saida /dev/shm/dados_abertos/saida \
    --brutos ~/dataurnas-t2/dados_abertos/brutos
```

`extrair` lê os CSV (Latin-1) com DuckDB e grava Parquet normalizados; `bu`
exporta os BUs do ClickHouse; `confrontar` cruza tudo. Tempo total no servidor:
cerca de 4 minutos.

### 3.4 Recebimento do BU (informativo)

A data e hora de recebimento do detalhe e do BU na web vem do sistema do TSE;
a do BU de referência vem do `aux.json` coletado (2º turno) ou da coleta do 1º
turno. Iguais ao segundo em 432.671 seções do 1º turno (86,7%; 486.873 com até
5 s) e em 246.395 do 2º (49,4%; mediana da diferença de 1 s, máximo de 54.812 s).
Não é tratado como divergência.

O campo `QT_ELEI_BIOM_SEM_HABILITACAO` do BU na web não corresponde a nenhum
campo de biometria do BU decodificado (igual ao comparecimento sem biometria em
12.274 de 499.206 seções; soma de 8.342.249 contra 6.940.334) e ficou fora do
confronto.

## 4. Correspondência urna x seção

### 4.1 1º turno: efetivada x BU

A urna e o código de carga da correspondência efetivada são iguais aos do BU nas
499.207 seções. A comparação da urna do BU com a urna esperada:

| Tipo de urna no BU | `TP_DIVERGENCIA` | Situação | Seções |
|---|---|---|---:|
| secao | vazio | igual à esperada | 496.130 (49 com BU recuperado pelo RED) |
| secao | vazio | urna de contingência da zona | 4 |
| secao | vazio | urna fora de qualquer correspondência do 1º turno | 9 |
| reservaSecao | C | urna de contingência da zona | 2.966 |
| reservaSecao | C | urna de contingência de outra zona da UF | 46 |
| reservaSecao | vazio | igual à esperada | 17 |
| reservaSecao | vazio | urna de contingência da zona | 1 |
| reservaSecao | vazio | urna fora de qualquer correspondência do 1º turno | 3 |
| contingencia (exterior) | C | urna de contingência da zona / sem esperada | 3 / 28 |

As 13 seções comuns e as 4 de reserva com `TP_DIVERGENCIA` vazio e urna diferente
da esperada são o achado 5. As 17 de reserva com urna igual à esperada têm dois
códigos de carga no BU (a urna foi carregada de novo como reserva) e já constavam
como esperadas; não é divergência.

### 4.2 2º turno: esperada (25/10) x BU

Não há correspondência efetivada do 2º turno publicada; a comparação é com a
esperada da 2ª geração e com o conjunto de contingência das duas gerações.

| Tipo de urna no BU | Situação | Seções |
|---|---|---:|
| secao | igual à esperada | 493.429 (6 com carga diferente, achado 4) |
| secao | urna de contingência da zona | 18 |
| secao | urna de contingência de outra zona da UF | 3 |
| secao | urna fora de qualquer correspondência do 2º turno | 14 |
| reservaSecao | igual à esperada | 3.063 |
| reservaSecao | urna de contingência da zona | 2.541 |
| reservaSecao | urna de contingência de outra zona da UF | 98 |
| reservaSecao | urna fora de qualquer correspondência do 2º turno | 10 |
| reservaEncerrandoSecao | urna de contingência da zona | 2 |
| contingencia (exterior) | sem esperada | 29 |

As 3.063 reservas iguais à esperada são, na maioria, seções que já tinham trocado
de urna no 1º turno e mantiveram a urna de reserva (o BU volta a registrar
`reservaSecao` com histórico de cargas). A assinatura do `.vsc` foi feita pela
urna do BU em todas as seções fora da coluna "igual à esperada"; nas 496.492
iguais à esperada, a exceção são as 3 seções de certificado diferente (4.5).

### 4.3 As 35 seções comuns com urna diferente da esperada (2º turno)

| Seção | Urna 1º turno | Esperada 24/10 | Esperada 25/10 | Urna no BU | Onde a urna do BU aparece |
|---|---:|---:|---:|---:|---|
| `AC/01120/0008/0072` | 2046562 | 2046562 | 2046562 | 2045984 | contingência da zona |
| `AP/06017/0001/0018` | 2016181 | 2016181 | 2016181 | 2016368 | contingência da zona |
| `AP/06025/0012/0031` | 2469754 | 2469754 | 2469754 | 2341853 | contingência da zona |
| `AP/06033/0001/0059` | 2019743 | 2019743 | 2019743 | 2016483 | contingência da zona |
| `AP/06076/0005/0027` | 2242362 | 2242362 | 2242362 | 2031338 | contingência da zona |
| `AP/06076/0005/0064` | 2241170 | 2241170 | 2241170 | 2240534 | contingência da zona |
| `AP/06084/0011/0037` | 2032264 | 2032264 | 2032264 | 2242659 | contingência da zona |
| `AP/06114/0012/0051` | 2355396 | 2355396 | 2355396 | 2353998 | contingência da zona |
| `AP/06122/0007/0164` | 2019795 | 2019795 | 2019795 | 2019470 | contingência da zona |
| `AP/06130/0007/0019` | 2019951 | 2019951 | 2019951 | 2019172 | contingência da zona |
| `MA/07536/0026/0088` | 2309878 | 2309878 | 2309878 | 2287775 | contingência da zona |
| `PA/04278/0076/0475` | 2148669 | 2148669 | 2148669 | 2026654 | contingência da zona |
| `PA/04278/0098/0273` | 2169930 | 2169930 | 2169930 | 2157972 | contingência da zona |
| `PA/05355/0104/0279` | 2410645 | 2410645 | 2410645 | 2423409 | contingência da zona |
| `PA/05630/0008/0325` | 1824691 | 1824691 | 1824691 | 1656304 | contingência da zona |
| `PR/77399/0124/0085` | 1780809 | 1780809 | 1780809 | 1661979 | contingência da zona |
| `RO/00051/0030/0123` | 2293033 | 2293033 | 2293033 | 2273941 | contingência da zona |
| `SP/70378/0115/0155` | 2256625 | 2256625 | 2256625 | 2288835 | contingência da zona |
| `BA/38490/0008/0432` | 2414120 | 2414120 | 2414120 | 2208418 | contingência de outra zona da UF |
| `BA/38490/0008/0606` | 2391278 | 2391278 | 2391278 | 2424785 | contingência de outra zona da UF |
| `MT/91553/0038/0113` | 2023944 | 2023944 | 2023944 | 2256442 | contingência de outra zona da UF |
| `BA/33774/0071/0150` | 1780000 | 1780000 | 1780000 | 1843885 | nenhum produto |
| `BA/39144/0071/0170` | 1771106 | 1771106 | 1771106 | 1844077 | nenhum produto |
| `MG/41238/0331/0001` | 2465586 | 2465586 | 2465586 | 2441970 | nenhum produto |
| `SE/31690/0012/0087` | 2302312 | 2302312 | 2302312 | 2351482 | nenhum produto |
| `SE/31712/0013/0082` | 2175982 | 2175982 | 2175982 | 2048848 | nenhum produto |
| `SE/31755/0005/0143` | 2294017 | 2294017 | 2294017 | 2283497 | nenhum produto |
| `SE/32476/0023/0118` | 2354969 | 2354969 | 2354969 | 2286014 | nenhum produto |
| `SE/32514/0035/0057` | 2174458 | 2174458 | 2174458 | 2312114 | nenhum produto |
| `MT/90670/0039/0376` | 2447087 | 2447087 | 2447087 | 2473230 | esperada de `MT/90670/0001/1007` no 1º turno |
| `PA/04278/0030/0295` | 2155867 | 2155867 | 2155867 | 2148509 | contingência da zona no 1º turno |
| `BA/35653/0173/0002` | 1753213 | 1753213 | 1833178 | 1753213 | urna do 1º turno; a esperada mudou em 25/10 e não foi usada |
| `PA/05215/0033/0158` | 2318458 | 2318458 | 2469714 | 2318458 | urna do 1º turno; a esperada mudou em 25/10 e não foi usada |
| `MA/09210/0001/0124` | 1813889 | 1656375 | 1656375 | 1813889 | urna original (carga de 28/09), esperada só na 1ª geração do 1º turno; a de 04/10 trocou para 1656375 (carga de 03/10), que não votou em nenhum turno |
| `MA/09210/0001/0125` | 1813386 | 1651908 | 1651908 | 1813386 | idem (esperada 1651908, carga de 03/10) |

Em todas, o BU registra uma única carga e `tipo_urna = secao`: a urna nova foi
carregada como urna de seção, e não como reserva. Sem a correspondência
efetivada do 2º turno, não há como confirmar se o TSE registrou essas trocas.

### 4.4 As 10 reservas fora de qualquer correspondência do 2º turno

| Seção | Urna no BU | Onde a urna aparece |
|---|---:|---|
| `MG/41238/0331/0197` | 2474562 | nenhum produto |
| `PA/05355/0104/0093` | 2324636 | nenhum produto |
| `SE/31054/0002/0524` | 1791181 | nenhum produto |
| `SE/31054/0002/0060` | 1766766 | esperada de `SE/31054/0001/0317` no 1º turno |
| `SE/31054/0002/0087` | 1767744 | esperada de `SE/31054/0002/0524` no 1º turno |
| `SE/31054/0002/0345` | 1791305 | esperada de `SE/31054/0001/0265` no 1º turno |
| `SE/31054/0002/0535` | 1789920 | esperada de `SE/31054/0002/1045` no 1º turno |
| `SE/31054/0002/0551` | 1796060 | esperada de `SE/31054/0002/0630` no 1º turno |
| `SP/69213/0317/0270` | 2144351 | esperada de `SP/69213/0317/0369` no 1º turno |
| `SP/69213/0317/0294` | 2376839 | esperada de `SP/69213/0317/0370` no 1º turno |

Lista completa das 108 reservas fora da zona em
`urna_t2_reserva_fora_contingencia.parquet`.

### 4.5 As 3 seções com certificado diferente da carga

`docs/certificados-2turno-2026.md` registra 3 seções do 2º turno cujo `.vsc` foi
assinado por uma urna diferente da que consta no BU. Nas correspondências:

| Seção | Urna no BU (1º e 2º turnos) | Urna que assinou | Onde a urna que assinou aparece |
|---|---:|---:|---|
| `SP/64777/0393/0312` | 2396114 | 2399743 | contingência da zona 0393 de SP/64777, nas 4 gerações (1º e 2º turnos); nunca como urna esperada de seção nem em BU |
| `RJ/58696/0027/0139` | 2179194 | 2189420 | contingência da zona 0027 de RJ/58696, nas 4 gerações; nunca em seção nem em BU |
| `ES/57932/0009/0085` | 1841837 | 1758779 | contingência da zona 0009 do ES (cadastrada no município 56898), nas 4 gerações; no BU do 2º turno de `ES/57932/0009/0112` como `reservaEncerrandoSecao` |

Nas três, a esperada (1º e 2º turnos), a efetivada do 1º turno e o BU dos dois
turnos registram a mesma urna e a mesma carga, sem mudança entre gerações. A urna
que assinou é, nas três, uma urna de contingência esperada para a própria zona.
Isso reforça a leitura de troca de equipamento depois da carga (a urna de
contingência assinou o arquivo produzido com a mídia da urna original), mas a
confirmação depende da correspondência efetivada do 2º turno, ainda não publicada.

### 4.6 As 4.435 seções com urna diferente entre os turnos

| Situação no 2º turno | Seções |
|---|---:|
| Urna nova já era a esperada na correspondência do 2º turno (troca planejada) | 1.746 |
| Urna de contingência da zona, BU como reserva | 2.541 |
| Urna de contingência de outra zona da UF, BU como reserva | 98 |
| Urna fora de qualquer correspondência do 2º turno, BU como reserva | 10 |
| Seção comum sem explicação nas correspondências (tabela 4.3, menos as 4 que mantiveram a urna do 1º turno) | 31 |
| Exterior, contingência sem esperada | 9 |

Das 1.746 trocas planejadas, 1.577 votaram com BU de seção comum (1.531 eram
seção comum no 1º turno, 44 reserva e 2 contingência) e 169 com BU de reserva
(161 eram seção comum no 1º turno e 8 reserva).

## 5. Contagem de seções por UF e município

Todas as UFs têm o mesmo número de seções no BU, no `votacao_secao`, no detalhe,
no BU na web (1º turno), na correspondência efetivada (1º turno) e na
correspondência esperada, com estas exceções, todas explicadas na seção 1:

| Turno | UF | BU | `votacao_secao` | detalhe | BU na web | Efetivada | Esperada |
|---|---|---:|---:|---:|---:|---:|---:|
| 1º | MA | 18.093 | 18.093 | 18.093 | 18.093 | 18.093 | 18.092 |
| 1º | MT | 8.287 | 8.287 | 8.287 | 8.287 | 8.287 | 8.286 |
| 1º | ZZ | 1.310 | 1.309 | 1.351 | 1.309 | 1.310 | 1.282 |
| 2º | ZZ | 1.310 | 1.308 | 1.351 | | | 1.281 |

Por município, as 83 linhas com contagem diferente estão todas no exterior
(seções não instaladas no detalhe e seções sem voto). Tabelas em
`contagens_uf.csv` e `contagens_municipio_divergentes.csv`.

## 6. Arquivos de saída

Em `data/parquet/2026/t2/dados_abertos/`:

| Arquivo | Conteúdo |
|---|---|
| `resumo.json` | todas as contagens deste documento |
| `divergencias.parquet` | uma linha por seção, confronto e campo divergente (valor no produto e na referência) |
| `cobertura_divergente.parquet` | seções presentes num lado e ausentes no outro |
| `urnas_secao.parquet` | por seção: urna e carga no BU dos dois turnos, esperada, efetivada, gerações, classificação |
| `urna_t2_secao_comum_sem_explicacao.parquet` | as 35 seções da tabela 4.3 |
| `urna_t2_reserva_fora_contingencia.parquet` | as 108 reservas fora do conjunto da zona |
| `urna_t2_carga_diverge.parquet` | as 6 seções do achado 4 |
| `urna_t1_divergente.parquet` | as seções do 1º turno com divergência ou marca ausente |
| `contagens_uf.csv`, `contagens_municipio_divergentes.csv` | contagens por produto |
| `manifesto.jsonl`, `ckan.json` | arquivos baixados, tamanhos, SHA-512 e metadados do CKAN |
| `normalizados/` | Parquet normalizados de cada produto e dos BUs |

## 7. Limitações

- A correspondência efetivada e o BU na web do 2º turno não estavam publicados em
  27/10/2026. O confronto do 2º turno usa a correspondência esperada, que é
  anterior à votação (25/10, 13h45, com a votação em curso).
- `votacao_secao` e `detalhe_votacao_secao` não têm `.sha512` publicado: a
  integridade desses dois arquivos foi conferida só entre as duas cópias baixadas
  (Mac e servidor), não contra um hash do TSE.
- O conjunto de contingência (`ccont`) é por zona; a classificação "contingência
  de outra zona da UF" não distingue empréstimo entre zonas de erro de cadastro.
- O código de carga é comparado só pelos 24 dígitos; a data de carga gravada no
  BU não foi exportada e não entra no confronto.
