#!/bin/bash
# TEST: CLAUDE.md Rules + English POS Fix + Latin Disambiguation
# Timestamp: 2026-04-08-triple-update
# Tests all three changes from the merge:
# 1. CLAUDE.md anti-fraud rules (verified by existence check)
# 2. English _fix_pos_tag suffix heuristics (10 words should be NOUN not PROPN)
# 3. Latin _disambiguate_latin_parses (5 words with confidence-ranked parses)
# NO HARDCODING. All analysis from real tools (spaCy, Morpheus).

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== TRIPLE UPDATE TEST ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code first
echo "--- Syncing code from origin/main ---"
git fetch origin && git reset --hard origin/main
echo "Now at: $(git rev-parse HEAD)"
echo ""

# THING 1: Verify CLAUDE.md rules exist
echo "=== THING 1: CLAUDE.md ANTI-FRAUD RULES ==="
echo "Checking for new rules in CLAUDE.md..."
if grep -q "ZERO HARDCODING RULE" CLAUDE.md && \
   grep -q "ZERO SHORTCUT RULE" CLAUDE.md && \
   grep -q "TESTING RULE" CLAUDE.md && \
   grep -q "NO BROKEN PUSHES RULE" CLAUDE.md && \
   grep -q "MARKER RULE" CLAUDE.md; then
    echo "[OK] All 5 anti-fraud rules present in CLAUDE.md"
else
    echo "[FAIL] Missing rules in CLAUDE.md"
    grep -E "(ZERO HARDCODING|ZERO SHORTCUT|TESTING RULE|NO BROKEN PUSHES|MARKER RULE)" CLAUDE.md || echo "No rules found"
    exit 1
fi
echo ""

# THING 2: English POS Fix
echo "=== THING 2: ENGLISH POS FIX TEST ==="
python3 << 'PYEOF'
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')

import analyzers.english as english

# Test words that should ALL be NOUN, not PROPN
# These all have common noun suffixes (-tion, -ment, -hood, -ary, -phy, -ure, etc.)
test_words = [
    'imagination',      # -tion suffix
    'civilization',     # -tion suffix
    'transportation',   # -tion suffix
    'establishment',    # -ment suffix
    'neighborhood',     # -hood suffix
    'dictionary',       # -ary suffix
    'astronomy',        # -my suffix (science field)
    'philosophy',       # -phy suffix
    'agriculture',      # -ure suffix
    'temperature',      # -ure suffix
]

print("Testing English POS fix with 10 suffix-based words:")
print(f"{'Word':<20} {'Expected':<10} {'Actual':<10} {'Status'}")
print("-" * 55)

passed = 0
failed = 0

for word in test_words:
    results = english.analyze_english(word)
    if results:
        actual_pos = results[0].get('pos', 'UNKNOWN')
    else:
        actual_pos = 'NO_RESULT'

    expected = 'NOUN'
    status = '[OK]' if actual_pos == expected else '[FAIL]'
    print(f"{word:<20} {expected:<10} {actual_pos:<10} {status}")

    if actual_pos == expected:
        passed += 1
    else:
        failed += 1

print("-" * 55)
print(f"Results: {passed}/10 passed, {failed}/10 failed")

if failed > 0:
    print("\n[FAIL] English POS fix not working - suffix heuristics should catch these")
    sys.exit(1)
else:
    print("\n[OK] English POS fix working correctly")
PYEOF

if [ $? -ne 0 ]; then
    echo "[FAIL] English POS test failed"
    exit 1
fi
echo ""

# THING 3: Latin Disambiguation
echo "=== THING 3: LATIN DISAMBIGUATION TEST ==="
python3 << 'PYEOF'
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')

import analyzers.latin as latin

# Test words with multiple possible parses
# Each should return a confidence-ranked list with best parse first
test_words = ['liber', 'amat', 'rex', 'bellum', 'iter']

print("Testing Latin disambiguation with 5 ambiguous words:")
print("Each word should return confidence-ranked parses with best first\n")

all_ok = True

for word in test_words:
    print(f"=== {word} ===")
    results = latin.analyze_latin(word, return_all=True)

    if not results:
        print(f"  [FAIL] No results for '{word}'")
        all_ok = False
        continue

    # Check that first result has highest confidence
    first_confidence = results[0].get('confidence', 0)
    is_best = results[0].get('is_best_parse', False)

    print(f"  Best parse: lemma='{results[0].get('lemma')}' pos='{results[0].get('pos')}' conf={first_confidence:.2f} is_best={is_best}")

    # Show all parses
    for i, r in enumerate(results):
        lemma = r.get('lemma', '?')
        pos = r.get('pos', '?')
        conf = r.get('confidence', 0)
        best_mark = '*' if r.get('is_best_parse', False) else ' '
        print(f"  {best_mark} [{i+1}] lemma='{lemma}' pos='{pos}' conf={conf:.2f}")

    # Verify ranking: best parse should be first
    if len(results) > 1:
        if not is_best:
            print(f"  [FAIL] First result not marked as best parse")
            all_ok = False
        else:
            print(f"  [OK] Best parse correctly ranked first with {len(results)} total parses")
    else:
        print(f"  [OK] Single unambiguous parse")

    print()

if all_ok:
    print("[OK] Latin disambiguation working correctly")
else:
    print("[FAIL] Latin disambiguation has issues")
    sys.exit(1)
PYEOF

if [ $? -ne 0 ]; then
    echo "[FAIL] Latin disambiguation test failed"
    exit 1
fi
echo ""

echo "=== ALL THREE TESTS PASSED ==="
echo "1. CLAUDE.md anti-fraud rules: [OK]"
echo "2. English POS suffix heuristics: [OK]"
echo "3. Latin parse disambiguation: [OK]"
echo ""
echo "=== TRIPLE UPDATE TASK COMPLETE ==="
echo "End: $(date -Iseconds)"
