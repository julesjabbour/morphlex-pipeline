#!/bin/bash
# TEST HSPELL CTYPES WRAPPER FOR HEBREW ROOT EXTRACTION
# Timestamp: 2026-04-08-hspell-ctypes
# HspellPy is dead on Python 3.12. Using ctypes to call libhspell.so.0 directly.
# NO HARDCODING. NO RULE-BASED FALLBACK.

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== HSPELL CTYPES HEBREW ROOT TEST ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code first
echo "--- Step 1: Syncing code from origin/main ---"
git fetch origin && git reset --hard origin/main
echo "Now at: $(git rev-parse HEAD)"
echo ""

# Verify honest Hebrew adapter (NO KNOWN_ROOTS)
echo "--- Step 2: Verify honest Hebrew adapter ---"
if grep -q "KNOWN_ROOTS" analyzers/hebrew.py; then
    echo "FAIL: KNOWN_ROOTS still present in hebrew.py - not honest!"
    exit 1
else
    echo "PASS: No KNOWN_ROOTS dictionary (honest adapter)"
fi

if grep -q "_extract_root_fallback\|_strip_affixes" analyzers/hebrew.py; then
    echo "FAIL: Rule-based fallback still present - not honest!"
    exit 1
else
    echo "PASS: No rule-based fallback (honest adapter)"
fi

# Verify ctypes approach
if grep -q "import ctypes" analyzers/hebrew.py; then
    echo "PASS: Using ctypes approach"
else
    echo "FAIL: Not using ctypes approach!"
    exit 1
fi
echo ""

# Verify Hspell C library installation
echo "--- Step 3: Verify Hspell C library ---"
if [ -f /usr/local/lib/libhspell.so.0 ]; then
    echo "PASS: libhspell.so.0 found at /usr/local/lib/libhspell.so.0"
    ls -la /usr/local/lib/libhspell*
else
    echo "FAIL: libhspell.so.0 not found at /usr/local/lib/libhspell.so.0"
    echo "Checking ldconfig..."
    ldconfig -p | grep hspell || echo "Not in ldconfig either"
    exit 1
fi
echo ""

# Test ctypes can load the library
echo "--- Step 4: Test ctypes can load libhspell.so.0 ---"
python3 << 'EOF'
import ctypes
import os

lib_path = '/usr/local/lib/libhspell.so.0'
print(f"Loading: {lib_path}")
print(f"File exists: {os.path.exists(lib_path)}")

try:
    lib = ctypes.CDLL(lib_path)
    print(f"SUCCESS: Loaded libhspell.so.0")

    # Check for required functions
    funcs = ['hspell_init', 'hspell_check_word', 'hspell_enum_splits', 'hspell_uninit']
    for func in funcs:
        if hasattr(lib, func):
            print(f"  - {func}: FOUND")
        else:
            print(f"  - {func}: MISSING")
except Exception as e:
    print(f"FAIL: Could not load library: {e}")
    exit(1)
EOF
echo ""

# Test Hebrew adapter with ctypes
echo "--- Step 5: Test Hebrew adapter with 10 RANDOM words ---"
python3 << 'EOF'
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')

from analyzers.hebrew import analyze_hebrew, _init_hspell, HSPELL_LIB_PATH

print("Hebrew adapter test (CTYPES - NO HARDCODING)")
print(f"Library path: {HSPELL_LIB_PATH}")

hspell_ok = _init_hspell()
print(f"Hspell initialized: {hspell_ok}")
print("")

# 10 random Hebrew words - NOT from any test list
# These are common Hebrew words that should have roots
test_words = [
    ('אוכל', 'food'),
    ('מכונית', 'car'),
    ('טלפון', 'telephone'),
    ('חלב', 'milk'),
    ('שמש', 'sun'),
    ('ירח', 'moon'),
    ('דלת', 'door'),
    ('רחוב', 'street'),
    ('גשם', 'rain'),
    ('שלג', 'snow'),
]

found = 0
empty = 0

print("=== 10 RANDOM HEBREW WORDS ===")
for word, meaning in test_words:
    results = analyze_hebrew(word)
    if results and results[0].get('root'):
        r = results[0]
        print(f"  {word} ({meaning}): root='{r['root']}', source={r['source_tool']}")
        found += 1
    else:
        print(f"  {word} ({meaning}): NO ROOT")
        empty += 1

print("")
print(f"=== RESULTS: {found}/10 roots found, {empty}/10 empty ===")

if found > 0:
    print("STATUS: SUCCESS - Hspell ctypes working")
else:
    print("STATUS: NEEDS INVESTIGATION - no roots found")
EOF
echo ""

# Run comprehensive test
echo "--- Step 6: Run comprehensive adapter test ---"
cd /mnt/pgdata/morphlex
python3 test_comprehensive.py 2>&1 | head -150
echo ""

echo "=== HSPELL CTYPES TEST COMPLETE ==="
echo "End: $(date -Iseconds)"
