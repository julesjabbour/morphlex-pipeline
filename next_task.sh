#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "======================================================================"
echo "REBUILD MASTER_TABLE_V2 WITH PREFIX NORMALIZATION"
echo "======================================================================"
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

python3 scripts/rebuild_master_table_v2.py

echo ""
echo "======================================================================"
echo "END OF REBUILD"
echo "======================================================================"
echo "End: $(date -Iseconds)"
