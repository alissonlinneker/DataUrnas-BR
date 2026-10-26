#!/usr/bin/env bash
# Sobe (ou recria) o ClickHouse do projeto no servidor de processamento.
#
# Roda NO SERVIDOR, por exemplo a partir do Mac:
#   ssh <servidor> 'bash -s' < scripts/ch/subir_clickhouse.sh
#
# Idempotente: gera a senha só na primeira vez (guardada em $BASE/.senha, 600),
# reescreve a configuração e recria o contêiner mantendo os dados em $BASE/data.
# Só publica as portas em 127.0.0.1 do servidor (HTTP 18123, nativa 19000).
set -euo pipefail

IMAGEM="clickhouse/clickhouse-server:26.8.35.10"   # LTS 26.8
NOME="dataurnas-clickhouse"
BASE="${DATAURNAS_CH_BASE:-$HOME/dataurnas-ch}"
MEMORIA="${DATAURNAS_CH_MEMORIA:-64g}"

mkdir -p "$BASE"/{data,logs,config.d,users.d,ref}
# 711: o usuário do contêiner (uid 101) atravessa a pasta sem listar nada
chmod 711 "$BASE"

if [ ! -s "$BASE/.senha" ]; then
  (umask 077; head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32 > "$BASE/.senha")
fi
chmod 600 "$BASE/.senha"
HASH=$(tr -d '\n' < "$BASE/.senha" | sha256sum | cut -d' ' -f1)

cat > "$BASE/config.d/dataurnas.xml" <<'XML'
<clickhouse>
    <listen_host>0.0.0.0</listen_host>
    <!-- 60 GB para o servidor dentro do limite de 64 GB do contêiner -->
    <max_server_memory_usage>64424509440</max_server_memory_usage>
    <logger>
        <level>information</level>
        <size>200M</size>
        <count>5</count>
    </logger>
    <!-- logs de sistema com retenção curta para poupar disco -->
    <query_log replace="1">
        <database>system</database>
        <table>query_log</table>
        <engine>ENGINE = MergeTree PARTITION BY event_date ORDER BY event_time TTL event_date + INTERVAL 7 DAY</engine>
        <flush_interval_milliseconds>7500</flush_interval_milliseconds>
    </query_log>
    <trace_log remove="1"/>
    <metric_log remove="1"/>
    <asynchronous_metric_log remove="1"/>
    <text_log remove="1"/>
    <latency_log remove="1"/>
</clickhouse>
XML

cat > "$BASE/users.d/dataurnas.xml" <<XML
<clickhouse>
    <users>
        <default remove="remove"/>
        <dataurnas>
            <password_sha256_hex>${HASH}</password_sha256_hex>
            <networks><ip>::/0</ip></networks>
            <profile>default</profile>
            <quota>default</quota>
            <access_management>1</access_management>
        </dataurnas>
    </users>
    <profiles>
        <default>
            <max_memory_usage>34359738368</max_memory_usage>
            <max_threads>48</max_threads>
        </default>
    </profiles>
</clickhouse>
XML

chmod 644 "$BASE/config.d/dataurnas.xml" "$BASE/users.d/dataurnas.xml"
chmod 755 "$BASE/config.d" "$BASE/users.d" "$BASE/ref"

docker pull -q "$IMAGEM" >/dev/null
if docker ps -a --format '{{.Names}}' | grep -qx "$NOME"; then
  docker rm -f "$NOME" >/dev/null
fi
docker run -d --name "$NOME" --restart unless-stopped \
  --memory "$MEMORIA" --ulimit nofile=262144:262144 \
  -p 127.0.0.1:18123:8123 -p 127.0.0.1:19000:9000 \
  -v "$BASE/data:/var/lib/clickhouse" \
  -v "$BASE/logs:/var/log/clickhouse-server" \
  -v "$BASE/config.d/dataurnas.xml:/etc/clickhouse-server/config.d/dataurnas.xml:ro" \
  -v "$BASE/users.d/dataurnas.xml:/etc/clickhouse-server/users.d/dataurnas.xml:ro" \
  -v "$BASE/ref:/var/lib/clickhouse/user_files/ref:ro" \
  "$IMAGEM" >/dev/null

for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:18123/ping >/dev/null 2>&1; then
    curl -fsS -u "dataurnas:$(cat "$BASE/.senha")" \
      'http://127.0.0.1:18123/?query=SELECT%20version()'
    exit 0
  fi
  sleep 1
done
echo "ClickHouse não respondeu em 60 s" >&2
docker logs --tail 50 "$NOME" >&2
exit 1
