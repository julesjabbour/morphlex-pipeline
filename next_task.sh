#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== ENG-015 ETYMOLOGY ENRICHER (Wiktextract) ==="
echo "Etymology index: /mnt/pgdata/morphlex/data/etymology_index.pkl"
echo "Raw Wiktextract: /mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz"
echo ""

# Check if etymology index exists
if [ -f "/mnt/pgdata/morphlex/data/etymology_index.pkl" ]; then
    echo "Etymology index already exists:"
    ls -lh /mnt/pgdata/morphlex/data/etymology_index.pkl
    echo ""
else
    echo "Etymology index does not exist. Building now..."
    echo "This will stream the 2.4GB raw Wiktextract dump (may take a few minutes)..."
    echo ""
    python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
from pipeline.etymology_enricher import build_etymology_index
build_etymology_index(force_rebuild=False)
"
    echo ""
fi

# Run test
echo "=== RUNNING ETYMOLOGY TEST ==="
python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
from pipeline.etymology_enricher import test_etymology
test_etymology()
"

echo ""
echo "=== COMPLETE ==="
