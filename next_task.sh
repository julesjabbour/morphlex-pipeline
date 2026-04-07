#!/bin/bash
# Task: Diagnostic - cat logs to diagnose v2 batch Slack failure

cd /mnt/pgdata/morphlex && source venv/bin/activate

GIT_HEAD=$(git rev-parse HEAD)
START_TIME=$(date -Iseconds)

echo "=== DIAGNOSTIC: v2 BATCH SLACK FAILURE ==="
echo "Start: $START_TIME"
echo "Git HEAD: $GIT_HEAD"
echo ""

echo "=== LAST 20 LINES OF /tmp/morphlex_cron.log ==="
tail -20 /tmp/morphlex_cron.log 2>&1 || echo "(file not found or empty)"
echo ""

echo "=== LAST 20 LINES OF /tmp/morphlex_debug.log ==="
tail -20 /tmp/morphlex_debug.log 2>&1 || echo "(file not found or empty)"
echo ""

echo "=== CONTENTS OF batch_1000_v2_errors.md ==="
if [ -f /mnt/pgdata/morphlex/reports/batch_1000_v2_errors.md ]; then
    cat /mnt/pgdata/morphlex/reports/batch_1000_v2_errors.md
else
    echo "(file does not exist)"
fi
echo ""

echo "=== STATS SECTION FROM batch_1000_v2 OUTPUT ==="
# Find the most recent task_output file from around 21:48-22:00
LATEST_OUTPUT=$(ls -t /mnt/pgdata/morphlex/reports/task_output_*.md 2>/dev/null | head -1)
if [ -n "$LATEST_OUTPUT" ]; then
    echo "Reading from: $LATEST_OUTPUT"
    echo ""
    # Extract just the stats section (after "=== STATS SUMMARY ===" to end)
    if grep -q "STATS SUMMARY\|Stats Summary\|=== OUTPUT FILES ===" "$LATEST_OUTPUT"; then
        sed -n '/STATS SUMMARY\|Stats Summary/,$p' "$LATEST_OUTPUT" | head -100
    else
        # If no stats section, show last 50 lines
        echo "(No stats section found, showing last 50 lines)"
        tail -50 "$LATEST_OUTPUT"
    fi
else
    echo "(no task_output file found)"
fi
echo ""

echo "=== ALL BATCH_1000_V2 FILES ==="
ls -la /mnt/pgdata/morphlex/reports/batch_1000_v2* 2>/dev/null || echo "(no v2 files found)"
ls -la /mnt/pgdata/morphlex/reports/pkl_rebuild_log.md 2>/dev/null || echo "(pkl_rebuild_log.md not found)"
echo ""

echo "=== TASK COMPLETE ==="
echo "End: $(date -Iseconds)"
echo "Git HEAD: $GIT_HEAD"
