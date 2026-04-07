#!/bin/bash
# run.sh - Cron entrypoint with all Session 44 safeguards
# Completely rewritten for reliability - no incremental patches

set -o pipefail
DEBUG_LOG="/tmp/morphlex_debug.log"

log() {
    echo "[$(date -Iseconds)] $1" >> "$DEBUG_LOG"
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
if ! git fetch origin main 2>>"$DEBUG_LOG"; then
    sleep 2
    git fetch origin main 2>>"$DEBUG_LOG" || { log "git fetch failed"; exit 1; }
fi
git reset --hard origin/main 2>>"$DEBUG_LOG" || { log "git reset failed"; exit 1; }
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
source venv/bin/activate || { log "venv activation failed"; exit 1; }

# Run task and capture output to file (not variable - avoids size limits)
TASK_OUTPUT="/tmp/morphlex_task_output_$$.txt"
log "Running task, output to $TASK_OUTPUT"

START_TIME=$(date -Iseconds)
GIT_HEAD=$(git rev-parse HEAD)

# Run task
bash next_task.sh > "$TASK_OUTPUT" 2>&1
EXIT_CODE=$?

log "Task finished with exit code $EXIT_CODE"

# Create marker IMMEDIATELY (prevents re-run on failure)
touch "$MARKER_FILE"
log "Marker created: $MARKER_FILE"

# Check output file
if [ ! -f "$TASK_OUTPUT" ]; then
    log "FATAL: Task output file missing"
    echo "ERROR: Task output file missing" | bash slack_report.sh
    exit 1
fi

OUTPUT_SIZE=$(stat -c%s "$TASK_OUTPUT" 2>/dev/null || echo 0)
log "Output size: $OUTPUT_SIZE bytes"

if [ "$OUTPUT_SIZE" -eq 0 ]; then
    log "WARNING: Task produced no output"
fi

# Build message with header
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
} > "${TASK_OUTPUT}.final"

FINAL_SIZE=$(stat -c%s "${TASK_OUTPUT}.final" 2>/dev/null || echo 0)
log "Final message size: $FINAL_SIZE bytes"

# Post to Slack (pass file path as argument - no piping, no variable size limits)
bash slack_report.sh "${TASK_OUTPUT}.final"
SLACK_EXIT=$?

log "slack_report.sh exit code: $SLACK_EXIT"

# Cleanup
rm -f "$TASK_OUTPUT" "${TASK_OUTPUT}.final"
log "=== run.sh complete ==="
