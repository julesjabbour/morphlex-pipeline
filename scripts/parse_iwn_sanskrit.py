#!/usr/bin/env python3
"""Parse IWN-En TSV files to build PWN synset-to-Sanskrit word mapping.

FIXED: The english_id column (index 2) contains raw numbers like 975187.
These need to be zero-padded to 8 digits and combined with POS from
column 3 (english_category_x) to make PWN IDs like 00975187-n.

The Sanskrit words are in column 8 (sanskrit_synset), comma-separated.

Output: data/open_wordnets/sanskrit_synset_map.pkl
Format: {synset_offset_pos: [sanskrit_word1, sanskrit_word2, ...], ...}

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


def log(msg):
    print(msg, flush=True)


def pos_to_char(pos_str):
    """Convert POS string to single character for PWN ID."""
    if not pos_str:
        return None
    pos = pos_str.strip().upper()
    if pos in ['NOUN', 'N']:
        return 'n'
    elif pos in ['VERB', 'V']:
        return 'v'
    elif pos in ['ADJECTIVE', 'ADJ', 'A', 'S']:
        return 'a'
    elif pos in ['ADVERB', 'ADV', 'R']:
        return 'r'
    return None


def make_pwn_id(english_id, pos_str):
    """Create PWN ID from raw number and POS.

    english_id: raw number like 975187
    pos_str: POS like 'NOUN' or 'ADJECTIVE'
    Returns: '00975187-n' format
    """
    if not english_id or not pos_str:
        return None

    # Clean and extract numeric ID
    id_str = str(english_id).strip()
    if not id_str:
        return None

    # Extract just the digits
    digits = re.sub(r'\D', '', id_str)
    if not digits:
        return None

    # Zero-pad to 8 digits
    padded = digits.zfill(8)

    # If more than 8 digits, take last 8
    if len(padded) > 8:
        padded = padded[-8:]

    # Get POS character
    pos_char = pos_to_char(pos_str)
    if not pos_char:
        return None

    return f"{padded}-{pos_char}"


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

            # Create PWN ID from raw number + POS
            pwn_id = make_pwn_id(english_id, pos_str)

            if not pwn_id:
                reason = "invalid_pwn_id"
                skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                skipped += 1
                if total_rows <= 5:
                    log(f"  SKIP row {total_rows}: english_id={english_id}, pos={pos_str} -> no valid PWN ID")
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

            # Add to map
            for word in words:
                if pwn_id in synset_map:
                    if word not in synset_map[pwn_id]:
                        synset_map[pwn_id].append(word)
                else:
                    synset_map[pwn_id] = [word]

            mapped += 1

            # Show first few successful mappings
            if mapped <= 5:
                log(f"  MAPPED row {total_rows}: {english_id} + {pos_str} -> {pwn_id} -> {words[:3]}")

            if total_rows % 5000 == 0:
                log(f"  Processed {total_rows:,}, mapped {mapped:,}, synsets {len(synset_map):,}")

    log("")
    log(f"Total rows: {total_rows:,}")
    log(f"Mapped: {mapped:,}")
    log(f"Skipped: {skipped:,}")
    log(f"Unique PWN synsets: {len(synset_map):,}")
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
    log("DIAGNOSTIC: COMPARE SYNSET ID FORMATS")
    log("=" * 70)
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
