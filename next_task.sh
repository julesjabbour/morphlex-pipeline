#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== DOWNLOADING WIKTEXTRACT DUMP ==="
echo "Downloading English Wiktextract from kaikki.org (~2.4GB)..."
wget -O /mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz \
  "https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz" 2>&1 | tail -5

echo ""
echo "File size:"
ls -lh /mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz

echo ""
echo "First 3 lines (to verify format):"
zcat /mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz | head -3 | python3 -c "
import sys, json
for line in sys.stdin:
    d = json.loads(line)
    print(f\"word={d.get('word')}, lang={d.get('lang')}, pos={d.get('pos')}\")
"

echo "=== DOWNLOAD COMPLETE ==="
