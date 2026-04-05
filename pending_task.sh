#!/bin/bash
source /mnt/pgdata/morphlex/venv/bin/activate
cd /mnt/pgdata/morphlex
python3 -c "
# First verify ENG-008 data exists
import psycopg2
db_config = {'host':'localhost','dbname':'morphlex','user':'morphlex_user','password':'morphlex_2026'}
conn = psycopg2.connect(**db_config)
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM lexicon.entries')
count = cur.fetchone()[0]
assert count > 0, f'No entries in DB — ENG-008 must run first. Found {count} entries.'
print(f'ENTRIES IN DB: {count}')

# Test translation of first 3 entries only (to stay within free tier)
cur.execute('SELECT id, word_native, language_code FROM lexicon.entries LIMIT 3')
entries = [{'id':r[0],'word_native':r[1],'language_code':r[2]} for r in cur.fetchall()]
conn.close()

from pipeline.translator import translate_batch
# Test single batch translation
test_words = [e['word_native'] for e in entries]
translations = translate_batch(test_words, 'en')
print(f'TRANSLATED {len(test_words)} words to English:')
for orig, trans in zip(test_words, translations):
    print(f'  {orig} -> {trans}')
print('ENG-009 PASS')
"
