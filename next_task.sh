#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

# Install NLTK if needed and download WordNet data silently
pip install nltk > /dev/null 2>&1
python3 -c "import nltk; nltk.download('wordnet', quiet=True); nltk.download('omw-1.4', quiet=True)" > /dev/null 2>&1

# Download German Wiktextract data
DATA_DIR="/mnt/pgdata/morphlex/data/open_wordnets"
GERMAN_FILE="$DATA_DIR/kaikki-german.jsonl.gz"

if [ ! -f "$DATA_DIR/kaikki-german.jsonl" ] && [ ! -f "$GERMAN_FILE" ]; then
    echo "Downloading German Wiktextract data..."
    wget -q 'https://kaikki.org/dictionary/German/kaikki.org-dictionary-German.jsonl.gz' -O "$GERMAN_FILE"
    if [ $? -ne 0 ]; then
        echo "FATAL: Download failed"
        exit 1
    fi
    echo "Downloaded: $(ls -lh "$GERMAN_FILE" | awk '{print $5}')"
fi

# Run German Wiktextract parser
echo ""
python3 scripts/parse_german_wiktextract.py

echo ""
echo "=== SUMMARY ==="
python3 << 'PYEOF'
import pickle
from pathlib import Path

wiktextract_file = Path('/mnt/pgdata/morphlex/data/open_wordnets/german_wiktextract_synset_map.pkl')
odenet_file = Path('/mnt/pgdata/morphlex/data/open_wordnets/odenet_synset_map.pkl')
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

# OdeNet stats (previous source)
if odenet_file.exists():
    with open(odenet_file, 'rb') as f:
        ode_map = pickle.load(f)
    ode_synsets = len(ode_map)
    ode_words = sum(len(v) for v in ode_map.values())
    ode_overlap = len(concept_synsets & set(ode_map.keys()))
    ode_pct = 100 * ode_overlap / len(concept_synsets) if concept_synsets else 0
    print(f"OdeNet (OLD):      {ode_synsets:,} synsets, {ode_words:,} words, {ode_overlap:,} overlap ({ode_pct:.1f}%)")
else:
    print("OdeNet: FILE NOT FOUND")
    ode_synsets = 0
    ode_words = 0

# Wiktextract stats (new source)
if wiktextract_file.exists():
    with open(wiktextract_file, 'rb') as f:
        wik_map = pickle.load(f)
    wik_synsets = len(wik_map)
    wik_words = sum(len(v) for v in wik_map.values())
    wik_overlap = len(concept_synsets & set(wik_map.keys()))
    wik_pct = 100 * wik_overlap / len(concept_synsets) if concept_synsets else 0
    print(f"Wiktextract (NEW): {wik_synsets:,} synsets, {wik_words:,} words, {wik_overlap:,} overlap ({wik_pct:.1f}%)")
    print("")
    if ode_synsets > 0:
        improvement = wik_synsets - ode_synsets
        improvement_pct = 100 * improvement / ode_synsets
        print(f"IMPROVEMENT: {improvement:+,} synsets ({improvement_pct:+.1f}%)")
        if wik_synsets >= 50000:
            print(f"TARGET MET: {wik_synsets:,} >= 50,000 synsets")
        else:
            print(f"TARGET NOT MET: {wik_synsets:,} < 50,000 synsets")
else:
    print("Wiktextract: FILE NOT FOUND")
PYEOF
