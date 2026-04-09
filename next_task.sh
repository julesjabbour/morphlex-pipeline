#!/bin/bash
# REWRITE BUILD_CONCEPT_MAP: Diagnostic + rewritten script with correct wn API
# Timestamp: 2026-04-09-diagnostic-rewrite
# STEP 1: Run diagnostic to discover actual wn API
# STEP 2: Run rewritten build_concept_map.py with correct API calls
# STEP 3: Print stats only

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== DIAGNOSTIC + BUILD CONCEPT MAP ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# STEP 1: Run diagnostic to discover actual wn API
echo "=== STEP 1: WN LIBRARY API DIAGNOSTIC ==="
python3 -c "
import wn
en = wn.lexicons(lang='en')[0]
ss = wn.synsets(lang='en')[0]
print('LEXICON attributes:')
for attr in ['id', 'language', 'label', 'version']:
    val = getattr(en, attr, 'MISSING')
    print(f'  en.{attr} = {repr(val)[:50]} (type={type(val).__name__})')
print()
print('SYNSET attributes:')
for attr in ['id', 'pos', 'ili']:
    val = getattr(ss, attr, 'MISSING')
    print(f'  ss.{attr} = {repr(val)[:50]} (type={type(val).__name__})')
print()
print('SYNSET methods:')
for method in ['definition', 'lemmas', 'senses', 'words']:
    try:
        val = getattr(ss, method)()
        print(f'  ss.{method}() = {repr(val)[:60]}')
    except Exception as e:
        print(f'  ss.{method}() ERROR: {e}')
print()
print('WORD attributes:')
words = ss.words()
if words:
    w = words[0]
    for attr in ['lemma', 'forms']:
        try:
            val = getattr(w, attr)
            print(f'  word.{attr} = {repr(val)[:60]} (callable={callable(val)})')
            if callable(val):
                print(f'  word.{attr}() = {repr(val())[:60]}')
        except Exception as e:
            print(f'  word.{attr} ERROR: {e}')
" 2>&1

echo ""
echo "=== STEP 2: RUN REWRITTEN BUILD_CONCEPT_MAP.PY ==="
python3 pipeline/build_concept_map.py

RESULT=$?

echo ""
echo "End: $(date -Iseconds)"
exit $RESULT
