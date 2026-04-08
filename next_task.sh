#!/bin/bash
# Phase 2 Test: Zero error suppression verification + adapter fixes
# Tests: English POS, Latin disambiguation, Greek honest-empty
# Timestamp: 2026-04-08-zero-suppression-test

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== PHASE 2 ADAPTER FIX TEST ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code
echo "--- Step 1: Syncing code from origin/main ---"
git fetch origin && git reset --hard origin/main
echo "Now at: $(git rev-parse HEAD)"
echo ""

# Zero suppression audit
echo "--- Step 2: Zero error suppression audit ---"
echo "Checking for forbidden patterns in Python files..."
SUPPRESS_COUNT=$(grep -r "filterwarnings.*ignore\|except.*:\s*pass$\|stderr.*DEVNULL" analyzers/ pipeline/ --include="*.py" 2>/dev/null | wc -l)
if [ "$SUPPRESS_COUNT" -eq 0 ]; then
    echo "PASS: Zero suppression patterns found in analyzers/ and pipeline/"
else
    echo "FAIL: Found $SUPPRESS_COUNT suppression patterns:"
    grep -rn "filterwarnings.*ignore\|except.*:\s*pass$\|stderr.*DEVNULL" analyzers/ pipeline/ --include="*.py"
fi
echo ""

# Verify adapter fixes
echo "--- Step 3: Verify adapter fix markers ---"
echo ""
echo "English POS fix (_fix_pos_tag morphological heuristics):"
if grep -q "_fix_pos_tag\|_suffix_pos_map" analyzers/english.py; then
    echo "  PASS: English POS fix present"
else
    echo "  FAIL: English POS fix missing"
fi

echo ""
echo "Latin disambiguation (_disambiguate_latin_parses):"
if grep -q "_disambiguate_latin_parses\|_parse_morpheus_lemma" analyzers/latin.py; then
    echo "  PASS: Latin disambiguation present"
else
    echo "  FAIL: Latin disambiguation missing"
fi

echo ""
echo "Greek honest-empty (TOOL LIMITATION):"
if grep -q "TOOL LIMITATION" analyzers/greek.py; then
    echo "  PASS: Greek TOOL LIMITATION documented"
else
    echo "  FAIL: Greek TOOL LIMITATION missing"
fi
echo ""

# Test Morpheus endpoints
echo "--- Step 4: Morpheus endpoint tests ---"
echo "Latin 'scribo':"
curl -s "http://localhost:1315/latin/scribo" | head -c 300
echo ""
echo ""
echo "Greek 'γράφω' (expected: empty or error - lexicon not loaded):"
curl -s "http://localhost:1315/greek/γραφω" | head -c 200 || echo "(empty)"
echo ""
echo ""

# Run comprehensive test
echo "--- Step 5: Comprehensive adapter test ---"
python3 test_comprehensive.py

echo ""
echo "=== TEST COMPLETE ==="
echo "End: $(date -Iseconds)"
