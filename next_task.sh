#!/bin/bash
# MERGE MORPHOLEX + WIKTEXTRACT FOR ENGLISH
# Timestamp: 2026-04-09-merge-morpholex-wiktextract-v1
# - Load master_table.csv
# - Apply priority rule: COMPOUND_DERIVATION > COMPOUND > DERIVATION > ROOT > UNKNOWN
# - Pick higher priority type, update root/derivation_info accordingly
# - Save back to master_table.csv

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== MERGE MORPHOLEX + WIKTEXTRACT FOR ENGLISH ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code from git
git fetch origin > /dev/null 2>&1
git reset --hard origin/main > /dev/null 2>&1

# Run the merge script
python3 scripts/merge_morpholex_wiktextract.py

RESULT=$?

echo ""
echo "End: $(date -Iseconds)"
exit $RESULT
