#!/bin/bash
source /mnt/pgdata/morphlex/venv/bin/activate
cd /mnt/pgdata/morphlex
python3 -c "
from analyzers.latin import analyze_latin
r1 = analyze_latin('scriptorum')
assert len(r1) > 0, 'No results'
print(f'ANALYSES: {len(r1)}')
print(f'LEMMA: {r1[0].get(\"lemma\",\"\")}')
print(f'POS: {r1[0].get(\"pos\",\"\")}')
r2 = analyze_latin('laudat')
assert len(r2) > 0
print(f'WORD2 LEMMA: {r2[0].get(\"lemma\",\"\")}')
print('ENG-006 PASS')
"
