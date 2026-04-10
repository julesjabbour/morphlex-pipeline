#!/bin/bash
# RUN AGWN DOWNLOAD SCRIPT
# Timestamp: 2026-04-10-agwn-run-v2
# - Execute the download_harvard_agwn.py script
# - Verify output file exists
# - Print file size and sample data

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== RUN AGWN DOWNLOAD SCRIPT ==="
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
echo "========================================================================"
echo "VERIFICATION"
echo "========================================================================"

PKL_FILE="/mnt/pgdata/morphlex/data/agwn/agwn_synset_lookup.pkl"
if [ -f "$PKL_FILE" ]; then
    echo "Does $PKL_FILE exist? YES"
    echo "File size: $(ls -lh "$PKL_FILE" | awk '{print $5}')"
    echo ""
    echo "Loading pickle and printing stats:"
    python3 -c "
import pickle
with open('$PKL_FILE', 'rb') as f:
    data = pickle.load(f)
print(f'Total keys: {len(data):,}')
print()
print('5 sample entries:')
for i, (k, v) in enumerate(sorted(data.items())[:5]):
    print(f'  {k}: {v[:3]}...' if len(v) > 3 else f'  {k}: {v}')
"
else
    echo "Does $PKL_FILE exist? NO"
    echo "ERROR: Download script did not create the expected file"
fi

echo ""
echo "End: $(date -Iseconds)"
exit $RESULT
