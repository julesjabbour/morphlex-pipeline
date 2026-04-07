#!/bin/bash
# ZOMBIE CLEANUP + REBUILD PKL WITH DIACRITICS FIX + 10-WORD TEST
# This script is picked up by cron via run.sh
#
# Order of operations:
# 1. Kill all other morphlex processes (zombie cleanup)
# 2. Clean git state and show HEAD
# 3. Rebuild pkl with diacritics-stripped keys
# 4. Run 10-word test
# 5. Create marker file (handled by run.sh on success)

set -e

echo "=== ZOMBIE CLEANUP + PKL REBUILD + 10-WORD TEST ==="
echo "Start: $(date -Iseconds)"
echo ""

# Step 1: KILL ALL OTHER MORPHLEX PROCESSES
echo "=== STEP 1: KILLING ZOMBIE PROCESSES ==="
echo "Killing build_forward_translations processes..."
KILLED_BFT=$(pgrep -f "build_forward_translations" 2>/dev/null | wc -l || echo "0")
pkill -f "build_forward_translations" 2>/dev/null || true
echo "Killing python3.*morphlex processes..."
KILLED_PY=$(pgrep -f "python3.*morphlex" 2>/dev/null | wc -l || echo "0")
pkill -f "python3.*morphlex" 2>/dev/null || true
echo "Waiting 5 seconds for graceful shutdown..."
sleep 5
echo "Force-killing any remaining processes..."
pkill -9 -f "build_forward_translations" 2>/dev/null || true
pkill -9 -f "python3.*morphlex" 2>/dev/null || true
echo "Zombie cleanup complete. Killed approximately: $KILLED_BFT build_forward_translations, $KILLED_PY python3.*morphlex"
echo ""

# Step 2: CLEAN GIT STATE
echo "=== STEP 2: CLEAN GIT STATE ==="
cd /mnt/pgdata/morphlex
git fetch origin main 2>&1 || { echo "Git fetch failed, retrying..."; sleep 2; git fetch origin main; }
git reset --hard origin/main
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Git HEAD (short): $(git rev-parse --short HEAD)"
echo ""

# Activate venv after git reset to ensure latest code
source venv/bin/activate

# Step 3: REBUILD PKL WITH DIACRITICS FIX
echo "=== STEP 3: REBUILD PKL ==="
echo "Current pkl before rebuild:"
ls -la data/forward_translations.pkl 2>/dev/null || echo "  (does not exist)"
echo ""

echo "Rebuilding forward_translations.pkl with diacritics-stripped keys..."
python3 pipeline/build_forward_translations.py
echo ""

# Step 4: RUN 10-WORD TEST
echo "=== STEP 4: 10-WORD TEST ==="
python3 << 'PYEOF'
import pickle
import os
import re
from datetime import datetime

PKL_PATH = '/mnt/pgdata/morphlex/data/forward_translations.pkl'

# Arabic diacritics pattern
ARABIC_DIACRITICS = re.compile(r'[\u064B-\u065F\u0670]')

# Test words: ماء نار يد عين حجر قلب شمس قمر شجرة دم
TEST_WORDS = [
    ('ماء', 'water'),
    ('نار', 'fire'),
    ('يد', 'hand'),
    ('عين', 'eye'),
    ('حجر', 'stone'),
    ('قلب', 'heart'),
    ('شمس', 'sun'),
    ('قمر', 'moon'),
    ('شجرة', 'tree'),
    ('دم', 'blood'),
]

LANGUAGES = ['ar', 'tr', 'de', 'en', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro']
TARGET_LANGUAGES = ['en', 'tr', 'de', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro']

# Load pkl
with open(PKL_PATH, 'rb') as f:
    translations = pickle.load(f)

file_size = os.path.getsize(PKL_PATH)
print(f"PKL file: {PKL_PATH}")
print(f"File size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
print(f"Total Arabic words: {len(translations):,}")
print()

# Sample 5 keys to prove diacritics are stripped
print("SAMPLE 5 PKL KEYS (proof diacritics stripped):")
keys_list = list(translations.keys())
import random
random.seed(42)
sample_keys = random.sample(keys_list, min(5, len(keys_list)))

for key in sample_keys:
    has_diacritics = bool(ARABIC_DIACRITICS.search(key))
    status = "HAS DIACRITICS" if has_diacritics else "clean"
    print(f"  '{key}' - {status}")
print()

# Count keys with diacritics
keys_with_diacritics = sum(1 for k in translations.keys() if ARABIC_DIACRITICS.search(k))
print(f"Keys with diacritics: {keys_with_diacritics:,} / {len(translations):,}")
print()

# Test each word
print("10-WORD TEST RESULTS:")
total_results = 0
lang_results = {lang: 0 for lang in LANGUAGES}

for ar_word, en_meaning in TEST_WORDS:
    trans = translations.get(ar_word, {})
    if trans:
        # Arabic word itself counts as 1
        lang_results['ar'] += 1
        total_results += 1
        # Count other languages
        for lang in TARGET_LANGUAGES:
            if lang in trans:
                lang_results[lang] += 1
                total_results += 1

print()
for lang in LANGUAGES:
    count = lang_results[lang]
    status = "[OK]" if count > 0 else "[MISS]"
    print(f"  {lang} : {count} results {status}")

print()
print(f"TOTAL: {total_results} results from 10 words x 11 languages")
print(f"PKL file size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
PYEOF

echo ""

# Step 5: Marker file creation is handled by run.sh on success
# Show the marker that will be created
MARKER_DIR="/tmp/morphlex_markers"
mkdir -p "$MARKER_DIR"
TASK_HASH=$(md5sum /mnt/pgdata/morphlex/next_task.sh | cut -d' ' -f1)
echo "=== STEP 5: MARKER FILE ==="
echo "Marker will be created at: $MARKER_DIR/done_$TASK_HASH"
echo "(run.sh creates the marker on success)"
echo ""

echo "End: $(date -Iseconds)"
echo "=== DONE ==="
