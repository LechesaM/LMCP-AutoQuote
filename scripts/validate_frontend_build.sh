#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR/frontend/command-centre"

npm ci --prefer-offline --no-audit --no-fund
npm run build

