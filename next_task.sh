#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== BUILD MORPHLEX TABLE (20 CONCEPTS) WITH BUG FIXES ==="
echo "Git: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

python3 scripts/build_morphlex_table.py

echo ""
echo "=== CSV PREVIEW (first 3 data rows, selected columns) ==="
python3 -c "
import csv
with open('data/morphlex_test_20.csv', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        if i >= 3:
            break
        ew = row.get('english_word','')[:15]
        lang = row.get('lang','')
        mt = row.get('morph_type','')[:20]
        root = row.get('root','')[:20]
        rt = row.get('root_templates','')[:50]
        has_rt = 'YES' if rt else 'NO'
        print(f'  {ew:<15} | {lang} | {mt:<20} | root={root:<15} | has_templates={has_rt}')
"

echo ""
echo "=== DONE ==="
