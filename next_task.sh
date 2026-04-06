#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== ORCHESTRATOR TEST: 11 LANGUAGES ==="
echo ""

python3 << 'PYEOF'
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')

from collections import defaultdict
from pipeline.orchestrator import PipelineOrchestrator

# Test words
TEST_WORDS = ['water', 'mother', 'book', 'king', 'star', 'fire', 'earth', 'house', 'eye', 'sun']

# All 11 language codes
LANGUAGES = ['ar', 'tr', 'de', 'en', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro']

orchestrator = PipelineOrchestrator()

# Track results per language
results_by_lang = defaultdict(list)
total_results = []

print("--- Running analysis ---")
for word in TEST_WORDS:
    for lang in LANGUAGES:
        try:
            results = orchestrator.analyze(word, lang)
            results_by_lang[lang].extend(results)
            total_results.extend(results)
        except Exception as e:
            print(f"  ERROR {lang}/{word}: {e}")

print("")
print("--- Results per language ---")
all_ok = True
for lang in LANGUAGES:
    count = len(results_by_lang[lang])
    status = "OK" if count > 0 else "EMPTY"
    if count == 0:
        all_ok = False
    print(f"  {lang:8}: {count:4} results [{status}]")

print("")
print(f"TOTAL: {len(total_results)} results from {len(TEST_WORDS)} words x {len(LANGUAGES)} languages")

# Test DB insert
print("")
print("--- Testing DB insert ---")
if total_results:
    db_config = {
        'host': 'localhost',
        'dbname': 'morphlex',
        'user': 'morphlex_user',
        'password': 'morphlex_2026'
    }
    try:
        orchestrator.insert_to_db(total_results[:10], db_config)  # Insert first 10 as test
        print("DB INSERT: OK (10 sample records)")
    except Exception as e:
        print(f"DB INSERT: FAILED - {e}")
else:
    print("DB INSERT: SKIPPED (no results)")

print("")
la_count = len(results_by_lang.get('la', []))
if la_count > 1:
    print(f"=== LATIN FIX VERIFIED: {la_count} results (was 1) ===")
else:
    print(f"=== WARNING: Latin still showing {la_count} results ===")

print("")
if all_ok:
    print("=== ALL 11 LANGUAGES RETURNING RESULTS ===")
else:
    print("=== SOME LANGUAGES STILL EMPTY - CHECK FIXES ===")

PYEOF

echo ""
echo "=== DONE ==="
