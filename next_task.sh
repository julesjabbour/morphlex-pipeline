#!/bin/bash
# FIX: Greek Morpheus - Convert to Beta Code
# Root cause: Morpheus expects Beta Code (ASCII), not UTF-8 Greek
# Example: γράφω must be sent as gra/fw
# Timestamp: 2026-04-08-greek-beta-code-fix

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== GREEK MORPHEUS FIX: BETA CODE CONVERSION ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code
echo "--- Step 1: Syncing code from origin/main ---"
git fetch origin && git reset --hard origin/main
echo "Now at: $(git rev-parse HEAD)"
echo ""

# Show the Beta Code fix
echo "--- Step 2: Verify Beta Code conversion added ---"
if grep -q "_greek_to_beta_code\|_BETA_LETTERS" analyzers/greek.py; then
    echo "PASS: Beta Code conversion function present"
    echo ""
    echo "Beta Code mapping preview:"
    grep -A5 "_BETA_LETTERS = {" analyzers/greek.py | head -6
else
    echo "FAIL: Beta Code conversion NOT found in greek.py"
    exit 1
fi
echo ""

# Test Beta Code conversion directly
echo "--- Step 3: Test Beta Code conversion ---"
python3 -c "
from analyzers.greek import _greek_to_beta_code

test_words = [
    ('γράφω', 'gra/fw'),
    ('λόγος', 'lo/gos'),
    ('ἄνθρωπος', 'a)/nqrwpos'),
    ('καρδία', 'kardi/a'),
    ('οἶκος', 'oi)=kos'),
]

print('Unicode -> Beta Code conversion:')
for greek, expected in test_words:
    beta = _greek_to_beta_code(greek)
    status = 'OK' if beta == expected else f'UNEXPECTED (expected {expected})'
    print(f'  {greek} -> {beta} [{status}]')
"
echo ""

# Test Morpheus endpoints directly
echo "--- Step 4: Direct Morpheus API test ---"
echo "Latin 'scribo' (baseline - should work):"
curl -s "http://localhost:1315/latin/scribo" | head -c 400
echo ""
echo ""

echo "Greek with Beta Code: gra/fw (γράφω):"
# Note: / needs to be URL-encoded as %2F
curl -s "http://localhost:1315/greek/gra%2Ffw" | head -c 400
echo ""
echo ""

echo "Greek with Beta Code: lo/gos (λόγος):"
curl -s "http://localhost:1315/greek/lo%2Fgos" | head -c 400
echo ""
echo ""

echo "Greek with Beta Code: a)nqrwpos (ἄνθρωπος, no accent):"
curl -s "http://localhost:1315/greek/a%29nqrwpos" | head -c 400
echo ""
echo ""

# Test through the adapter
echo "--- Step 5: Test Greek adapter with Beta Code ---"
python3 -c "
from analyzers.greek import analyze_greek

test_words = ['γράφω', 'λόγος', 'καρδία', 'οἶκος', 'ἀγάπη']

print('Greek adapter test results:')
for word in test_words:
    results = analyze_greek(word)
    if results:
        roots = [r.get('root', '') or r.get('lemma', '') for r in results]
        source = results[0].get('source_tool', 'unknown')
        print(f'  {word}: {len(results)} results, roots={roots[:3]}, source={source}')
    else:
        print(f'  {word}: NO RESULTS')
"
echo ""

# Run comprehensive test
echo "--- Step 6: Comprehensive adapter test ---"
python3 test_comprehensive.py

echo ""
echo "=== GREEK FIX TEST COMPLETE ==="
echo "End: $(date -Iseconds)"
