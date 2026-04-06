#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== GREEK ADAPTER TEST (ENG-019 via Wiktextract) ==="
python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
from analyzers.greek import analyze_greek
words = ['λόγος', 'ἄνθρωπος', 'θεός', 'πόλις', 'σοφία']
total = 0
for w in words:
    r = analyze_greek(w)
    print(f'  {w}: {len(r)} analyses')
    if r: print(f'    -> {r[0]}')
    total += len(r)
print(f'\nTotal results: {total}')
" 2>&1

echo "=== TEST COMPLETE ==="
