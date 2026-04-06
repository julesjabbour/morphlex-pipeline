cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== INDEX VERIFICATION ==="
ls -lh /mnt/pgdata/morphlex/data/wiktextract_index.pkl
echo ""

python3 -c "
import sys, pickle
sys.path.insert(0, '/mnt/pgdata/morphlex')

# Check index size
with open('/mnt/pgdata/morphlex/data/wiktextract_index.pkl', 'rb') as f:
    idx = pickle.load(f)
print('Languages in index:', list(idx.keys()))
for lang, data in idx.items():
    print(f'  {lang}: {len(data)} entries')

# Test Hebrew
from analyzers.hebrew import analyze_hebrew
for w in ['ספר','כתב','בית','שלום','אדם']:
    r = analyze_hebrew(w)
    print(f'HE {w}: {len(r)} results')

# Test Greek
from analyzers.greek import analyze_greek
for w in ['λόγος','θεός','πόλις']:
    r = analyze_greek(w)
    print(f'GRC {w}: {len(r)} results')
" 2>&1

echo "=== COMPLETE ==="
