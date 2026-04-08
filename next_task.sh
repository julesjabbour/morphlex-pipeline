#!/bin/bash
# HARDCODING AUDIT TEST - 270 NEW WORDS
# Timestamp: 2026-04-08-audit-test
# Tests all language adapters with completely new words never seen before.
# If an adapter is hardcoded, it will fail on these new words.

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== HARDCODING AUDIT TEST ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code first
echo "--- Syncing code from origin/main ---"
git fetch origin && git reset --hard origin/main
echo "Now at: $(git rev-parse HEAD)"
echo ""

# Run the audit test
echo "--- Running 270-word audit test ---"
python3 pipeline/audit_test.py 2>&1

echo ""
echo "=== AUDIT TASK COMPLETE ==="
echo "End: $(date -Iseconds)"
