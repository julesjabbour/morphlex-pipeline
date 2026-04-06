#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate
rm -f /tmp/.eng015* /tmp/.task_done*
python3 -c "
import gzip, json
with gzip.open('data/raw-wiktextract-data.jsonl.gz', 'rt') as f:
    for line in f:
        e = json.loads(line)
        if e.get('word') == 'house' and e.get('lang_code') == 'en':
            print('KEYS:', [k for k in e.keys()])
            t = e.get('translations', [])
            print(f'translations: type={type(t).__name__}, len={len(t)}')
            if t:
                for x in t[:3]:
                    print(f'  {x}')
            s = e.get('senses', [])
            print(f'senses: {len(s)}')
            if s:
                print(f'sense0 keys: {list(s[0].keys())}')
                st = s[0].get('translations', None)
                if st:
                    print(f'sense0 trans: type={type(st).__name__}, len={len(st)}')
                    for x in st[:3]:
                        print(f'  {x}')
                else:
                    print('sense0: no translations key')
            break
" 2>&1
touch /tmp/.eng015_rawdump2
echo "DONE"
