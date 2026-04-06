#!/bin/bash
# ENG-016: Japanese Adapter Test

# Install fugashi and unidic-lite if not present
pip install fugashi unidic-lite --break-system-packages 2>/dev/null

# Change to correct working directory
cd /mnt/pgdata/morphlex && source /mnt/pgdata/morphlex/venv/bin/activate

python3 << 'EOF'
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')

from analyzers.japanese import analyze_japanese

print("=== JAPANESE ADAPTER TEST (ENG-016) ===")
print("Testing Japanese adapter with 5 words...")
print()

# Test words: school, eat, beautiful, run, teacher
test_words = [
    ('学校', 'school'),
    ('食べる', 'eat'),
    ('美しい', 'beautiful'),
    ('走る', 'run'),
    ('先生', 'teacher'),
]

total_results = 0
all_results = []

for word, meaning in test_words:
    results = analyze_japanese(word)
    count = len(results)
    total_results += count
    all_results.extend(results)
    print(f"  {word} ({meaning}): {count} analyses")

    # Show first result details if available
    if results:
        r = results[0]
        reading = r.get('morphological_features', {}).get('reading', 'N/A') if r.get('morphological_features') else 'N/A'
        print(f"    -> lemma: {r['lemma']}, POS: {r['pos']}, reading: {reading}")

print()
print(f"Total results: {total_results}")

# Show sample result
if all_results:
    print()
    print("Sample result (first):")
    sample = all_results[0]
    for key, value in sample.items():
        print(f"  {key}: {value}")

print()
print("=== TEST COMPLETE ===")
EOF
