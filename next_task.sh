#!/bin/bash
# ENG-021: Wiktextract Integration Test
# Tests loading English entries from Wiktextract dump

cd /mnt/pgdata/morphlex && source venv/bin/activate

python3 << 'EOF'
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')

from pipeline.wiktextract_loader import load_wiktextract, get_stats

FILEPATH = '/mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz'
MAX_ENTRIES = 1000

print("=== WIKTEXTRACT INTEGRATION TEST (ENG-021) ===")
print(f"Loading first {MAX_ENTRIES} English entries from Wiktextract dump...")
print(f"File: {FILEPATH}")
print()

data = load_wiktextract(FILEPATH, max_entries=MAX_ENTRIES)
stats = get_stats(data)

print(f"Total entries loaded: {stats['total_words']}")
print(f"Total definitions: {stats['total_definitions']}")
print(f"Entries with etymology: {stats['entries_with_etymology']}")

print(f"\nLanguages found in translations:")
if stats['translations_by_lang']:
    for lang, count in sorted(stats['translations_by_lang'].items(), key=lambda x: -x[1]):
        print(f"  {lang}: {count} translations")
else:
    print("  (no translations found in sample)")

# Find a good sample entry with translations
sample_entry = None
for word, entry in data.items():
    if entry['translations'] and len(entry['definitions']) > 0:
        sample_entry = (word, entry)
        break

if sample_entry:
    word, entry = sample_entry
    print(f"\n=== SAMPLE ENTRY WITH TRANSLATIONS ===")
    print(f"Word: {word}")
    print(f"POS: {entry['pos']}")
    print(f"Definitions ({len(entry['definitions'])} total):")
    for i, defn in enumerate(entry['definitions'][:3], 1):
        print(f"  {i}. {defn[:100]}{'...' if len(defn) > 100 else ''}")
    print(f"Translations:")
    for lang, words in entry['translations'].items():
        print(f"  {lang}: {', '.join(words[:5])}{'...' if len(words) > 5 else ''}")
    if entry['etymology']:
        print(f"Etymology templates ({len(entry['etymology'])} total):")
        for etym in entry['etymology'][:2]:
            print(f"  - {etym['name']}: {etym['args']}")
    if entry['etymology_text']:
        etym_text = entry['etymology_text'][:150]
        print(f"Etymology text: {etym_text}{'...' if len(entry['etymology_text']) > 150 else ''}")
else:
    print("\n(No sample entry with translations found)")

print("\n=== TEST COMPLETE ===")
EOF
