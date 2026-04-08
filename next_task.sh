#!/bin/bash
# Test fixes for Phase 2 broken adapters:
# 1. Greek: Document as TOOL LIMITATION, return empty roots (zero error suppression)
# 2. English POS: Fix spaCy PROPN misclassification with morphological heuristics
# 3. Latin: Fix lemma parsing (comma separator) and add disambiguation logic
# Timestamp: 2026-04-08-phase2-adapter-fixes

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== PHASE 2 ADAPTER FIXES TEST ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code
echo "--- Step 1: Syncing code from origin/main ---"
git fetch origin && git reset --hard origin/main
echo "Now at: $(git rev-parse HEAD)"
echo ""

# Test 1: English POS fix
echo "--- Test 1: English POS Fix ---"
echo "Testing spaCy PROPN->NOUN fix for common nouns..."
python3 << 'PYTEST'
from analyzers.english import analyze_english

test_words = ['dictionary', 'book', 'water', 'heart', 'beautiful', 'running']
print("Word            | POS      | Expected | Status")
print("-" * 55)

expected = {
    'dictionary': 'NOUN',
    'book': 'NOUN',
    'water': 'NOUN',
    'heart': 'NOUN',
    'beautiful': 'ADJ',
    'running': 'VERB'
}

all_pass = True
for word in test_words:
    results = analyze_english(word)
    pos = results[0]['pos'] if results else 'N/A'
    exp = expected.get(word, '?')
    status = 'PASS' if pos == exp else 'FAIL'
    if status == 'FAIL':
        all_pass = False
    print(f"{word:15} | {pos:8} | {exp:8} | {status}")

print()
if all_pass:
    print("English POS Fix: ALL PASS")
else:
    print("English POS Fix: SOME FAILURES")
PYTEST
echo ""

# Test 2: Latin lemma parsing and disambiguation
echo "--- Test 2: Latin Lemma Parsing and Disambiguation ---"
echo "Testing Latin lemma extraction from Morpheus format..."
python3 << 'PYTEST'
from analyzers.latin import analyze_latin, _parse_morpheus_lemma

# Test lemma parsing
print("Lemma parsing tests:")
test_cases = [
    ("scri_bo_,scribo", "scribo"),
    ("laudo_.laudo", "laudo"),
    ("amo", "amo"),
    ("domu_s,domus", "domus"),
    ("manu_s,manus#1", "manus"),
]

all_pass = True
for input_val, expected in test_cases:
    result = _parse_morpheus_lemma(input_val)
    status = "PASS" if result == expected else "FAIL"
    if status == "FAIL":
        all_pass = False
    print(f"  '{input_val}' -> '{result}' (expected '{expected}'): {status}")

print()

# Test full analysis with disambiguation
print("Full analysis tests (checking disambiguation):")
test_words = ['scribo', 'domus', 'amo', 'cor']
for word in test_words:
    results = analyze_latin(word)
    if results:
        r = results[0]
        print(f"  {word}: lemma='{r['lemma']}', root='{r['root']}', pos='{r['pos']}', conf={r['confidence']:.2f}")
    else:
        print(f"  {word}: NO RESULTS")

print()
if all_pass:
    print("Latin Lemma Parsing: ALL PASS")
else:
    print("Latin Lemma Parsing: SOME FAILURES")
PYTEST
echo ""

# Test 3: Greek tool limitation (zero error suppression)
echo "--- Test 3: Greek Tool Limitation (Zero Error Suppression) ---"
echo "Testing that Greek returns empty roots, not fake input-word roots..."
python3 << 'PYTEST'
from analyzers.greek import analyze_greek

test_words = ['γράφω', 'καρδία', 'ὕδωρ', 'οἶκος', 'χείρ']
print("Greek word   | Root       | Status")
print("-" * 45)

all_pass = True
for word in test_words:
    results = analyze_greek(word)
    if results:
        root = results[0].get('root', '')
        # PASS if root is empty OR different from input word
        # FAIL if root equals input word (fake root)
        if root == word or root == word.lower():
            status = "FAIL (fake root = input)"
            all_pass = False
        elif root == '':
            status = "PASS (empty = honest)"
        else:
            status = f"PASS (real root)"
        print(f"{word:12} | {root:10} | {status}")
    else:
        print(f"{word:12} | (no results) | PASS (no fake data)")

print()
if all_pass:
    print("Greek Zero Error Suppression: ALL PASS")
else:
    print("Greek Zero Error Suppression: FAILURES (returning fake roots)")
PYTEST
echo ""

# Run full comprehensive test
echo "--- Step 4: Running comprehensive 10-word test ---"
python3 test_comprehensive.py

echo ""
echo "=== ALL PHASE 2 FIX TESTS COMPLETE ==="
echo "End: $(date -Iseconds)"
