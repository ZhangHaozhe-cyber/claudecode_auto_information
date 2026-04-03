#!/bin/bash
set -e
cd "$(dirname "$0")"

COUNTRY="${1:-cn}"
MODE="${2:-daily}"

echo "Running medical policy workflow: country=$COUNTRY, mode=$MODE"
python run.py --country "$COUNTRY" --mode "$MODE"
