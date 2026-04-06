#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== PIE ADAPTER TEST ==="
ls -lh data/wiktextract_index.pkl

python3 -c "
import sys, pickle
sys.path.insert(0, '/mnt/pgdata/morphlex')

with open('data/wiktextract_index.pkl', 'rb') as f:
    idx = pickle.load(f)
pie_count = len(idx.get('ine-pro', {}))
print(f'ine-pro entries in index: {pie_count}')
if pie_count > 0:
    print(f'Sample PIE forms: {list(idx[\"ine-pro\"].keys())[:5]}')

from analyzers.pie import analyze_pie
for w in ['*wódr̥', '*ph₂tḗr', '*méh₂tēr']:
    r = analyze_pie(w)
    print(f'PIE {w}: {len(r)} results')
    if r: print(f'  -> {r[0]}')
" 2>&1

echo "=== COMPLETE ==="
