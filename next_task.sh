#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== BUILD MORPHLEX TABLE (20 CONCEPTS) ==="
echo "Git: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

python3 scripts/build_morphlex_table.py

echo ""
echo "=== CSV PREVIEW (first 5 rows) ==="
head -6 /mnt/pgdata/morphlex/data/morphlex_test_20.csv | column -t -s','

echo ""
echo "=== DONE ==="
