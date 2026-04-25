#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "Running Latin WordNet parser..."
python3 scripts/parse_latin_wordnet.py

echo ""
echo "Running Greek WordNet parser..."
python3 scripts/parse_agwn_jcuenod.py

echo ""
echo "=== SUMMARY ==="
python3 << 'PYEOF'
import pickle
from pathlib import Path

latin_file = Path('/mnt/pgdata/morphlex/data/open_wordnets/latin_synset_map.pkl')
greek_file = Path('/mnt/pgdata/morphlex/data/open_wordnets/agwn_synset_map.pkl')
concept_file = Path('/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl')

# Load concept map for overlap calc
concept_synsets = set()
if concept_file.exists():
    with open(concept_file, 'rb') as f:
        cm = pickle.load(f)
    for k in cm.keys():
        if isinstance(k, str) and k.startswith('oewn-'):
            concept_synsets.add(k)
    print(f"concept_wordnet_map: {len(concept_synsets):,} synsets")
    print("")

# Latin stats
if latin_file.exists():
    with open(latin_file, 'rb') as f:
        latin_map = pickle.load(f)
    lat_synsets = len(latin_map)
    lat_words = sum(len(v) for v in latin_map.values())
    lat_overlap = len(concept_synsets & set(latin_map.keys()))
    lat_pct = 100 * lat_overlap / len(concept_synsets) if concept_synsets else 0
    print(f"LATIN: {lat_synsets:,} synsets, {lat_words:,} words, {lat_overlap:,} overlap ({lat_pct:.1f}%)")
else:
    print(f"LATIN: FILE NOT FOUND")

# Greek stats
if greek_file.exists():
    with open(greek_file, 'rb') as f:
        greek_map = pickle.load(f)
    grk_synsets = len(greek_map)
    grk_words = sum(len(v) for v in greek_map.values())
    grk_overlap = len(concept_synsets & set(greek_map.keys()))
    grk_pct = 100 * grk_overlap / len(concept_synsets) if concept_synsets else 0
    print(f"GREEK: {grk_synsets:,} synsets, {grk_words:,} words, {grk_overlap:,} overlap ({grk_pct:.1f}%)")
else:
    print(f"GREEK: FILE NOT FOUND")
PYEOF
