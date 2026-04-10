#!/usr/bin/env python3
"""Build PWN 3.0 -> OEWN synset ID bridge using ILI (Interlingual Index).

PROBLEM: Our concept_wordnet_map.pkl uses OEWN (Open English WordNet) synset IDs
like oewn-00001740-a. Sanskrit IWN data uses PWN 3.0 offsets like 01796323-a.
These are DIFFERENT numbers for the SAME concepts because OEWN reorganized offsets.

SOLUTION: Use ILI as the bridge. Both PWN 3.0 and OEWN map to the same ILI codes.

Steps:
1. Download PWN 3.0 via wn package: wn.download('omw-en:1.4')
2. Load both PWN 3.0 and OEWN as Wordnet objects (NOT Lexicon objects!)
3. For each PWN 3.0 synset: get ILI -> find OEWN synset with same ILI -> record mapping
4. Save as data/open_wordnets/pwn30_to_oewn_map.pkl

Output format: {pwn30_id: oewn_id, ...}
  e.g., {'01796323-a': '00001740-a', ...}

This bridge is also needed for Latin and Greek - save as shared resource.

Zero error suppression. All exceptions logged visibly.

CRITICAL API NOTES (from wn_api_audit.py):
- wn.lexicons() returns Lexicon objects (metadata only, NO synsets() method!)
- wn.Wordnet(name) returns Wordnet objects (HAS synsets() method!)
- PROPERTIES (no parens): id, label, language, pos, ili, lemma
- METHODS (with parens): synsets(), words(), definition(), examples(), forms()
"""

import os
import pickle
import re
import sys
from datetime import datetime
from pathlib import Path

# Suppress download progress but NOT errors/warnings
import logging
logging.getLogger('wn').setLevel(logging.WARNING)

OUTPUT_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets")
OUTPUT_FILE = OUTPUT_DIR / "pwn30_to_oewn_map.pkl"
CONCEPT_MAP_FILE = Path("/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl")
SANSKRIT_MAP_FILE = Path("/mnt/pgdata/morphlex/data/open_wordnets/sanskrit_synset_map.pkl")


def log(msg):
    print(msg, flush=True)


def synset_to_offset_pos(synset):
    """Extract offset-pos ID from a wn Synset object.

    E.g., 'oewn-00001740-a' -> '00001740-a'
    Uses synset.id (PROPERTY, not method).
    """
    sid = synset.id  # PROPERTY not method
    # Handle formats like 'oewn-00001740-a' or 'omw-en-00001740-a'
    match = re.search(r'(\d{8})-([nvasr])', sid)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return None


def main():
    log("=" * 70)
    log("BUILD PWN 3.0 -> OEWN SYNSET ID BRIDGE")
    log("=" * 70)

    git_head = os.popen('git rev-parse HEAD 2>/dev/null').read().strip()
    if git_head:
        log(f"Git HEAD: {git_head}")

    start_time = datetime.now()
    log(f"Start: {start_time.isoformat()}")
    log("")

    # Step 1: Import and setup wn
    log("=" * 70)
    log("STEP 1: IMPORT AND SETUP WN PACKAGE")
    log("=" * 70)
    log("")

    try:
        import wn
        log("wn package imported successfully")
    except ImportError as e:
        log(f"FATAL: Cannot import wn: {e}")
        log("Install with: pip install wn")
        sys.exit(1)

    # Step 2: Download required wordnets
    log("")
    log("=" * 70)
    log("STEP 2: DOWNLOAD REQUIRED WORDNETS")
    log("=" * 70)
    log("")

    # Check what's already downloaded (Lexicon objects for info only)
    log("Checking installed wordnets...")
    installed = list(wn.lexicons())
    log(f"Currently installed: {len(installed)} lexicons")
    for lex in installed[:10]:
        # PROPERTIES not methods
        log(f"  {lex.id} ({lex.label})")
    if len(installed) > 10:
        log(f"  ... and {len(installed) - 10} more")
    log("")

    # Download PWN 3.0 (OMW English WordNet based on PWN 3.0)
    pwn_downloads = ['omw-en:1.4']
    oewn_downloads = ['oewn:2024', 'ewn:2020']

    for wn_id in pwn_downloads:
        log(f"Ensuring {wn_id} is available...")
        try:
            wn.download(wn_id, progress=False)
            log("  Downloaded")
        except TypeError:
            # progress parameter not supported in all versions
            try:
                wn.download(wn_id)
                log("  Downloaded (no progress param)")
            except Exception as e:
                log(f"  Note: {e}")
        except Exception as e:
            if "already added" in str(e).lower() or "exists" in str(e).lower():
                log("  Already installed")
            else:
                log(f"  Note: {e}")

    for wn_id in oewn_downloads:
        log(f"Ensuring {wn_id} is available...")
        try:
            wn.download(wn_id, progress=False)
            log("  Downloaded")
        except TypeError:
            try:
                wn.download(wn_id)
                log("  Downloaded (no progress param)")
            except Exception as e:
                log(f"  Note: {e}")
        except Exception as e:
            if "already added" in str(e).lower() or "exists" in str(e).lower():
                log("  Already installed")
            else:
                log(f"  Note: {e}")

    log("")

    # Step 3: Load Wordnet objects (NOT Lexicon objects!)
    # CRITICAL: wn.Wordnet(name) returns a Wordnet with .synsets() method
    #           wn.lexicons() returns Lexicon objects WITHOUT .synsets() method
    log("=" * 70)
    log("STEP 3: LOAD WORDNET OBJECTS AND BUILD ILI MAPS")
    log("=" * 70)
    log("")

    # Load PWN 3.0 as Wordnet object
    pwn_wn = None
    for name in ['omw-en']:
        try:
            pwn_wn = wn.Wordnet(name)
            log(f"Loaded PWN 3.0 as Wordnet: {name}")
            break
        except Exception as e:
            log(f"  Could not load {name}: {e}")

    if not pwn_wn:
        log("FATAL: Could not load PWN 3.0 (omw-en) as Wordnet object")
        sys.exit(1)

    # Load OEWN as Wordnet object
    oewn_wn = None
    for name in ['oewn', 'ewn']:
        try:
            oewn_wn = wn.Wordnet(name)
            log(f"Loaded OEWN as Wordnet: {name}")
            break
        except Exception as e:
            log(f"  Could not load {name}: {e}")

    if not oewn_wn:
        log("FATAL: Could not load OEWN as Wordnet object")
        sys.exit(1)

    log("")

    # Build ILI -> OEWN offset map
    log("Building ILI -> OEWN offset map...")
    ili_to_oewn = {}

    # Use Wordnet.synsets() - this is the correct method!
    oewn_synsets = list(oewn_wn.synsets())
    log(f"  OEWN synsets: {len(oewn_synsets):,}")

    for synset in oewn_synsets:
        ili = synset.ili  # PROPERTY not method
        if ili:
            offset_pos = synset_to_offset_pos(synset)
            if offset_pos:
                # ili.id is a PROPERTY not method
                ili_key = ili.id if hasattr(ili, 'id') else str(ili)
                ili_to_oewn[ili_key] = offset_pos

    log(f"  ILI -> OEWN mappings: {len(ili_to_oewn):,}")
    log("")

    # Build PWN 3.0 offset -> ILI map, then compose to get PWN -> OEWN
    log("Building PWN 3.0 offset -> OEWN offset bridge...")

    # Use Wordnet.synsets() - this is the correct method!
    pwn_synsets = list(pwn_wn.synsets())
    log(f"  PWN 3.0 synsets: {len(pwn_synsets):,}")

    pwn_to_oewn = {}
    no_ili_count = 0
    no_oewn_match = 0

    for synset in pwn_synsets:
        pwn_offset = synset_to_offset_pos(synset)
        if not pwn_offset:
            continue

        ili = synset.ili  # PROPERTY not method
        if not ili:
            no_ili_count += 1
            continue

        # ili.id is a PROPERTY not method
        ili_key = ili.id if hasattr(ili, 'id') else str(ili)

        if ili_key in ili_to_oewn:
            oewn_offset = ili_to_oewn[ili_key]
            pwn_to_oewn[pwn_offset] = oewn_offset
        else:
            no_oewn_match += 1

    log(f"  PWN -> OEWN mappings: {len(pwn_to_oewn):,}")
    log(f"  PWN synsets without ILI: {no_ili_count:,}")
    log(f"  PWN synsets with ILI but no OEWN match: {no_oewn_match:,}")
    log("")

    # Step 4: Validate against concept_wordnet_map
    log("=" * 70)
    log("STEP 4: VALIDATE AGAINST CONCEPT_WORDNET_MAP")
    log("=" * 70)
    log("")

    if CONCEPT_MAP_FILE.exists():
        log(f"Loading {CONCEPT_MAP_FILE}...")
        with open(CONCEPT_MAP_FILE, 'rb') as f:
            concept_map = pickle.load(f)

        # Extract OEWN synset IDs from concept_map
        concept_oewn_ids = set()
        for k in concept_map.keys():
            match = re.search(r'(\d{8})-([nvasr])', str(k))
            if match:
                concept_oewn_ids.add(f"{match.group(1)}-{match.group(2)}")

        log(f"Concept map OEWN synsets: {len(concept_oewn_ids):,}")

        # Check how many of our OEWN targets are in concept_map
        bridge_oewn_ids = set(pwn_to_oewn.values())
        overlap = bridge_oewn_ids & concept_oewn_ids
        log(f"Bridge OEWN targets: {len(bridge_oewn_ids):,}")
        log(f"Overlap with concept_map: {len(overlap):,}")
        if bridge_oewn_ids:
            log(f"Coverage: {100*len(overlap)/len(bridge_oewn_ids):.1f}%")
    else:
        log(f"WARNING: {CONCEPT_MAP_FILE} not found")
    log("")

    # Step 5: Test Sanskrit remapping
    log("=" * 70)
    log("STEP 5: TEST SANSKRIT REMAPPING")
    log("=" * 70)
    log("")

    if SANSKRIT_MAP_FILE.exists():
        log(f"Loading {SANSKRIT_MAP_FILE}...")
        with open(SANSKRIT_MAP_FILE, 'rb') as f:
            sanskrit_map = pickle.load(f)

        sanskrit_pwn_ids = set(sanskrit_map.keys())
        log(f"Sanskrit PWN synsets: {len(sanskrit_pwn_ids):,}")

        # Check direct overlap (before remapping)
        if CONCEPT_MAP_FILE.exists():
            direct_overlap = sanskrit_pwn_ids & concept_oewn_ids
            log(f"Direct overlap (before remap): {len(direct_overlap):,}")

        # Remap Sanskrit IDs through bridge
        remapped_count = 0
        remapped_overlap = set()
        for pwn_id in sanskrit_pwn_ids:
            if pwn_id in pwn_to_oewn:
                oewn_id = pwn_to_oewn[pwn_id]
                remapped_count += 1
                if CONCEPT_MAP_FILE.exists() and oewn_id in concept_oewn_ids:
                    remapped_overlap.add(oewn_id)

        log(f"Sanskrit IDs mappable via bridge: {remapped_count:,}")
        if CONCEPT_MAP_FILE.exists():
            log(f"Overlap after remapping: {len(remapped_overlap):,}")
            log(f"Improvement: {len(direct_overlap):,} -> {len(remapped_overlap):,}")
    else:
        log(f"WARNING: {SANSKRIT_MAP_FILE} not found (run parse_iwn_sanskrit.py first)")
    log("")

    # Step 6: Write output
    log("=" * 70)
    log("STEP 6: WRITE OUTPUT")
    log("=" * 70)
    log("")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'wb') as f:
        pickle.dump(pwn_to_oewn, f, protocol=pickle.HIGHEST_PROTOCOL)

    output_size = OUTPUT_FILE.stat().st_size
    log(f"Written: {OUTPUT_FILE}")
    log(f"Size: {output_size:,} bytes ({output_size/1024:.1f} KB)")
    log("")

    # Step 7: Report
    log("=" * 70)
    log("REPORT")
    log("=" * 70)
    log("")

    log(f"Total PWN 3.0 -> OEWN mappings: {len(pwn_to_oewn):,}")
    log("")
    log("10 sample mappings (PWN -> OEWN):")
    for pwn, oewn in list(pwn_to_oewn.items())[:10]:
        log(f"  {pwn} -> {oewn}")

    # Show some cases where PWN != OEWN to prove the bridge is useful
    log("")
    log("10 mappings where IDs DIFFER (proving bridge necessity):")
    diff_count = 0
    for pwn, oewn in pwn_to_oewn.items():
        if pwn != oewn:
            log(f"  {pwn} -> {oewn}")
            diff_count += 1
            if diff_count >= 10:
                break

    # Count how many differ
    total_diff = sum(1 for p, o in pwn_to_oewn.items() if p != o)
    log(f"")
    log(f"IDs that differ: {total_diff:,} ({100*total_diff/len(pwn_to_oewn):.1f}%)")
    log(f"IDs that match: {len(pwn_to_oewn) - total_diff:,}")

    log("")
    log(f"Duration: {datetime.now() - start_time}")
    log(f"End: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
