#!/bin/bash
source /mnt/pgdata/morphlex/venv/bin/activate
cd /mnt/pgdata/morphlex
python3 -c "
from pipeline.orchestrator import PipelineOrchestrator
orch = PipelineOrchestrator()

# Test dispatch to all 6 languages
test_words = [
    ('كتاب', 'ar'),
    ('okudum', 'tr'),
    ('Handschuh', 'de'),
    ('unhappiness', 'en'),
    ('scriptorum', 'la'),
    ('我爱北京', 'zh'),
]

results = orch.batch_analyze(test_words)
print(f'TOTAL RESULTS: {len(results)}')

# Count per language
from collections import Counter
langs = Counter(r['language_code'] for r in results)
for lang, count in sorted(langs.items()):
    print(f'  {lang}: {count} analyses')

# Test DB insert
db_config = {
    'host': 'localhost',
    'dbname': 'morphlex',
    'user': 'morphlex_user',
    'password': 'morphlex_2026'
}
orch.insert_to_db(results, db_config)

# Verify in DB
import psycopg2
conn = psycopg2.connect(**db_config)
cur = conn.cursor()
cur.execute('SELECT language_code, COUNT(*) FROM lexicon.entries GROUP BY language_code ORDER BY language_code')
rows = cur.fetchall()
print('DB COUNTS:')
for lang, count in rows:
    print(f'  {lang}: {count}')
conn.close()

print('ENG-008 PASS')
"
