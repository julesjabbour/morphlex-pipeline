cd /mnt/pgdata/morphlex && source venv/bin/activate
python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
from analyzers.greek import analyze_greek
for w in ['λόγος','θεός','πόλις']:
    r = analyze_greek(w)
    print(f'GRC {w}: {len(r)} results')
    if r: print(f'  -> {r[0]}')
"
