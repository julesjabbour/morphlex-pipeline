#!/bin/bash
# PHASE 3: Full Wiktextract Morphology Extraction
# Timestamp: 2026-04-08-full-wikt-morph
# Purpose: Process ENTIRE 2.4GB dump, extract all morphology data
# Expected runtime: 30-120 minutes (DO NOT TIMEOUT)
# NO HARDCODING. NO SHORTCUTS. FULL DUMP PROCESSING.

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== PHASE 3: WIKTEXTRACT FULL MORPHOLOGY EXTRACTION ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code first
echo "--- Syncing code from origin/main ---"
git fetch origin && git reset --hard origin/main
echo "Now at: $(git rev-parse HEAD)"
echo ""

echo "=== EXTRACTION PARAMETERS ==="
echo "Input: /mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz (2.4GB)"
echo "Output: /mnt/pgdata/morphlex/data/wiktextract_morphology.pkl"
echo "Target languages: ar, de, en, grc, he, ine-pro, ja, la, sa, tr, zh"
echo ""
echo "Templates to extract:"
echo "  Derivation: af, affix, prefix, suffix, confix, circumfix, infix"
echo "  Compound: compound, com"
echo "  Etymology: inh, bor, der, cog"
echo ""
echo "NOTE: This will take 30-120 minutes. DO NOT INTERRUPT."
echo ""

# Run full extraction
python3 pipeline/extract_wiktextract_morphology.py

exit_code=$?

echo ""
echo "=== EXTRACTION FINISHED ==="
echo "Exit code: $exit_code"

# Verify output file exists and show size
if [ -f /mnt/pgdata/morphlex/data/wiktextract_morphology.pkl ]; then
    echo "Output file exists:"
    ls -lh /mnt/pgdata/morphlex/data/wiktextract_morphology.pkl
else
    echo "ERROR: Output file not created!"
fi

echo ""
echo "End: $(date -Iseconds)"
