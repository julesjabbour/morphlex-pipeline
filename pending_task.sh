#!/bin/bash
source /mnt/pgdata/morphlex/venv/bin/activate
cd /mnt/pgdata/morphlex

echo "=== ORCHESTRATOR TEST (ENG-008) ==="

# Test batch: 10 words per language (60 total)
python3 << 'PYEOF'
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')

from pipeline.orchestrator import PipelineOrchestrator

# Test words (10 per language)
test_batch = [
    # Arabic
    ('kitab', 'ar'), ('kalb', 'ar'), ('bayt', 'ar'), ('madrasa', 'ar'), ('qalam', 'ar'),
    ('yaktub', 'ar'), ('darasa', 'ar'), ('kabir', 'ar'), ('saghir', 'ar'), ('jamil', 'ar'),
    # Turkish
    ('okudum', 'tr'), ('kitap', 'tr'), ('ev', 'tr'), ('gelmek', 'tr'), ('yazmak', 'tr'),
    ('okul', 'tr'), ('buyuk', 'tr'), ('kucuk', 'tr'), ('guzel', 'tr'), ('insan', 'tr'),
    # German
    ('Handschuh', 'de'), ('Haus', 'de'), ('Buch', 'de'), ('Schule', 'de'), ('Kindergarten', 'de'),
    ('schreiben', 'de'), ('lesen', 'de'), ('Freiheit', 'de'), ('Freundschaft', 'de'), ('Weltanschauung', 'de'),
    # English
    ('unhappiness', 'en'), ('running', 'en'), ('beautiful', 'en'), ('unbelievable', 'en'), ('friendship', 'en'),
    ('quickly', 'en'), ('teacher', 'en'), ('happiness', 'en'), ('wonderful', 'en'), ('impossible', 'en'),
    # Latin
    ('laudat', 'la'), ('amat', 'la'), ('rex', 'la'), ('bellum', 'la'), ('amor', 'la'),
    ('bonus', 'la'), ('magnus', 'la'), ('scribo', 'la'), ('video', 'la'), ('audio', 'la'),
    # Chinese
    ('学习', 'zh'), ('中国', 'zh'), ('朋友', 'zh'), ('明天', 'zh'), ('工作', 'zh'),
    ('美丽', 'zh'), ('快乐', 'zh'), ('时间', 'zh'), ('电脑', 'zh'), ('学校', 'zh'),
]

print(f"Testing orchestrator with {len(test_batch)} words...")

orchestrator = PipelineOrchestrator()
results = orchestrator.batch_analyze(test_batch)

print(f"\nTotal analysis results: {len(results)}")

# Group by language for summary
by_lang = {}
for r in results:
    lang = r.get('language_code', 'unknown')
    by_lang[lang] = by_lang.get(lang, 0) + 1

print("\nResults by language:")
for lang, count in sorted(by_lang.items()):
    print(f"  {lang}: {count}")

if results:
    print(f"\nSample result: {results[0]}")

# Insert into database
if results:
    db_config = {
        'host': 'localhost',
        'dbname': 'morphlex',
        'user': 'postgres',
        'password': ''
    }
    try:
        orchestrator.insert_to_db(results, db_config)
        print("\nDatabase insert: SUCCESS")
    except Exception as e:
        print(f"\nDatabase insert: FAILED - {e}")
else:
    print("\nNo results to insert")
PYEOF

echo ""
echo "=== DATABASE CHECK ==="

# Check PostgreSQL count and sample
psql -U postgres -d morphlex -c "SELECT count(*) AS total_entries FROM lexicon.entries;" 2>&1
psql -U postgres -d morphlex -c "SELECT language_code, word_native, lemma, pos, source_tool FROM lexicon.entries ORDER BY id DESC LIMIT 1;" 2>&1

echo "=== TEST COMPLETE ==="
