#!/bin/bash
FLAG="/tmp/.eng015_debug_concepts"
if [ -f "$FLAG" ]; then
    echo "=== ALREADY COMPLETE ==="
    exit 0
fi
cd /mnt/pgdata/morphlex && source venv/bin/activate
python3 -c "
import sys, pickle, json
sys.path.insert(0, '/mnt/pgdata/morphlex')
with open('data/wiktextract_index.pkl','rb') as f:
    idx = pickle.load(f)

# Show what German words map to 'water'
de_idx = idx.get('de', {})
water_words = []
for foreign_word, concepts in de_idx.items():
    for c in concepts:
        eng = c.get('english_word','') if isinstance(c, dict) else str(c)
        if eng == 'water':
            water_words.append((foreign_word, c))

print(f'German words mapping to water: {len(water_words)}')
for fw, c in water_words[:5]:
    print(f'  {fw}:')
    if isinstance(c, dict):
        print(f'    keys: {list(c.keys())}')
        print(f'    pos: {c.get(\"pos\",\"MISSING\")}')
        print(f'    english_word: {c.get(\"english_word\",\"MISSING\")}')
    else:
        print(f'    type: {type(c)}, value: {c}')

print()
# Same for fire
fire_words = []
for foreign_word, concepts in de_idx.items():
    for c in concepts:
        eng = c.get('english_word','') if isinstance(c, dict) else str(c)
        if eng == 'fire':
            fire_words.append((foreign_word, c))

print(f'German words mapping to fire: {len(fire_words)}')
for fw, c in fire_words[:5]:
    print(f'  {fw}:')
    if isinstance(c, dict):
        print(f'    pos: {c.get(\"pos\",\"MISSING\")}')
    else:
        print(f'    type: {type(c)}')
" 2>&1
touch "$FLAG"
echo "=== DONE ==="
