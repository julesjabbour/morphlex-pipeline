#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== CORRECTED VM DIAGNOSTIC ==="

echo ""
echo "--- Wiktextract raw dump (gz) ---"
ls -lh data/raw-wiktextract-data.jsonl.gz 2>/dev/null || echo "NOT FOUND as .gz"
ls -lh data/*.gz 2>/dev/null || echo "NO .gz FILES"
ls -lh data/*.jsonl 2>/dev/null || echo "NO .jsonl FILES"

echo ""
echo "--- CAMeL Tools (in venv) ---"
python3 -c "from camel_tools.morphology.analyzer import Analyzer; a=Analyzer.builtin_analyzer(); r=a.analyze('kitab'); print(f'CAMeL: OK - {len(r)} analyses for kitab')" 2>&1 || echo "CAMeL: FAILED"

echo ""
echo "--- Quick adapter test (1 word each) ---"
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from analyzers.arabic import analyze as ar; print(f'AR: {len(ar(\"kitab\"))} results')
except Exception as e: print(f'AR: FAILED - {e}')
try:
    from analyzers.turkish import analyze as tr; print(f'TR: {len(tr(\"okudum\"))} results')
except Exception as e: print(f'TR: FAILED - {e}')
try:
    from analyzers.german import analyze as de; print(f'DE: {len(de(\"Handschuh\"))} results')
except Exception as e: print(f'DE: FAILED - {e}')
try:
    from analyzers.english import analyze as en; print(f'EN: {len(en(\"unhappiness\"))} results')
except Exception as e: print(f'EN: FAILED - {e}')
try:
    from analyzers.latin import analyze as la; print(f'LA: {len(la(\"scriptorum\"))} results')
except Exception as e: print(f'LA: FAILED - {e}')
try:
    from analyzers.chinese import analyze as zh; print(f'ZH: {len(zh(\"学校\"))} results')
except Exception as e: print(f'ZH: FAILED - {e}')
try:
    from analyzers.japanese import analyze as ja; print(f'JA: {len(ja(\"学校\"))} results')
except Exception as e: print(f'JA: FAILED - {e}')
try:
    from analyzers.hebrew import analyze as he; print(f'HE: {len(he(\"ספר\"))} results')
except Exception as e: print(f'HE: FAILED - {e}')
try:
    from analyzers.sanskrit import analyze as sa; print(f'SA: {len(sa(\"देव\"))} results')
except Exception as e: print(f'SA: FAILED - {e}')
try:
    from analyzers.greek import analyze as grc; print(f'GRC: {len(grc(\"λόγος\"))} results')
except Exception as e: print(f'GRC: FAILED - {e}')
try:
    from analyzers.pie import analyze as pie; print(f'PIE: {len(pie(\"water\"))} results')
except Exception as e: print(f'PIE: FAILED - {e}')
" 2>&1

echo ""
echo "=== END CORRECTED DIAGNOSTIC ==="
