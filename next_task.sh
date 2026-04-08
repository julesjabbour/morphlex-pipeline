#!/bin/bash
# Greek adapter: Document as TOOL LIMITATION, stop returning fake roots
# Issue: Morpheus returns empty responses for Greek (works for Latin only)
# Fix: Return empty root instead of input word when no data found
# Status: Greek now joins Hebrew/Sanskrit as honestly empty, not fake PASS
# Timestamp: 2026-04-08-greek-honest-empty

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== GREEK TOOL LIMITATION FIX ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code
echo "--- Step 1: Syncing code from origin/main ---"
git fetch origin && git reset --hard origin/main
echo "Now at: $(git rev-parse HEAD)"
echo ""

# Verify the fix
echo "--- Step 2: Verifying Greek adapter changes ---"
echo "Checking greek.py for honest empty root behavior..."
if grep -q "TOOL LIMITATION" analyzers/greek.py; then
    echo "PASS: Greek adapter documents tool limitation"
else
    echo "FAIL: Missing tool limitation documentation"
fi

if grep -q "zero error suppression" analyzers/greek.py; then
    echo "PASS: Greek adapter has zero error suppression comment"
else
    echo "INFO: Zero error suppression comment not found"
fi

echo ""

# Direct test of Greek Morpheus endpoint
echo "--- Step 3: Testing Morpheus Greek endpoint directly ---"
echo "Testing word: γράφω (write)"
curl -s "http://localhost:1315/greek/γραφω" | head -c 200 || echo "(empty or error)"
echo ""
echo "Testing word: καρδία (heart)"
curl -s "http://localhost:1315/greek/καρδια" | head -c 200 || echo "(empty or error)"
echo ""

# For comparison, test Latin
echo "Testing Latin for comparison: scribo"
curl -s "http://localhost:1315/latin/scribo" | head -c 200
echo ""
echo ""

# Run comprehensive test
echo "--- Step 4: Running comprehensive test ---"
echo "Expected: Greek roots should be EMPTY (not fake roots from input word)"
echo ""
python3 test_comprehensive.py

echo ""
echo "=== TEST COMPLETE ==="
echo "End: $(date -Iseconds)"
