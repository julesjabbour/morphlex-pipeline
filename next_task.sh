#!/bin/bash
# Rebuild forward_translations.pkl from full Wiktextract data
#
# Reads Arabic entries from data/raw-wiktextract-data.jsonl.gz
# Extracts translations to all 10 target languages (en, tr, de, la, zh, ja, he, sa, grc, ine-pro)
# Builds the full Arabic-to-X forward_translations.pkl
#
# Usage: bash next_task.sh
# Working directory: /mnt/pgdata/morphlex

set -e

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== REBUILD FORWARD TRANSLATIONS FROM WIKTEXTRACT ==="
echo "Start: $(date -Iseconds)"
echo ""

# Check that raw data exists
if [ ! -f "data/raw-wiktextract-data.jsonl.gz" ]; then
    echo "ERROR: data/raw-wiktextract-data.jsonl.gz not found"
    exit 1
fi

# Show current file size
if [ -f "data/forward_translations.pkl" ]; then
    BEFORE_SIZE=$(stat -c%s "data/forward_translations.pkl")
    echo "Current forward_translations.pkl: $BEFORE_SIZE bytes"
else
    echo "No existing forward_translations.pkl"
fi

# Run the build script
python3 pipeline/build_forward_translations.py

# Show new file size
if [ -f "data/forward_translations.pkl" ]; then
    AFTER_SIZE=$(stat -c%s "data/forward_translations.pkl")
    AFTER_SIZE_MB=$(echo "scale=2; $AFTER_SIZE / 1048576" | bc)
    echo ""
    echo "=== REBUILD COMPLETE ==="
    echo "New forward_translations.pkl: ${AFTER_SIZE_MB}MB ($AFTER_SIZE bytes)"
fi

echo ""
echo "End: $(date -Iseconds)"
echo "=== Build complete ==="
