#!/bin/bash
source /mnt/pgdata/morphlex/venv/bin/activate
cd /mnt/pgdata/morphlex
python3 -c "
from analyzers.chinese import analyze_chinese
r1 = analyze_chinese('我爱北京天安门')
assert len(r1) > 0, 'No results'
print(f'SEGMENTS: {len(r1)}')
for r in r1:
    print(f'  {r[\"word_native\"]} -> pinyin={r.get(\"morphological_features\",{}).get(\"pinyin\",\"?\")}')
print('ENG-007 PASS')
"
