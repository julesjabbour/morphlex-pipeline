#!/bin/bash
# CHECK ONLY: Verify concept_wordnet_map.pkl exists and report stats
# Timestamp: 2026-04-09-pkl-check-only
# NO INSTALLS. NO DOWNLOADS. JUST CHECK AND REPORT.

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== CONCEPT_WORDNET_MAP.PKL STATUS CHECK ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

PKL_FILE="/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl"

if [ ! -f "$PKL_FILE" ]; then
    echo "FILE DOES NOT EXIST: $PKL_FILE"
    echo ""
    echo "End: $(date -Iseconds)"
    exit 0
fi

echo "FILE EXISTS: $PKL_FILE"
ls -lh "$PKL_FILE"
echo ""

# Load and report stats
python3 << 'PYEOF'
import pickle
import sys

pkl_path = "/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl"

try:
    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)
except Exception as e:
    print(f"ERROR loading pkl: {e}")
    sys.exit(1)

print(f"TOTAL SYNSETS: {len(data)}")
print("")

# Count per-language coverage
lang_counts = {}
for synset_id, langs_dict in data.items():
    for lang in langs_dict.keys():
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

print("PER-LANGUAGE COVERAGE:")
for lang, count in sorted(lang_counts.items(), key=lambda x: -x[1]):
    print(f"  {lang}: {count} synsets")
print("")

# Find 5 sample entries with 4+ languages
print("SAMPLE ENTRIES WITH 4+ LANGUAGES:")
count = 0
for synset_id, langs_dict in data.items():
    if len(langs_dict) >= 4:
        print(f"  {synset_id}: {dict(langs_dict)}")
        count += 1
        if count >= 5:
            break

if count == 0:
    print("  (No entries found with 4+ languages)")
PYEOF

echo ""
echo "End: $(date -Iseconds)"
