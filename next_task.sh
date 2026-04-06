#!/bin/bash
rm -f /tmp/.task_done* /tmp/.eng015* /tmp/.eng020*
cd /mnt/pgdata/morphlex && source venv/bin/activate
rm -f data/pie_index.pkl
cat > analyzers/pie.py << 'PYEOF'
import pickle, os
_etym = None
ETYM_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'etymology_index.pkl')
def _load_etym():
    global _etym
    if _etym is None:
        with open(ETYM_PATH, 'rb') as f: _etym = pickle.load(f)
def analyze_pie(english_word):
    _load_etym()
    results = []
    entry = _etym.get(english_word)
    if not entry: return results
    for t in entry.get('templates', []):
        if not isinstance(t, dict): continue
        args = t.get('args', {})
        if not isinstance(args, dict): continue
        src_lang = args.get('2', '')
        src_word = args.get('3', '')
        if src_lang == 'ine-pro' and src_word:
            if not any(r['word_native'] == src_word for r in results):
                results.append({'language_code':'ine-pro','word_native':src_word,'lemma':src_word,'english_concept':english_word,'relation':t.get('name',''),'source_tool':'wiktextract-etymology','confidence':0.9})
    return results
def get_pie_coverage():
    _load_etym()
    return sum(1 for w,e in _etym.items() if any(isinstance(t,dict) and isinstance(t.get('args'),dict) and t['args'].get('2')=='ine-pro' for t in e.get('templates',[])))
PYEOF
echo "=== PIE COVERAGE ==="
python3 -c "
import sys;sys.path.insert(0,'/mnt/pgdata/morphlex')
from analyzers.pie import get_pie_coverage
print(f'Words with PIE: {get_pie_coverage()}')
" 2>&1
echo ""
echo "=== TEST ==="
python3 -c "
import sys;sys.path.insert(0,'/mnt/pgdata/morphlex')
from analyzers.pie import analyze_pie
for w in ['water','father','mother','star','bear','eye','sun','fire','earth','house']:
    r = analyze_pie(w)
    print(f'{w}: {len(r)} PIE')
    for x in r[:3]: print(f'  {x[\"word_native\"]} ({x[\"relation\"]})')
    if not r: print('  NONE')
" 2>&1
touch /tmp/.eng020_forward_done
echo "=== DONE ==="
