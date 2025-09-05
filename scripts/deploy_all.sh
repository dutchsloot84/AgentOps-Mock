#!/usr/bin/env bash
set -euo pipefail

: "${REGION:=us-central1}"

make deps \
 && make deploy-mock \
 && make deploy-tasks \
 && make deploy-claims \
 && make upsert \
 && make deploy-agent \
 && make urls
