#!/bin/bash
source /mnt/pgdata/morphlex/venv/bin/activate
cd /mnt/pgdata/morphlex

# Fix infra issues
pip install openpyxl -q
docker start morpheus-api 2>/dev/null || docker run -d --name morpheus-api -p 1315:1315 --restart=always perseidsproject/morpheus-api:v1.0.15
sleep 10

# Find cedict
echo "CEDICT SEARCH:"
find /mnt/pgdata -name "cedict*" -type f 2>/dev/null

# Run full test
python3 << 'PYEOF'
results = {}

try:
    from analyzers.arabic import analyze_arabic
    r = analyze_arabic('كتاب')
    results['AR'] = f"PASS ({len(r)} analyses)"
except Exception as e:
    results['AR'] = f"FAIL: {str(e)[:80]}"

try:
    from analyzers.turkish import analyze_turkish
    r = analyze_turkish('okudum')
    results['TR'] = f"PASS ({len(r)} analyses)"
except Exception as e:
    results['TR'] = f"FAIL: {str(e)[:80]}"

try:
    from analyzers.german import analyze_german
    r = analyze_german('Handschuh')
    results['DE'] = f"PASS ({len(r)} analyses)"
except Exception as e:
    results['DE'] = f"FAIL: {str(e)[:80]}"

try:
    from analyzers.english import analyze_english
    r = analyze_english('unhappiness')
    results['EN'] = f"PASS ({len(r)} analyses)"
except Exception as e:
    results['EN'] = f"FAIL: {str(e)[:80]}"

try:
    from analyzers.latin import analyze_latin
    r = analyze_latin('scriptorum')
    results['LA'] = f"PASS ({len(r)} analyses)"
except Exception as e:
    results['LA'] = f"FAIL: {str(e)[:80]}"

try:
    from analyzers.chinese import analyze_chinese
    r = analyze_chinese('北京')
    results['ZH'] = f"PASS ({len(r)} analyses)"
except Exception as e:
    results['ZH'] = f"FAIL: {str(e)[:80]}"

try:
    from pipeline.orchestrator import PipelineOrchestrator
    orch = PipelineOrchestrator()
    test = [('كتاب','ar'),('okudum','tr'),('Handschuh','de'),('running','en'),('laudat','la'),('北京','zh')]
    batch = orch.batch_analyze(test)
    db_config = {'host':'localhost','dbname':'morphlex','user':'morphlex_user','password':'morphlex_2026'}
    orch.insert_to_db(batch, db_config)
    import psycopg2
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()
    cur.execute('SELECT language_code, COUNT(*) FROM lexicon.entries GROUP BY language_code ORDER BY language_code')
    rows = cur.fetchall()
    conn.close()
    db_str = ' '.join(f"{l}={c}" for l,c in rows)
    results['ORCH'] = f"PASS ({len(batch)} results DB: {db_str})"
except Exception as e:
    results['ORCH'] = f"FAIL: {str(e)[:80]}"

for k,v in results.items():
    print(f"{k}: {v}")
passed = sum(1 for v in results.values() if v.startswith('PASS'))
print(f"SCORE: {passed}/{len(results)}")
PYEOF
