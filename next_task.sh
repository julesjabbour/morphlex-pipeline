#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "======================================================================"
echo "PRINT REBUILD SCRIPT WORD LOOP (LINES 100-250)"
echo "======================================================================"
echo "Git: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo "---"
echo ""

sed -n '100,250p' /mnt/pgdata/morphlex/scripts/rebuild_master_table_v2.py

echo ""
echo "======================================================================"
echo "END OF WORD LOOP SECTION"
echo "======================================================================"
echo "End: $(date -Iseconds)"
