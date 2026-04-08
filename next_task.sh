#!/bin/bash
# Comprehensive adapter test after Greek Morpheus wiring
# Changes in this commit:
# 1. Greek adapter wired to Morpheus (like Latin)
# 2. Hebrew adapter accepts coverage gap (7 entries, expected empty)
# 3. Sanskrit diagnostic to assess coverage
# 4. Chinese _find_cedict_path() actually called
# 5. English logs when MorphoLex missing
# Timestamp: 2026-04-08-rerun-after-fix-v2

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== COMPREHENSIVE ADAPTER TEST ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# First sync the code
echo "--- Step 1: Syncing code from origin/main ---"
git fetch origin && git reset --hard origin/main
echo "Now at: $(git rev-parse HEAD)"
echo ""

# Verify Greek adapter is wired to Morpheus
echo "--- Step 2: Verifying Greek Morpheus wiring ---"
if grep -q "MORPHEUS_GREEK_URL" analyzers/greek.py; then
    echo "PASS: Greek adapter has MORPHEUS_GREEK_URL defined"
    grep "MORPHEUS_GREEK_URL" analyzers/greek.py
else
    echo "FAIL: Greek adapter NOT wired to Morpheus"
fi
echo ""

# Run comprehensive test
echo "--- Step 3: Running comprehensive 10-word test ---"
python3 test_comprehensive.py

echo ""
echo "=== ALL TESTS COMPLETE ==="
echo "End: $(date -Iseconds)"
