#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== OPTIMIZED BUILD: 100 CONCEPTS WITH MEMORY MONITORING ==="
echo "Git: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Run the optimized build_morphlex_table.py
python3 scripts/build_morphlex_table.py

echo ""
echo "=== CSV PREVIEW (first 5 data rows) ==="
python3 -c "
import csv
with open('data/morphlex_test_100.csv', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        if i >= 5:
            break
        cid = row.get('concept_id','')[:25]
        ew = row.get('english_word','')[:12]
        lang = row.get('lang','')
        mt = row.get('morph_type','')[:15]
        print(f'  {cid:<25} | {ew:<12} | {lang} | {mt:<15}')
"

echo ""
echo "=== DONE ==="
