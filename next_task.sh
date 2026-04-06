#!/bin/bash
FLAG="/tmp/.eng015_v4_crosslinks"
if [ -f "$FLAG" ]; then
    echo "=== ALREADY COMPLETE ==="
    exit 0
fi

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== RAW DATA DEBUG ==="
python3 -c "
import sys, pickle
sys.path.insert(0, '/mnt/pgdata/morphlex')
with open('data/etymology_index.pkl','rb') as f:
    idx = pickle.load(f)
if 'water' in idx:
    t = idx['water'].get('translations', {})
    print(f'water translations type: {type(t)}')
    for lang in ['ar','he','ja','zh','de','tr','sa','la','grc','ine-pro']:
        val = t.get(lang, 'MISSING')
        print(f'  {lang}: {val}')
else:
    print('water NOT IN INDEX')
" 2>&1

echo ""
echo "=== CROSS-LINK TEST ==="
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
