#!/bin/bash
# DIAGNOSTIC: Sample Wiktextract entries with derivation/compound templates
# Timestamp: 2026-04-08-wikt-diagnostic
# Purpose: Show JSON structure of affix/compound templates BEFORE writing full extraction
# NO HARDCODING. All analysis from real data.

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== WIKTEXTRACT MORPHOLOGY DIAGNOSTIC ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code first
echo "--- Syncing code from origin/main ---"
git fetch origin && git reset --hard origin/main
echo "Now at: $(git rev-parse HEAD)"
echo ""

echo "=== SAMPLING DERIVATION/COMPOUND TEMPLATES ==="
echo "Looking for affix/prefix/suffix/confix/compound templates in 11 languages"
echo "Sampling 3 entries per language to see actual JSON structure"
echo ""

python3 pipeline/diagnostic_wiktextract_morphology.py

echo ""
echo "=== DIAGNOSTIC COMPLETE ==="
echo "Next step: After reviewing output, push full extraction script"
echo "End: $(date -Iseconds)"
