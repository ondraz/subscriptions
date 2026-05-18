#!/usr/bin/env bash
# Runs on the production server. Invoked via `make deploy` (locally or from CI).
# Expects REF env var (git tag, branch, or commit sha) to check out before
# rebuilding the Compose stack.
set -euxo pipefail

: "${REF:?REF is required}"

cd /opt/tidemill

# Make sure /opt/tidemill is a clean mirror of $REF.
# - fetch all branches/tags and prune deleted ones
# - reset --hard to overwrite any drift in tracked files (missing files,
#   stale routes.tsx vs. missing pages/*, half-applied prior deploys)
# - clean -fdx removes untracked files and ignored build artefacts so the
#   Docker build context matches the committed tree exactly
git fetch --prune --tags --force origin '+refs/heads/*:refs/remotes/origin/*'
git reset --hard "$REF"
git clean -fdx
git rev-parse HEAD

docker compose -f deploy/compose/docker-compose.yml build
docker compose -f deploy/compose/docker-compose.yml up -d --force-recreate
