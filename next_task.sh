#!/bin/bash
# BACKFILL ENGLISH ROOT AND DERIVATION from wiktextract_match
# Timestamp: 2026-04-09-backfill-en-root-derivation-v1
# - For English rows with wiktextract_match containing from=X, set root and derivation_info
# - For English rows with compound data, set compound_components
# - Does NOT change morph_type

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== BACKFILL ENGLISH ROOT AND DERIVATION ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code from git
git fetch origin > /dev/null 2>&1
git reset --hard origin/main > /dev/null 2>&1

# Run the backfill script
python3 pipeline/backfill_english_root_derivation.py

RESULT=$?

echo ""
echo "End: $(date -Iseconds)"
exit $RESULT
