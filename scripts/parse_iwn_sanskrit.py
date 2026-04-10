#!/usr/bin/env python3
"""Parse IWN-En TSV files to build OEWN synset-to-Sanskrit word mapping.

FIXED: The english_id column (index 2) contains raw numbers like 975187.
These need to be zero-padded to 8 digits and combined with POS from
column 3 (english_category_x) to make PWN IDs like 00975187-n.

BRIDGE: Sanskrit IWN uses PWN 2.1 synset IDs (NOT PWN 3.0!). Our concept_wordnet_map.pkl
uses OEWN (Open English WordNet) IDs. We use the full bridge:
  IWN offset (PWN 2.1) -> PWN 3.0 -> OEWN
This bridge is built by download_pwn_and_build_bridge.py using Princeton's
official 2.1to3.0 mapping files.

The Sanskrit words are in column 8 (sanskrit_synset), comma-separated.

Output: data/open_wordnets/sanskrit_synset_map.pkl
Format: {oewn_synset_id: [sanskrit_word1, sanskrit_word2, ...], ...}

Zero error suppression. All exceptions logged visibly.
"""

import csv
import os
import pickle
import re
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets/iwn-en")
OUTPUT_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets")
OUTPUT_FILE = OUTPUT_DIR / "sanskrit_synset_map.pkl"
CONCEPT_MAP_FILE = Path("/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl")
# Use the full IWN -> OEWN bridge (built via PWN 2.1 -> 3.0 -> OEWN)
BRIDGE_MAP_FILE = OUTPUT_DIR / "iwn_to_oewn_bridge.pkl"


def log(msg):
    print(msg, flush=True)


def pos_to_chars(pos_str):
    """Convert POS string to possible single characters for PWN ID.

    Returns a list of possible POS chars to try.
    For adjectives, returns both 'a' and 's' since WordNet distinguishes
    adjectives (a) from satellite adjectives (s), but IWN just says ADJECTIVE.
    """
    if not pos_str:
        return []
    pos = pos_str.strip().upper()
    if pos in ['NOUN', 'N']:
        return ['n']
    elif pos in ['VERB', 'V']:
        return ['v']
    elif pos in ['ADJECTIVE', 'ADJ', 'A', 'S']:
        # Try both adjective and satellite adjective
        return ['a', 's']
    elif pos in ['ADVERB', 'ADV', 'R']:
        return ['r']
    return []


def make_pwn_ids(english_id, pos_str):
    """Create possible PWN IDs from raw number and POS.

    english_id: raw number like 975187
    pos_str: POS like 'NOUN' or 'ADJECTIVE'
    Returns: list of possible IDs like ['00975187-a', '00975187-s'] for adjectives
    """
    if not english_id or not pos_str:
        return []

    # Clean and extract numeric ID
    id_str = str(english_id).strip()
    if not id_str:
        return []

    # Extract just the digits
    digits = re.sub(r'\D', '', id_str)
    if not digits:
        return []

    # Zero-pad to 8 digits
    padded = digits.zfill(8)

    # If more than 8 digits, take last 8
    if len(padded) > 8:
        padded = padded[-8:]

    # Get possible POS characters (may be multiple for adjectives)
    pos_chars = pos_to_chars(pos_str)
    if not pos_chars:
        return []

    return [f"{padded}-{pc}" for pc in pos_chars]


def main():
    log("=" * 70)
    log("PARSE IWN-EN SANSKRIT - BUILD PWN SYNSET MAP")
    log("=" * 70)

    git_head = os.popen('git rev-parse HEAD 2>/dev/null').read().strip()
    if git_head:
        log(f"Git HEAD: {git_head}")

    start_time = datetime.now()
    log(f"Start: {start_time.isoformat()}")
    log("")

    # Step 0: Load IWN -> OEWN bridge map (built via PWN 2.1 -> 3.0 -> OEWN)
    log("=" * 70)
    log("STEP 0: LOAD IWN -> OEWN BRIDGE MAP")
    log("=" * 70)
    log("")

    iwn_to_oewn = {}
    if BRIDGE_MAP_FILE.exists():
        log(f"Loading {BRIDGE_MAP_FILE}...")
        try:
            with open(BRIDGE_MAP_FILE, 'rb') as f:
                iwn_to_oewn = pickle.load(f)
            log(f"Loaded {len(iwn_to_oewn):,} IWN -> OEWN mappings")
            log("(Built via PWN 2.1 -> PWN 3.0 -> OEWN chain)")

            # Show sample mappings
            log("5 sample mappings:")
            for iwn, oewn in list(iwn_to_oewn.items())[:5]:
                log(f"  {iwn} -> {oewn}")
            log("")
        except Exception as e:
            log(f"FATAL: Could not load bridge map: {e}")
            log("Run download_pwn_and_build_bridge.py first!")
            sys.exit(1)
    else:
        log(f"FATAL: Bridge map not found: {BRIDGE_MAP_FILE}")
        log("Run download_pwn_and_build_bridge.py first!")
        sys.exit(1)

    # Also load concept_wordnet_map to validate overlap
    log("=" * 70)
    log("STEP 0b: LOAD CONCEPT MAP FOR VALIDATION")
    log("=" * 70)
    log("")

    concept_synsets = set()
    if CONCEPT_MAP_FILE.exists():
        log(f"Loading {CONCEPT_MAP_FILE}...")
        try:
            with open(CONCEPT_MAP_FILE, 'rb') as f:
                concept_map = pickle.load(f)
            log(f"Loaded {len(concept_map):,} concepts")

            # Extract all synset IDs (both 'a' and 's' adjectives are in concept_map)
            for k in concept_map.keys():
                m = re.search(r'(\d{8})-([nvasr])', str(k))
                if m:
                    concept_synsets.add(f"{m.group(1)}-{m.group(2)}")

            log(f"Extracted {len(concept_synsets):,} unique synset IDs")

            # Show POS distribution
            pos_dist = {}
            for sid in concept_synsets:
                pos = sid.split('-')[1]
                pos_dist[pos] = pos_dist.get(pos, 0) + 1
            log(f"POS distribution in concept_map: {pos_dist}")
            log("")
        except Exception as e:
            log(f"WARNING: Could not load concept_map: {e}")
    else:
        log(f"WARNING: {CONCEPT_MAP_FILE} not found")
    log("")

    # Step 1: Explore directory
    log("=" * 70)
    log("STEP 1: EXPLORE DIRECTORY")
    log("=" * 70)
    log("")

    if not DATA_DIR.exists():
        log(f"FATAL: Directory not found: {DATA_DIR}")
        sys.exit(1)

    log(f"Directory: {DATA_DIR}")
    log("")

    # Find all files
    all_files = [f for f in DATA_DIR.rglob('*') if f.is_file()]
    log(f"Total files: {len(all_files)}")

    for f in all_files[:30]:
        log(f"  {f.relative_to(DATA_DIR)} ({f.stat().st_size:,} bytes)")
    if len(all_files) > 30:
        log(f"  ... and {len(all_files)-30} more")

    # Find data files
    data_files = [f for f in all_files if f.suffix in ['.tsv', '.csv', '.txt']]
    log(f"")
    log(f"Data files: {len(data_files)}")

    # Look for Sanskrit-related files
    sanskrit_files = [f for f in all_files if 'sanskrit' in f.name.lower()]
    log(f"Sanskrit-named files: {len(sanskrit_files)}")
    for f in sanskrit_files:
        log(f"  {f.name}")

    # Check for specific target
    target = DATA_DIR / "data" / "english-hindi-sanskrit-linked.tsv"
    if not target.exists():
        target = DATA_DIR / "english-hindi-sanskrit-linked.tsv"

    log("")
    if target.exists():
        log(f"Target file EXISTS: {target}")
        data_file = target
    elif sanskrit_files:
        data_file = sanskrit_files[0]
        log(f"Using Sanskrit file: {data_file}")
    elif data_files:
        data_file = data_files[0]
        log(f"Using first data file: {data_file}")
    else:
        log("FATAL: No data files found")
        sys.exit(1)

    # Step 2: Explore file structure
    log("")
    log("=" * 70)
    log("STEP 2: EXPLORE FILE STRUCTURE")
    log("=" * 70)
    log("")

    log(f"Analyzing: {data_file.name}")
    log("")

    # Print first 30 lines
    log("First 30 lines:")
    with open(data_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= 30:
                break
            log(f"  {i}: {line.rstrip()[:120]}")
    log("")

    # Detect delimiter
    with open(data_file, 'r', encoding='utf-8') as f:
        first_line = f.readline()

    tab_count = first_line.count('\t')
    comma_count = first_line.count(',')
    delimiter = '\t' if tab_count >= comma_count else ','
    delim_name = 'TAB' if delimiter == '\t' else delimiter
    log(f"Delimiter: {delim_name} (tabs={tab_count}, commas={comma_count})")

    # Parse header
    with open(data_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=delimiter)
        header = next(reader, None)

    if header:
        log(f"Columns ({len(header)}):")
        for i, col in enumerate(header):
            indicators = []
            cl = col.lower()
            if 'sanskrit' in cl:
                indicators.append('SANSKRIT')
            if 'english' in cl:
                indicators.append('ENGLISH')
            if 'hindi' in cl:
                indicators.append('HINDI')
            if 'category' in cl or 'pos' in cl:
                indicators.append('POS')
            if 'synset' in cl:
                indicators.append('SYNSET')
            if 'id' in cl:
                indicators.append('ID')
            ind_str = f" <- {', '.join(indicators)}" if indicators else ""
            log(f"  [{i}] {col}{ind_str}")

    # Step 3: Parse file
    log("")
    log("=" * 70)
    log("STEP 3: PARSE FILE")
    log("=" * 70)
    log("")

    # FIXED column indices based on task description:
    # Column 2 (english_id) - raw numbers like 975187
    # Column 3 (english_category_x) - POS like NOUN, ADJECTIVE, VERB
    # Column 8 (sanskrit_synset) - comma-separated Sanskrit words
    ENGLISH_ID_COL = 2
    POS_COL = 3
    SANSKRIT_COL = 8

    log(f"Using FIXED columns:")
    log(f"  english_id (raw number): column {ENGLISH_ID_COL}")
    log(f"  english_category_x (POS): column {POS_COL}")
    log(f"  sanskrit_synset (words): column {SANSKRIT_COL}")
    log("")

    synset_map = {}
    total_rows = 0
    mapped = 0
    skipped = 0
    skip_reasons = {}
    bridged_count = 0
    unbridged_count = 0

    with open(data_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=delimiter)
        header = next(reader, None)  # Skip header

        if not header:
            log("FATAL: Empty file")
            sys.exit(1)

        log(f"Header row: {header}")
        log(f"Columns at indices: [{ENGLISH_ID_COL}]={header[ENGLISH_ID_COL] if len(header) > ENGLISH_ID_COL else 'N/A'}, "
            f"[{POS_COL}]={header[POS_COL] if len(header) > POS_COL else 'N/A'}, "
            f"[{SANSKRIT_COL}]={header[SANSKRIT_COL] if len(header) > SANSKRIT_COL else 'N/A'}")
        log("")
        log("Processing rows...")

        for row in reader:
            total_rows += 1

            # Check row has enough columns
            if len(row) <= SANSKRIT_COL:
                reason = "row_too_short"
                skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                skipped += 1
                continue

            english_id = row[ENGLISH_ID_COL].strip()
            pos_str = row[POS_COL].strip()
            sanskrit_text = row[SANSKRIT_COL].strip()

            # Skip empty english_id
            if not english_id:
                reason = "empty_english_id"
                skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                skipped += 1
                continue

            # Skip empty or null Sanskrit
            if not sanskrit_text or sanskrit_text.lower() in ['', '-', 'na', 'n/a', 'null', 'none', 'nan']:
                reason = "empty_sanskrit"
                skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                skipped += 1
                continue

            # Create possible PWN IDs from raw number + POS
            # For adjectives, this returns both 'a' and 's' variants
            possible_ids = make_pwn_ids(english_id, pos_str)

            if not possible_ids:
                reason = "invalid_pwn_id"
                skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                skipped += 1
                if total_rows <= 5:
                    log(f"  SKIP row {total_rows}: english_id={english_id}, pos={pos_str} -> no valid PWN ID")
                continue

            # Pick the ID that exists in IWN->OEWN bridge map
            # For adjectives, try both 'a' and 's' variants
            iwn_id = None
            oewn_id = None
            for pid in possible_ids:
                if pid in iwn_to_oewn:
                    iwn_id = pid
                    oewn_id = iwn_to_oewn[pid]
                    bridged_count += 1
                    break

            # If no bridge match, try to find matching concept synset directly
            if oewn_id is None:
                for pid in possible_ids:
                    if pid in concept_synsets:
                        iwn_id = pid
                        oewn_id = pid  # Same ID (rare case where IWN==OEWN)
                        unbridged_count += 1
                        break

            # If still no match, skip this row
            if oewn_id is None:
                reason = "no_oewn_bridge"
                skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                skipped += 1
                if total_rows <= 10:
                    log(f"  SKIP row {total_rows}: IWN IDs {possible_ids} not in bridge map")
                continue

            # Sanskrit text might have multiple words separated by comma
            words = [w.strip() for w in sanskrit_text.split(',')]

            # Filter valid words
            words = [w for w in words if w and w.lower() not in ['', '-', 'na', 'n/a', 'null', 'none', 'nan']]

            if not words:
                reason = "no_valid_words"
                skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                skipped += 1
                continue

            # Add to map using OEWN ID as key
            for word in words:
                if oewn_id in synset_map:
                    if word not in synset_map[oewn_id]:
                        synset_map[oewn_id].append(word)
                else:
                    synset_map[oewn_id] = [word]

            mapped += 1

            # Show first few successful mappings
            if mapped <= 5:
                log(f"  MAPPED row {total_rows}: {english_id} + {pos_str} -> IWN:{iwn_id} -> OEWN:{oewn_id} -> {words[:3]}")

            if total_rows % 5000 == 0:
                log(f"  Processed {total_rows:,}, mapped {mapped:,}, synsets {len(synset_map):,}")

    log("")
    log(f"Total rows: {total_rows:,}")
    log(f"Mapped: {mapped:,}")
    log(f"Skipped: {skipped:,}")
    log(f"Unique OEWN synsets: {len(synset_map):,}")
    log(f"Bridged (PWN->OEWN): {bridged_count:,}")
    log(f"Direct (no bridge needed): {unbridged_count:,}")
    log("")
    log("Skip reasons:")
    for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
        log(f"  {reason}: {count:,}")

    # Step 4: Write output
    log("")
    log("=" * 70)
    log("STEP 4: WRITE OUTPUT")
    log("=" * 70)
    log("")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'wb') as f:
        pickle.dump(synset_map, f, protocol=pickle.HIGHEST_PROTOCOL)

    output_size = OUTPUT_FILE.stat().st_size
    log(f"Written: {OUTPUT_FILE}")
    log(f"Size: {output_size:,} bytes ({output_size/1024:.1f} KB)")

    # Step 5: Report
    log("")
    log("=" * 70)
    log("REPORT")
    log("=" * 70)
    log("")

    log(f"Synsets mapped: {len(synset_map):,}")
    total_words = sum(len(v) for v in synset_map.values())
    log(f"Total Sanskrit words: {total_words:,}")
    if synset_map:
        log(f"Avg words/synset: {total_words/len(synset_map):.2f}")

    log("")
    log("5 sample entries:")
    for sid, words in list(synset_map.items())[:5]:
        preview = ', '.join(words[:3])
        if len(words) > 3:
            preview += f"... (+{len(words)-3})"
        log(f"  {sid}: [{preview}]")

    # Check overlap with detailed diagnostics
    log("")
    log("=" * 70)
    log("DIAGNOSTIC: VERIFY OEWN SYNSET OVERLAP")
    log("=" * 70)
    log("")
    log("Sanskrit synsets are now OEWN IDs (via IWN PWN 2.1 -> 3.0 -> OEWN bridge).")
    log("Overlap should now be in the thousands, not ~50.")
    log("")

    if CONCEPT_MAP_FILE.exists():
        try:
            with open(CONCEPT_MAP_FILE, 'rb') as f:
                concept_map = pickle.load(f)

            # Show 10 raw keys from concept_map
            log("10 SAMPLE KEYS from concept_wordnet_map.pkl (RAW):")
            raw_keys = list(concept_map.keys())[:10]
            for k in raw_keys:
                log(f"  '{k}'")

            log("")

            # Extract synset IDs
            concept_synsets = set()
            for k in concept_map.keys():
                m = re.search(r'(\d{8})-([nvasr])', str(k))
                if m:
                    concept_synsets.add(f"{m.group(1)}-{m.group(2)}")

            log("10 SAMPLE KEYS from concept_wordnet_map.pkl (EXTRACTED):")
            for sid in list(concept_synsets)[:10]:
                log(f"  '{sid}'")

            log("")
            log("10 SAMPLE KEYS from sanskrit_synset_map:")
            for sid in list(synset_map.keys())[:10]:
                log(f"  '{sid}'")

            log("")

            # Check for common patterns - look at first overlapping ones
            overlap = concept_synsets & set(synset_map.keys())
            log(f"concept_map synsets: {len(concept_synsets):,}")
            log(f"Sanskrit synsets: {len(synset_map):,}")
            log(f"Overlap: {len(overlap):,}")
            if concept_synsets:
                log(f"Coverage: {100*len(overlap)/len(concept_synsets):.1f}%")

            if overlap:
                log("")
                log("5 OVERLAPPING SYNSETS:")
                for sid in list(overlap)[:5]:
                    log(f"  {sid}")

            # Analyze non-overlapping IDs to find pattern
            log("")
            log("ANALYZING NON-OVERLAPPING IDS:")
            sanskrit_only = set(synset_map.keys()) - concept_synsets
            log(f"Sanskrit-only synsets: {len(sanskrit_only):,}")
            log("10 sample Sanskrit-only IDs:")
            for sid in list(sanskrit_only)[:10]:
                log(f"  '{sid}'")

            # Check offset lengths
            log("")
            log("OFFSET LENGTH ANALYSIS:")
            concept_lengths = {}
            for sid in concept_synsets:
                offset = sid.split('-')[0]
                length = len(offset)
                concept_lengths[length] = concept_lengths.get(length, 0) + 1
            log(f"concept_map offset lengths: {concept_lengths}")

            sanskrit_lengths = {}
            for sid in synset_map.keys():
                offset = sid.split('-')[0]
                length = len(offset)
                sanskrit_lengths[length] = sanskrit_lengths.get(length, 0) + 1
            log(f"sanskrit_map offset lengths: {sanskrit_lengths}")

        except Exception as e:
            log(f"ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    else:
        log(f"Not found: {CONCEPT_MAP_FILE}")

    log("")
    log(f"Duration: {datetime.now() - start_time}")
    log(f"End: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
