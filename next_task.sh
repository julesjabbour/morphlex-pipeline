#!/bin/bash
rm -f /tmp/.eng015* /tmp/.task_done*
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== BUILDING FORWARD TRANSLATION INDEX ==="
python3 pipeline/build_forward_translations.py 2>&1

echo ""
echo "=== CROSS-LINK TEST ==="
python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
from pipeline.etymology_enricher import enrich_etymology, load_indexes
load_indexes()
for w in ['water','mother','book','king','star','sun','eye','fire','earth','house']:
    r = enrich_etymology(w)
    print(f'{w}: {r[\"cross_links\"]}')
" 2>&1

touch /tmp/.eng015_forward_done
echo "=== DONE ==="
