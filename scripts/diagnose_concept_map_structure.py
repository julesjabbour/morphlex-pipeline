#!/usr/bin/env python3
"""
Re-diagnose synset overlap with correct concept_wordnet_map structure detection.
Read-only diagnostic - does not modify any pkl files.
"""

import pickle
import os
from datetime import datetime

def main():
    print("=" * 70)
    print("RE-DIAGNOSE CONCEPT_MAP STRUCTURE")
    print("=" * 70)
    print(f"Git HEAD: {os.popen('git rev-parse HEAD').read().strip()}")
    print(f"Start: {datetime.now().isoformat()}")
    print()

    # Paths
    concept_map_path = "/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl"
    latin_path = "/mnt/pgdata/morphlex/data/open_wordnets/latin_synset_map.pkl"
    agwn_path = "/mnt/pgdata/morphlex/data/open_wordnets/agwn_synset_map.pkl"
    german_path = "/mnt/pgdata/morphlex/data/open_wordnets/german_wiktextract_synset_map.pkl"
    latin_dir = "/mnt/pgdata/morphlex/data/open_wordnets/latin-wordnet/"
    agwn_dir = "/mnt/pgdata/morphlex/data/open_wordnets/agwn-jcuenod/"

    # Step 1: Load and analyze concept_wordnet_map structure
    print("=" * 70)
    print("STEP 1: ANALYZE CONCEPT_WORDNET_MAP STRUCTURE")
    print("=" * 70)
    print()

    with open(concept_map_path, 'rb') as f:
        cm = pickle.load(f)

    print(f"type(cm): {type(cm)}")
    print(f"type(cm).__name__: {type(cm).__name__}")

    if hasattr(cm, '__len__'):
        print(f"len(cm): {len(cm)}")
    else:
        print("len(cm): N/A (no __len__)")

    print()

    if isinstance(cm, dict):
        print("Structure: DICT")
        keys = list(cm.keys())[:3]
        print(f"First 3 keys: {keys}")
        print()
        for i, k in enumerate(keys):
            print(f"Key {i}: {repr(k)} (type={type(k).__name__})")
            v = cm[k]
            print(f"  Value type: {type(v).__name__}")
            if isinstance(v, dict):
                print(f"  Value keys: {list(v.keys())[:10]}")
                for vk in list(v.keys())[:3]:
                    vv = v[vk]
                    if isinstance(vv, (list, tuple)) and len(vv) > 5:
                        print(f"    {repr(vk)}: [{repr(vv[0])}, {repr(vv[1])}, ... ({len(vv)} items)]")
                    elif isinstance(vv, str) and len(vv) > 100:
                        print(f"    {repr(vk)}: {repr(vv[:100])}...")
                    else:
                        print(f"    {repr(vk)}: {repr(vv)}")
            elif isinstance(v, (list, tuple)):
                print(f"  Value len: {len(v)}")
                print(f"  First 3 elements: {v[:3]}")
            else:
                print(f"  Value: {repr(v)[:200]}")
            print()

    elif isinstance(cm, list):
        print("Structure: LIST")
        print(f"First 3 elements:")
        for i, elem in enumerate(cm[:3]):
            print(f"  Element {i}: type={type(elem).__name__}")
            if isinstance(elem, dict):
                print(f"    Keys: {list(elem.keys())}")
                for k in list(elem.keys())[:5]:
                    v = elem[k]
                    if isinstance(v, str) and len(v) > 100:
                        print(f"      {k}: {repr(v[:100])}...")
                    else:
                        print(f"      {k}: {repr(v)}")
            else:
                print(f"    Value: {repr(elem)[:200]}")
            print()
    else:
        print(f"Structure: OTHER ({type(cm).__name__})")
        print(f"repr: {repr(cm)[:500]}")

    # Step 2: Identify synset ID extraction method
    print("=" * 70)
    print("STEP 2: IDENTIFY SYNSET ID EXTRACTION METHOD")
    print("=" * 70)
    print()

    synset_ids = set()
    extraction_method = "unknown"

    if isinstance(cm, dict):
        first_key = list(cm.keys())[0] if cm else None
        first_val = cm[first_key] if first_key else None

        # Check if keys are synset IDs (oewn-* pattern or digits)
        if first_key and isinstance(first_key, str):
            if first_key.startswith('oewn-') or (first_key[0].isdigit() and '-' in first_key):
                print("Keys appear to be synset IDs")
                synset_ids = set(cm.keys())
                extraction_method = "dict keys are synset IDs"
            else:
                print(f"Keys do NOT look like synset IDs (first key: {repr(first_key)})")

        # Check if it's a nested structure: {synset_id: {words:[], definition:...}}
        if first_val and isinstance(first_val, dict):
            if 'words' in first_val or 'definition' in first_val or 'synset_id' in first_val:
                # It might be {arbitrary_key: {synset_id: X, words: [...], ...}}
                if 'synset_id' in first_val:
                    print("Values contain 'synset_id' field - extracting from there")
                    for k, v in cm.items():
                        if isinstance(v, dict) and 'synset_id' in v:
                            synset_ids.add(v['synset_id'])
                    extraction_method = "v['synset_id'] for v in cm.values()"
                else:
                    # The dict keys might BE the synset IDs, but let's check
                    # what OEWN synsets look like
                    print("Values have words/definition but no synset_id field")
                    print("Checking if outer keys are synset IDs...")
                    # Check 10 random keys
                    sample_keys = list(cm.keys())[:10]
                    oewn_like = sum(1 for k in sample_keys if isinstance(k, str) and (k.startswith('oewn-') or (len(k) > 8 and k[8] == '-')))
                    print(f"  {oewn_like}/10 sample keys look like synset IDs")
                    if oewn_like > 5:
                        synset_ids = set(cm.keys())
                        extraction_method = "dict keys are synset IDs"

        # Last resort: maybe it's {word: synset_data} and synset_id is in nested structure
        if not synset_ids:
            print("Attempting to find synset_id anywhere in nested structure...")
            for k, v in list(cm.items())[:100]:
                if isinstance(v, dict):
                    for vk, vv in v.items():
                        if isinstance(vk, str) and (vk.startswith('oewn-') or (len(vk) > 8 and vk[8:9] == '-' and vk[:8].isdigit())):
                            synset_ids.add(vk)
                        if isinstance(vv, str) and (vv.startswith('oewn-') or (len(vv) > 8 and vv[8:9] == '-' and vv[:8].isdigit())):
                            synset_ids.add(vv)

            if synset_ids:
                extraction_method = "found in nested dict values"
            else:
                print("Could not find synset IDs - dumping full structure of first entry")
                first_key = list(cm.keys())[0]
                import json
                try:
                    print(json.dumps({first_key: cm[first_key]}, indent=2, default=str)[:2000])
                except:
                    print(repr(cm[first_key])[:2000])

    elif isinstance(cm, list):
        # Check if list of dicts with synset_id
        if cm and isinstance(cm[0], dict):
            if 'synset_id' in cm[0]:
                print("List of dicts with 'synset_id' field")
                synset_ids = {item['synset_id'] for item in cm if isinstance(item, dict) and 'synset_id' in item}
                extraction_method = "item['synset_id'] for item in list"
            elif 'id' in cm[0]:
                print("List of dicts with 'id' field")
                synset_ids = {item['id'] for item in cm if isinstance(item, dict) and 'id' in item}
                extraction_method = "item['id'] for item in list"

    # If we still don't have synset_ids, try to detect the structure more carefully
    if not synset_ids and isinstance(cm, dict):
        print()
        print("FALLBACK: Checking ALL keys in concept_map...")
        all_keys_str = [k for k in cm.keys() if isinstance(k, str)]
        oewn_keys = [k for k in all_keys_str if k.startswith('oewn-')]
        pwn_keys = [k for k in all_keys_str if len(k) >= 10 and k[8:9] == '-' and k[:8].isdigit()]
        print(f"  Total keys: {len(cm)}")
        print(f"  String keys: {len(all_keys_str)}")
        print(f"  OEWN-pattern keys (oewn-*): {len(oewn_keys)}")
        print(f"  PWN-pattern keys (XXXXXXXX-X): {len(pwn_keys)}")

        if oewn_keys:
            print(f"  Sample OEWN keys: {oewn_keys[:5]}")
            synset_ids = set(oewn_keys)
            extraction_method = "oewn-* pattern keys"
        elif pwn_keys:
            print(f"  Sample PWN keys: {pwn_keys[:5]}")
            synset_ids = set(pwn_keys)
            extraction_method = "PWN pattern keys"

    print()
    print(f"Extraction method: {extraction_method}")
    print(f"Total synset IDs extracted: {len(synset_ids)}")
    if synset_ids:
        sample = list(synset_ids)[:5]
        print(f"Sample synset IDs: {sample}")

    # Step 3: Load other pkl files
    print()
    print("=" * 70)
    print("STEP 3: LOAD LANGUAGE PKL FILES")
    print("=" * 70)
    print()

    with open(latin_path, 'rb') as f:
        latin_map = pickle.load(f)
    print(f"Latin synset map: {len(latin_map)} synsets")
    latin_synsets = set(latin_map.keys())
    print(f"  Sample keys: {list(latin_synsets)[:3]}")

    with open(agwn_path, 'rb') as f:
        agwn_map = pickle.load(f)
    print(f"AGWN (Greek) synset map: {len(agwn_map)} synsets")
    agwn_synsets = set(agwn_map.keys())
    print(f"  Sample keys: {list(agwn_synsets)[:3]}")

    with open(german_path, 'rb') as f:
        german_map = pickle.load(f)
    print(f"German synset map: {len(german_map)} synsets")
    german_synsets = set(german_map.keys())
    print(f"  Sample keys: {list(german_synsets)[:3]}")

    # Step 4: Compute overlaps
    print()
    print("=" * 70)
    print("STEP 4: COMPUTE OVERLAPS")
    print("=" * 70)
    print()

    if synset_ids:
        latin_overlap = latin_synsets & synset_ids
        agwn_overlap = agwn_synsets & synset_ids
        german_overlap = german_synsets & synset_ids

        print(f"concept_map synset IDs: {len(synset_ids)}")
        print()
        print(f"Latin ({len(latin_synsets)} synsets):")
        print(f"  Overlap with concept_map: {len(latin_overlap)} ({100*len(latin_overlap)/len(latin_synsets):.1f}%)")
        if latin_overlap:
            print(f"  Sample overlapping: {list(latin_overlap)[:5]}")
        print()
        print(f"AGWN/Greek ({len(agwn_synsets)} synsets):")
        print(f"  Overlap with concept_map: {len(agwn_overlap)} ({100*len(agwn_overlap)/len(agwn_synsets):.1f}%)")
        if agwn_overlap:
            print(f"  Sample overlapping: {list(agwn_overlap)[:5]}")
        print()
        print(f"German ({len(german_synsets)} synsets):")
        print(f"  Overlap with concept_map: {len(german_overlap)} ({100*len(german_overlap)/len(german_synsets):.1f}%)")
        if german_overlap:
            print(f"  Sample overlapping: {list(german_overlap)[:5]}")
    else:
        print("ERROR: Could not extract synset IDs from concept_map")
        print("Cannot compute overlaps")

    # Step 5: Check SQL files
    print()
    print("=" * 70)
    print("STEP 5: CHECK SQL FILE AVAILABILITY")
    print("=" * 70)
    print()

    print(f"Latin WordNet directory: {latin_dir}")
    if os.path.exists(latin_dir):
        files = os.listdir(latin_dir)
        sql_files = [f for f in files if f.endswith('.sql')]
        print(f"  Total files: {len(files)}")
        print(f"  SQL files: {len(sql_files)}")
        for f in sorted(sql_files):
            path = os.path.join(latin_dir, f)
            size = os.path.getsize(path)
            print(f"    {f} ({size:,} bytes)")
    else:
        print("  DIRECTORY NOT FOUND")

    print()
    print(f"AGWN directory: {agwn_dir}")
    if os.path.exists(agwn_dir):
        files = os.listdir(agwn_dir)
        sql_files = [f for f in files if f.endswith('.sql')]
        print(f"  Total files: {len(files)}")
        print(f"  SQL files: {len(sql_files)}")
        for f in sorted(sql_files)[:10]:
            path = os.path.join(agwn_dir, f)
            size = os.path.getsize(path)
            print(f"    {f} ({size:,} bytes)")
        if len(sql_files) > 10:
            print(f"    ... and {len(sql_files) - 10} more")
    else:
        print("  DIRECTORY NOT FOUND")

    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()
    print(f"concept_wordnet_map.pkl:")
    print(f"  Type: {type(cm).__name__}")
    print(f"  Entries: {len(cm)}")
    print(f"  Synset ID extraction: {extraction_method}")
    print(f"  Unique synset IDs: {len(synset_ids)}")
    print()
    if synset_ids:
        print("Overlap summary:")
        print(f"  Latin: {len(latin_overlap)}/{len(latin_synsets)} ({100*len(latin_overlap)/len(latin_synsets):.2f}%)")
        print(f"  Greek (AGWN): {len(agwn_overlap)}/{len(agwn_synsets)} ({100*len(agwn_overlap)/len(agwn_synsets):.2f}%)")
        print(f"  German: {len(german_overlap)}/{len(german_synsets)} ({100*len(german_overlap)/len(german_synsets):.2f}%)")
    print()
    print(f"Duration: {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()
