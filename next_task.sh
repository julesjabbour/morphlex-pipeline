#!/bin/bash
# VERIFY NEW PKL WITH 10-WORD ARABIC ANCHOR TEST
# Reports pkl rebuild stats and runs pipeline end-to-end test
#
# Usage: bash next_task.sh
# Working directory: /mnt/pgdata/morphlex

set -e

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== ARABIC ANCHOR TEST WITH NEW PKL ==="
echo "Start: $(date -Iseconds)"
echo ""

# First report the pkl stats from the rebuild
python3 << 'PYEOF'
import pickle
import os
import sys
from datetime import datetime
from io import StringIO

PKL_PATH = '/mnt/pgdata/morphlex/data/forward_translations.pkl'
FULL_OUTPUT_PATH = '/mnt/pgdata/morphlex/arabic_anchor_test_full_pkl.md'

# Test words
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

print("=" * 60)
print("PKL REBUILD STATS (from truncated Slack output)")
print("=" * 60)

# Load and report pkl stats
if not os.path.exists(PKL_PATH):
    print(f"ERROR: {PKL_PATH} not found!")
    sys.exit(1)

pkl_size = os.path.getsize(PKL_PATH)
print(f"PKL file: {PKL_PATH}")
print(f"File size: {pkl_size:,} bytes ({pkl_size/1024/1024:.2f} MB)")
print()

with open(PKL_PATH, 'rb') as f:
    forward_translations = pickle.load(f)

print(f"Total Arabic words in pkl: {len(forward_translations):,}")
print()

# Per-language coverage
print("Per-language coverage:")
lang_counts = {lang: 0 for lang in TARGET_LANGUAGES}
for word_trans in forward_translations.values():
    for lang in word_trans:
        if lang in lang_counts:
            lang_counts[lang] += 1

for lang in TARGET_LANGUAGES:
    print(f"  {lang}: {lang_counts[lang]:,} Arabic words have translations")

print()
print("=" * 60)
print("10-WORD ARABIC ANCHOR TEST")
print("=" * 60)

# Full output for markdown file
full_output = StringIO()

def write_full(msg):
    full_output.write(msg + "\n")

write_full("# Arabic Anchor Pipeline Test - Full PKL Verification")
write_full("")
write_full(f"**Test date:** {datetime.now().isoformat()}")
write_full(f"**PKL file:** {PKL_PATH}")
write_full(f"**PKL size:** {pkl_size:,} bytes ({pkl_size/1024/1024:.2f} MB)")
write_full(f"**Total Arabic words:** {len(forward_translations):,}")
write_full("")
write_full("## Per-language coverage in PKL")
write_full("")
for lang in TARGET_LANGUAGES:
    write_full(f"- {lang}: {lang_counts[lang]:,}")
write_full("")
write_full("---")
write_full("")

# Show translations for test words
write_full("## Test Word Translations")
write_full("")

print()
print("Test word translations from pkl:")
for ar_word, en_meaning in TEST_WORDS:
    trans = forward_translations.get(ar_word, {})
    status = "FOUND" if trans else "MISSING"
    print(f"  {ar_word} ({en_meaning}): {status} - {len(trans)} languages")
    write_full(f"### {ar_word} ({en_meaning})")
    if trans:
        for lang, word in sorted(trans.items()):
            write_full(f"- {lang}: {word}")
    else:
        write_full("- NOT FOUND in pkl")
    write_full("")

print()

# Import orchestrator and run analysis
sys.path.insert(0, '/mnt/pgdata/morphlex')
from pipeline.orchestrator import PipelineOrchestrator

write_full("---")
write_full("")
write_full("## Detailed Analysis Results")
write_full("")

orchestrator = PipelineOrchestrator()

# Track results
results_by_lang = {lang: {'count': 0, 'ok': 0, 'empty': 0, 'words_received': [], 'all_results': []} for lang in LANGUAGES}
all_results = []

for arabic_word, english_meaning in TEST_WORDS:
    word_trans = forward_translations.get(arabic_word, {})
    write_full(f"### Arabic: {arabic_word} ({english_meaning})")
    write_full("")
    write_full(f"Translations from pkl: {word_trans}")
    write_full("")

    for lang in LANGUAGES:
        # Determine what word the adapter will receive
        if lang == 'ar':
            word_received = arabic_word
        elif lang == 'ine-pro':
            word_received = word_trans.get('en', 'NO_TRANSLATION')
        else:
            word_received = word_trans.get(lang, 'NO_TRANSLATION')

        try:
            results = orchestrator.analyze(arabic_word, lang)
            count = len(results) if results else 0
        except Exception as e:
            results = []
            count = 0
            write_full(f"**ERROR** {lang}: {e}")

        results_by_lang[lang]['count'] += count
        results_by_lang[lang]['words_received'].append(word_received)
        results_by_lang[lang]['all_results'].extend(results or [])

        if count > 0:
            results_by_lang[lang]['ok'] += 1
            all_results.extend(results)
        else:
            results_by_lang[lang]['empty'] += 1

        # Write detailed results
        write_full(f"**{lang}**: received `{word_received}` -> {count} results")
        if results:
            for r in results:
                lemma = r.get('lemma', '?')
                pos = r.get('pos', '?')
                root = r.get('root', '')
                morph = r.get('morphological_features', {})
                write_full(f"  - lemma={lemma}, pos={pos}, root={root}, features={morph}")
        write_full("")

    write_full("---")
    write_full("")

# Summary table in markdown
write_full("## Per-Language Summary Table")
write_full("")
write_full("| Language | Total | OK | Empty | Status | Sample Words Received |")
write_full("|----------|------:|---:|------:|--------|----------------------|")

summary_lines = []
for lang in LANGUAGES:
    stats = results_by_lang[lang]
    count = stats['count']
    ok = stats['ok']
    empty = stats['empty']
    words = stats['words_received'][:3]

    if lang == 'ar':
        status = '[OK]' if count > 0 else '[EMPTY]'
    else:
        has_arabic_input = any('\u0600' <= c <= '\u06ff' for w in words for c in str(w))
        if has_arabic_input:
            status = '[WRONG-LANG]'
        elif count > 0:
            status = '[OK]'
        else:
            status = '[EMPTY]'

    sample_words = ', '.join(str(w)[:15] for w in words)
    write_full(f"| {lang} | {count} | {ok} | {empty} | {status} | {sample_words} |")
    summary_lines.append((lang, count, status))

write_full("")
write_full(f"**TOTAL:** {len(all_results)} results from {len(TEST_WORDS)} words x {len(LANGUAGES)} languages")
write_full("")

# Write full output to file
with open(FULL_OUTPUT_PATH, 'w', encoding='utf-8') as f:
    f.write(full_output.getvalue())

# Print summary to stdout
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print()
print("Per-language results:")
for lang, count, status in summary_lines:
    print(f"  {lang:<10} : {count:>4} results {status}")

print()
print(f"TOTAL: {len(all_results)} results from {len(TEST_WORDS)} words x {len(LANGUAGES)} languages")
print()
print(f"PKL file size: {pkl_size:,} bytes ({pkl_size/1024/1024:.2f} MB)")
print(f"Full details: {FULL_OUTPUT_PATH}")
PYEOF

echo ""
echo "End: $(date -Iseconds)"
echo "=== DONE ==="
