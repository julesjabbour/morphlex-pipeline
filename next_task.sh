#!/bin/bash
# Task: Retrieve pkl rebuild report from ~16:44-16:53 UTC today
# Session: Show key count, file size, and any errors/warnings

cd /mnt/pgdata/morphlex && source venv/bin/activate

GIT_HEAD=$(git rev-parse HEAD)
START_TIME=$(date -Iseconds)

echo "=== PKL REBUILD REPORT RETRIEVAL ==="
echo "Start: $START_TIME"
echo "Git HEAD: $GIT_HEAD"
echo ""

# ============================================================
# PART 1: LIST ALL REPORT FILES FROM TODAY
# ============================================================

echo "============================================================"
echo "PART 1: All report files from today (with timestamps)"
echo "============================================================"
echo ""

REPORTS_DIR="/mnt/pgdata/morphlex/reports"
echo "Files in $REPORTS_DIR:"
ls -la "$REPORTS_DIR"/ 2>/dev/null | grep "Apr  7" || echo "  (no files from today)"
echo ""

# ============================================================
# PART 2: FIND PKL-RELATED REPORT FROM 16:44-16:53 WINDOW
# ============================================================

echo "============================================================"
echo "PART 2: Finding pkl rebuild report from 16:44-16:53 UTC"
echo "============================================================"
echo ""

# Find files modified between 16:40 and 17:00 today
echo "Files modified between 16:40-17:00 UTC today:"
find "$REPORTS_DIR" -type f -newermt "2026-04-07 16:40:00" ! -newermt "2026-04-07 17:00:00" -ls 2>/dev/null
echo ""

# Look for any file with pkl, forward_translation, or rebuild in name
echo "Files with pkl/forward/rebuild in name:"
ls -la "$REPORTS_DIR"/*pkl* "$REPORTS_DIR"/*forward* "$REPORTS_DIR"/*rebuild* 2>/dev/null || echo "  (none found with those names)"
echo ""

# ============================================================
# PART 3: CAT ALL .md FILES FROM 16:40-17:00 WINDOW
# ============================================================

echo "============================================================"
echo "PART 3: Contents of .md files from 16:40-17:00 UTC window"
echo "============================================================"
echo ""

for f in $(find "$REPORTS_DIR" -name "*.md" -type f -newermt "2026-04-07 16:40:00" ! -newermt "2026-04-07 17:00:00" 2>/dev/null); do
    echo "--- FILE: $f ---"
    echo "Size: $(stat -c%s "$f") bytes"
    echo "Modified: $(stat -c%y "$f")"
    echo ""
    cat "$f"
    echo ""
    echo "--- END OF FILE ---"
    echo ""
done

# Also check for any .txt or .log files in that window
for f in $(find "$REPORTS_DIR" -type f \( -name "*.txt" -o -name "*.log" \) -newermt "2026-04-07 16:40:00" ! -newermt "2026-04-07 17:00:00" 2>/dev/null); do
    echo "--- FILE: $f ---"
    echo "Size: $(stat -c%s "$f") bytes"
    echo "Modified: $(stat -c%y "$f")"
    echo ""
    cat "$f"
    echo ""
    echo "--- END OF FILE ---"
    echo ""
done

# ============================================================
# PART 4: CURRENT PKL FILE STATS
# ============================================================

echo "============================================================"
echo "PART 4: Current forward_translations.pkl stats"
echo "============================================================"
echo ""

PKL_FILE="/mnt/pgdata/morphlex/data/forward_translations.pkl"
if [ -f "$PKL_FILE" ]; then
    echo "File: $PKL_FILE"
    echo "Size: $(stat -c%s "$PKL_FILE") bytes ($(numfmt --to=iec-i --suffix=B $(stat -c%s "$PKL_FILE")))"
    echo "Modified: $(stat -c%y "$PKL_FILE")"
    echo ""

    # Get key count via Python
    echo "Key count from Python:"
    python3 -c "
import pickle
with open('$PKL_FILE', 'rb') as f:
    data = pickle.load(f)
print(f'Total keys: {len(data)}')
print(f'Type: {type(data).__name__}')
if len(data) > 0:
    sample_key = list(data.keys())[0]
    print(f'Sample key: {sample_key!r}')
    print(f'Sample value type: {type(data[sample_key]).__name__}')
"
else
    echo "PKL file not found at $PKL_FILE"
fi

echo ""

# ============================================================
# PART 5: CHECK CRON LOG FOR PKL REBUILD OUTPUT
# ============================================================

echo "============================================================"
echo "PART 5: Cron log entries from 16:40-17:00 UTC"
echo "============================================================"
echo ""

if [ -f /tmp/morphlex_cron.log ]; then
    echo "Searching cron log for 16:4* and 16:5* entries..."
    grep -E "^2026-04-07T16:4|^2026-04-07T16:5|16:4|16:5" /tmp/morphlex_cron.log | tail -200
else
    echo "Cron log not found"
fi

echo ""

END_TIME=$(date -Iseconds)
echo "============================================================"
echo "RETRIEVAL COMPLETE"
echo "============================================================"
echo ""
echo "Start: $START_TIME"
echo "End:   $END_TIME"
echo "Git HEAD: $GIT_HEAD"
