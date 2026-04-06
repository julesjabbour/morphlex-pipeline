#!/bin/bash
FLAG="/tmp/.eng015_noun_fix"
if [ -f "$FLAG" ]; then
    echo "=== ALREADY COMPLETE ==="
    exit 0
fi
cd /mnt/pgdata/morphlex && source venv/bin/activate
python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
from pipeline.etymology_enricher import enrich_etymology, load_indexes
load_indexes()
for word in ['water','mother','book','king','star','sun','eye','fire','earth','house']:
    r = enrich_etymology(word)
    print(f'{word}: {r[\"cross_links\"]}')
" 2>&1
touch "$FLAG"
echo "=== DONE ==="
