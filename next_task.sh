#!/bin/bash
# Task: Rebuild forward_translations.pkl + 1000-word batch test
# Session: Rebuild pkl with full logging, then test 1000 Arabic words across all 11 languages
# Zero error suppression - all exceptions must log visibly

cd /mnt/pgdata/morphlex && source venv/bin/activate

GIT_HEAD=$(git rev-parse HEAD)
START_TIME=$(date -Iseconds)

echo "=== PKL REBUILD + 1000-WORD BATCH TEST ==="
echo "Start: $START_TIME"
echo "Git HEAD: $GIT_HEAD"
echo ""

# ============================================================
# TASK 1: REBUILD forward_translations.pkl WITH FULL LOGGING
# ============================================================

echo "============================================================"
echo "TASK 1: REBUILD forward_translations.pkl"
echo "============================================================"
echo ""

# Record previous pkl stats
PKL_PATH="/mnt/pgdata/morphlex/data/forward_translations.pkl"
PREV_KEY_COUNT=18807  # Known previous count

if [ -f "$PKL_PATH" ]; then
    PREV_SIZE=$(stat -c%s "$PKL_PATH")
    echo "Previous pkl file size: $PREV_SIZE bytes"
else
    PREV_SIZE=0
    echo "No previous pkl file exists"
fi
echo "Previous key count (known): $PREV_KEY_COUNT"
echo ""

echo "--- Running build_forward_translations.py with FULL logging ---"
echo ""

# Run the build script - all output visible, no suppression
python3 /mnt/pgdata/morphlex/pipeline/build_forward_translations.py 2>&1
BUILD_EXIT_CODE=$?

echo ""
echo "Build exit code: $BUILD_EXIT_CODE"
echo ""

# Analyze the rebuilt pkl
if [ -f "$PKL_PATH" ]; then
    NEW_SIZE=$(stat -c%s "$PKL_PATH")
    echo "New pkl file size: $NEW_SIZE bytes ($(echo "scale=2; $NEW_SIZE/1024/1024" | bc) MB)"

    python3 << 'PYEOF'
import pickle
import sys

PKL_PATH = '/mnt/pgdata/morphlex/data/forward_translations.pkl'
PREV_COUNT = 18807

with open(PKL_PATH, 'rb') as f:
    translations = pickle.load(f)

new_count = len(translations)
print(f"New key count: {new_count:,}")
print(f"Previous key count: {PREV_COUNT:,}")

diff = new_count - PREV_COUNT
if diff > 0:
    print(f"CHANGE: +{diff} entries gained")
elif diff < 0:
    print(f"CHANGE: {diff} entries lost")
else:
    print("CHANGE: No difference (same count)")

# Language coverage stats
print()
print("Language coverage in rebuilt pkl:")
lang_counts = {}
for word, trans in translations.items():
    for lang in trans.keys():
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

for lang in sorted(lang_counts.keys()):
    print(f"  {lang}: {lang_counts[lang]:,} entries")
PYEOF
else
    echo "ERROR: PKL file was not created!"
fi

echo ""
echo "============================================================"
echo "TASK 1 COMPLETE"
echo "============================================================"
echo ""

# ============================================================
# TASK 2: 1000-WORD BATCH TEST WITH ALL ADAPTERS
# ============================================================

echo "============================================================"
echo "TASK 2: 1000-WORD BATCH TEST ACROSS ALL 11 LANGUAGES"
echo "============================================================"
echo ""

python3 << 'PYEOF'
import pickle
import csv
import os
import sys
import traceback
from datetime import datetime
from collections import defaultdict

# Import orchestrator
sys.path.insert(0, '/mnt/pgdata/morphlex')
from pipeline.orchestrator import PipelineOrchestrator

PKL_PATH = '/mnt/pgdata/morphlex/data/forward_translations.pkl'
REPORTS_DIR = '/mnt/pgdata/morphlex/reports'
CSV_PATH = os.path.join(REPORTS_DIR, 'batch_1000_test.csv')
ERROR_PATH = os.path.join(REPORTS_DIR, 'batch_1000_errors.md')

os.makedirs(REPORTS_DIR, exist_ok=True)

# Load pkl and get first 1000 keys
print("Loading forward_translations.pkl...")
with open(PKL_PATH, 'rb') as f:
    translations = pickle.load(f)

arabic_keys = list(translations.keys())[:1000]
print(f"Testing first {len(arabic_keys)} Arabic keys across 11 languages")
print()

# Languages to test
LANGUAGES = ['ar', 'en', 'tr', 'de', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro']

# Initialize orchestrator
print("Initializing orchestrator...")
orchestrator = PipelineOrchestrator()

# Track results and errors
results = []
errors = []
error_counts = defaultdict(int)
success_count = 0
fail_count = 0
skipped_count = 0

print("Running batch test...")
print()

for i, arabic_word in enumerate(arabic_keys):
    if (i + 1) % 100 == 0:
        print(f"  Processed {i + 1}/1000 words...")

    word_succeeded = False

    for lang in LANGUAGES:
        try:
            # For Arabic, call directly. For others, orchestrator handles translation lookup
            analysis_results = orchestrator.analyze(arabic_word, lang)

            if analysis_results:
                word_succeeded = True
                for r in analysis_results:
                    results.append({
                        'arabic_key': arabic_word,
                        'language': lang,
                        'word_native': r.get('word_native', ''),
                        'lemma': r.get('lemma', ''),
                        'root': r.get('root', ''),
                        'pos': r.get('pos', ''),
                        'source_tool': r.get('source_tool', ''),
                        'status': 'OK'
                    })
            else:
                # No results - could be no translation available or adapter returned empty
                skipped_count += 1

        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            error_counts[f"{error_type}: {error_msg[:100]}"] += 1

            errors.append({
                'arabic_key': arabic_word,
                'language': lang,
                'error_type': error_type,
                'error_message': error_msg,
                'traceback': traceback.format_exc()
            })
            fail_count += 1

    if word_succeeded:
        success_count += 1
    else:
        fail_count += 1

print()
print("=" * 60)
print("BATCH TEST RESULTS SUMMARY")
print("=" * 60)
print()
print(f"Total Arabic words tested: {len(arabic_keys)}")
print(f"Words with at least one successful analysis: {success_count}")
print(f"Words with zero results across all languages: {fail_count - len(errors)}")
print(f"Total analysis results: {len(results)}")
print(f"Total errors encountered: {len(errors)}")
print(f"Skipped (no translation available): {skipped_count}")
print()

# Results by language
print("Results per language:")
lang_result_counts = defaultdict(int)
for r in results:
    lang_result_counts[r['language']] += 1

for lang in LANGUAGES:
    count = lang_result_counts[lang]
    status = "[OK]" if count > 0 else "[EMPTY]"
    print(f"  {lang}: {count} results {status}")

print()

# Error summary
if error_counts:
    print("ERROR TYPES AND FREQUENCIES:")
    for err, count in sorted(error_counts.items(), key=lambda x: -x[1]):
        print(f"  {count}x: {err}")
else:
    print("No errors encountered!")

print()

# Write CSV results
print(f"Writing results to {CSV_PATH}...")
with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
    if results:
        writer = csv.DictWriter(f, fieldnames=['arabic_key', 'language', 'word_native', 'lemma', 'root', 'pos', 'source_tool', 'status'])
        writer.writeheader()
        writer.writerows(results)
        print(f"  Wrote {len(results)} rows to CSV")
    else:
        f.write("No results\n")
        print("  No results to write")

# Write error log
print(f"Writing errors to {ERROR_PATH}...")
with open(ERROR_PATH, 'w', encoding='utf-8') as f:
    f.write("# Batch 1000 Test - Error Log\n\n")
    f.write(f"**Date:** {datetime.now().isoformat()}\n")
    f.write(f"**Total Errors:** {len(errors)}\n\n")

    if error_counts:
        f.write("## Error Summary by Type\n\n")
        f.write("| Error Type | Count |\n")
        f.write("|------------|-------|\n")
        for err, count in sorted(error_counts.items(), key=lambda x: -x[1]):
            f.write(f"| {err[:80]} | {count} |\n")
        f.write("\n")

    if errors:
        f.write("## Detailed Errors\n\n")
        for i, e in enumerate(errors[:50], 1):  # First 50 errors only
            f.write(f"### Error {i}\n")
            f.write(f"- **Arabic Key:** {e['arabic_key']}\n")
            f.write(f"- **Language:** {e['language']}\n")
            f.write(f"- **Type:** {e['error_type']}\n")
            f.write(f"- **Message:** {e['error_message']}\n")
            f.write(f"```\n{e['traceback']}\n```\n\n")

        if len(errors) > 50:
            f.write(f"\n... and {len(errors) - 50} more errors (see full log)\n")
    else:
        f.write("## No Errors\n\nAll 1000 words processed without exceptions.\n")

print(f"  Wrote error log")
print()
print("BATCH TEST COMPLETE")
PYEOF

echo ""

END_TIME=$(date -Iseconds)
echo "============================================================"
echo "ALL TASKS COMPLETE"
echo "============================================================"
echo ""
echo "Start: $START_TIME"
echo "End:   $END_TIME"
echo "Git HEAD: $GIT_HEAD"
echo ""
echo "Output files:"
echo "  - /mnt/pgdata/morphlex/reports/batch_1000_test.csv"
echo "  - /mnt/pgdata/morphlex/reports/batch_1000_errors.md"
