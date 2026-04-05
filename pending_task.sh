#!/bin/bash
source /mnt/pgdata/morphlex/venv/bin/activate
cd /mnt/pgdata/morphlex
python3 -c "
from analyzers.english import analyze_english
r1 = analyze_english('unhappiness')
assert len(r1) > 0, 'No results'
print(f'LEMMA: {r1[0].get(\"lemma\",\"\")}')
print(f'POS: {r1[0].get(\"pos\",\"\")}')
print(f'ROOT: {r1[0].get(\"root\",\"\")}')
r2 = analyze_english('running')
assert len(r2) > 0
print(f'WORD2 LEMMA: {r2[0].get(\"lemma\",\"\")}')
print('ENG-005 PASS')
"
