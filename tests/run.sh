#!/usr/bin/env bash
# Run the suite on a fresh copy of the live database (see tests/testdb.py).
#   tests/run.sh                 everything
#   tests/run.sh "test_targets*.py"
set -euo pipefail
cd "$(dirname "$0")/.."
LIVE=branding_gate
TEST=${BG_TEST_DB:-branding_gate_test}
[ "$TEST" = "$LIVE" ] && { echo "BG_TEST_DB must not be the live database" >&2; exit 1; }
MYSQL=(-u ps -pAa@123456)
mysql "${MYSQL[@]}" -e "DROP DATABASE IF EXISTS \`$TEST\`; CREATE DATABASE \`$TEST\` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci" 2>/dev/null
mysqldump "${MYSQL[@]}" --single-transaction --routines --triggers --no-tablespaces "$LIVE" 2>/dev/null \
  | mysql "${MYSQL[@]}" "$TEST" 2>/dev/null
set -a; [ -f .env ] && . ./.env; set +a
export BG_DB="$TEST" BG_MONGO_DB="$TEST"
timeout 1500 ./branding_gate_VENV/bin/python -W ignore -m unittest discover -s tests -p "${1:-test_*.py}"
git checkout -- docs/sales-request-journey-and-privileges.pdf 2>/dev/null || true
