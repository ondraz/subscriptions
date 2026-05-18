#!/usr/bin/env bash
# Runs on the production server. Invoked via `make deploy` (locally or from CI).
# Expects REF env var (git tag, branch, or commit sha) to check out before
# rebuilding the Compose stack.
set -euxo pipefail

: "${REF:?REF is required}"

cd /opt/tidemill
git fetch --tags --force origin
git checkout "$REF"
git rev-parse HEAD

docker compose -f deploy/compose/docker-compose.yml build
docker compose -f deploy/compose/docker-compose.yml up -d --force-recreate
