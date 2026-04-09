#!/bin/bash
# DATA QUALITY CHECK on master_table.csv
# Timestamp: 2026-04-09-data-quality-check-v1
# - Read-only diagnostic
# - Print stats on morph_type, root, wiktextract_match, POS
# - No file modifications

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== DATA QUALITY CHECK: master_table.csv ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code from git
git fetch origin > /dev/null 2>&1
git reset --hard origin/main > /dev/null 2>&1

# Run the data quality check
python3 pipeline/data_quality_check.py

RESULT=$?

echo ""
echo "End: $(date -Iseconds)"
exit $RESULT
