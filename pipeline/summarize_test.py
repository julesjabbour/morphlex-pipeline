import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
langs = sorted(set(r['language'] for r in data))
print(f"Languages: {len(langs)}")
print(f"Total results: {len(data)}")
for l in langs:
    count = sum(1 for r in data if r['language'] == l)
    print(f"  {l}: {count}")
