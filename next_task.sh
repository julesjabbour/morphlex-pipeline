#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== HEBREW ADAPTER TEST (ENG-017 via Wiktextract) ==="
python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
from analyzers.hebrew import analyze_hebrew

words = ['ספר', 'כתב', 'בית', 'שלום', 'אדם']
total = 0
for w in words:
    r = analyze_hebrew(w)
    print(f'  {w}: {len(r)} analyses')
    if r:
        print(f'    -> {r[0]}')
    total += len(r)
print(f'\nTotal results: {total}')
" 2>&1

echo "=== TEST COMPLETE ==="
