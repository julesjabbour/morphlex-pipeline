#!/bin/bash
FLAG="/tmp/.eng015_crosslinks_v2"
if [ -f "$FLAG" ]; then
    echo "=== ALREADY COMPLETE — SKIPPING ==="
    exit 0
fi

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== REBUILDING ETYMOLOGY INDEX WITH TRANSLATIONS ==="
rm -f data/etymology_index.pkl
python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
from pipeline.etymology_enricher import build_etymology_index
build_etymology_index()
" 2>&1

echo ""
echo "=== CROSS-LINK TEST ==="
python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
from pipeline.etymology_enricher import enrich_etymology, load_indexes
load_indexes()
for word in ['water', 'mother', 'book', 'king', 'star', 'sun', 'eye', 'fire', 'earth', 'house']:
    r = enrich_etymology(word)
    print(f'{word}: cross_links={r[\"cross_links\"]}')
" 2>&1

echo ""
touch "$FLAG"
echo "=== COMPLETE — flag set ==="
