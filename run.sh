#!/bin/bash
cd /mnt/pgdata/morphlex

# Force-sync with GitHub (handles dirty repo)
GIT_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
git fetch origin 2>&1
FETCH_EXIT=$?
git reset --hard origin/main 2>&1
RESET_EXIT=$?
GIT_AFTER=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

echo "[$(date)] Git sync: $GIT_BEFORE -> $GIT_AFTER (fetch=$FETCH_EXIT, reset=$RESET_EXIT)" >> /tmp/pipeline.log

# Check if there's a task to run (use next_task.sh, not pending_task.sh)
if [ -f next_task.sh ]; then
  # Compute md5 hash of task file content
  TASK_HASH=$(md5sum next_task.sh | cut -d' ' -f1)
  FLAG_FILE="/tmp/.task_done_${TASK_HASH}"

  # Check if this exact task already ran (prevents infinite loop after git reset)
  if [ -f "$FLAG_FILE" ]; then
    echo "[$(date)] Skipping next_task.sh (already ran, hash: $TASK_HASH)" >> /tmp/pipeline.log
  else
    echo "[$(date)] Running next_task.sh (hash: $TASK_HASH)" >> /tmp/pipeline.log
    source /mnt/pgdata/morphlex/venv/bin/activate
    TASK_OUTPUT=$(bash next_task.sh 2>&1)
    EXIT_CODE=$?

    # Create flag file to mark this task as done
    touch "$FLAG_FILE"

    if [ $EXIT_CODE -eq 0 ]; then STATUS="SUCCESS"; else STATUS="FAILED (exit code $EXIT_CODE)"; fi
    bash /mnt/pgdata/morphlex/slack_report.sh "*Task $STATUS*
$TASK_OUTPUT"
    echo "[$(date)] Task $STATUS" >> /tmp/pipeline.log
  fi
fi
