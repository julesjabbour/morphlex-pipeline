#!/bin/bash
echo "=== VM DIAGNOSTIC ==="
echo "Cron status:"
crontab -l 2>&1
echo ""
echo "Flag files in /tmp:"
ls -la /tmp/.eng015* /tmp/.task_done* 2>&1
echo ""
echo "Last 5 lines of pipeline log:"
tail -5 /mnt/pgdata/morphlex/pipeline.log 2>&1 || echo "no log"
echo ""
echo "Git status:"
cd /mnt/pgdata/morphlex && git log --oneline -3 2>&1
echo ""
echo "next_task.sh hash:"
md5sum /mnt/pgdata/morphlex/next_task.sh 2>&1
echo ""
echo "Any running python3:"
ps aux | grep python3 | grep -v grep 2>&1
echo "=== END DIAGNOSTIC ==="

rm -f /tmp/.eng015*
rm -f /tmp/.task_done*

cd /mnt/pgdata/morphlex && source venv/bin/activate
python3 -c "
import gzip, json
with gzip.open('data/raw-wiktextract-data.jsonl.gz', 'rt') as f:
    for line in f:
        entry = json.loads(line)
        if entry.get('word') == 'house' and entry.get('lang_code') == 'en':
            print('TOP KEYS:', list(entry.keys()))
            if 'translations' in entry:
                trans = entry['translations']
                print(f'translations type: {type(trans).__name__}, len: {len(trans)}')
                for t in trans[:5]:
                    print(f'  {t}')
            else:
                print('NO translations at top level')
            if 'senses' in entry:
                for i, s in enumerate(entry['senses'][:2]):
                    print(f'sense {i} keys: {list(s.keys())}')
                    if 'translations' in s:
                        print(f'  sense translations: {s[\"translations\"][:3]}')
            break
" 2>&1

touch /tmp/.eng015_diag_done
echo "=== ALL DONE ==="
