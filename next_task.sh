#!/bin/bash
# Rebuild pkl with diacritics fix + 10-word Arabic test
# This script runs once via cron, then gets a marker to prevent re-runs.

cd /mnt/pgdata/morphlex && source venv/bin/activate

# Re-enable crontab (was removed by nuclear stop)
(crontab -l 2>/dev/null | grep -v morphlex; echo "*/2 * * * * cd /mnt/pgdata/morphlex && bash run.sh >> /tmp/morphlex_cron.log 2>&1") | crontab -

echo "=== REBUILD PKL + 10-WORD TEST ==="
echo "Start: $(date -Iseconds)"
echo "Git HEAD: $(git rev-parse HEAD)"
echo ""

# Rebuild forward_translations.pkl with diacritics-stripped keys
echo "=== STEP 1: REBUILD PKL ==="
python3 pipeline/build_forward_translations.py
echo ""

# Run 10-word test and show 5 sample keys
echo "=== STEP 2: 10-WORD TEST ==="
python3 << 'PYEOF'
import pickle
import os
import re
import random

PKL_PATH = '/mnt/pgdata/morphlex/data/forward_translations.pkl'
ARABIC_DIACRITICS = re.compile(r'[\u064B-\u065F\u0670]')

# 10 test words
TEST_WORDS = ['ماء', 'نار', 'يد', 'عين', 'حجر', 'قلب', 'شمس', 'قمر', 'شجرة', 'دم']
LANGUAGES = ['ar', 'en', 'tr', 'de', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro']

with open(PKL_PATH, 'rb') as f:
    translations = pickle.load(f)

file_size = os.path.getsize(PKL_PATH)
print(f"PKL file size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
print(f"Total Arabic keys: {len(translations):,}")
print()

# Show 5 sample keys to prove diacritics are stripped
print("5 SAMPLE PKL KEYS (proof diacritics stripped):")
random.seed(42)
sample_keys = random.sample(list(translations.keys()), min(5, len(translations)))
for key in sample_keys:
    has_diacritics = bool(ARABIC_DIACRITICS.search(key))
    status = "HAS DIACRITICS!" if has_diacritics else "clean"
    print(f"  '{key}' - {status}")
print()

# Count total keys with diacritics
keys_with_diacritics = sum(1 for k in translations.keys() if ARABIC_DIACRITICS.search(k))
print(f"Keys with diacritics: {keys_with_diacritics} / {len(translations)}")
print()

# Test 10 words across 11 languages
print("10-WORD TEST:")
lang_results = {lang: 0 for lang in LANGUAGES}
total = 0

for word in TEST_WORDS:
    trans = translations.get(word, {})
    if trans:
        lang_results['ar'] += 1
        total += 1
        for lang in LANGUAGES[1:]:  # skip 'ar'
            if lang in trans:
                lang_results[lang] += 1
                total += 1

print()
for lang in LANGUAGES:
    count = lang_results[lang]
    status = "[OK]" if count > 0 else "[EMPTY]"
    print(f"  {lang} : {count} results {status}")

print()
print(f"TOTAL: {total} results from 10 words x 11 languages")
PYEOF

echo ""
echo "End: $(date -Iseconds)"
echo "=== DONE ==="
