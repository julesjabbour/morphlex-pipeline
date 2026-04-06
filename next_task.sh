#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== TESTING SANSKRIT ADAPTER (ENG-018) ==="
python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
from analyzers.sanskrit import analyze_sanskrit

# Test with 5 Sanskrit words
test_words = [
    ('देव', 'deva/god'),
    ('वाच्', 'vac/speech'),
    ('मनस्', 'manas/mind'),
    ('राजन्', 'rajan/king'),
    ('पथ', 'path/road'),
]

total_results = 0
for word, meaning in test_words:
    r = analyze_sanskrit(word)
    total_results += len(r)
    print(f'SA {word} ({meaning}): {len(r)} results')
    if r:
        print(f'  -> {r[0]}')

print()
print(f'=== SUMMARY ===')
print(f'Total words tested: {len(test_words)}')
print(f'Total results: {total_results}')
"

echo "=== COMPLETE ==="
