#!/bin/bash
source /mnt/pgdata/morphlex/venv/bin/activate
cd /mnt/pgdata/morphlex
python3 -c "
r={}
try:
    from analyzers.arabic import analyze_arabic
    r['AR']=len(analyze_arabic(chr(1603)+chr(1578)+chr(1575)+chr(1576)))
except Exception as e: r['AR']=str(e)[:60]
try:
    from analyzers.turkish import analyze_turkish
    r['TR']=len(analyze_turkish('okudum'))
except Exception as e: r['TR']=str(e)[:60]
try:
    from analyzers.german import analyze_german
    r['DE']=len(analyze_german('Handschuh'))
except Exception as e: r['DE']=str(e)[:60]
try:
    from analyzers.english import analyze_english
    r['EN']=len(analyze_english('running'))
except Exception as e: r['EN']=str(e)[:60]
try:
    from analyzers.latin import analyze_latin
    r['LA']=len(analyze_latin('laudat'))
except Exception as e: r['LA']=str(e)[:60]
try:
    from analyzers.chinese import analyze_chinese
    r['ZH']=len(analyze_chinese('water'))
except Exception as e: r['ZH']=str(e)[:60]
p=sum(1 for v in r.values() if isinstance(v,int))
print(' '.join(k+':'+str(v) for k,v in r.items())+' SCORE:'+str(p)+'/6')
"
