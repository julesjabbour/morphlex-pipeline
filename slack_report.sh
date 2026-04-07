#!/bin/bash
# slack_report.sh - Posts to Slack, handles any message size
# Completely rewritten for reliability - no incremental patches
# Usage: bash slack_report.sh /path/to/message.txt
#    OR: echo "message" | bash slack_report.sh

set -o pipefail
DEBUG_LOG="/tmp/morphlex_debug.log"

log() {
    echo "[$(date -Iseconds)] slack_report: $1" >> "$DEBUG_LOG"
}

# Load webhook URL
CONFIG="/mnt/pgdata/morphlex/.webhook_url"
if [ ! -f "$CONFIG" ]; then
    log "FATAL: No webhook config at $CONFIG"
    echo "ERROR: No webhook config at $CONFIG" >&2
    exit 1
fi
WEBHOOK_URL=$(cat "$CONFIG")

if [ -z "$WEBHOOK_URL" ] || [[ ! "$WEBHOOK_URL" =~ ^https:// ]]; then
    log "FATAL: Invalid webhook URL"
    echo "ERROR: Invalid webhook URL" >&2
    exit 1
fi

# Get message - either from file argument or stdin
if [ -n "$1" ] && [ -f "$1" ]; then
    INPUT_FILE="$1"
    log "Reading from file: $INPUT_FILE"
else
    # Read stdin to temp file
    INPUT_FILE="/tmp/slack_input_$$.txt"
    cat > "$INPUT_FILE"
    log "Read stdin to: $INPUT_FILE"
    CLEANUP_INPUT=1
fi

# Verify input
if [ ! -f "$INPUT_FILE" ]; then
    log "FATAL: Input file missing: $INPUT_FILE"
    echo "ERROR: Input file missing" >&2
    exit 1
fi

INPUT_SIZE=$(stat -c%s "$INPUT_FILE" 2>/dev/null || echo 0)
log "Input size: $INPUT_SIZE bytes"

if [ "$INPUT_SIZE" -eq 0 ]; then
    log "WARNING: Empty message, posting placeholder"
    echo "(empty output)" > "$INPUT_FILE"
fi

# Save to reports directory
REPORTS_DIR="/mnt/pgdata/morphlex/reports"
mkdir -p "$REPORTS_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="$REPORTS_DIR/task_output_${TIMESTAMP}.md"
cp "$INPUT_FILE" "$REPORT_FILE"
log "Saved to: $REPORT_FILE"

# Post to Slack using external Python script (no inline heredoc issues)
python3 /mnt/pgdata/morphlex/slack_post.py "$WEBHOOK_URL" "$INPUT_FILE"
PYTHON_EXIT=$?

if [ $PYTHON_EXIT -ne 0 ]; then
    log "Python poster failed with exit $PYTHON_EXIT"
    echo "ERROR: Slack post failed" >&2
fi

# Cleanup stdin temp file if we created it
if [ -n "$CLEANUP_INPUT" ]; then
    rm -f "$INPUT_FILE"
fi

log "Complete (exit $PYTHON_EXIT)"
exit $PYTHON_EXIT
