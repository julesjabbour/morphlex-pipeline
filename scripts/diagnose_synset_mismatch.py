#!/usr/bin/env python3
"""
Diagnose why Latin and Greek synset IDs have low overlap with concept_wordnet_map.
Read-only diagnostic - does not modify any files.
"""
import pickle
import re
import os
import subprocess
from datetime import datetime

def main():
    print("=" * 70)
    print("DIAGNOSE LATIN/GREEK SYNSET ID MISMATCH")
    print("=" * 70)

    git_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
    print(f"Git HEAD: {git_hash}")
    print(f"Start: {datetime.now().isoformat()}")

    # Paths
    latin_pkl_path = '/mnt/pgdata/morphlex/data/open_wordnets/latin_synset_map.pkl'
    agwn_pkl_path = '/mnt/pgdata/morphlex/data/open_wordnets/agwn_synset_map.pkl'
    concept_pkl_path = '/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl'
    pwn30_bridge_path = '/mnt/pgdata/morphlex/data/open_wordnets/pwn30_to_oewn_map.pkl'
    latin_sql_path = '/mnt/pgdata/morphlex/data/open_wordnets/latin-wordnet/latin_synonyms.sql'
    agwn_sql_path = '/mnt/pgdata/morphlex/data/open_wordnets/agwn-jcuenod/greek_synonyms_1.sql'

    # STEP 1: Load pickle files
    print("\n" + "=" * 70)
    print("STEP 1: LOAD PICKLE FILES")
    print("=" * 70)

    with open(latin_pkl_path, 'rb') as f:
        latin_map = pickle.load(f)
    print(f"Latin synset map: {len(latin_map)} synsets")

    with open(agwn_pkl_path, 'rb') as f:
        agwn_map = pickle.load(f)
    print(f"AGWN (Greek) synset map: {len(agwn_map)} synsets")

    with open(concept_pkl_path, 'rb') as f:
        concept_map = pickle.load(f)
    print(f"Concept wordnet map: {len(concept_map)} entries")

    with open(pwn30_bridge_path, 'rb') as f:
        pwn30_to_oewn = pickle.load(f)
    print(f"PWN 3.0 -> OEWN bridge: {len(pwn30_to_oewn)} mappings")

    # Extract synset IDs from concept_map
    concept_synset_ids = set()
    for concept_id, synset_dict in concept_map.items():
        if isinstance(synset_dict, dict):
            concept_synset_ids.update(synset_dict.keys())
    print(f"Unique synset IDs in concept_wordnet_map: {len(concept_synset_ids)}")

    # STEP 2: Sample synset IDs and check formats
    print("\n" + "=" * 70)
    print("STEP 2: SAMPLE SYNSET IDs AND FORMAT ANALYSIS")
    print("=" * 70)

    latin_ids = list(latin_map.keys())[:10]
    agwn_ids = list(agwn_map.keys())[:10]
    concept_ids = list(concept_synset_ids)[:10]

    print("\nFirst 10 Latin synset IDs:")
    for sid in latin_ids:
        in_concept = "IN concept_map" if sid in concept_synset_ids else "NOT in concept_map"
        print(f"  {sid} -> {in_concept}")

    print("\nFirst 10 AGWN (Greek) synset IDs:")
    for sid in agwn_ids:
        in_concept = "IN concept_map" if sid in concept_synset_ids else "NOT in concept_map"
        print(f"  {sid} -> {in_concept}")

    print("\nFirst 10 concept_wordnet_map synset IDs:")
    for sid in concept_ids:
        print(f"  {sid}")

    # Analyze ID formats
    def analyze_formats(ids):
        formats = {'oewn-*-n': 0, 'oewn-*-v': 0, 'oewn-*-a': 0, 'oewn-*-r': 0, 'oewn-*-s': 0,
                   'raw-*-n': 0, 'raw-*-v': 0, 'raw-*-a': 0, 'raw-*-r': 0, 'raw-*-s': 0, 'other': 0}
        for sid in ids:
            sid_str = str(sid)
            if sid_str.startswith('oewn-'):
                parts = sid_str.split('-')
                if len(parts) >= 3:
                    pos = parts[-1]
                    key = f'oewn-*-{pos}'
                    formats[key] = formats.get(key, 0) + 1
                else:
                    formats['other'] += 1
            elif '-' in sid_str:
                parts = sid_str.split('-')
                if len(parts) == 2:
                    pos = parts[1]
                    key = f'raw-*-{pos}'
                    formats[key] = formats.get(key, 0) + 1
                else:
                    formats['other'] += 1
            else:
                formats['other'] += 1
        return {k: v for k, v in formats.items() if v > 0}

    print("\n--- Format distribution ---")
    print(f"Latin: {analyze_formats(latin_map.keys())}")
    print(f"AGWN: {analyze_formats(agwn_map.keys())}")
    print(f"concept_map: {analyze_formats(concept_synset_ids)}")

    # STEP 3: Read raw SQL and extract PWN offsets
    print("\n" + "=" * 70)
    print("STEP 3: RAW SQL PWN OFFSETS")
    print("=" * 70)

    def extract_pwn_offsets_from_sql(sql_path, limit=5):
        offsets = []
        with open(sql_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if 'VALUES' in line:
                    matches = re.findall(r"VALUES\s*\((.+?)\);", line, re.IGNORECASE)
                    for match in matches:
                        parts = [p.strip().strip("'\"") for p in match.split(',')]
                        if len(parts) >= 4:
                            offsets.append(parts[3])
                            if len(offsets) >= limit:
                                return offsets
        return offsets

    print(f"\nLatin SQL ({latin_sql_path}):")
    latin_offsets = extract_pwn_offsets_from_sql(latin_sql_path, 5)
    for i, offset in enumerate(latin_offsets):
        print(f"  Row {i+1} PWN offset (col 4): {offset}")

    print(f"\nGreek SQL ({agwn_sql_path}):")
    agwn_offsets = extract_pwn_offsets_from_sql(agwn_sql_path, 5)
    for i, offset in enumerate(agwn_offsets):
        print(f"  Row {i+1} PWN offset (col 4): {offset}")

    # Analyze offset format
    print("\n--- PWN offset format analysis ---")
    for name, offsets in [("Latin", latin_offsets), ("Greek", agwn_offsets)]:
        if offsets:
            sample = offsets[0]
            is_8digit = len(sample) == 8 and sample.isdigit()
            print(f"{name}: sample='{sample}', 8-digit zero-padded: {is_8digit}")

    # STEP 4: Check PWN offsets against bridge
    print("\n" + "=" * 70)
    print("STEP 4: PWN OFFSET BRIDGE LOOKUP")
    print("=" * 70)

    # Sample bridge keys
    bridge_keys = list(pwn30_to_oewn.keys())[:10]
    print(f"\nFirst 10 PWN 3.0 bridge keys (format check):")
    for key in bridge_keys:
        print(f"  {key} -> {pwn30_to_oewn[key]}")

    print("\n--- Testing raw offsets against PWN 3.0 bridge ---")
    pos_suffixes = ['n', 'v', 'a', 'r', 's']

    for name, offsets in [("Latin", latin_offsets), ("Greek", agwn_offsets)]:
        print(f"\n{name} offsets:")
        for offset in offsets[:3]:
            found = False
            for pos in pos_suffixes:
                key = f"{offset}-{pos}"
                if key in pwn30_to_oewn:
                    print(f"  {offset}-{pos}: FOUND -> {pwn30_to_oewn[key]}")
                    found = True
                    break
            if not found:
                all_tried = ', '.join([f"{offset}-{p}" for p in pos_suffixes])
                print(f"  {offset}: NOT FOUND (tried: {all_tried})")

    # STEP 5: Compute overlap stats
    print("\n" + "=" * 70)
    print("STEP 5: OVERLAP STATISTICS")
    print("=" * 70)

    # Get OEWN values from bridge (the target format)
    bridge_oewn_values = set(pwn30_to_oewn.values())
    print(f"\nBridge OEWN values (output side): {len(bridge_oewn_values)}")

    latin_oewn_overlap = len(set(latin_map.keys()) & bridge_oewn_values)
    agwn_oewn_overlap = len(set(agwn_map.keys()) & bridge_oewn_values)

    print(f"\nLatin synsets in bridge OEWN values: {latin_oewn_overlap}/{len(latin_map)} ({100*latin_oewn_overlap/len(latin_map):.1f}%)")
    print(f"AGWN synsets in bridge OEWN values: {agwn_oewn_overlap}/{len(agwn_map)} ({100*agwn_oewn_overlap/len(agwn_map):.1f}%)")

    latin_concept_overlap = len(set(latin_map.keys()) & concept_synset_ids)
    agwn_concept_overlap = len(set(agwn_map.keys()) & concept_synset_ids)

    print(f"\nLatin synsets in concept_wordnet_map: {latin_concept_overlap}/{len(concept_synset_ids)} ({100*latin_concept_overlap/len(concept_synset_ids):.2f}%)")
    print(f"AGWN synsets in concept_wordnet_map: {agwn_concept_overlap}/{len(concept_synset_ids)} ({100*agwn_concept_overlap/len(concept_synset_ids):.2f}%)")

    # STEP 6: Hypothesis testing - is the bridge the wrong version?
    print("\n" + "=" * 70)
    print("STEP 6: HYPOTHESIS TESTING")
    print("=" * 70)

    # Check if raw offsets are PWN 3.0, 2.0, or 1.6
    print("\nTesting if SQL offsets match PWN 3.0 format...")

    # Sample more offsets for statistical analysis
    all_latin_offsets = extract_pwn_offsets_from_sql(latin_sql_path, 100)
    all_agwn_offsets = extract_pwn_offsets_from_sql(agwn_sql_path, 100)

    def test_offsets_against_bridge(offsets, name):
        found_count = 0
        for offset in offsets:
            for pos in pos_suffixes:
                key = f"{offset}-{pos}"
                if key in pwn30_to_oewn:
                    found_count += 1
                    break
        pct = 100 * found_count / len(offsets) if offsets else 0
        print(f"{name}: {found_count}/{len(offsets)} offsets found in PWN 3.0 bridge ({pct:.1f}%)")
        return found_count, len(offsets)

    latin_found, latin_total = test_offsets_against_bridge(all_latin_offsets, "Latin")
    agwn_found, agwn_total = test_offsets_against_bridge(all_agwn_offsets, "Greek")

    # Check what format the parsers produced vs what concept_map expects
    print("\n--- Key format comparison ---")

    # Sample a Latin synset ID that IS in the pkl
    latin_sample = list(latin_map.keys())[0]
    agwn_sample = list(agwn_map.keys())[0]
    concept_sample = list(concept_synset_ids)[0]

    print(f"Latin pkl key example: '{latin_sample}'")
    print(f"AGWN pkl key example: '{agwn_sample}'")
    print(f"concept_map key example: '{concept_sample}'")

    # Check the overlap synsets
    print("\n--- Overlapping synsets (the 53 Latin matches) ---")
    latin_overlaps = set(latin_map.keys()) & concept_synset_ids
    for i, sid in enumerate(list(latin_overlaps)[:5]):
        print(f"  {sid}")

    print("\n--- Overlapping synsets (the 178 Greek matches) ---")
    agwn_overlaps = set(agwn_map.keys()) & concept_synset_ids
    for i, sid in enumerate(list(agwn_overlaps)[:5]):
        print(f"  {sid}")

    # FINAL DIAGNOSIS
    print("\n" + "=" * 70)
    print("DIAGNOSIS SUMMARY")
    print("=" * 70)

    print(f"""
FINDINGS:

1. FORMAT ANALYSIS:
   - Latin pkl keys: mostly raw PWN format (XXXXXXXX-X) with some oewn- prefix
   - AGWN pkl keys: mostly raw PWN format (XXXXXXXX-X) with some oewn- prefix
   - concept_wordnet_map keys: all use oewn- prefix (oewn-XXXXXXXX-X)

2. BRIDGE LOOKUP:
   - Latin raw SQL offsets in PWN 3.0 bridge: {latin_found}/{latin_total} ({100*latin_found/latin_total if latin_total else 0:.1f}%)
   - Greek raw SQL offsets in PWN 3.0 bridge: {agwn_found}/{agwn_total} ({100*agwn_found/agwn_total if agwn_total else 0:.1f}%)

3. OVERLAP WITH concept_wordnet_map:
   - Latin: {latin_concept_overlap}/120,630 (0.04%)
   - Greek: {agwn_concept_overlap}/120,630 (0.1%)

4. HYPOTHESIS:
   - If raw offsets ARE in PWN 3.0 bridge -> parser is not applying bridge correctly
   - If raw offsets are NOT in PWN 3.0 bridge -> source data uses different PWN version (2.0 or 1.6)

CONCLUSION:
""")

    if latin_found / max(latin_total, 1) < 0.1:
        print("   Latin: Raw offsets NOT in PWN 3.0 -> likely uses PWN 2.0 or 1.6")
        print("   FIX NEEDED: Build PWN 2.0 -> PWN 3.0 -> OEWN bridge chain")
    else:
        print("   Latin: Raw offsets ARE in PWN 3.0 -> parser bridge logic may be broken")

    if agwn_found / max(agwn_total, 1) < 0.1:
        print("   Greek: Raw offsets NOT in PWN 3.0 -> likely uses PWN 2.0 or 1.6")
        print("   FIX NEEDED: Build PWN 2.0 -> PWN 3.0 -> OEWN bridge chain")
    else:
        print("   Greek: Raw offsets ARE in PWN 3.0 -> parser bridge logic may be broken")

    print(f"\nDuration: completed")
    print(f"End: {datetime.now().isoformat()}")

if __name__ == '__main__':
    main()
