cd /mnt/pgdata/morphlex && source venv/bin/activate
echo "=== BUILDING WIKTEXTRACT INDEX ==="
python3 pipeline/build_wiktextract_index.py
echo ""
echo "=== TESTING HEBREW WITH INDEX ==="
python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
from analyzers.hebrew import analyze_hebrew
for w in ['ספר','כתב','בית','שלום','אדם']:
    r = analyze_hebrew(w)
    print(f'{w}: {len(r)} results')
    if r: print(f'  -> {r[0]}')
"
echo "=== COMPLETE ==="
