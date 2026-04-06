#!/bin/bash
rm -f /tmp/.task_done* /tmp/.eng015* /tmp/.eng020*
cd /mnt/pgdata/morphlex && source venv/bin/activate

# Step 1: Create analyzers/pie.py via heredoc
cat > analyzers/pie.py << 'PYEOF'
import pickle, os

_pie_index = None
PIE_INDEX_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'pie_index.pkl')
ETYM_INDEX_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'etymology_index.pkl')

def _build_pie_index():
    with open(ETYM_INDEX_PATH, 'rb') as f:
        etym = pickle.load(f)
    pie = {}
    for eng_word, data in etym.items():
        for t in data.get('templates', []):
            if not isinstance(t, dict):
                continue
            args = t.get('args', {})
            name = t.get('name', '')
            src_lang = args.get('2', '') if isinstance(args, dict) else ''
            src_word = args.get('3', '') if isinstance(args, dict) else ''
            if src_lang == 'ine-pro' and src_word:
                if src_word not in pie:
                    pie[src_word] = []
                if eng_word not in pie[src_word]:
                    pie[src_word].append(eng_word)
    with open(PIE_INDEX_PATH, 'wb') as f:
        pickle.dump(pie, f)
    print(f'PIE index: {len(pie)} forms -> English concepts')
    return pie

def analyze_pie(word):
    global _pie_index
    if _pie_index is None:
        if os.path.exists(PIE_INDEX_PATH):
            with open(PIE_INDEX_PATH, 'rb') as f:
                _pie_index = pickle.load(f)
        else:
            _pie_index = _build_pie_index()
    results = []
    if word in _pie_index:
        for eng in _pie_index[word]:
            results.append({
                'language_code': 'ine-pro',
                'word_native': word,
                'lemma': word,
                'pos': '',
                'morphological_features': {},
                'source_tool': 'wiktextract-etymology',
                'confidence': 0.8,
                'word_translit': '',
                'english_concept': eng
            })
    return results

if __name__ == '__main__':
    _build_pie_index()
PYEOF

# Step 2: Build PIE index from etymology_index.pkl
echo "=== BUILD PIE INDEX ==="
python3 analyzers/pie.py 2>&1

echo ""
echo "=== PIE INDEX STATS ==="
python3 -c "
import pickle
with open('data/pie_index.pkl','rb') as f: idx=pickle.load(f)
print(f'Total PIE forms: {len(idx)}')
print(f'Sample forms:')
for k in list(idx.keys())[:10]:
    print(f'  {k} -> {idx[k][:3]}')
" 2>&1

echo ""
echo "=== PIE ADAPTER TEST ==="
python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
from analyzers.pie import analyze_pie
tests = ['*wódr̥','*ph₂tḗr','*méh₂tēr','*h₂stḗr','*dʰeh₁-','*bʰer-']
for w in tests:
    r = analyze_pie(w)
    print(f'{w}: {len(r)} results')
    if r: print(f'  -> {[x[\"english_concept\"] for x in r[:5]]}')
    else: print('  -> NO MATCH')
" 2>&1

touch /tmp/.eng020_done
echo "=== DONE ==="
