#!/bin/bash
# DOWNLOAD ALL ANCIENT GREEK LEMMAS FROM HARVARD API
# Timestamp: 2026-04-10-agwn-download-v1
# - Paginate through /api/lemmas (~1,126 pages)
# - Extract synset mappings for each lemma
# - Build pwn_offset_pos -> lemmas lookup
# - Save as agwn_synset_lookup.pkl

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== DOWNLOAD ANCIENT GREEK LEMMAS FROM HARVARD API ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code from git
git fetch origin > /dev/null 2>&1
git reset --hard origin/main > /dev/null 2>&1

# Run the download script
python3 scripts/download_harvard_agwn.py

RESULT=$?

echo ""
echo "End: $(date -Iseconds)"
exit $RESULT
