#!/bin/bash
# Task: Verify Slack fix + show v2 batch results
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== SLACK FIX VERIFICATION ==="
echo "This message proves the universal fix works."
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Time: $(date -Iseconds)"
echo ""

echo "=== V2 BATCH RESULTS ==="
echo ""

echo "--- PKL Rebuild Log ---"
if [ -f reports/pkl_rebuild_log.md ]; then
    cat reports/pkl_rebuild_log.md
else
    echo "(not found - checking task outputs)"
    ls -la reports/task_output_*.md 2>/dev/null | tail -5
fi
echo ""

echo "--- V2 CSV Info ---"
CSV="reports/batch_1000_v2_test.csv"
if [ -f "$CSV" ]; then
    echo "Columns: $(head -1 $CSV)"
    echo "Column count: $(head -1 $CSV | tr ',' '\n' | wc -l)"
    echo "Row count: $(wc -l < $CSV)"
    echo ""
    echo "First 5 data rows:"
    head -6 "$CSV" | tail -5
    echo ""
    echo "Rows with filled root column (sample):"
    awk -F',' 'NR>1 && $5!="" {print}' "$CSV" | head -3
else
    echo "(batch_1000_v2_test.csv not found)"
    echo "Available batch files:"
    ls -la reports/batch* 2>/dev/null || echo "none"
fi
echo ""

echo "--- V2 Errors/Stats ---"
if [ -f reports/batch_1000_v2_errors.md ]; then
    cat reports/batch_1000_v2_errors.md
else
    echo "(batch_1000_v2_errors.md not found)"
fi
echo ""

echo "--- Debug Logs (last 10 lines) ---"
echo "/tmp/morphlex_debug.log:"
tail -10 /tmp/morphlex_debug.log 2>/dev/null || echo "(not found)"
echo ""

echo "=== TASK COMPLETE ==="
echo "End: $(date -Iseconds)"
