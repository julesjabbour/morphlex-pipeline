#!/bin/bash
# COMPARE MORPHOLEX vs WIKTEXTRACT FOR ENGLISH
# Timestamp: 2026-04-09-compare-morpholex-wiktextract-v1
# - Read master_table.csv English rows
# - Compare morph_type/root from MorphoLex adapter vs wiktextract_match
# - Create english_comparison.csv with agreement analysis

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== COMPARE MORPHOLEX vs WIKTEXTRACT FOR ENGLISH ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code from git
git fetch origin > /dev/null 2>&1
git reset --hard origin/main > /dev/null 2>&1

# Run the comparison script
python3 scripts/compare_morpholex_wiktextract.py

RESULT=$?

echo ""
echo "End: $(date -Iseconds)"
exit $RESULT
