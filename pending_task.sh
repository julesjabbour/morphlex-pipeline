#!/bin/bash
source /mnt/pgdata/morphlex/venv/bin/activate
cd /mnt/pgdata/morphlex
python3 -c "
from analyzers.turkish import analyze_turkish
r1 = analyze_turkish('okudum')
assert len(r1) > 0, 'No results'
assert r1[0]['language_code'] == 'tr'
assert r1[0]['lemma'] == 'oku' or 'oku' in str(r1[0]['lemma'])
print(f'LEMMA: {r1[0][\"lemma\"]}')
print(f'POS: {r1[0][\"pos\"]}')
r2 = analyze_turkish('evler')
assert len(r2) > 0
print(f'WORD2 LEMMA: {r2[0][\"lemma\"]}')
print('ENG-003 PASS')
"
