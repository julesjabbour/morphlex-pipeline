#!/bin/bash
rm -f /tmp/.task_done* /tmp/.eng015*
cd /mnt/pgdata/morphlex && source venv/bin/activate
echo "=== BUILD FORWARD INDEX ==="
python3 pipeline/build_forward_translations.py 2>&1 | tail -5
echo ""
echo "=== TEST ==="
python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
from pipeline.etymology_enricher import enrich_etymology, load_indexes
load_indexes()
for w in ['water','mother','book','king','star','sun','eye','fire','earth','house']:
    r = enrich_etymology(w)
    print(f'{w}: {r[\"cross_links\"]}')
" 2>&1
touch /tmp/.eng015_forward_final
echo "=== DONE ==="
