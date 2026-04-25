#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "======================================================================"
echo "VERIFY PREFIX-FIX HYPOTHESIS"
echo "======================================================================"
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

python3 << 'EOF'
import pickle
cm = pickle.load(open('/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl', 'rb'))
concept_keys = set(cm.keys())
sanskrit = pickle.load(open('/mnt/pgdata/morphlex/data/open_wordnets/sanskrit_synset_map.pkl', 'rb'))
turkish = pickle.load(open('/mnt/pgdata/morphlex/data/open_wordnets/kenet_synset_map.pkl', 'rb'))
german = pickle.load(open('/mnt/pgdata/morphlex/data/open_wordnets/german_wiktextract_synset_map.pkl', 'rb'))
odenet = pickle.load(open('/mnt/pgdata/morphlex/data/open_wordnets/odenet_synset_map.pkl', 'rb'))
latin = pickle.load(open('/mnt/pgdata/morphlex/data/open_wordnets/latin_synset_map.pkl', 'rb'))
agwn = pickle.load(open('/mnt/pgdata/morphlex/data/open_wordnets/agwn_synset_map.pkl', 'rb'))
bridge = pickle.load(open('/mnt/pgdata/morphlex/data/open_wordnets/pwn30_to_oewn_map.pkl', 'rb'))
print('Test 1: Just add oewn- prefix to pkl keys')
for name, pkl in [('sanskrit', sanskrit), ('turkish', turkish), ('odenet', odenet), ('german_wiktextract', german)]:
    prefixed = {'oewn-' + k.replace('-s', '-a') for k in pkl.keys()}
    overlap = len(prefixed & concept_keys)
    print(f'  {name}: {overlap}/{len(pkl)} = {100*overlap/len(pkl):.1f}%')
print()
print('Test 2: Bridge then prefix (key -> bridge -> oewn-prefix)')
for name, pkl in [('sanskrit', sanskrit), ('turkish', turkish), ('odenet', odenet), ('german_wiktextract', german)]:
    via_bridge = 0
    for k in pkl.keys():
        bridged = bridge.get(k.replace('-s', '-n'))
        if bridged and ('oewn-' + bridged) in concept_keys:
            via_bridge += 1
    print(f'  {name}: {via_bridge}/{len(pkl)} = {100*via_bridge/len(pkl):.1f}%')
print()
print('Test 3: Latin/Greek already have oewn- prefix - test direct overlap')
for name, pkl in [('latin', latin), ('agwn', agwn)]:
    overlap = len(set(pkl.keys()) & concept_keys)
    print(f'  {name} direct: {overlap}/{len(pkl)} = {100*overlap/len(pkl):.1f}%')
print()
print('Test 4: Strip oewn- prefix from latin/agwn, run through bridge, re-add prefix')
for name, pkl in [('latin', latin), ('agwn', agwn)]:
    via_bridge = 0
    for k in pkl.keys():
        stripped = k.replace('oewn-', '')
        bridged = bridge.get(stripped)
        if bridged and ('oewn-' + bridged) in concept_keys:
            via_bridge += 1
    print(f'  {name} via bridge: {via_bridge}/{len(pkl)} = {100*via_bridge/len(pkl):.1f}%')
EOF

echo ""
echo "======================================================================"
echo "END OF VERIFICATION"
echo "======================================================================"
echo "End: $(date -Iseconds)"
