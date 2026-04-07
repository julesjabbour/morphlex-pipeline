#!/bin/bash
# Run updated build_forward_translations.py with INVERTED Arabic->X logic
#
# The script processes English Wiktionary entries:
# 1. Finds English entries that have an Arabic translation
# 2. Uses the Arabic word as the KEY
# 3. Collects all other translations (en, tr, de, la, zh, ja, he, sa, grc, ine-pro) as VALUES
#
# Usage: bash next_task.sh
# Working directory: /mnt/pgdata/morphlex

set -e

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== REBUILD FORWARD TRANSLATIONS (INVERTED ARABIC->X) ==="
echo "Start: $(date -Iseconds)"
echo ""

# Fetch latest code to ensure we have the inverted script
echo "Fetching latest code from GitHub..."
git fetch origin && git reset --hard origin/main
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
echo ""

# Run the build script - it outputs stats and runs debug sampling if 0 results
python3 pipeline/build_forward_translations.py

# Show final file size summary
if [ -f "data/forward_translations.pkl" ]; then
    AFTER_SIZE=$(stat -c%s "data/forward_translations.pkl")
    if [ "$AFTER_SIZE" -gt 1048576 ]; then
        AFTER_SIZE_MB=$(echo "scale=2; $AFTER_SIZE / 1048576" | bc)
        echo ""
        echo "=== FINAL: forward_translations.pkl: ${AFTER_SIZE_MB}MB ($AFTER_SIZE bytes) ==="
    else
        AFTER_SIZE_KB=$(echo "scale=2; $AFTER_SIZE / 1024" | bc)
        echo ""
        echo "=== FINAL: forward_translations.pkl: ${AFTER_SIZE_KB}KB ($AFTER_SIZE bytes) ==="
    fi
fi

echo ""
echo "End: $(date -Iseconds)"
echo "=== Build complete ==="
