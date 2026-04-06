#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== ETYMOLOGY ENRICHER TEST ==="

python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')

from pipeline.etymology_enricher import test_etymology
results = test_etymology()

print()
print('=== SUMMARY ===')
print(f'Etymology DB index entries: {results[\"index_counts\"][\"etymology_db\"]}')
print(f'CogNet index entries: {results[\"index_counts\"][\"cognet\"]}')
total_hits = sum(r['enrichments_count'] for r in results['test_results'])
print(f'Total enrichments found across test words: {total_hits}')
" 2>&1

echo "=== COMPLETE ==="
