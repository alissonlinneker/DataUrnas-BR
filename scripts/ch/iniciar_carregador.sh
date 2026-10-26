#!/usr/bin/env bash
# Inicia o carregador em laço (a cada 5 min) no servidor, desligado do terminal.
# Idempotente: se já houver um carregador vivo, só informa o PID.
#   ~/dataurnas-ch/app/scripts/ch/iniciar_carregador.sh
# Parar: kill "$(cat ~/dataurnas-ch/carregador.pid)"
set -euo pipefail
BASE="${DATAURNAS_CH_BASE:-$HOME/dataurnas-ch}"
PIDF="$BASE/carregador.pid"
if [ -s "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
  echo "carregador já rodando: PID $(cat "$PIDF")"
  exit 0
fi
cd "$BASE"
setsid nohup "$BASE/venv/bin/python" "$BASE/app/scripts/ch/carregar.py" \
  --loop "${INTERVALO:-300}" --workers "${WORKERS:-48}" \
  >> "$BASE/carregador.log" 2>&1 < /dev/null &
echo $! > "$PIDF"
echo "carregador iniciado: PID $(cat "$PIDF")"
