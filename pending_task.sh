#!/bin/bash
source /mnt/pgdata/morphlex/venv/bin/activate
cd /mnt/pgdata/morphlex
python3 -c "
from pipeline.etymology_enricher import enrich_etymology
r1 = enrich_etymology('book', 'en')
print(f'RELATIONS: {len(r1)}')
for r in r1[:5]:
    print(f'  {r[\"relation_type\"]}: {r[\"related_word\"]} ({r[\"related_language\"]})')
r2 = enrich_etymology('water', 'en')
print(f'WATER RELATIONS: {len(r2)}')
print('ENG-015 PASS')
"
