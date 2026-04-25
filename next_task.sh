#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

python3 << 'PYEOF'
import pickle
from collections import Counter

with open('/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl', 'rb') as f:
    cm = pickle.load(f)

print(f"Total synsets: {len(cm):,}")

# Sample 3 synsets, show all language codes per synset
for sid, data in list(cm.items())[:3]:
    words = data.get('words', {})
    print(f"\n{sid}: pos={data.get('pos')}, langs={list(words.keys())}")
    for lang, wlist in words.items():
        print(f"  {lang}: {wlist[:3]}")

# Count language distribution
lang_counts = Counter()
for data in cm.values():
    for lang in data.get('words', {}).keys():
        lang_counts[lang] += 1

print(f"\nLanguage coverage:")
for lang, cnt in lang_counts.most_common():
    print(f"  {lang}: {cnt:,} synsets")
PYEOF
