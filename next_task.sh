#!/bin/bash
# PHASE 5a: Install WordNet + OMW and Build Concept Map
# Timestamp: 2026-04-09-wordnet-omw-concept-map
# Purpose: Install WordNet/OMW, build pkl mapping synsets to multilingual words
# Expected runtime: 10-30 minutes
# NO HARDCODING. NO SHORTCUTS. ALL SYNSETS PROCESSED.

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== PHASE 5a: WORDNET + OMW CONCEPT MAP ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code first
echo "--- Syncing code from origin/main ---"
git fetch origin && git reset --hard origin/main
echo "Now at: $(git rev-parse HEAD)"
echo ""

# Step 1: Install packages
echo "=== STEP 1: Installing packages ==="
pip install nltk wn --break-system-packages
if [ $? -ne 0 ]; then
    echo "ERROR: pip install failed!"
    exit 1
fi
echo "Package installation complete."
echo ""

# Step 2: Download WordNet data (NLTK)
echo "=== STEP 2: Downloading WordNet/OMW data ==="
python3 -c "import nltk; nltk.download('wordnet'); nltk.download('omw-1.4')"
if [ $? -ne 0 ]; then
    echo "ERROR: NLTK download failed!"
    exit 1
fi

# Download wn library data - English WordNet first, then OMW
echo "Downloading English WordNet (oewn:2024)..."
python3 -c "import wn; wn.download('oewn:2024')"
if [ $? -ne 0 ]; then
    echo "WARNING: oewn download returned non-zero (may already exist)"
fi

echo "Downloading Open Multilingual Wordnet (omw:1.4)..."
python3 -c "import wn; wn.download('omw:1.4')"
if [ $? -ne 0 ]; then
    echo "WARNING: omw download returned non-zero (may already exist)"
fi
echo "Data download complete."
echo ""

# Step 3: Run the concept map builder
echo "=== STEP 3: Building concept map ==="
python3 pipeline/build_concept_map.py

exit_code=$?

echo ""
echo "=== BUILD FINISHED ==="
echo "Exit code: $exit_code"

# Verify output file exists and show size
if [ -f /mnt/pgdata/morphlex/data/concept_wordnet_map.pkl ]; then
    echo "Output file exists:"
    ls -lh /mnt/pgdata/morphlex/data/concept_wordnet_map.pkl
else
    echo "ERROR: Output file not created!"
fi

echo ""
echo "End: $(date -Iseconds)"
