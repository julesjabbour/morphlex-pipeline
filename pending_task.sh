#!/bin/bash
source /mnt/pgdata/morphlex/venv/bin/activate
cd /mnt/pgdata/morphlex
python3 -c "
from analyzers.german import analyze_german
r1 = analyze_german('Handschuh')
assert len(r1) > 0, 'No results'
has_compound = any(r.get('compound_components') for r in r1)
print(f'COMPOUND: {[r.get(\"compound_components\") for r in r1]}')
r2 = analyze_german('getestet')
assert len(r2) > 0
print(f'LEMMA: {r2[0].get(\"lemma\",\"\")}')
print(f'POS: {r2[0].get(\"pos\",\"\")}')
print('ENG-004 PASS')
"
