cd /mnt/pgdata/morphlex

echo "=== TASK RUNNER DIAGNOSTIC ==="
echo "--- Cron status ---"
crontab -l 2>&1
echo ""
echo "--- Flag files in /tmp ---"
ls -la /tmp/.task_done_* 2>&1
echo ""
echo "--- Current next_task.sh hash ---"
md5sum next_task.sh 2>&1
echo ""
echo "--- Any running python3 processes ---"
ps aux | grep python3 | grep -v grep
echo ""
echo "--- Last 10 lines of pipeline log ---"
tail -10 /tmp/pipeline.log 2>&1
echo "=== DIAGNOSTIC COMPLETE ==="
