#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "======================================================================"
echo "FULL INVESTIGATION OF WORDNET DIRECTORIES AND BRIDGE"
echo "======================================================================"
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

echo "======================================================================"
echo "STEP 1: LATIN-WORDNET DIRECTORY CONTENTS"
echo "======================================================================"
ls -lah /mnt/pgdata/morphlex/data/open_wordnets/latin-wordnet/
echo ""

echo "======================================================================"
echo "STEP 2: AGWN-JCUENOD DIRECTORY CONTENTS"
echo "======================================================================"
ls -lah /mnt/pgdata/morphlex/data/open_wordnets/agwn-jcuenod/
echo ""

echo "======================================================================"
echo "STEP 3: FIRST 500 BYTES OF EACH FILE IN LATIN-WORDNET"
echo "======================================================================"
for f in /mnt/pgdata/morphlex/data/open_wordnets/latin-wordnet/*; do
    echo "--- $f ---"
    file "$f"
    head -c 500 "$f" 2>/dev/null
    echo ""
done
echo ""

echo "======================================================================"
echo "STEP 4: FIRST 500 BYTES OF EACH FILE IN AGWN-JCUENOD"
echo "======================================================================"
for f in /mnt/pgdata/morphlex/data/open_wordnets/agwn-jcuenod/*; do
    echo "--- $f ---"
    file "$f"
    head -c 500 "$f" 2>/dev/null
    echo ""
done
echo ""

echo "======================================================================"
echo "STEP 5: GIT LOG FOR THESE PATHS (LAST 30 COMMITS)"
echo "======================================================================"
git log --oneline --all -- 'data/open_wordnets/latin-wordnet/' 'data/open_wordnets/agwn-jcuenod/' 2>&1 | head -30
echo ""

echo "======================================================================"
echo "STEP 6: GIT STATUS OF DATA DIR"
echo "======================================================================"
git status data/open_wordnets/ 2>&1 | head -40
echo ""

echo "======================================================================"
echo "STEP 7: PYTHON BRIDGE FILE ANALYSIS"
echo "======================================================================"
python3 -c "
import pickle

bridge_path = '/mnt/pgdata/morphlex/data/open_wordnets/pwn30_to_oewn_map.pkl'
bridge = pickle.load(open(bridge_path, 'rb'))

print(f'Type: {type(bridge).__name__}')
print(f'Total mappings: {len(bridge):,}')
print('')

items = list(bridge.items())[:20]
print('First 20 entries:')
for k, v in items:
    print(f'  {k!r:30} -> {v!r}')

print('')
identity_count = sum(1 for k, v in bridge.items() if k == v)
print(f'Identity mappings (key==value): {identity_count:,} of {len(bridge):,} ({100*identity_count/len(bridge):.1f}%)')

print('')
non_identity = [(k, v) for k, v in bridge.items() if k != v][:5]
print(f'First 5 non-identity mappings:')
for k, v in non_identity:
    print(f'  {k!r} -> {v!r}')
"

echo ""
echo "======================================================================"
echo "END OF INVESTIGATION"
echo "======================================================================"
echo "End: $(date -Iseconds)"
