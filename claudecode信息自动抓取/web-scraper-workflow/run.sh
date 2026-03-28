#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "=== Web Scraper Workflow ==="
echo "Date: $(date +%Y-%m-%d)"
echo ""

# 读取 sources 列表并逐一抓取
SOURCES=$(python3 -c "
import json
with open('config.json') as f:
    config = json.load(f)
for s in config['sources']:
    print(json.dumps(s))
")

FAILED=0
SUCCESS=0

while IFS= read -r source; do
    NAME=$(echo "$source" | python3 -c "import sys,json; print(json.load(sys.stdin)['name'])")
    echo "Scraping: $NAME ..."
    if python3 scraper.py "$source"; then
        SUCCESS=$((SUCCESS + 1))
    else
        echo "  [WARN] Failed to scrape $NAME, skipping."
        FAILED=$((FAILED + 1))
    fi
done <<< "$SOURCES"

echo ""
echo "Scraping done: $SUCCESS succeeded, $FAILED failed."

if [ "$SUCCESS" -eq 0 ]; then
    echo "[ERROR] All sources failed. Aborting."
    exit 1
fi

echo ""
echo "Running analyzer..."
python3 analyzer.py

echo ""
echo "=== Done ==="
