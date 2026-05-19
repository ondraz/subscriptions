#!/usr/bin/env bash
# Runs on the production server. Invoked via `make wipe-prod`.
# Destructive: removes all named volumes (postgres, redpanda, caddy certs,
# frontend assets, plus the observability stack: loki, tempo, prometheus,
# grafana, alloy) and brings the stack back up with empty state.
set -euxo pipefail

cd /opt/tidemill

COMPOSE_FILES=(
  -f deploy/compose/docker-compose.yml
  -f deploy/compose/docker-compose.observability.yml
)

docker compose "${COMPOSE_FILES[@]}" down -v --remove-orphans
docker compose "${COMPOSE_FILES[@]}" up -d
