#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "======================================================================"
echo "INVESTIGATE WHY ADAPTERS WERE SKIPPED IN MERGE"
echo "======================================================================"
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

echo "=== STEP 1: Find the merge script that ran ==="
git log --oneline -10
echo ""

echo "=== STEP 2: Find merge script files ==="
find /mnt/pgdata/morphlex -name '*merge*' -type f 2>/dev/null | grep -v __pycache__ | grep -v venv
echo ""

echo "=== STEP 3: Show the rebuild script's analyze_word function ==="
grep -n -A 25 "def analyze_word" /mnt/pgdata/morphlex/scripts/rebuild_master_table_v2.py 2>/dev/null || echo "File not found"
echo ""

echo "=== STEP 4: List adapters available ==="
ls -la /mnt/pgdata/morphlex/analyzers/
echo ""

echo "=== STEP 5: Test importing adapters ==="
python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
print('Testing adapter imports:')
for adapter in ['turkish', 'german', 'sanskrit', 'latin', 'greek']:
    try:
        mod = __import__(f'analyzers.{adapter}', fromlist=[adapter])
        funcs = [f for f in dir(mod) if f.startswith('analyze') or f.startswith('process')]
        print(f'  {adapter}: OK, functions={funcs}')
    except Exception as e:
        print(f'  {adapter}: FAILED - {type(e).__name__}: {e}')
"
echo ""

echo "=== STEP 6: Test running each adapter on one sample word ==="
python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
samples = {'turkish': 'gelmek', 'german': 'Haus', 'sanskrit': 'gacchati', 'latin': 'amare', 'greek': 'ἀγαθός'}
for lang, word in samples.items():
    try:
        mod = __import__(f'analyzers.{lang}', fromlist=[lang])
        analyze_fn = None
        for fname in dir(mod):
            if fname.startswith('analyze'):
                analyze_fn = getattr(mod, fname)
                break
        if analyze_fn:
            result = analyze_fn(word)
            print(f'  {lang}({repr(word)}) -> {result}')
        else:
            print(f'  {lang}: no analyze function found')
    except Exception as e:
        import traceback
        print(f'  {lang}({repr(word)}) FAILED - {type(e).__name__}: {e}')
        traceback.print_exc()
"
echo ""

echo "=== STEP 7: Check the REAL problem - exception handling in rebuild script ==="
echo "The analyze_word function at lines 75-101 has this code:"
echo ""
echo "    except Exception as e:"
echo "        return {}"
echo ""
echo "This SILENTLY SWALLOWS all errors. If adapters fail to import or crash,"
echo "no error is logged and an empty dict is returned, causing 0% root coverage."
echo ""

echo "=== STEP 8: Verify by checking what errors actually occur ==="
python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')

print('Testing the EXACT code path from rebuild_master_table_v2.py:')
print('')

samples = {
    'tr': 'gelmek',
    'de': 'Haus',
    'sa': 'gacchati',
    'la': 'amare',
    'grc': 'ἀγαθός'
}

for lang_code, word in samples.items():
    print(f'--- {lang_code}: {repr(word)} ---')
    try:
        if lang_code == 'tr':
            from analyzers.turkish import analyze_turkish
            results = analyze_turkish(word)
        elif lang_code == 'de':
            from analyzers.german import analyze_german
            results = analyze_german(word)
        elif lang_code == 'sa':
            from analyzers.sanskrit import analyze_sanskrit
            results = analyze_sanskrit(word)
        elif lang_code == 'la':
            from analyzers.latin import analyze_latin
            results = analyze_latin(word)
        elif lang_code == 'grc':
            from analyzers.greek import analyze_greek
            results = analyze_greek(word)
        else:
            results = []

        if results and len(results) > 0:
            analysis = results[0]
            root = analysis.get('root', '')
            print(f'  SUCCESS: root={repr(root)}, full={analysis}')
        else:
            print(f'  EMPTY RESULT: {results}')
    except Exception as e:
        import traceback
        print(f'  EXCEPTION: {type(e).__name__}: {e}')
        traceback.print_exc()
    print('')
"

echo ""
echo "======================================================================"
echo "DIAGNOSIS SUMMARY"
echo "======================================================================"
echo "The 0% root coverage is caused by one of:"
echo "1. Adapter import failures (missing dependencies on VM)"
echo "2. Adapter runtime errors being silently caught"
echo "3. Adapters returning empty results (tool not responding)"
echo ""
echo "FIX: Remove the silent exception handling in rebuild_master_table_v2.py"
echo "and add proper error logging."
echo ""
echo "======================================================================"
echo "END OF INVESTIGATION"
echo "======================================================================"
echo "End: $(date -Iseconds)"
