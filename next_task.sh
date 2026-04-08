#!/bin/bash
# Greek root extraction fix and Sanskrit data gap documentation
# Changes in this commit:
# 1. Greek adapter REWRITTEN - added debug output, multiple parsing strategies, lemma as fallback
# 2. Sanskrit documented as DATA GAP (like Hebrew) - PKL has different vocabulary than translations
# 3. Root extraction now ALWAYS returns lemma/word (never empty for non-empty input)
# Timestamp: 2026-04-08-greek-fix-v1

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== GREEK ROOT EXTRACTION FIX TEST ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# First sync the code
echo "--- Step 1: Syncing code from origin/main ---"
git fetch origin && git reset --hard origin/main
echo "Now at: $(git rev-parse HEAD)"
echo ""

# Verify Greek adapter changes
echo "--- Step 2: Verifying Greek adapter changes ---"
if grep -q "_DEBUG_MORPHEUS = True" analyzers/greek.py; then
    echo "PASS: Greek adapter has debug output enabled"
else
    echo "INFO: Greek debug output not enabled"
fi

if grep -q "Strategy 1:" analyzers/greek.py; then
    echo "PASS: Greek adapter has multiple parsing strategies"
else
    echo "INFO: Greek parsing strategies not found"
fi
echo ""

# Run comprehensive test - debug output will show Morpheus responses
echo "--- Step 3: Running test (watch for [DEBUG] lines showing Morpheus responses) ---"
python3 test_comprehensive.py

echo ""
echo "=== ALL TESTS COMPLETE ==="
echo "End: $(date -Iseconds)"
