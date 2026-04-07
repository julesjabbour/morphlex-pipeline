#!/bin/bash
# EMERGENCY: Kill all morphlex processes and exit
# This stops the 8-hour zombie loop
pkill -9 -f "build_forward_translations" 2>/dev/null
pkill -9 -f "python3.*morphlex" 2>/dev/null
pkill -9 -f "next_task" 2>/dev/null
# Remove any stale locks
rm -f /tmp/morphlex_run.lock
exit 0
