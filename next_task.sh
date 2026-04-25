#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "======================================================================"
echo "PRINT REBUILD SCRIPT AND TEST ANALYZE_WORD IN ISOLATION"
echo "======================================================================"
git_head=$(git rev-parse HEAD 2>/dev/null)
echo "Git: $git_head"
echo "Start: $(date -Iseconds)"
echo "---"

echo ""
echo "======================================================================"
echo "STEP 1: PRINT FULL rebuild_master_table_v2.py"
echo "======================================================================"
echo ""
cat /mnt/pgdata/morphlex/scripts/rebuild_master_table_v2.py

echo ""
echo "======================================================================"
echo "STEP 2: WRITE TEST SCRIPT TO /tmp/test_analyze.py"
echo "======================================================================"
echo ""

cat > /tmp/test_analyze.py << 'PYEOF'
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
sys.path.insert(0, '/mnt/pgdata/morphlex/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location("rebuild", "/mnt/pgdata/morphlex/scripts/rebuild_master_table_v2.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
analyze_word = mod.analyze_word
samples = [('tr', 'gelmek'), ('tr', 'kitap'), ('de', 'Haus'), ('de', 'Hund'), ('sa', 'gacchati'), ('sa', 'agni'), ('la', 'amare'), ('la', 'puer'), ('grc', 'logos'), ('grc', 'aner')]
for lang, word in samples:
    print(f'--- {lang}: {word!r} ---')
    try:
        result = analyze_word(word, lang)
        print(f'  Result type: {type(result).__name__}')
        print(f'  Result: {result}')
        if isinstance(result, dict):
            print(f'  root field: {result.get("root", "NOT_PRESENT")!r}')
    except Exception as e:
        print(f'  EXCEPTION: {type(e).__name__}: {e}')
    print()
PYEOF

echo "Test script written to /tmp/test_analyze.py"
echo ""
echo "Contents:"
cat /tmp/test_analyze.py

echo ""
echo "======================================================================"
echo "STEP 3: RUN TEST SCRIPT"
echo "======================================================================"
echo ""

python3 /tmp/test_analyze.py

echo ""
echo "======================================================================"
echo "END OF TEST"
echo "======================================================================"
echo "End: $(date -Iseconds)"
