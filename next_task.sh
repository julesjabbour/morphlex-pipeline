#!/bin/bash
# PHASE 5b: RUN PIPELINE ON 100 CONCEPTS (DEBUG SUPPRESSED)
# Timestamp: 2026-04-09-phase5b-debug-suppressed-v1
# - Suppress ALL debug output (logging=WARNING, no [DEBUG] prints)
# - Check MorphoLex-en location
# - Output only final summary

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== PHASE 5b: RUN PIPELINE TEST (100 CONCEPTS - CLEAN OUTPUT) ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code from git
git fetch origin > /dev/null 2>&1
git reset --hard origin/main > /dev/null 2>&1

# Check MorphoLex-en location
echo "Checking MorphoLex-en location..."
MORPHOLEX_FOUND=$(find /mnt/pgdata -name "MorphoLex*" -type d 2>/dev/null | head -5)
if [ -n "$MORPHOLEX_FOUND" ]; then
    echo "MorphoLex directories found:"
    echo "$MORPHOLEX_FOUND"
else
    echo "MorphoLex-en directory NOT found on VM"
fi
echo ""

echo "Running pipeline on first 100 concepts..."
python3 pipeline/run_pipeline.py

RESULT=$?

echo ""
echo "End: $(date -Iseconds)"
exit $RESULT
