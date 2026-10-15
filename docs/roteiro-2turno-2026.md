# Roteiro de coleta do 2º turno de 2026 (25/10/2026)

Este roteiro repete, para o 2º turno, a coleta feita no 1º turno. Os mesmos
scripts de `scripts/ele2026/` aceitam `--turno 2`, que troca de uma vez:

| Parâmetro | 1º turno (padrão) | 2º turno (`--turno 2`) |
|---|---|---|
| Pleito (arquivos de urna) | 3220 | 3221 |
| Eleição (Presidente) | 6257 | 6258 |
| Data da votação | 04/10/2026 | 25/10/2026 |
| Diretório base | `data/parquet/2026/` | `data/parquet/2026/t2/` |
| Log da integridade | `data/ele2026_integridade.log` | `data/ele2026_t2_integridade.log` |
| Prefixo do `secao_id` | `1T/` | `2T/` |

Os parâmetros ficam num lugar só: `parametros_turno()` em
`src/dataurnas/downloader/ele2026.py` (valores em `ELE2026`, `src/dataurnas/config.py`).
Os nomes dos arquivos de urna seguem o pleito (`o03221ac...-bu.dat` no lugar de
`o03220ac...-bu.dat`); nenhum script monta esses nomes, todos vêm do `aux.json`.

O pleito 3221 também lista suplementares e consultas, além da eleição 6258
(Federal 2º turno) e da 6260 (Estadual 2º turno). O `cs.json` de cada UF traz
só as seções com 2º turno ou suplementar, e o BU é sempre filtrado pela eleição
6258 e pelo cargo de Presidente.

## Interpretadores

- Coleta (rede, processos longos): um Python 3.11 ou mais recente com as dependências do projeto.
- Testes e lint: `.venv/bin/python` do checkout.

Todos os comandos abaixo partem da raiz do repositório.

```sh
PY=/opt/homebrew/bin/python3.14
```

## 0. Antes de começar: testes

```sh
.venv/bin/python -m pytest tests/ele2026 -q
.venv/bin/python -m ruff check scripts/ele2026 src tests/ele2026
```

## 1. Conferir a configuração no TSE

Confirmar que o pleito 3221 existe, tem data 25/10/2026 e lista a eleição 6258:

```sh
curl -s https://resultados.tse.jus.br/oficial/comum/config/ele-c.json \
  -o /tmp/ele-c.json
python3 - <<'PY'
import json

def busca(o, caminho=""):
    if isinstance(o, dict):
        if any(str(v) in ("3221", "6258") for v in o.values()):
            print(caminho, {k: v for k, v in o.items() if not isinstance(v, (list, dict))})
        for k, v in o.items():
            busca(v, f"{caminho}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            busca(v, f"{caminho}[{i}]")

busca(json.load(open("/tmp/ele-c.json", encoding="utf-8")))
PY
```

O pleito 3221 deve ter data 25/10/2026 e conter a eleição 6258
("Eleição Ordinária Federal - 2026 2º Turno", t=2). Se os códigos forem outros,
corrigir `pleito_2t`, `eleicao_2t` e `data_2t` em `ELE2026` antes de seguir.

Confirmar que a lista de seções de uma UF já foi publicada (precisa ser HTTP 200):

```sh
curl -s -o /dev/null -w '%{http_code}\n' \
  https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/config/ac/ac-p003221-cs.json
curl -s -o /dev/null -w '%{http_code}\n' \
  https://resultados.tse.jus.br/oficial/ele2026/6258/dados/br/br-c0001-e006258-u.json
```

Enquanto responder 403 ou 404, os dados ainda não estão publicados: aguardar.

## 2. Resultado agregado (Brasil, UF, município)

```sh
$PY scripts/ele2026/fetch_resultados.py --turno 2
```

Grava em `data/parquet/2026/t2/`: `candidatos.parquet`, `resultado_uf.parquet`,
`resultado_municipio.parquet` e `resumo_br.json` (com `"pleito": "3221"`,
`"eleicao": "6258"`, `"turno": 2`). Código de saída 2 indica municípios sem
resultado: rodar de novo mais tarde.

## 3. BU por seção

Teste com duas UFs pequenas:

```sh
$PY scripts/ele2026/fetch_secoes.py --turno 2 --ufs ac,rr
```

Coleta nacional (27 UFs + zz), em segundo plano e com prioridade baixa:

```sh
nohup nice -n 20 $PY scripts/ele2026/fetch_secoes.py --turno 2 \
  > data/ele2026_t2_secoes.log 2>&1 &
```

Saída em `data/parquet/2026/t2/`: partes em `secoes_parts/`, checkpoint em
`secoes_checkpoint.txt` e, ao final, `secoes_2026.parquet` e
`votos_presidente_2026.parquet`. Se houver erros (`secoes_erros.txt`), rodar o
mesmo comando de novo: o checkpoint pula o que já foi feito. Para só consolidar:

```sh
$PY scripts/ele2026/fetch_secoes.py --turno 2 --so-consolidar
```

Opções úteis (iguais às do 1º turno): `--concorrencia 96`, `--taxa 50`,
`--taxa-max 90`, `--conexoes 4`, `--no-modelo` (não baixa o `.vsc`).

## 4. Reconciliação BU x resultado oficial

```sh
$PY scripts/ele2026/reconcile.py --turno 2 --ufs ac,rr
$PY scripts/ele2026/reconcile.py --turno 2 --so-divergencias
```

Sai com código 1 se alguma UF divergir.

## 5. Integridade dos arquivos e auditoria BU/log

Teste com duas UFs:

```sh
$PY scripts/ele2026/fetch_integridade.py --turno 2 --ufs ac,rr
```

Coleta nacional:

```sh
nohup nice -n 20 $PY scripts/ele2026/fetch_integridade.py --turno 2 \
  > /dev/null 2>&1 &
tail -f data/ele2026_t2_integridade.log
```

Com `--turno 2` os padrões são:

- saída: `data/parquet/2026/t2/integridade/` (`secoes.parquet`,
  `arquivos_<uf>.parquet`, `resumo.json` com `"pleito": "3221"`, `divergencias.jsonl`);
- auditoria BU/log: `data/parquet/2026/t2/auditoria/` (`issues_2026.parquet` e
  `secoes_log_2026.parquet`, com `secao_id` iniciando em `2T/`; o log é
  filtrado pela data 25/10/2026, porque o log do 2º turno acumula o 1º);
- votos conferidos contra `data/parquet/2026/t2/votos_presidente_2026.parquet`
  (rodar o passo 3 antes; com `--no-conferir-votos` a conferência é desligada);
- log: `data/ele2026_t2_integridade.log`.

Vários processos podem rodar juntos com UFs disjuntas (`--ufs`). Para refazer
erros, rodar de novo; para só consolidar:

```sh
$PY scripts/ele2026/fetch_integridade.py --turno 2 --so-consolidar
```

## 6. Ocorrências de publicação (arquivos listados e não publicados)

```sh
$PY scripts/ele2026/registrar_ocorrencias_publicacao.py --turno 2
$PY scripts/ele2026/registrar_ocorrencias_publicacao.py --turno 2 --acompanhar 300
```

Lê `data/ele2026_t2_integridade*.log` e grava
`data/parquet/2026/t2/integridade/ocorrencias_publicacao.jsonl`.

## 7. Catálogo de hashes para publicação

Com a coleta parada:

```sh
$PY scripts/ele2026/publicar_catalogo.py --turno 2 --versao vX.Y.Z
```

Copia os catálogos para `dist/catalogo-integridade-2026-t2/`, grava o
`SHA256SUMS` e o manifesto em `data/parquet/2026/t2/integridade/`. Os anexos
têm os mesmos nomes do 1º turno (`arquivos_<uf>.parquet`), então devem ir numa
versão própria do GitHub.

## 8. Painel

Os carregadores do painel de 2026 (`src/dataurnas/dashboard/data2026.py` e
`pages/eleicoes_2026.py`) ainda leem só o 1º turno em `data/parquet/2026/`.
Os dados do 2º turno ficam isolados em `data/parquet/2026/t2/` com os mesmos
nomes e esquemas, então uma página do 2º turno pode reutilizar os mesmos
carregadores apontando para esse diretório. Isso fica para depois da coleta.

## Pendências conhecidas

- `scripts/ele2026/analisar_certificados.py` continua só no 1º turno (usa
  `E.PLEITO` e a data 04/10/2026 para a validade dos certificados).
- `_PLEITO_DATAS` em `src/dataurnas/analyzer/batch.py` não lista o pleito 3221;
  a coleta não depende disso, porque passa a data do turno explicitamente.
