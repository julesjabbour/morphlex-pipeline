#!/bin/bash
# Diagnostic: Find Wiktextract dump file location

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== WIKTEXTRACT FILE SEARCH ==="
echo "--- /mnt/pgdata/morphlex/data/ ---"
ls -lhS /mnt/pgdata/morphlex/data/ 2>&1
echo ""
echo "--- Search for wikt* files ---"
find /mnt/pgdata -name "*wikt*" -o -name "*wiktextract*" 2>/dev/null
echo ""
echo "--- Search for large .gz or .jsonl files ---"
find /mnt/pgdata -name "*.jsonl*" -o -name "*.gz" 2>/dev/null | head -20
echo ""
echo "--- Home directory ---"
ls -lhS ~/wikt* ~/raw-wikt* 2>/dev/null
ls -lhS ~/*.jsonl* ~/*.gz 2>/dev/null
echo "=== SEARCH COMPLETE ==="
