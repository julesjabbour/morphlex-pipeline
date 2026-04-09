#!/bin/bash
# BACKFILL ENGLISH MORPH_TYPE from wiktextract_match
# Timestamp: 2026-04-09-backfill-en-morph-type-v1
# - Update morph_type for English rows where UNKNOWN but wiktextract_match has type=
# - Parse type= value and overwrite UNKNOWN

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== BACKFILL ENGLISH MORPH_TYPE ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code from git
git fetch origin > /dev/null 2>&1
git reset --hard origin/main > /dev/null 2>&1

# Run the backfill script
python3 pipeline/backfill_english_morph_type.py

RESULT=$?

echo ""
echo "End: $(date -Iseconds)"
exit $RESULT
