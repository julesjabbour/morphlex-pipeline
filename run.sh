#!/bin/bash
# Permanent run.sh with all safeguards (Session 44 rules)
# 1. flock to prevent concurrent runs
# 2. Marker file to prevent re-running same task
# 3. Silent exit when no task exists

# Acquire lock - exit silently if another instance is running
exec 200>/tmp/morphlex_run.lock
flock -n 200 || exit 0

cd /mnt/pgdata/morphlex

# Sync with remote
git fetch origin main 2>>/tmp/morphlex_debug.log && git reset --hard origin/main 2>>/tmp/morphlex_debug.log

# If next_task.sh doesn't exist, exit silently
[ -f next_task.sh ] || exit 0

# Calculate hash of current task
HASH=$(md5sum next_task.sh | cut -d' ' -f1)
MARKER_DIR="/tmp/morphlex_markers"
MARKER_FILE="$MARKER_DIR/done_$HASH"

# If this task was already run, exit silently
mkdir -p "$MARKER_DIR"
[ -f "$MARKER_FILE" ] && exit 0

# Activate venv and run the task
source venv/bin/activate

# Use temp file for output - avoids bash variable limits on large outputs
# (storing megabytes in $OUTPUT can fail silently, causing empty Slack posts)
TMPFILE=$(mktemp /tmp/morphlex_output.XXXXXX)
trap "rm -f '$TMPFILE'" EXIT

START_TIME=$(date -Iseconds)
bash next_task.sh > "$TMPFILE" 2>&1
EXIT_CODE=$?

# Create marker ALWAYS (regardless of success/failure) - prevents infinite loops
touch "$MARKER_FILE"

# Post to Slack via stdin - pipe temp file directly (never store in variable)
{
    if [ $EXIT_CODE -eq 0 ]; then
        echo "*Task SUCCESS*"
    else
        echo "*Task FAILED (exit code $EXIT_CODE)*"
    fi
    cat "$TMPFILE"
} | bash slack_report.sh
