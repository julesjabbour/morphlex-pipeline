#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "======================================================================"
echo "PRINT REBUILD SCRIPT REMAINDER (LINES 250-420)"
echo "======================================================================"
echo "Git: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo "---"
echo ""

sed -n '250,420p' /mnt/pgdata/morphlex/scripts/rebuild_master_table_v2.py

echo ""
echo "======================================================================"
echo "END OF REBUILD SCRIPT REMAINDER"
echo "======================================================================"
echo "End: $(date -Iseconds)"
