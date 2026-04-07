#!/bin/bash
# Task: Run batch test with all fixes for Problems 0-7
# - Problem 0: Rebuild pkl with full logging
# - Problem 1: Root extraction for all adapters
# - Problem 2: morph_type classification
# - Problem 3: derivation detail columns
# - Problem 4: Arabic duplicate consolidation
# - Problem 5: English POS tagging fix
# - Problem 6: German compound decomposition fix
# - Problem 7: Slack progress updates every 2 minutes

cd /mnt/pgdata/morphlex && source venv/bin/activate

GIT_HEAD=$(git rev-parse HEAD)
START_TIME=$(date -Iseconds)

echo "=== BATCH TEST v2 ==="
echo "Start: $START_TIME"
echo "Git HEAD: $GIT_HEAD"
echo ""

# Run the batch test
python3 pipeline/batch_test.py 1000 true

EXIT_CODE=$?

END_TIME=$(date -Iseconds)
echo ""
echo "=== TASK COMPLETE ==="
echo "Start: $START_TIME"
echo "End: $END_TIME"
echo "Git HEAD: $GIT_HEAD"
echo "Exit code: $EXIT_CODE"

# Show output file sizes
echo ""
echo "=== OUTPUT FILES ==="
ls -la /mnt/pgdata/morphlex/reports/batch_1000_v2_* /mnt/pgdata/morphlex/reports/pkl_rebuild_log.md 2>/dev/null

exit $EXIT_CODE
