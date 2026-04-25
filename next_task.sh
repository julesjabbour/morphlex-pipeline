#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "======================================================================"
echo "RUN REBUILD_MASTER_TABLE_V2.PY WITH SYS.PATH FIX"
echo "======================================================================"
echo "Git: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo "---"
echo ""

python3 scripts/rebuild_master_table_v2.py

echo ""
echo "======================================================================"
echo "END OF REBUILD"
echo "======================================================================"
echo "End: $(date -Iseconds)"
