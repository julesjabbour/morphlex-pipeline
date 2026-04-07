#!/bin/bash
# Task: Show v2 batch results - pkl rebuild log, CSV headers, row count, sample data, stats

cd /mnt/pgdata/morphlex && source venv/bin/activate

GIT_HEAD=$(git rev-parse HEAD)
START_TIME=$(date -Iseconds)

echo "=== V2 BATCH RESULTS ==="
echo "Start: $START_TIME"
echo "Git HEAD: $GIT_HEAD"
echo ""

echo "=== 1. PKL REBUILD LOG ==="
if [ -f /mnt/pgdata/morphlex/reports/pkl_rebuild_log.md ]; then
    cat /mnt/pgdata/morphlex/reports/pkl_rebuild_log.md
else
    echo "(pkl_rebuild_log.md not found - checking for any pkl-related task output)"
    # Look for pkl rebuild output in task_output files
    LATEST=$(ls -t /mnt/pgdata/morphlex/reports/task_output_*.md 2>/dev/null | head -5)
    for f in $LATEST; do
        if grep -q "forward_translations.pkl\|pkl rebuild\|key count" "$f" 2>/dev/null; then
            echo "Found in: $f"
            grep -A5 -B2 "key count\|pkl\|forward_translations" "$f" | head -50
            break
        fi
    done
fi
echo ""

echo "=== 2. V2 CSV COLUMN HEADERS ==="
if [ -f /mnt/pgdata/morphlex/reports/batch_1000_v2_test.csv ]; then
    head -1 /mnt/pgdata/morphlex/reports/batch_1000_v2_test.csv
    echo ""
    echo "Column count: $(head -1 /mnt/pgdata/morphlex/reports/batch_1000_v2_test.csv | tr ',' '\n' | wc -l)"
else
    echo "(batch_1000_v2_test.csv not found)"
fi
echo ""

echo "=== 3. V2 CSV ROW COUNT ==="
if [ -f /mnt/pgdata/morphlex/reports/batch_1000_v2_test.csv ]; then
    ROWS=$(wc -l < /mnt/pgdata/morphlex/reports/batch_1000_v2_test.csv)
    echo "Total rows (including header): $ROWS"
    echo "Data rows: $((ROWS - 1))"
else
    echo "(batch_1000_v2_test.csv not found)"
fi
echo ""

echo "=== 4. SAMPLE DATA WITH NEW COLUMNS ==="
if [ -f /mnt/pgdata/morphlex/reports/batch_1000_v2_test.csv ]; then
    # Show first 10 data rows with all columns
    echo "First 10 rows:"
    head -11 /mnt/pgdata/morphlex/reports/batch_1000_v2_test.csv | column -t -s',' 2>/dev/null || head -11 /mnt/pgdata/morphlex/reports/batch_1000_v2_test.csv
    echo ""
    # Show sample of filled root, morph_type, compound_components columns
    echo "Sample rows with filled root column:"
    awk -F',' 'NR>1 && $5!="" {print NR": "$0}' /mnt/pgdata/morphlex/reports/batch_1000_v2_test.csv | head -5
    echo ""
    echo "Sample rows with filled morph_type:"
    awk -F',' 'NR>1 && $6!="" && $6!="UNKNOWN" {print NR": "$0}' /mnt/pgdata/morphlex/reports/batch_1000_v2_test.csv | head -5
    echo ""
    echo "Sample rows with compound_components:"
    awk -F',' 'NR>1 && $9!="" {print NR": "$0}' /mnt/pgdata/morphlex/reports/batch_1000_v2_test.csv | head -5
else
    echo "(batch_1000_v2_test.csv not found)"
fi
echo ""

echo "=== 5. STATS SUMMARY ==="
if [ -f /mnt/pgdata/morphlex/reports/batch_1000_v2_errors.md ]; then
    echo "--- From batch_1000_v2_errors.md ---"
    cat /mnt/pgdata/morphlex/reports/batch_1000_v2_errors.md
else
    echo "(batch_1000_v2_errors.md not found)"
fi
echo ""

# Also check for stats in task_output files
echo "--- From task_output files ---"
LATEST_OUTPUT=$(ls -t /mnt/pgdata/morphlex/reports/task_output_*.md 2>/dev/null | head -1)
if [ -n "$LATEST_OUTPUT" ]; then
    echo "Latest output file: $LATEST_OUTPUT"
    if grep -q "STATS SUMMARY\|Stats Summary\|Root fill rate\|morph_type" "$LATEST_OUTPUT"; then
        sed -n '/STATS SUMMARY\|Stats Summary\|=== OUTPUT/,$p' "$LATEST_OUTPUT" | head -80
    else
        echo "(No stats section found in $LATEST_OUTPUT)"
    fi
else
    echo "(no task_output file found)"
fi
echo ""

echo "=== 6. ALL BATCH FILES ==="
ls -la /mnt/pgdata/morphlex/reports/batch* /mnt/pgdata/morphlex/reports/pkl* 2>/dev/null || echo "(no batch or pkl files found)"
echo ""

echo "=== TASK COMPLETE ==="
echo "End: $(date -Iseconds)"
echo "Git HEAD: $GIT_HEAD"
