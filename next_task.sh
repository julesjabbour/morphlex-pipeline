#!/bin/bash
# DIAGNOSTIC: CHECK AGWN DOWNLOAD STATUS
# Timestamp: 2026-04-10-agwn-diagnostic-v1

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== AGWN DOWNLOAD DIAGNOSTIC ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

echo "======================================================================"
echo "CHECK 1: LIST /mnt/pgdata/morphlex/data/agwn/"
echo "======================================================================"
ls -la /mnt/pgdata/morphlex/data/agwn/
echo ""

echo "======================================================================"
echo "CHECK 2: CHECKPOINT FILE"
echo "======================================================================"
if [ -f /mnt/pgdata/morphlex/data/agwn/harvard_agwn_checkpoint.json ]; then
    echo "harvard_agwn_checkpoint.json EXISTS - full contents:"
    cat /mnt/pgdata/morphlex/data/agwn/harvard_agwn_checkpoint.json
else
    echo "harvard_agwn_checkpoint.json does NOT exist"
fi
echo ""

echo "======================================================================"
echo "CHECK 3: LEMMAS FILE"
echo "======================================================================"
if [ -f /mnt/pgdata/morphlex/data/agwn/harvard_agwn_lemmas.json ]; then
    echo "harvard_agwn_lemmas.json EXISTS"
    ls -la /mnt/pgdata/morphlex/data/agwn/harvard_agwn_lemmas.json
    echo ""
    echo "Counting lemmas:"
    python3 -c "import json; d=json.load(open('/mnt/pgdata/morphlex/data/agwn/harvard_agwn_lemmas.json')); print('Total lemmas:', len(d))"
else
    echo "harvard_agwn_lemmas.json does NOT exist"
fi
echo ""

echo "======================================================================"
echo "CHECK 4: DEBUG LOG"
echo "======================================================================"
if [ -f /tmp/morphlex_debug.log ]; then
    echo "Last 50 lines of /tmp/morphlex_debug.log:"
    tail -50 /tmp/morphlex_debug.log
else
    echo "/tmp/morphlex_debug.log does NOT exist"
fi
echo ""

echo "======================================================================"
echo "CHECK 5: MARKER FILES"
echo "======================================================================"
ls -la /tmp/morphlex_markers/ 2>/dev/null || ls -la /tmp/morphlex* 2>/dev/null || echo "No morphlex marker files found"
echo ""

echo "======================================================================"
echo "End: $(date -Iseconds)"
