#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate
echo "=== REBUILDING INDEX WITH PIE ==="
python3 pipeline/build_wiktextract_index.py
echo ""
echo "=== TESTING PIE ==="
python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
from analyzers.pie import analyze_pie
for w in ['*wódr̥', '*ph₂tḗr', '*méh₂tēr']:
    r = analyze_pie(w)
    print(f'PIE {w}: {len(r)} results')
    if r: print(f'  -> {r[0]}')
" 2>&1
echo "=== COMPLETE ==="
