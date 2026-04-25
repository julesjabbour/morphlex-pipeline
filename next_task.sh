#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "======================================================================"
echo "FULL MERGE_PKLS_TO_MASTER_V2.PY SCRIPT"
echo "======================================================================"
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

cat /mnt/pgdata/morphlex/scripts/merge_pkls_to_master_v2.py

echo ""
echo "======================================================================"
echo "END OF SCRIPT"
echo "======================================================================"
echo "End: $(date -Iseconds)"
