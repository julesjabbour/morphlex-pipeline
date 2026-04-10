#!/bin/bash
# RUN AGWN LEMMA DOWNLOAD
# Timestamp: 2026-04-10-agwn-lemma-download-v3

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== AGWN LEMMA DOWNLOAD ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code from git
git fetch origin > /dev/null 2>&1
git reset --hard origin/main > /dev/null 2>&1

# Run the download script
python3 scripts/download_harvard_agwn.py

echo ""
echo "End: $(date -Iseconds)"
