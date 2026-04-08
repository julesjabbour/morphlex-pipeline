#!/bin/bash
# TEST HSPELL SUBPROCESS FOR HEBREW ROOT EXTRACTION
# Timestamp: 2026-04-08-parser-fix-88962a1
# ctypes approach segfaults. Using subprocess to call hspell binary directly.
# NO HARDCODING. NO RULE-BASED FALLBACK.

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== HSPELL SUBPROCESS HEBREW ROOT TEST ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code first
echo "--- Step 1: Syncing code from origin/main ---"
git fetch origin && git reset --hard origin/main
echo "Now at: $(git rev-parse HEAD)"
echo ""

# Verify honest Hebrew adapter (NO KNOWN_ROOTS, NO rule-based fallback, NO ctypes)
echo "--- Step 2: Verify honest Hebrew adapter ---"
if grep -q "KNOWN_ROOTS" analyzers/hebrew.py; then
    echo "FAIL: KNOWN_ROOTS still present in hebrew.py - not honest!"
    exit 1
else
    echo "PASS: No KNOWN_ROOTS dictionary (honest adapter)"
fi

if grep -q "_extract_root_fallback\|_strip_affixes\|HEBREW_CONSONANTS" analyzers/hebrew.py; then
    echo "FAIL: Rule-based fallback still present - not honest!"
    exit 1
else
    echo "PASS: No rule-based fallback (honest adapter)"
fi

# Verify subprocess approach (NOT ctypes)
if grep -q "import subprocess" analyzers/hebrew.py; then
    echo "PASS: Using subprocess approach"
else
    echo "FAIL: Not using subprocess approach!"
    exit 1
fi

if grep -q "^import ctypes" analyzers/hebrew.py; then
    echo "FAIL: Still using ctypes (will segfault)!"
    exit 1
else
    echo "PASS: No ctypes import (avoiding segfault)"
fi
echo ""

# Verify hspell binary exists
echo "--- Step 3: Verify hspell binary ---"
if command -v hspell &> /dev/null; then
    HSPELL_PATH=$(which hspell)
    echo "PASS: hspell binary found at $HSPELL_PATH"
    hspell --version 2>&1 || echo "(no version output)"
else
    echo "FAIL: hspell binary not found in PATH"
    echo "Checking /usr/local/bin/hspell..."
    if [ -f /usr/local/bin/hspell ]; then
        echo "Found at /usr/local/bin/hspell"
        export PATH=$PATH:/usr/local/bin
        /usr/local/bin/hspell --version 2>&1 || echo "(no version output)"
    else
        echo "Not found at /usr/local/bin/hspell either"
        exit 1
    fi
fi
echo ""

# Debug hspell output formats
echo "--- Step 4: Debug hspell binary output formats ---"
echo "Testing different hspell flags with שלום (shalom) and מילון (dictionary)"
echo "NOTE: -l is for linguistic info, -H is for He Ha-sh'ela prefix (NOT HTML!)"

for WORD in "שלום" "מילון" "הבית" "כתבתי"; do
    echo ""
    echo "=== Word: $WORD ==="

    echo "Default mode (spell check only):"
    echo "$WORD" | iconv -f UTF-8 -t ISO-8859-8 2>/dev/null | hspell 2>&1 | iconv -f ISO-8859-8 -t UTF-8 2>/dev/null | head -5

    echo "Linguistic info mode (-l):"
    echo "$WORD" | iconv -f UTF-8 -t ISO-8859-8 2>/dev/null | hspell -l 2>&1 | iconv -f ISO-8859-8 -t UTF-8 2>/dev/null | head -10

    echo "Linginfo + He prefix (-l -H):"
    echo "$WORD" | iconv -f UTF-8 -t ISO-8859-8 2>/dev/null | hspell -l -H 2>&1 | iconv -f ISO-8859-8 -t UTF-8 2>/dev/null | head -10

    echo "Corrections + Linginfo (-c -l):"
    echo "$WORD" | iconv -f UTF-8 -t ISO-8859-8 2>/dev/null | hspell -c -l 2>&1 | iconv -f ISO-8859-8 -t UTF-8 2>/dev/null | head -10
done
echo ""

# Test Hebrew adapter with subprocess
echo "--- Step 5: Debug hspell Python integration ---"
python3 << 'EOF'
import sys
import json
sys.path.insert(0, '/mnt/pgdata/morphlex')

from analyzers.hebrew import debug_hspell, _find_hspell, _hspell_path

print("Debugging hspell integration from Python")
print("")

hspell_ok = _find_hspell()
print(f"hspell binary available: {hspell_ok}")
if _hspell_path:
    print(f"hspell path: {_hspell_path}")
print("")

if hspell_ok:
    # Debug first word to see raw output
    test_word = 'מילון'
    print(f"=== Raw hspell output for '{test_word}' ===")
    debug_info = debug_hspell(test_word)
    for mode, info in debug_info.items():
        if mode in ['word', 'encoded']:
            print(f"{mode}: {info}")
        elif isinstance(info, dict):
            print(f"\n{mode}:")
            for k, v in info.items():
                val_str = repr(v) if len(repr(v)) < 300 else repr(v)[:300] + '...'
                print(f"  {k}: {val_str}")
    print("")
EOF
echo ""

echo "--- Step 6: Test Hebrew adapter with 20 RANDOM words ---"
python3 << 'EOF'
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')

from analyzers.hebrew import analyze_hebrew, _find_hspell, _hspell_path

print("Hebrew adapter test (SUBPROCESS - NO HARDCODING)")

hspell_ok = _find_hspell()
print(f"hspell binary available: {hspell_ok}")
if _hspell_path:
    print(f"hspell path: {_hspell_path}")
print("")

# 20 random Hebrew words - NOT from any test list
test_words = [
    ('מילון', 'dictionary'),
    ('לב', 'heart'),
    ('מים', 'water'),
    ('בית', 'house'),
    ('יד', 'hand'),
    ('עין', 'eye'),
    ('ספר', 'book'),
    ('שולחן', 'table'),
    ('כיסא', 'chair'),
    ('חלון', 'window'),
    ('דלת', 'door'),
    ('שמש', 'sun'),
    ('ירח', 'moon'),
    ('כוכב', 'star'),
    ('עץ', 'tree'),
    ('פרח', 'flower'),
    ('ילד', 'child'),
    ('אישה', 'woman'),
    ('איש', 'man'),
    ('אהבה', 'love'),
]

found = 0
empty = 0

print("=== 20 RANDOM HEBREW WORDS ===")
for word, meaning in test_words:
    try:
        results = analyze_hebrew(word)
        if results and results[0].get('root'):
            r = results[0]
            print(f"  {word} ({meaning}): root='{r['root']}', source={r['source_tool']}")
            found += 1
        else:
            print(f"  {word} ({meaning}): NO ROOT")
            empty += 1
    except Exception as e:
        print(f"  {word} ({meaning}): ERROR - {e}")
        import traceback
        traceback.print_exc()
        empty += 1

print("")
print(f"=== RESULTS: {found}/20 roots found, {empty}/20 empty ===")

if found > 0:
    print("STATUS: SUCCESS - Hebrew root extraction working")
elif hspell_ok:
    print("STATUS: hspell found but no roots - need to check hspell output format")
else:
    print("STATUS: hspell not available - only wiktextract fallback")
EOF
echo ""

# Run comprehensive test
echo "--- Step 7: Run comprehensive adapter test ---"
cd /mnt/pgdata/morphlex
python3 test_comprehensive.py 2>&1 | head -150
echo ""

echo "=== HSPELL SUBPROCESS TEST COMPLETE ==="
echo "End: $(date -Iseconds)"
