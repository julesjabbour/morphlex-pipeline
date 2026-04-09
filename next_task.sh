#!/bin/bash
# FULL PRODUCTION RUN: ALL 120K+ CONCEPTS
# Timestamp: 2026-04-09-full-production-run-v1
# - Process ALL concepts with 2+ target languages
# - Checkpointing every 1,000 concepts
# - Output to data/master_table.csv
# - Expected runtime: several hours

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== FULL PRODUCTION RUN: ALL CONCEPTS ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code from git
git fetch origin > /dev/null 2>&1
git reset --hard origin/main > /dev/null 2>&1

# Check for existing checkpoint
if [ -f "data/pipeline_checkpoint.pkl" ]; then
    echo "Found existing checkpoint - will resume from last position"
fi
echo ""

echo "Starting full pipeline run..."
python3 pipeline/run_pipeline.py

RESULT=$?

echo ""
echo "End: $(date -Iseconds)"
exit $RESULT
