#!/bin/bash
FLAG="/tmp/.eng015_v3_test"
if [ -f "$FLAG" ]; then
    echo "=== ALREADY COMPLETE ==="
    exit 0
fi

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "Index size:"
ls -lh data/etymology_index.pkl 2>&1

python3 -c "
import sys, pickle
sys.path.insert(0, '/mnt/pgdata/morphlex')
with open('data/etymology_index.pkl','rb') as f:
    idx = pickle.load(f)
sample = list(idx.keys())[:1]
entry = idx[sample[0]]
print(f'Keys in entry: {list(entry.keys())}')
print(f'Has translations: {\"translations\" in entry}')
if 'translations' in entry:
    print(f'Translation langs: {list(entry[\"translations\"].keys())[:5]}')
" 2>&1

echo ""

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
