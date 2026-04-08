#!/bin/bash
# SANSKRIT VIDYUT INSTALLATION AND TEST
# Timestamp: 2026-04-08-sanskrit-vidyut
# Installs Vidyut Sanskrit analyzer and tests with 20 random words.
# NO HARDCODING. All analysis from Vidyut's morphological database.

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== SANSKRIT VIDYUT INSTALLATION AND TEST ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code first
echo "--- Syncing code from origin/main ---"
git fetch origin && git reset --hard origin/main
echo "Now at: $(git rev-parse HEAD)"
echo ""

# Install dependencies
echo "--- Installing Vidyut and dependencies ---"
pip install vidyut indic-transliteration 2>&1 | tail -5
echo ""

# Download Vidyut data if not present
VIDYUT_DATA_DIR="/mnt/pgdata/morphlex/data/vidyut_data"
if [ ! -d "$VIDYUT_DATA_DIR/kosha" ]; then
    echo "--- Downloading Vidyut data ---"
    python3 << 'PYEOF'
import vidyut
import os

data_path = '/mnt/pgdata/morphlex/data/vidyut_data'
if not os.path.exists(data_path):
    os.makedirs(data_path)

print(f"Downloading Vidyut data to {data_path}...")
vidyut.download_data(data_path)
print("Download complete!")
print(f"Files created: {os.listdir(data_path)}")
PYEOF
    echo ""
else
    echo "--- Vidyut data already present at $VIDYUT_DATA_DIR ---"
    echo ""
fi

# Run Sanskrit adapter test with the 20 user-specified words
echo "--- Testing Sanskrit adapter with 20 words ---"
python3 << 'PYEOF'
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')

import analyzers.sanskrit as sanskrit

# The 20 test words specified by user (NEVER SEEN BEFORE - NO HARDCODING)
test_words = [
    'पुस्तक',   # book
    'नदी',      # river
    'वायु',     # wind
    'अग्नि',    # fire
    'पर्वत',    # mountain
    'सूर्य',    # sun
    'चन्द्र',   # moon
    'वृक्ष',    # tree
    'पुष्प',    # flower
    'जल',       # water
    'पृथ्वी',   # earth
    'आकाश',     # sky
    'मार्ग',    # path
    'नगर',      # city
    'राजा',     # king
    'देव',      # god
    'कन्या',    # daughter
    'पुत्र',    # son
    'गुरु',     # teacher
    'शिष्य',    # student
]

print("=== SANSKRIT MORPHOLOGICAL ANALYSIS (VIDYUT) ===\n")

# Check Vidyut availability
vidyut_ok = sanskrit._init_vidyut()
print(f"Vidyut available: {vidyut_ok}")
if not vidyut_ok:
    print(f"FATAL: Vidyut not available")
    sys.exit(1)
print()

found = 0
empty = 0

print(f"{'Word':<12} {'Root':<12} {'Type':<15} {'Source'}")
print("-" * 55)

for word in test_words:
    results = sanskrit.analyze_sanskrit(word)
    if results and results[0].get('root'):
        r = results[0]
        root_type = r['morphological_features'].get('root_type', 'unknown')
        print(f"{word:<12} {r['root']:<12} {root_type:<15} {r['source_tool']}")
        found += 1
    else:
        print(f"{word:<12} NO ROOT FOUND")
        empty += 1

print("-" * 55)
print(f"\n=== RESULTS: {found}/20 roots found ({found*100/20:.0f}%) ===")

if found >= 18:  # Allow 2 failures for edge cases
    print("STATUS: [OK] Sanskrit adapter working with Vidyut")
else:
    print("STATUS: [FAIL] Too many failures - check Vidyut installation")
    sys.exit(1)
PYEOF

echo ""
echo "=== SANSKRIT VIDYUT TASK COMPLETE ==="
echo "End: $(date -Iseconds)"
