#!/bin/bash
cd /mnt/pgdata/morphlex

LOCKFILE="/tmp/morphlex_run.lock"
LOGFILE="/tmp/pipeline.log"

# Lock: prevent concurrent runs. Exit silently if another instance is running.
exec 200>"$LOCKFILE"
if ! flock -n 200; then
  exit 0
fi

# Force-sync with GitHub (handles dirty repo)
GIT_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
git fetch origin 2>&1
FETCH_EXIT=$?
git reset --hard origin/main 2>&1
RESET_EXIT=$?
GIT_AFTER=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

echo "[$(date)] Git sync: $GIT_BEFORE -> $GIT_AFTER (fetch=$FETCH_EXIT, reset=$RESET_EXIT)" >> "$LOGFILE"

# Exit silently if no task exists
if [ ! -f next_task.sh ]; then
  exit 0
fi

echo "[$(date)] Running next_task.sh" >> "$LOGFILE"
source /mnt/pgdata/morphlex/venv/bin/activate
TASK_OUTPUT=$(bash next_task.sh 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
  STATUS="SUCCESS"
  # Rename to .done so it won't re-run
  mv next_task.sh next_task.sh.done
  git add next_task.sh.done 2>/dev/null
  git rm --cached next_task.sh 2>/dev/null
  git commit -m "Mark task done: $(date -Iseconds)" 2>/dev/null
  git push origin main 2>/dev/null
else
  STATUS="FAILED (exit code $EXIT_CODE)"
  # On failure, also rename to prevent infinite loop
  mv next_task.sh "next_task.sh.failed.$(date +%s)"
fi

bash /mnt/pgdata/morphlex/slack_report.sh "*Task $STATUS*
$TASK_OUTPUT"
echo "[$(date)] Task $STATUS" >> "$LOGFILE"
