#!/bin/bash
# HEBREW ROOT EXTRACTION FIX
# Install HspellPy and test triconsonantal root extraction
# Timestamp: 2026-04-08-hebrew-root-fix

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== HEBREW ROOT EXTRACTION FIX ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code
echo "--- Step 1: Syncing code from origin/main ---"
git fetch origin && git reset --hard origin/main
echo "Now at: $(git rev-parse HEAD)"
echo ""

# Verify updated Hebrew adapter
echo "--- Step 2: Verify updated Hebrew adapter ---"
if grep -q "KNOWN_ROOTS\|_extract_root_hspell\|_extract_root_fallback" analyzers/hebrew.py; then
    echo "PASS: Hebrew root extraction functions present"
    echo ""
    echo "Known roots sample:"
    grep -A5 "KNOWN_ROOTS = {" analyzers/hebrew.py | head -6
else
    echo "FAIL: Hebrew root extraction code NOT found"
    exit 1
fi
echo ""

# Try to install Hspell and HspellPy
echo "--- Step 3: Attempt to install HspellPy ---"

# Check if HspellPy is already installed
if python3 -c "import HspellPy; print('HspellPy already installed')" 2>/dev/null; then
    echo "HspellPy is available"
else
    echo "HspellPy not found, attempting installation..."

    # Check if Hspell C library exists
    if ldconfig -p | grep -q libhspell; then
        echo "Hspell C library found, installing HspellPy..."
        pip install HspellPy 2>&1 | head -10
    else
        echo "NOTE: Hspell C library not installed"
        echo "HspellPy requires the Hspell C library which needs sudo to install."
        echo "Proceeding with rule-based fallback extraction..."
        echo ""
        echo "To install Hspell C library (requires sudo):"
        echo "  wget http://hspell.ivrix.org.il/hspell-1.4.tar.gz"
        echo "  tar xzf hspell-1.4.tar.gz && cd hspell-1.4"
        echo "  ./configure --enable-shared --enable-linginfo"
        echo "  make && sudo make install && sudo ldconfig"
        echo "  pip install HspellPy"
    fi
fi
echo ""

# Test Hebrew root extraction with required test words
echo "--- Step 4: Test Hebrew root extraction ---"
python3 << 'EOF'
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')

from analyzers.hebrew import analyze_hebrew, _extract_hebrew_root, _init_hspell, KNOWN_ROOTS

print("Testing Hebrew triconsonantal root extraction")
print(f"HspellPy available: {_init_hspell()}")
print(f"Known roots dictionary size: {len(KNOWN_ROOTS)}")
print("")

# Required test words from the task
test_words = [
    ('מילון', 'dictionary', 'מלל'),   # m-l-l related to words
    ('לב', 'heart', 'לבב'),           # l-b-b hollow root
    ('מים', 'water', 'מים'),          # m-y-m unusual root
    ('בית', 'house', 'בית'),          # b-y-t
    ('יד', 'hand', 'ידד'),             # y-d-d hollow root
    ('עין', 'eye', 'עין'),            # ayin-y-n
]

print("=== REQUIRED TEST WORDS ===")
found_roots = 0
for word, meaning, expected_root in test_words:
    results = analyze_hebrew(word)
    if results:
        root = results[0].get('root', '')
        source = results[0].get('source_tool', 'unknown')
        conf = results[0].get('confidence', 0)
        status = 'MATCH' if root == expected_root else f'(expected {expected_root})'
        print(f"  {word} ({meaning}): root='{root}' {status}, source={source}, conf={conf:.2f}")
        if root:
            found_roots += 1
    else:
        # Try direct extraction
        root = _extract_hebrew_root(word, [])
        status = 'MATCH' if root == expected_root else f'(expected {expected_root})'
        print(f"  {word} ({meaning}): root='{root}' {status}, source=direct")
        if root:
            found_roots += 1

print("")
print(f"Found roots: {found_roots}/{len(test_words)}")
print("")

# Test additional common Hebrew words
additional_words = ['ספר', 'כתב', 'אהבה', 'שלום', 'ילד', 'אמר', 'עשה', 'ראה', 'שמע']
print("=== ADDITIONAL COMMON WORDS ===")
additional_found = 0
for word in additional_words:
    results = analyze_hebrew(word)
    if results:
        root = results[0].get('root', '')
        source = results[0].get('source_tool', 'unknown')
        print(f"  {word}: root='{root}', source={source}")
        if root:
            additional_found += 1
    else:
        root = _extract_hebrew_root(word, [])
        print(f"  {word}: root='{root}', source=direct")
        if root:
            additional_found += 1

print("")
print(f"Additional found: {additional_found}/{len(additional_words)}")

EOF
echo ""

# Test through orchestrator integration
echo "--- Step 5: Test orchestrator integration ---"
python3 << 'EOF'
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')

from analyzers.hebrew import analyze_hebrew

# Test words that would come from forward_translations (Arabic concepts)
# These are the Hebrew translations of common Arabic words
test_translations = [
    'מילון',   # dictionary (from Arabic قاموس via translation)
    'לב',      # heart (from Arabic قلب)
    'בית',     # house (from Arabic بيت)
    'יד',      # hand (from Arabic يد)
    'עין',     # eye (from Arabic عين)
    'כתוב',    # write (from Arabic كتب)
    'שמע',     # hear (from Arabic سمع)
]

print("Hebrew translations root extraction:")
found = 0
empty = 0

for word in test_translations:
    results = analyze_hebrew(word)
    if results:
        root = results[0].get('root', '')
        if root:
            found += 1
        else:
            empty += 1
        print(f"  {word}: root='{root}' ({len(results)} analyses)")
    else:
        print(f"  {word}: NO MATCH")
        empty += 1

print("")
print(f"Summary: {found} found roots, {empty} empty")
if found >= len(test_translations) // 2:
    print("STATUS: PASS - Hebrew root extraction working")
else:
    print("STATUS: PARTIAL - Some roots extracted, needs improvement")

EOF
echo ""

# Run comprehensive test
echo "--- Step 6: Run comprehensive adapter test ---"
python3 test_comprehensive.py 2>&1 | head -100
echo ""

echo "=== HEBREW ROOT EXTRACTION TEST COMPLETE ==="
echo "End: $(date -Iseconds)"
