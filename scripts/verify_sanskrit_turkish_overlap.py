#!/usr/bin/env python3
"""Verify Sanskrit and Turkish synset overlap with concept_map."""

import pickle
import random
from datetime import datetime
from pathlib import Path


def main():
    print("=" * 70)
    print("VERIFY SANSKRIT/TURKISH SYNSET OVERLAP AND BRIDGE CORRECTNESS")
    print("=" * 70)
    print(f"Start: {datetime.now().isoformat()}")
    print()

    base = Path("/mnt/pgdata/morphlex/data")
    ownet = base / "open_wordnets"

    print("=" * 70)
    print("STEP 1: LOAD CONCEPT_WORDNET_MAP")
    print("=" * 70)

    with open(base / "concept_wordnet_map.pkl", "rb") as f:
        concept_map = pickle.load(f)

    concept_synsets = set(concept_map.keys())
    print(f"concept_wordnet_map: {len(concept_synsets):,} synsets")
    print(f"Sample 3 keys: {list(concept_synsets)[:3]}")
    print()

    print("=" * 70)
    print("STEP 2: LOAD SANSKRIT_SYNSET_MAP.PKL")
    print("=" * 70)

    sanskrit_path = ownet / "sanskrit_synset_map.pkl"
    if sanskrit_path.exists():
        with open(sanskrit_path, "rb") as f:
            sanskrit_map = pickle.load(f)
        sanskrit_synsets = set(sanskrit_map.keys())
        print(f"Total synsets: {len(sanskrit_synsets):,}")
        sample_keys = list(sanskrit_synsets)[:5]
        print(f"Sample 5 keys: {sample_keys}")

        overlap = sanskrit_synsets & concept_synsets
        print(f"Overlap count: {len(overlap):,}")
        print(f"Overlap percentage: {100*len(overlap)/len(sanskrit_synsets):.2f}%")
        if overlap:
            print(f"Sample overlapping: {list(overlap)[:5]}")
    else:
        print("ERROR: sanskrit_synset_map.pkl does not exist")
        sanskrit_synsets = set()
    print()

    print("=" * 70)
    print("STEP 3: LOAD KENET_SYNSET_MAP.PKL (TURKISH)")
    print("=" * 70)

    kenet_path = ownet / "kenet_synset_map.pkl"
    if kenet_path.exists():
        with open(kenet_path, "rb") as f:
            kenet_map = pickle.load(f)
        kenet_synsets = set(kenet_map.keys())
        print(f"Total synsets: {len(kenet_synsets):,}")
        sample_keys = list(kenet_synsets)[:5]
        print(f"Sample 5 keys: {sample_keys}")

        overlap = kenet_synsets & concept_synsets
        print(f"Overlap count: {len(overlap):,}")
        print(f"Overlap percentage: {100*len(overlap)/len(kenet_synsets):.2f}%")
        if overlap:
            print(f"Sample overlapping: {list(overlap)[:5]}")
    else:
        print("ERROR: kenet_synset_map.pkl does not exist")
        kenet_synsets = set()
    print()

    print("=" * 70)
    print("STEP 4: LOAD ODENET_SYNSET_MAP.PKL (OLD GERMAN)")
    print("=" * 70)

    odenet_path = ownet / "odenet_synset_map.pkl"
    if odenet_path.exists():
        with open(odenet_path, "rb") as f:
            odenet_map = pickle.load(f)
        odenet_synsets = set(odenet_map.keys())
        print(f"Total synsets: {len(odenet_synsets):,}")
        sample_keys = list(odenet_synsets)[:5]
        print(f"Sample 5 keys: {sample_keys}")

        overlap = odenet_synsets & concept_synsets
        print(f"Overlap count: {len(overlap):,}")
        print(f"Overlap percentage: {100*len(overlap)/len(odenet_synsets):.2f}%")
        if overlap:
            print(f"Sample overlapping: {list(overlap)[:5]}")
    else:
        print("ERROR: odenet_synset_map.pkl does not exist")
        odenet_synsets = set()
    print()

    print("=" * 70)
    print("STEP 5: CROSS-CHECK 5 CONCEPT_MAP SYNSETS IN ALL 6 PKLS")
    print("=" * 70)

    german_wikt_path = ownet / "german_wiktextract_synset_map.pkl"
    latin_path = ownet / "latin_synset_map.pkl"
    agwn_path = ownet / "agwn_synset_map.pkl"

    all_pkl_synsets = {}

    for name, path in [
        ("sanskrit", sanskrit_path),
        ("kenet (Turkish)", kenet_path),
        ("odenet (Old German)", odenet_path),
        ("german_wiktextract", german_wikt_path),
        ("latin", latin_path),
        ("agwn (Greek)", agwn_path),
    ]:
        if path.exists():
            with open(path, "rb") as f:
                data = pickle.load(f)
            all_pkl_synsets[name] = set(data.keys())
        else:
            all_pkl_synsets[name] = set()
            print(f"WARNING: {name} pkl not found")

    random.seed(42)
    sample_concept_ids = random.sample(list(concept_synsets), 5)

    print(f"\nSampled 5 concept_map synset IDs:")
    for sid in sample_concept_ids:
        print(f"\n  {sid}:")
        found_in = []
        for name, synsets in all_pkl_synsets.items():
            if sid in synsets:
                found_in.append(name)
        if found_in:
            print(f"    Found in: {', '.join(found_in)}")
        else:
            print(f"    NOT FOUND in any pkl")
    print()

    print("=" * 70)
    print("STEP 6: ANALYZE PWN30_TO_OEWN_MAP.PKL")
    print("=" * 70)

    bridge_path = ownet / "pwn30_to_oewn_map.pkl"
    if bridge_path.exists():
        with open(bridge_path, "rb") as f:
            bridge = pickle.load(f)

        print(f"Total mappings: {len(bridge):,}")

        sample_keys = list(bridge.keys())[:3]
        print(f"\nSample 3 keys (PWN 3.0 side):")
        for k in sample_keys:
            print(f"  {k!r}")

        sample_vals = list(bridge.values())[:3]
        print(f"\nSample 3 values (OEWN side):")
        for v in sample_vals:
            print(f"  {v!r}")

        oewn_in_concept = sum(1 for v in sample_vals if v in concept_synsets)
        print(f"\nOf those 3 OEWN values, {oewn_in_concept} exist in concept_map keys")

        all_oewn_values = set(bridge.values())
        overlap_with_concept = all_oewn_values & concept_synsets
        print(f"\nFull bridge analysis:")
        print(f"  Unique OEWN values in bridge: {len(all_oewn_values):,}")
        print(f"  OEWN values that exist in concept_map: {len(overlap_with_concept):,}")
        print(f"  Bridge->concept_map coverage: {100*len(overlap_with_concept)/len(all_oewn_values):.2f}%")
    else:
        print("ERROR: pwn30_to_oewn_map.pkl does not exist")
    print()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(f"\nconcept_wordnet_map: {len(concept_synsets):,} synsets")
    print()
    print("Language pkl overlaps with concept_map:")

    results = []
    for name, synsets in all_pkl_synsets.items():
        if synsets:
            overlap = synsets & concept_synsets
            pct = 100*len(overlap)/len(synsets) if synsets else 0
            results.append((name, len(synsets), len(overlap), pct))

    for name, total, overlap, pct in sorted(results, key=lambda x: -x[3]):
        print(f"  {name}: {overlap:,}/{total:,} ({pct:.2f}%)")

    print()
    print(f"End: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
