#!/bin/bash
# DOWNLOAD AGWN AND REPLACE MODERN GREEK IN CONCEPT MAP
# Timestamp: 2026-04-10-agwn-replacement-v1
# - Download Ancient Greek WordNet data
# - Build synset-to-Ancient-Greek lookup
# - Replace Modern Greek (el) words with Ancient Greek words in concept_wordnet_map.pkl

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== DOWNLOAD AGWN AND REPLACE MODERN GREEK ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code from git
git fetch origin > /dev/null 2>&1
git reset --hard origin/main > /dev/null 2>&1

# Run the replacement script
python3 scripts/replace_modern_greek_with_agwn.py

RESULT=$?

echo ""
echo "End: $(date -Iseconds)"
exit $RESULT
