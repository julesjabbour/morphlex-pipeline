#!/bin/bash
# run.sh - Cron entrypoint with all Session 44 safeguards
# Full rewrite with inline Slack posting and visible error logging

set -o pipefail
DEBUG_LOG="/tmp/morphlex_debug.log"
REPORTS_DIR="/mnt/pgdata/morphlex/reports"

# FIX: chown root-owned lock and log files to cron user BEFORE any I/O
# These may have been created by an earlier sudo run
CRON_USER=$(whoami)
if [ -f /tmp/morphlex_run.lock ] && [ "$(stat -c '%U' /tmp/morphlex_run.lock 2>/dev/null)" != "$CRON_USER" ]; then
    sudo chown "$CRON_USER:$CRON_USER" /tmp/morphlex_run.lock 2>/dev/null || true
fi
if [ -f "$DEBUG_LOG" ] && [ "$(stat -c '%U' "$DEBUG_LOG" 2>/dev/null)" != "$CRON_USER" ]; then
    sudo chown "$CRON_USER:$CRON_USER" "$DEBUG_LOG" 2>/dev/null || true
fi

log() {
    echo "[$(date -Iseconds)] $1" | tee -a "$DEBUG_LOG"
}

log "=== run.sh started ==="

# SAFEGUARD 1: flock to prevent concurrent runs
exec 200>/tmp/morphlex_run.lock
if ! flock -n 200; then
    log "Another instance running, exiting"
    exit 0
fi

cd /mnt/pgdata/morphlex || { log "FATAL: cd failed"; exit 1; }

# Sync with remote (retry once on failure)
log "Fetching from origin..."
if ! git fetch origin main 2>&1 | tee -a "$DEBUG_LOG"; then
    sleep 2
    if ! git fetch origin main 2>&1 | tee -a "$DEBUG_LOG"; then
        log "FATAL: git fetch failed"
        exit 1
    fi
fi

if ! git reset --hard origin/main 2>&1 | tee -a "$DEBUG_LOG"; then
    log "FATAL: git reset failed"
    exit 1
fi

GIT_HEAD=$(git rev-parse HEAD)
log "Git sync complete: $(git rev-parse --short HEAD)"

# SAFEGUARD 3: Silent exit if no task
if [ ! -f next_task.sh ]; then
    log "No next_task.sh, exiting"
    exit 0
fi

# SAFEGUARD 2: Marker file to prevent re-running same task
HASH=$(md5sum next_task.sh | cut -d' ' -f1)
MARKER_DIR="/tmp/morphlex_markers"
MARKER_FILE="$MARKER_DIR/done_$HASH"
mkdir -p "$MARKER_DIR"

if [ -f "$MARKER_FILE" ]; then
    log "Task already run (marker exists), exiting"
    exit 0
fi

# Activate venv
if ! source venv/bin/activate; then
    log "FATAL: venv activation failed"
    exit 1
fi

# Run task and capture output to file
TASK_OUTPUT="/tmp/morphlex_task_output_$$.txt"
log "Running task, output to $TASK_OUTPUT"

START_TIME=$(date -Iseconds)

# Run task - capture stdout and stderr
bash next_task.sh > "$TASK_OUTPUT" 2>&1
EXIT_CODE=$?

log "Task finished with exit code $EXIT_CODE"

# Create marker IMMEDIATELY (prevents re-run on failure)
touch "$MARKER_FILE"
log "Marker created: $MARKER_FILE"

# Check output file
if [ ! -f "$TASK_OUTPUT" ]; then
    log "FATAL: Task output file missing"
    TASK_OUTPUT="/tmp/morphlex_fallback_$$.txt"
    echo "ERROR: Task output file was not created" > "$TASK_OUTPUT"
fi

OUTPUT_SIZE=$(stat -c%s "$TASK_OUTPUT" 2>/dev/null || echo 0)
log "Output size: $OUTPUT_SIZE bytes"

# Build final message with header
FINAL_OUTPUT="/tmp/morphlex_final_$$.txt"
{
    if [ $EXIT_CODE -eq 0 ]; then
        echo "*Task SUCCESS*"
    else
        echo "*Task FAILED (exit $EXIT_CODE)*"
    fi
    echo "Git: $GIT_HEAD"
    echo "Start: $START_TIME"
    echo "---"
    cat "$TASK_OUTPUT"
} > "$FINAL_OUTPUT"

FINAL_SIZE=$(stat -c%s "$FINAL_OUTPUT" 2>/dev/null || echo 0)
log "Final message size: $FINAL_SIZE bytes"

# Save to reports directory
mkdir -p "$REPORTS_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="$REPORTS_DIR/task_output_${TIMESTAMP}.md"
cp "$FINAL_OUTPUT" "$REPORT_FILE"
log "Saved report to: $REPORT_FILE"

# ============================================================================
# SLACK POSTING - INLINE WITH FULL ERROR LOGGING
# ============================================================================

WEBHOOK_CONFIG="/mnt/pgdata/morphlex/.webhook_url"

# Check webhook config exists
if [ ! -f "$WEBHOOK_CONFIG" ]; then
    log "ERROR: No webhook config at $WEBHOOK_CONFIG"
    echo "SLACK ERROR: No webhook config file found at $WEBHOOK_CONFIG"
    rm -f "$TASK_OUTPUT" "$FINAL_OUTPUT"
    exit 1
fi

WEBHOOK_URL=$(cat "$WEBHOOK_CONFIG")

# Validate webhook URL
if [ -z "$WEBHOOK_URL" ]; then
    log "ERROR: Webhook URL is empty"
    echo "SLACK ERROR: Webhook URL is empty in config file"
    rm -f "$TASK_OUTPUT" "$FINAL_OUTPUT"
    exit 1
fi

if [[ ! "$WEBHOOK_URL" =~ ^https:// ]]; then
    log "ERROR: Webhook URL does not start with https://"
    echo "SLACK ERROR: Invalid webhook URL format (must start with https://)"
    rm -f "$TASK_OUTPUT" "$FINAL_OUTPUT"
    exit 1
fi

log "Webhook URL loaded (${#WEBHOOK_URL} chars)"

# Read message content
MESSAGE_TEXT=$(cat "$FINAL_OUTPUT")
MESSAGE_LEN=${#MESSAGE_TEXT}
log "Message length: $MESSAGE_LEN chars"

# Function to post a single chunk to Slack with full error logging
post_to_slack() {
    local text="$1"
    local chunk_num="$2"
    local total_chunks="$3"

    # Escape text for JSON: escape backslashes, quotes, newlines, tabs
    local escaped_text
    escaped_text=$(printf '%s' "$text" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')

    # Build JSON payload
    local payload="{\"text\": $escaped_text}"

    log "Posting chunk $chunk_num/$total_chunks (${#text} chars)"

    # Make curl request with full error capture
    local response_file="/tmp/slack_response_$$.txt"
    local http_code

    http_code=$(curl -s -w "%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$payload" \
        --connect-timeout 30 \
        --max-time 60 \
        -o "$response_file" \
        "$WEBHOOK_URL" 2>&1)

    local curl_exit=$?
    local response_body=""
    if [ -f "$response_file" ]; then
        response_body=$(cat "$response_file")
        rm -f "$response_file"
    fi

    # Log full details
    log "Curl exit code: $curl_exit, HTTP status: $http_code"

    if [ $curl_exit -ne 0 ]; then
        log "ERROR: curl failed with exit code $curl_exit"
        echo "SLACK ERROR: curl failed (exit $curl_exit)"
        echo "  HTTP code: $http_code"
        echo "  Response: $response_body"
        return 1
    fi

    if [ "$http_code" != "200" ]; then
        log "ERROR: Slack returned HTTP $http_code"
        log "Response body: $response_body"
        echo "SLACK ERROR: HTTP $http_code"
        echo "  Response body: $response_body"
        return 1
    fi

    log "Chunk $chunk_num posted successfully"
    return 0
}

# Split message if needed (Slack limit is ~4000 chars, use 3500 for safety)
MAX_CHARS=3500
SLACK_SUCCESS=true

if [ $MESSAGE_LEN -le $MAX_CHARS ]; then
    # Single chunk
    if ! post_to_slack "$MESSAGE_TEXT" 1 1; then
        SLACK_SUCCESS=false
    fi
else
    # Split into chunks at line boundaries
    log "Message too long ($MESSAGE_LEN chars), splitting into chunks"

    # Use Python to split reliably
    CHUNKS_FILE="/tmp/slack_chunks_$$.txt"
    python3 << 'PYEOF' - "$FINAL_OUTPUT" "$CHUNKS_FILE" $MAX_CHARS
import sys
import json

input_file = sys.argv[1]
output_file = sys.argv[2]
max_chars = int(sys.argv[3])

with open(input_file, 'r', encoding='utf-8', errors='replace') as f:
    text = f.read()

chunks = []
lines = text.split('\n')
current_chunk = []
current_len = 0

for line in lines:
    line_len = len(line) + 1  # +1 for newline

    if current_len + line_len > max_chars and current_chunk:
        chunks.append('\n'.join(current_chunk))
        current_chunk = []
        current_len = 0

    # Handle single lines longer than max
    if line_len > max_chars:
        for i in range(0, len(line), max_chars - 100):
            chunks.append(line[i:i + max_chars - 100])
    else:
        current_chunk.append(line)
        current_len += line_len

if current_chunk:
    chunks.append('\n'.join(current_chunk))

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(chunks, f)

print(f"Split into {len(chunks)} chunks")
PYEOF

    PYTHON_EXIT=$?
    if [ $PYTHON_EXIT -ne 0 ]; then
        log "ERROR: Python chunk splitter failed with exit $PYTHON_EXIT"
        echo "SLACK ERROR: Failed to split message into chunks"
        SLACK_SUCCESS=false
    else
        # Read and post chunks
        TOTAL_CHUNKS=$(python3 -c "import json; print(len(json.load(open('$CHUNKS_FILE'))))")
        log "Split into $TOTAL_CHUNKS chunks"

        for i in $(seq 0 $((TOTAL_CHUNKS - 1))); do
            CHUNK_TEXT=$(python3 -c "import json; chunks=json.load(open('$CHUNKS_FILE')); print(chunks[$i])")
            CHUNK_NUM=$((i + 1))

            # Add part header if multiple chunks
            if [ $TOTAL_CHUNKS -gt 1 ]; then
                CHUNK_TEXT="[Part $CHUNK_NUM/$TOTAL_CHUNKS]"$'\n'"$CHUNK_TEXT"
            fi

            if ! post_to_slack "$CHUNK_TEXT" $CHUNK_NUM $TOTAL_CHUNKS; then
                SLACK_SUCCESS=false
                log "Failed to post chunk $CHUNK_NUM/$TOTAL_CHUNKS"
            fi

            # Small delay between chunks
            if [ $CHUNK_NUM -lt $TOTAL_CHUNKS ]; then
                sleep 1
            fi
        done

        rm -f "$CHUNKS_FILE"
    fi
fi

# Final status
if [ "$SLACK_SUCCESS" = true ]; then
    log "Slack posting complete - SUCCESS"
    echo "Slack: Posted successfully ($MESSAGE_LEN chars)"
else
    log "Slack posting complete - FAILED"
    echo "Slack: FAILED to post (see errors above)"
    echo "Report saved to: $REPORT_FILE"
fi

# Cleanup
rm -f "$TASK_OUTPUT" "$FINAL_OUTPUT"

log "=== run.sh complete ==="
