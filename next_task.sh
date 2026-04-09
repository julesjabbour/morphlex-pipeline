#!/bin/bash
# INSTALL MORPHOLEX FOR ENGLISH
# Timestamp: 2026-04-09-install-morpholex-v1
# - Download MorphoLex xlsx to /mnt/pgdata/morphlex/MorphoLex-en/
# - Test English adapter with 5 words
# - Re-analyze all English rows in master_table.csv

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== INSTALL MORPHOLEX FOR ENGLISH ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code from git
git fetch origin > /dev/null 2>&1
git reset --hard origin/main > /dev/null 2>&1

# Run the install script
python3 pipeline/install_morpholex.py

RESULT=$?

echo ""
echo "End: $(date -Iseconds)"
exit $RESULT
