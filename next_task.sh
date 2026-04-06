#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== ENG-015 + ENG-020 COMBINED TEST ==="

# Skip index build if exists
if [ -f data/etymology_index.pkl ]; then
  echo "Etymology index exists, skipping build"
else
  echo "Building etymology index..."
  python3 pipeline/etymology_enricher.py --build-index
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
echo "=== SELF-DESTRUCT ==="
rm -f /mnt/pgdata/morphlex/next_task.sh
echo "next_task.sh removed — no more reruns"
echo "=== ALL TESTS COMPLETE ==="
