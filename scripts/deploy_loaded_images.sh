#!/usr/bin/env sh
set -eu

DEPLOY_ROOT="${1:-$(pwd)}"

cd "$DEPLOY_ROOT"

chmod 644 docker-compose.prod.yml

docker compose -f docker-compose.prod.yml up -d
