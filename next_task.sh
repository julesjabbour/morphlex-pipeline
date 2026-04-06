#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== TIMED ORCHESTRATOR TEST: 100 WORDS x 11 LANGUAGES ==="
echo ""

python3 << 'PYEOF'
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')

from collections import defaultdict
from datetime import datetime
from pipeline.orchestrator import PipelineOrchestrator

# 100 common English nouns for timing test
TEST_WORDS = [
    'water', 'fire', 'hand', 'eye', 'stone', 'heart', 'sun', 'moon', 'tree', 'blood',
    'earth', 'wind', 'rain', 'snow', 'star', 'light', 'dark', 'gold', 'silver', 'iron',
    'bone', 'salt', 'sand', 'clay', 'dust', 'smoke', 'ice', 'wood', 'leaf', 'root',
    'seed', 'fruit', 'fish', 'bird', 'wolf', 'horse', 'lion', 'snake', 'bear', 'deer',
    'ant', 'bee', 'milk', 'bread', 'meat', 'rice', 'wine', 'beer', 'oil', 'wax',
    'egg', 'wool', 'silk', 'skin', 'hair', 'nail', 'tooth', 'tongue', 'nose', 'ear',
    'arm', 'leg', 'foot', 'knee', 'neck', 'back', 'head', 'face', 'mouth', 'lip',
    'bone', 'wing', 'tail', 'horn', 'claw', 'fur', 'rope', 'net', 'bow', 'axe',
    'knife', 'sword', 'wheel', 'boat', 'door', 'wall', 'roof', 'road', 'bridge', 'tower',
    'gate', 'pit', 'hill', 'field', 'lake', 'river', 'sea', 'sky', 'cloud', 'thunder'
]

# All 11 language codes
LANGUAGES = ['ar', 'tr', 'de', 'en', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro']

# Print start time
start_time = datetime.now()
print(f"START TIME: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
print("")

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
for lang in LANGUAGES:
    count = len(results_by_lang[lang])
    status = "OK" if count > 0 else "EMPTY"
    print(f"  {lang:8}: {count:4} results [{status}]")

print("")
print(f"TOTAL: {len(total_results)} results from {len(TEST_WORDS)} words x {len(LANGUAGES)} languages")

# Print end time
end_time = datetime.now()
print("")
print(f"END TIME: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
elapsed = (end_time - start_time).total_seconds()
print(f"ELAPSED: {elapsed:.2f} seconds")
print(f"TIME PER WORD: {elapsed / len(TEST_WORDS):.3f} seconds/word")

PYEOF

echo ""
echo "=== DONE ==="
