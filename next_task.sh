#!/bin/bash
# Arabic Anchor Pipeline Test
# Tests the pipeline with 10 Arabic words across all 11 languages
#
# Usage: bash next_task.sh
# Working directory: /mnt/pgdata/morphlex

set -e

cd /mnt/pgdata/morphlex

# Activate venv
source /mnt/pgdata/morphlex/venv/bin/activate

# Suppress warnings at bash level
export PYTHONWARNINGS="ignore"

echo "=== ARABIC ANCHOR PIPELINE TEST ==="
echo "Start: $(date -Iseconds)"
echo ""

# Run the Arabic anchor test
python3 test_arabic_anchor.py 2>&1

echo ""
echo "End: $(date -Iseconds)"
echo "=== Test complete ==="
