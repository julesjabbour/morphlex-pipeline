#!/bin/bash
# Task: Diagnose why commit 3aafb44 ran but didn't post to Slack
# Session: Fetch cron logs, report files, and test webhook

cd /mnt/pgdata/morphlex && source venv/bin/activate

GIT_HEAD=$(git rev-parse HEAD)
START_TIME=$(date -Iseconds)

echo "=== SLACK POST DIAGNOSTIC ==="
echo "Start: $START_TIME"
echo "Git HEAD: $GIT_HEAD"
echo ""

# ============================================================
# PART 1: CRON LOG - LAST 100 LINES
# ============================================================

echo "============================================================"
echo "PART 1: /tmp/morphlex_cron.log (last 100 lines)"
echo "============================================================"
echo ""

if [ -f /tmp/morphlex_cron.log ]; then
    tail -100 /tmp/morphlex_cron.log
else
    echo "File not found: /tmp/morphlex_cron.log"
fi

echo ""

# ============================================================
# PART 2: DEBUG LOG
# ============================================================

echo "============================================================"
echo "PART 2: /tmp/morphlex_debug.log (last 50 lines)"
echo "============================================================"
echo ""

if [ -f /tmp/morphlex_debug.log ]; then
    tail -50 /tmp/morphlex_debug.log
else
    echo "File not found: /tmp/morphlex_debug.log"
fi

echo ""

# ============================================================
# PART 3: REPORT FILES FROM TODAY
# ============================================================

echo "============================================================"
echo "PART 3: Report files from /mnt/pgdata/morphlex/reports/"
echo "============================================================"
echo ""

REPORTS_DIR="/mnt/pgdata/morphlex/reports"

echo "Files in reports dir (sorted by date):"
ls -lt "$REPORTS_DIR" 2>/dev/null || echo "  (directory not found or empty)"
echo ""

# Check for batch_1000_test.csv
echo "--- batch_1000_test.csv (first 50 lines if exists) ---"
if [ -f "$REPORTS_DIR/batch_1000_test.csv" ]; then
    echo "File size: $(stat -c%s "$REPORTS_DIR/batch_1000_test.csv") bytes"
    echo "Modified: $(stat -c%y "$REPORTS_DIR/batch_1000_test.csv")"
    echo ""
    head -50 "$REPORTS_DIR/batch_1000_test.csv"
    echo ""
    echo "(showing first 50 lines only)"
else
    echo "File not found: batch_1000_test.csv"
fi

echo ""

# Check for batch_1000_errors.md
echo "--- batch_1000_errors.md (full contents if exists) ---"
if [ -f "$REPORTS_DIR/batch_1000_errors.md" ]; then
    echo "File size: $(stat -c%s "$REPORTS_DIR/batch_1000_errors.md") bytes"
    echo "Modified: $(stat -c%y "$REPORTS_DIR/batch_1000_errors.md")"
    echo ""
    cat "$REPORTS_DIR/batch_1000_errors.md"
else
    echo "File not found: batch_1000_errors.md"
fi

echo ""

# ============================================================
# PART 4: WEBHOOK URL CHECK
# ============================================================

echo "============================================================"
echo "PART 4: Webhook URL validation"
echo "============================================================"
echo ""

WEBHOOK_FILE="/mnt/pgdata/morphlex/.webhook_url"
if [ -f "$WEBHOOK_FILE" ]; then
    URL=$(cat "$WEBHOOK_FILE")
    echo "Webhook file exists: YES"
    echo "URL length: ${#URL} characters"
    echo "URL starts with https://: $(if [[ "$URL" == https://* ]]; then echo YES; else echo NO; fi)"
    # Show first 30 chars only (safe portion)
    echo "URL prefix: ${URL:0:30}..."

    # Test the webhook with a simple ping
    echo ""
    echo "Testing webhook with curl..."
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" \
        -d '{"text":"🔍 Webhook test from diagnostic task"}' \
        "$URL" 2>&1)
    echo "HTTP response code: $RESPONSE"

    if [ "$RESPONSE" = "200" ]; then
        echo "Webhook test: SUCCESS"
    else
        echo "Webhook test: FAILED"
    fi
else
    echo "Webhook file NOT FOUND at $WEBHOOK_FILE"
    echo "This is likely the root cause - no webhook URL configured!"
fi

echo ""

# ============================================================
# PART 5: MARKER FILE STATUS
# ============================================================

echo "============================================================"
echo "PART 5: Marker file status"
echo "============================================================"
echo ""

echo "Marker directory contents:"
ls -la /tmp/morphlex_markers/ 2>/dev/null || echo "  (directory not found)"
echo ""

# Check for marker from commit 3aafb44
TASK_3AAFB44_HASH="77197b2ae2ae3cb59724d8f2d7a9e3bd"  # Approximate hash
echo "Known marker hashes:"
for f in /tmp/morphlex_markers/done_*; do
    if [ -f "$f" ]; then
        basename "$f"
        stat -c "  Created: %y" "$f"
    fi
done

echo ""

END_TIME=$(date -Iseconds)
echo "============================================================"
echo "DIAGNOSTIC COMPLETE"
echo "============================================================"
echo ""
echo "Start: $START_TIME"
echo "End:   $END_TIME"
echo "Git HEAD: $GIT_HEAD"
echo ""
echo "If this message appears in Slack, the slack_report.sh fix is working!"
