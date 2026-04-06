#!/bin/bash
FLAG="/tmp/.eng015_020_complete"
if [ -f "$FLAG" ]; then
    echo "=== ALREADY COMPLETE — SKIPPING ==="
    exit 0
fi

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== ENG-015 + ENG-020 COMBINED TEST ==="

if [ -f data/etymology_index.pkl ]; then
  echo "Etymology index exists, skipping build"
else
  echo "Building etymology index..."
  python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
from pipeline.etymology_enricher import build_etymology_index
build_etymology_index()
"
fi

echo ""
echo "=== ETYMOLOGY ENRICHER TEST ==="
python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
from pipeline.etymology_enricher import enrich_etymology, load_indexes
load_indexes()
for word in ['water', 'mother', 'book', 'king', 'star']:
    r = enrich_etymology(word)
    print(f'{word}: ancestors={len(r[\"ancestors\"])}, cognates={len(r[\"cognates\"])}, cross_links={r[\"cross_links\"]}')
" 2>&1

echo ""
echo "=== PIE ADAPTER TEST ==="
python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
from analyzers.pie import analyze_pie
for w in ['*wódr̥', '*ph₂tḗr', '*méh₂tēr']:
    r = analyze_pie(w)
    print(f'PIE {w}: {len(r)} results')
    if r: print(f'  -> {r[0]}')
" 2>&1

echo ""
touch "$FLAG"
echo "=== ALL TESTS COMPLETE — flag set, will not rerun ==="
