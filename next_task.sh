#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== FULL 9000 CONCEPT BUILD ==="
echo "Git: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Run the full build - 9000 concepts, output to morphlex_full.csv
# Output is summary stats only - no per-word progress
python3 scripts/build_morphlex_table.py

echo ""
echo "=== DONE ==="
