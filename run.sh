#!/bin/bash
# NUCLEAR STOP: Kill all processes AND disable cron
# 1. Kill ALL morphlex-related processes
pkill -9 -f "build_forward_translations" 2>/dev/null
pkill -9 -f "python3.*morphlex" 2>/dev/null
pkill -9 -f "next_task" 2>/dev/null
pkill -9 -f "slack_report" 2>/dev/null
pkill -9 -f "curl.*hooks.slack" 2>/dev/null
# 2. Disable the cron so it stops firing entirely
crontab -r 2>/dev/null
# 3. Leave a marker so we know it worked
echo "CRON DISABLED AT $(date -u)" > /tmp/morphlex_cron_disabled
exit 0
