#!/bin/bash
# Cron runner for morphlex pipeline
# Called every 2 minutes by cron
#
# Features:
# - flock to prevent concurrent runs
# - git fetch/reset to get latest code
# - Marker file system to prevent re-running same task

cd /mnt/pgdata/morphlex

LOCKFILE="/tmp/morphlex_run.lock"
LOGFILE="/tmp/pipeline.log"
MARKER_DIR="/tmp/morphlex_markers"

# Create marker directory if needed
mkdir -p "$MARKER_DIR"

# Lock: prevent concurrent runs. Exit silently if another instance is running.
exec 200>"$LOCKFILE"
if ! flock -n 200; then
  exit 0
fi

# Force-sync with GitHub (handles dirty repo)
GIT_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Fetch with retry (up to 4 attempts with exponential backoff)
FETCH_EXIT=1
for attempt in 1 2 3 4; do
  git fetch origin main 2>&1
  FETCH_EXIT=$?
  if [ $FETCH_EXIT -eq 0 ]; then
    break
  fi
  DELAY=$((2 ** attempt))
  echo "[$(date)] Git fetch attempt $attempt failed, retrying in ${DELAY}s..." >> "$LOGFILE"
  sleep $DELAY
done

if [ $FETCH_EXIT -ne 0 ]; then
  echo "[$(date)] Git fetch failed after 4 attempts" >> "$LOGFILE"
  exit 1
fi

git reset --hard origin/main 2>&1
RESET_EXIT=$?
GIT_AFTER=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

echo "[$(date)] Git sync: $GIT_BEFORE -> $GIT_AFTER (fetch=$FETCH_EXIT, reset=$RESET_EXIT)" >> "$LOGFILE"

# Exit silently if no task exists
if [ ! -f next_task.sh ]; then
  exit 0
fi

# Create marker based on next_task.sh content hash (survives git reset)
TASK_HASH=$(md5sum next_task.sh | cut -d' ' -f1)
MARKER_FILE="$MARKER_DIR/done_$TASK_HASH"

# Check if this exact task was already completed
if [ -f "$MARKER_FILE" ]; then
  echo "[$(date)] Task already done (marker exists for hash $TASK_HASH)" >> "$LOGFILE"
  exit 0
fi

echo "[$(date)] Running next_task.sh (hash=$TASK_HASH)" >> "$LOGFILE"
source /mnt/pgdata/morphlex/venv/bin/activate
TASK_OUTPUT=$(bash next_task.sh 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
  STATUS="SUCCESS"
  # Write marker file to prevent re-running (survives git reset)
  echo "$(date -Iseconds)" > "$MARKER_FILE"
  echo "[$(date)] Created marker file: $MARKER_FILE" >> "$LOGFILE"
else
  STATUS="FAILED (exit code $EXIT_CODE)"
  # On failure, also write marker to prevent infinite loop (different prefix)
  echo "$(date -Iseconds) - exit $EXIT_CODE" > "$MARKER_DIR/failed_$TASK_HASH"
fi

bash /mnt/pgdata/morphlex/slack_report.sh "*Task $STATUS*
$TASK_OUTPUT"
echo "[$(date)] Task $STATUS" >> "$LOGFILE"
