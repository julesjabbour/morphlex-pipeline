#!/bin/bash
# ENG-019: Test Ancient Greek adapter
# Test words: logos, anthropos, theos, polis, sophia

echo "=== ANCIENT GREEK ADAPTER TEST (ENG-019) ==="

cd /mnt/pgdata/morphlex
source /mnt/pgdata/morphlex/venv/bin/activate

python3 << 'EOF'
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')

from analyzers.greek import analyze_greek

test_words = ['logos', 'anthropos', 'theos', 'polis', 'sophia']

print(f"Testing Greek adapter with {len(test_words)} words...")
print()

all_results = []
for word in test_words:
    results = analyze_greek(word)
    all_results.extend(results)
    print(f"  {word}: {len(results)} analyses")

print()
print(f"Total results: {len(all_results)}")

if all_results:
    print()
    print("Sample result:")
    sample = all_results[0]
    print(f"  word: {sample.get('word_native')}")
    print(f"  lemma: {sample.get('lemma')}")
    print(f"  pos: {sample.get('pos')}")
    print(f"  features: {sample.get('morphological_features')}")
    print(f"  language_code: {sample.get('language_code')}")
    print(f"  source_tool: {sample.get('source_tool')}")
else:
    print("No results returned - check if Morpheus is running on port 1315")

print()
print("=== TEST COMPLETE ===")
EOF
