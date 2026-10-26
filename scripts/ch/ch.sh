#!/usr/bin/env bash
# clickhouse-client do contêiner com o usuário do projeto. Roda no servidor.
#   ch.sh "SELECT count() FROM dataurnas.bu_secao"
#   ch.sh < consulta.sql          (várias consultas, separadas por ;)
set -euo pipefail
SENHA=$(cat "${DATAURNAS_CH_BASE:-$HOME/dataurnas-ch}/.senha")
if [ $# -gt 0 ]; then
  exec docker exec -i dataurnas-clickhouse clickhouse-client --user dataurnas \
    --password "$SENHA" --database dataurnas -q "$*"
fi
exec docker exec -i dataurnas-clickhouse clickhouse-client --user dataurnas \
  --password "$SENHA" --database dataurnas --multiquery
