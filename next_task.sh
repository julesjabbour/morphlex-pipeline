#!/bin/bash
# BUILD CONCEPT MAP WITH ILI-BASED CROSS-LANGUAGE LOOKUP
# Timestamp: 2026-04-09-ili-fix
# Uses wn.synsets(ili=ili) to find matching synsets in ALL OMW languages

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== BUILD CONCEPT MAP (ILI-BASED) ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync the rewritten build_concept_map.py from git
git fetch origin > /dev/null 2>&1
git reset --hard origin/main > /dev/null 2>&1

echo "Running ILI-based concept map builder..."
python3 pipeline/build_concept_map.py

RESULT=$?

echo ""
echo "End: $(date -Iseconds)"
exit $RESULT
