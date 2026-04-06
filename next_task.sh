#!/bin/bash
cd /mnt/pgdata/morphlex

echo "=== VM DIAGNOSTIC ==="
echo ""
echo "--- Data files (pkl indexes) ---"
ls -lh data/*.pkl 2>/dev/null || echo "NO PKL FILES FOUND"
echo ""
echo "--- Analyzers ---"
ls -la analyzers/*.py 2>/dev/null || echo "NO ANALYZER FILES FOUND"
echo ""
echo "--- Pipeline scripts ---"
ls -la pipeline/*.py 2>/dev/null || echo "NO PIPELINE FILES FOUND"
echo ""
echo "--- Wiktextract dump ---"
ls -lh data/kaikki*.jsonl 2>/dev/null || ls -lh data/wiktextract*.jsonl 2>/dev/null || echo "NO WIKTEXTRACT DUMP FOUND"
echo ""
echo "--- CAMeL Tools test ---"
source venv/bin/activate 2>/dev/null
python3 -c "from camel_tools.morphology.analyzer import Analyzer; a=Analyzer.builtin_analyzer(); print('CAMeL: OK')" 2>/dev/null || echo "CAMeL: FAILED"
echo ""
echo "--- Index verification ---"
python3 -c "
import pickle
for f in ['data/etymology_index.pkl', 'data/forward_translations.pkl', 'data/wiktextract_index.pkl']:
    try:
        d=pickle.load(open(f,'rb'))
        print(f'{f}: {len(d)} entries')
    except Exception as e:
        print(f'{f}: FAILED - {e}')
" 2>/dev/null
echo ""
echo "--- PostgreSQL ---"
PGPASSWORD=morphlex_2026 psql -h localhost -U morphlex_user -d morphlex -c "SELECT COUNT(*) as rows FROM lexicon.entries;" 2>/dev/null || echo "DB: FAILED"
echo ""
echo "--- Disk ---"
df -h /mnt/pgdata | tail -1
echo ""
echo "=== END DIAGNOSTIC ==="
