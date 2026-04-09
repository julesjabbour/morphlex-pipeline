#!/bin/bash
# PHASE 5b: RUN PIPELINE ON 100 CONCEPTS
# Timestamp: 2026-04-09-phase5b-test
# Process first 100 concepts with 3+ languages through adapters

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== PHASE 5b: RUN PIPELINE TEST (100 CONCEPTS) ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code from git
git fetch origin > /dev/null 2>&1
git reset --hard origin/main > /dev/null 2>&1

echo "Running pipeline on first 100 concepts..."
python3 pipeline/run_pipeline.py

RESULT=$?

echo ""
echo "End: $(date -Iseconds)"
exit $RESULT
