#!/bin/bash
# DIAGNOSE ANCIENT GREEK WORDNET DATA SOURCES
# Timestamp: 2026-04-10-agwn-diagnostic-v1
# - Check downloaded files in data/agwn/
# - Try Harvard API endpoints
# - Try wn Python package for Ancient Greek
# - Try CLARIN-IT with ?sequence=1 parameter

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== DIAGNOSE AGWN DATA SOURCES ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code from git
git fetch origin > /dev/null 2>&1
git reset --hard origin/main > /dev/null 2>&1

# Run the diagnostic script
python3 scripts/diagnose_agwn.py

RESULT=$?

echo ""
echo "End: $(date -Iseconds)"
exit $RESULT
