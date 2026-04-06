#!/bin/bash
# 10-word orchestrator test across all 11 languages
# Languages: ar, tr, de, en, la, zh, ja, he, sa, grc, ine-pro

cd /mnt/pgdata/morphlex && python3 orchestrator.py --words water fire hand eye stone heart sun moon tree blood --output-format json > /tmp/test_results.json 2>&1 && echo "TEST COMPLETE" && cat /tmp/test_results.json | python3 -c "import sys,json; data=json.load(sys.stdin); langs=set(r['language'] for r in data); print(f'Languages: {len(langs)}'); print(f'Total results: {len(data)}'); [print(f'  {l}: {sum(1 for r in data if r[\"language\"]==l)}') for l in sorted(langs)]"
