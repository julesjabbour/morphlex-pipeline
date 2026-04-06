#!/bin/bash
rm -f /tmp/.task_done* /tmp/.eng015*
cd /mnt/pgdata/morphlex

echo "=== FILE CHECK ==="
ls -lh data/forward_translations.pkl 2>&1
echo ""
echo "=== RUNNING PROCESSES ==="
ps aux | grep python3 | grep -v grep 2>&1 || echo "none"
echo ""
echo "=== LAST 3 GIT COMMITS ==="
git log --oneline -3 2>&1
echo ""
echo "=== RUN.SH LOG ==="
tail -10 /tmp/morphlex_run.log 2>&1 || echo "no log"
echo ""

if [ -f data/forward_translations.pkl ]; then
    source venv/bin/activate
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
else
    echo "forward_translations.pkl DOES NOT EXIST"
    echo "Building now..."
    source venv/bin/activate
    python3 pipeline/build_forward_translations.py 2>&1 | tail -5
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
fi

touch /tmp/.eng015_check_done
echo "=== DONE ==="
