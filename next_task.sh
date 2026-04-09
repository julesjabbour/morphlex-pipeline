#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== concept_wordnet_map.pkl Check ==="
echo "Git HEAD: $(git rev-parse --short HEAD)"
echo "Start: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

PKL_FILE="data/concept_wordnet_map.pkl"

if [ ! -f "$PKL_FILE" ]; then
    echo "FILE NOT FOUND: $PKL_FILE"
    echo ""
    echo "End: $(date '+%Y-%m-%d %H:%M:%S')"
    exit 0
fi

# File exists - report size
SIZE_BYTES=$(stat -c%s "$PKL_FILE")
SIZE_MB=$(echo "scale=2; $SIZE_BYTES / 1048576" | bc)
echo "FILE EXISTS: $PKL_FILE"
echo "SIZE: ${SIZE_MB} MB ($SIZE_BYTES bytes)"
echo ""

# Load and analyze with Python
python3 << 'PYEOF'
import pickle
import sys

try:
    with open("data/concept_wordnet_map.pkl", "rb") as f:
        data = pickle.load(f)
except Exception as e:
    print(f"ERROR loading pkl: {e}")
    sys.exit(1)

print(f"TOTAL SYNSETS: {len(data)}")
print("")

# Per-language coverage
lang_counts = {}
entries_4plus = []

for synset_id, langs in data.items():
    if isinstance(langs, dict):
        num_langs = len(langs)
        for lang in langs.keys():
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
        if num_langs >= 4 and len(entries_4plus) < 5:
            entries_4plus.append((synset_id, langs))

print("PER-LANGUAGE COVERAGE:")
for lang in sorted(lang_counts.keys()):
    print(f"  {lang}: {lang_counts[lang]}")
print("")

print("5 SAMPLE ENTRIES WITH 4+ LANGUAGES:")
for synset_id, langs in entries_4plus:
    lang_list = ", ".join(sorted(langs.keys()))
    print(f"  {synset_id}: [{lang_list}]")
    for lang, words in sorted(langs.items()):
        if isinstance(words, list):
            print(f"    {lang}: {words[:3]}")
        else:
            print(f"    {lang}: {words}")
    print("")
PYEOF

echo "End: $(date '+%Y-%m-%d %H:%M:%S')"
