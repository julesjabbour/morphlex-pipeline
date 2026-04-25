#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate
echo "=== Running rebuild_master_table_v2.py ==="
python3 scripts/rebuild_master_table_v2.py
echo ""
echo "=== Done ==="
