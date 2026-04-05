#!/bin/bash
source /mnt/pgdata/morphlex/venv/bin/activate
cd /mnt/pgdata/morphlex
python3 -c "
from analyzers.arabic import analyze_arabic
results = analyze_arabic('كتاب')
assert len(results) > 0, 'No results'
r = results[0]
assert 'root' in r and r['root'], f'No root: {r}'
assert r['language_code'] == 'ar', f'Wrong lang: {r}'
print(f'ROOT: {r[\"root\"]}')
print(f'LEMMA: {r.get(\"lemma\",\"\")}')
print(f'POS: {r.get(\"pos\",\"\")}')
print(f'ANALYSES: {len(results)}')
r2 = analyze_arabic('ذهب')
assert len(r2) > 0, 'No results for dhahab'
print(f'WORD2 ROOT: {r2[0][\"root\"]}')
print('ENG-002 PASS')
"
