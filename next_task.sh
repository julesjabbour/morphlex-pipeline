#!/bin/bash
cd /mnt/pgdata/morphlex
source venv/bin/activate

echo "=== BUILD MORPHLEX TABLE (20 CONCEPTS) WITH HIT RATE FIXES + CLASSIFICATION ==="
echo "Git: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

python3 scripts/build_morphlex_table.py

echo ""
echo "=== CSV PREVIEW (first 3 data rows, selected columns) ==="
python3 -c "
import csv
with open('/mnt/pgdata/morphlex/data/morphlex_test_20.csv') as f:
    reader = csv.DictReader(f)
    count = 0
    for row in reader:
        if count >= 3:
            break
        print(f\"  {row['english_word']:15} | {row['lang']:3} | {row['morph_type']:20} | root={row['root'][:20]}\")
        count += 1
"

echo ""
echo "=== DONE ==="
