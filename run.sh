#!/bin/bash
cd /mnt/pgdata/morphlex

# Force-sync with GitHub (handles dirty repo from completed_task.sh)
git fetch origin && git reset --hard origin/main

# Check if there's a pending task
if [ -f pending_task.sh ]; then
  echo "[$(date)] Running pending_task.sh" >> /tmp/pipeline.log
  source /mnt/pgdata/morphlex/venv/bin/activate
  TASK_OUTPUT=$(bash pending_task.sh 2>&1)
  EXIT_CODE=$?
  mv pending_task.sh completed_task.sh
  if [ $EXIT_CODE -eq 0 ]; then STATUS="SUCCESS"; else STATUS="FAILED (exit code $EXIT_CODE)"; fi
  bash /mnt/pgdata/morphlex/slack_report.sh "*Task $STATUS*
$TASK_OUTPUT"
  echo "[$(date)] Task $STATUS" >> /tmp/pipeline.log
fi
