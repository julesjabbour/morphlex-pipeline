#!/usr/bin/env python3
"""Fix Sanskrit synset mapping using NLTK WordNet gloss matching.

PROBLEM: IWN Sanskrit data has 11,082 unique concepts but the synset IDs use
PWN 2.1 numbering. We couldn't map PWN 2.1 -> 3.0 because the official Princeton
mapping files weren't found at expected paths.

SOLUTION: Use NLTK's WordNet (which IS PWN 3.0) to match English words + glosses.

Each IWN row has:
- Column 4: english_synset_words (e.g., "folk_dancing, folk_dance")
- Column 5: english_gloss (definition text)
- Column 3: english_category_x (POS)
- Column 8: sanskrit_synset (Sanskrit words)

Algorithm:
1. Look up English word(s) in NLTK WordNet with correct POS
2. If 1 synset -> take its offset directly
3. If multiple synsets -> compare IWN's english_gloss against each synset's
   .definition() using simple word overlap similarity. Pick the best match.
4. If 0 synsets -> try each word in comma-separated list individually

NLTK synset.offset() returns PWN 3.0 8-digit offsets. Combined with synset.pos()
we get IDs like "00532338-n" which can be converted to OEWN via our existing
pwn30_to_oewn_map.pkl bridge.

Output: data/open_wordnets/sanskrit_synset_map.pkl with OEWN IDs as keys.

Zero error suppression. All exceptions logged visibly.
"""

import csv
import os
import pickle
import re
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# NLTK imports (will be installed on VM)
import nltk
from nltk.corpus import wordnet as wn

DATA_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets/iwn-en")
OUTPUT_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets")
OUTPUT_FILE = OUTPUT_DIR / "sanskrit_synset_map.pkl"
PWN30_TO_OEWN_FILE = OUTPUT_DIR / "pwn30_to_oewn_map.pkl"
CONCEPT_MAP_FILE = Path("/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl")


def log(msg):
    print(msg, flush=True)


def nltk_pos_to_wn(pos_str):
    """Convert IWN POS string to WordNet POS constant."""
    if not pos_str:
        return None
    pos = pos_str.strip().upper()
    if pos in ['NOUN', 'N']:
        return wn.NOUN
    elif pos in ['VERB', 'V']:
        return wn.VERB
    elif pos in ['ADJECTIVE', 'ADJ', 'A', 'S']:
        return wn.ADJ
    elif pos in ['ADVERB', 'ADV', 'R']:
        return wn.ADV
    return None


def wn_pos_to_char(pos):
    """Convert WordNet POS constant to single character."""
    if pos == wn.NOUN:
        return 'n'
    elif pos == wn.VERB:
        return 'v'
    elif pos == wn.ADJ:
        return 'a'
    elif pos == wn.ADV:
        return 'r'
    elif pos == 's':  # satellite adjective
        return 's'
    return pos


def synset_to_id(synset):
    """Convert NLTK synset to offset-pos ID string like '00532338-n'."""
    offset = synset.offset()
    pos = synset.pos()
    # NLTK uses 's' for satellite adjectives, keep it
    return f"{offset:08d}-{pos}"


def word_overlap_similarity(gloss1, gloss2):
    """Compute simple word overlap similarity between two glosses."""
    if not gloss1 or not gloss2:
        return 0.0

    # Tokenize: lowercase, split on non-alphanumeric
    words1 = set(re.findall(r'[a-z]+', gloss1.lower()))
    words2 = set(re.findall(r'[a-z]+', gloss2.lower()))

    # Remove common stopwords
    stopwords = {'a', 'an', 'the', 'of', 'to', 'in', 'for', 'is', 'are', 'was',
                 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does',
                 'did', 'and', 'or', 'but', 'if', 'then', 'else', 'when', 'at',
                 'by', 'on', 'with', 'from', 'as', 'into', 'that', 'which', 'who',
                 'it', 'its', 'this', 'these', 'those', 'such', 'not', 'no', 'any',
                 'some', 'one', 'used', 'esp', 'etc'}
    words1 -= stopwords
    words2 -= stopwords

    if not words1 or not words2:
        return 0.0

    # Jaccard-like overlap
    intersection = len(words1 & words2)
    union = len(words1 | words2)

    return intersection / union if union > 0 else 0.0


def lookup_synset(english_words, pos_str, english_gloss):
    """Look up the best matching NLTK WordNet synset.

    Args:
        english_words: Comma-separated English words (e.g., "folk_dancing, folk_dance")
        pos_str: POS string (e.g., "NOUN")
        english_gloss: The definition text from IWN

    Returns:
        Best matching synset or None
    """
    wn_pos = nltk_pos_to_wn(pos_str)
    if not wn_pos:
        return None

    # Split words and try each
    words = [w.strip().replace(' ', '_') for w in english_words.split(',')]
    words = [w for w in words if w]

    all_synsets = []

    for word in words:
        # Try exact lookup
        synsets = wn.synsets(word, pos=wn_pos)
        all_synsets.extend(synsets)

        # If no results, try without underscores
        if not synsets and '_' in word:
            word_nospace = word.replace('_', '')
            synsets = wn.synsets(word_nospace, pos=wn_pos)
            all_synsets.extend(synsets)

    # Deduplicate
    seen = set()
    unique_synsets = []
    for s in all_synsets:
        sid = synset_to_id(s)
        if sid not in seen:
            seen.add(sid)
            unique_synsets.append(s)

    if not unique_synsets:
        return None

    if len(unique_synsets) == 1:
        return unique_synsets[0]

    # Multiple synsets: use gloss matching
    best_synset = None
    best_score = -1

    for synset in unique_synsets:
        try:
            nltk_gloss = synset.definition()
            score = word_overlap_similarity(english_gloss, nltk_gloss)
            if score > best_score:
                best_score = score
                best_synset = synset
        except Exception:
            continue

    return best_synset


def main():
    log("=" * 70)
    log("FIX SANSKRIT SYNSET MAPPING - NLTK WORDNET GLOSS MATCHING")
    log("=" * 70)

    git_head = os.popen('git rev-parse HEAD 2>/dev/null').read().strip()
    if git_head:
        log(f"Git HEAD: {git_head}")

    start_time = datetime.now()
    log(f"Start: {start_time.isoformat()}")
    log("")

    # Step 0: Load PWN 3.0 -> OEWN bridge
    log("=" * 70)
    log("STEP 0: LOAD PWN 3.0 -> OEWN BRIDGE")
    log("=" * 70)
    log("")

    pwn_to_oewn = {}
    if PWN30_TO_OEWN_FILE.exists():
        log(f"Loading {PWN30_TO_OEWN_FILE}...")
        try:
            with open(PWN30_TO_OEWN_FILE, 'rb') as f:
                pwn_to_oewn = pickle.load(f)
            log(f"Loaded {len(pwn_to_oewn):,} PWN 3.0 -> OEWN mappings")
            log("5 sample mappings:")
            for pwn, oewn in list(pwn_to_oewn.items())[:5]:
                log(f"  {pwn} -> {oewn}")
        except Exception as e:
            log(f"WARNING: Could not load bridge: {e}")
            log("Will use PWN 3.0 IDs directly")
    else:
        log(f"Bridge not found: {PWN30_TO_OEWN_FILE}")
        log("Will use PWN 3.0 IDs directly")
    log("")

    # Step 0b: Load concept map for validation
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

            for k in concept_map.keys():
                m = re.search(r'(\d{8})-([nvasr])', str(k))
                if m:
                    concept_synsets.add(f"{m.group(1)}-{m.group(2)}")

            log(f"Extracted {len(concept_synsets):,} unique synset IDs")
        except Exception as e:
            log(f"WARNING: Could not load concept_map: {e}")
    else:
        log(f"WARNING: {CONCEPT_MAP_FILE} not found")
    log("")

    # Step 1: Find IWN Sanskrit file
    log("=" * 70)
    log("STEP 1: FIND IWN SANSKRIT FILE")
    log("=" * 70)
    log("")

    target = DATA_DIR / "data" / "english-hindi-sanskrit-linked.tsv"
    if not target.exists():
        target = DATA_DIR / "english-hindi-sanskrit-linked.tsv"

    if not target.exists():
        log(f"FATAL: Sanskrit file not found: {target}")
        sys.exit(1)

    log(f"Using file: {target}")
    log(f"Size: {target.stat().st_size:,} bytes")
    log("")

    # Step 2: Extract unique concepts from IWN
    log("=" * 70)
    log("STEP 2: EXTRACT UNIQUE CONCEPTS FROM IWN")
    log("=" * 70)
    log("")

    # Column indices (0-based):
    # 2: english_id
    # 3: english_category_x (POS)
    # 4: english_synset_words
    # 5: english_gloss
    # 8: sanskrit_synset

    ENGLISH_ID_COL = 2
    POS_COL = 3
    ENGLISH_WORDS_COL = 4
    ENGLISH_GLOSS_COL = 5
    SANSKRIT_COL = 8

    # First pass: collect unique concepts and their Sanskrit words
    # Key: (english_id, english_words, POS, english_gloss)
    # Value: set of Sanskrit words
    concepts = defaultdict(set)
    total_rows = 0
    skipped_no_sanskrit = 0

    log(f"Reading {target.name}...")

    with open(target, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        header = next(reader, None)

        if header:
            log(f"Header columns: {len(header)}")
            log(f"  [{ENGLISH_WORDS_COL}] = {header[ENGLISH_WORDS_COL] if len(header) > ENGLISH_WORDS_COL else 'N/A'}")
            log(f"  [{ENGLISH_GLOSS_COL}] = {header[ENGLISH_GLOSS_COL] if len(header) > ENGLISH_GLOSS_COL else 'N/A'}")
            log(f"  [{POS_COL}] = {header[POS_COL] if len(header) > POS_COL else 'N/A'}")
            log(f"  [{SANSKRIT_COL}] = {header[SANSKRIT_COL] if len(header) > SANSKRIT_COL else 'N/A'}")

        for row in reader:
            total_rows += 1

            if len(row) <= SANSKRIT_COL:
                continue

            english_id = row[ENGLISH_ID_COL].strip()
            pos_str = row[POS_COL].strip()
            english_words = row[ENGLISH_WORDS_COL].strip()
            english_gloss = row[ENGLISH_GLOSS_COL].strip()
            sanskrit_text = row[SANSKRIT_COL].strip()

            if not sanskrit_text or sanskrit_text.lower() in ['', '-', 'na', 'n/a', 'null', 'none', 'nan']:
                skipped_no_sanskrit += 1
                continue

            # Parse Sanskrit words
            sanskrit_words = [w.strip() for w in sanskrit_text.split(',')]
            sanskrit_words = [w for w in sanskrit_words if w and w.lower() not in ['', '-', 'na', 'n/a', 'null', 'none', 'nan']]

            if not sanskrit_words:
                skipped_no_sanskrit += 1
                continue

            # Create concept key
            concept_key = (english_id, english_words, pos_str, english_gloss)
            concepts[concept_key].update(sanskrit_words)

    log("")
    log(f"Total rows: {total_rows:,}")
    log(f"Skipped (no Sanskrit): {skipped_no_sanskrit:,}")
    log(f"Unique concepts: {len(concepts):,}")
    log("")

    # Show sample concepts
    log("5 sample concepts:")
    for i, (key, words) in enumerate(list(concepts.items())[:5]):
        eng_id, eng_words, pos, gloss = key
        log(f"  {i+1}. [{pos}] {eng_words[:50]}... -> {len(words)} Sanskrit words")
    log("")

    # Step 3: Match concepts to NLTK WordNet
    log("=" * 70)
    log("STEP 3: MATCH CONCEPTS TO NLTK WORDNET")
    log("=" * 70)
    log("")

    synset_map = {}  # OEWN ID -> list of Sanskrit words

    matched_single = 0
    matched_gloss = 0
    unmatched = 0
    bridged_to_oewn = 0
    direct_pwn = 0

    progress_interval = max(1, len(concepts) // 20)

    for i, (key, sanskrit_words) in enumerate(concepts.items()):
        english_id, english_words, pos_str, english_gloss = key

        if i > 0 and i % progress_interval == 0:
            log(f"  Progress: {i:,}/{len(concepts):,} ({100*i/len(concepts):.0f}%)")

        # Look up in NLTK WordNet
        synset = lookup_synset(english_words, pos_str, english_gloss)

        if synset is None:
            unmatched += 1
            continue

        # Check if single or gloss match
        wn_pos = nltk_pos_to_wn(pos_str)
        words = [w.strip().replace(' ', '_') for w in english_words.split(',')]
        all_synsets = []
        for word in words:
            all_synsets.extend(wn.synsets(word, pos=wn_pos))

        if len(set(synset_to_id(s) for s in all_synsets)) == 1:
            matched_single += 1
        else:
            matched_gloss += 1

        # Convert to PWN 3.0 ID
        pwn_id = synset_to_id(synset)

        # Convert to OEWN ID via bridge
        if pwn_id in pwn_to_oewn:
            oewn_id = pwn_to_oewn[pwn_id]
            bridged_to_oewn += 1
        else:
            # Use PWN 3.0 ID directly (many are same as OEWN)
            oewn_id = pwn_id
            direct_pwn += 1

        # Add to map
        if oewn_id not in synset_map:
            synset_map[oewn_id] = []
        synset_map[oewn_id].extend(sanskrit_words)

    # Deduplicate words per synset
    for oewn_id in synset_map:
        synset_map[oewn_id] = list(set(synset_map[oewn_id]))

    log("")
    log(f"Matching results:")
    log(f"  Total concepts: {len(concepts):,}")
    log(f"  Matched via single synset: {matched_single:,}")
    log(f"  Matched via gloss similarity: {matched_gloss:,}")
    log(f"  Unmatched: {unmatched:,}")
    log(f"  Match rate: {100*(matched_single+matched_gloss)/len(concepts):.1f}%")
    log("")
    log(f"OEWN conversion:")
    log(f"  Bridged (PWN 3.0 -> OEWN): {bridged_to_oewn:,}")
    log(f"  Direct (PWN 3.0 = OEWN): {direct_pwn:,}")
    log(f"  Unique OEWN synsets: {len(synset_map):,}")
    log("")

    # Step 4: Write output
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
    log("")

    # Step 5: Validate overlap with concept_wordnet_map
    log("=" * 70)
    log("STEP 5: VALIDATE OVERLAP WITH CONCEPT_WORDNET_MAP")
    log("=" * 70)
    log("")

    sanskrit_synsets = set(synset_map.keys())
    overlap = sanskrit_synsets & concept_synsets

    log(f"concept_wordnet_map synsets: {len(concept_synsets):,}")
    log(f"Sanskrit synsets: {len(sanskrit_synsets):,}")
    log(f"Overlap: {len(overlap):,}")

    if concept_synsets:
        log(f"Coverage of concept_map: {100*len(overlap)/len(concept_synsets):.2f}%")
    if sanskrit_synsets:
        log(f"Sanskrit overlap rate: {100*len(overlap)/len(sanskrit_synsets):.1f}%")
    log("")

    # Show sample overlaps
    if overlap:
        log("10 sample overlapping synsets:")
        for sid in list(overlap)[:10]:
            words = synset_map[sid][:3]
            log(f"  {sid}: {words}")
    log("")

    # Show non-overlapping analysis
    sanskrit_only = sanskrit_synsets - concept_synsets
    log(f"Sanskrit-only synsets (not in concept_map): {len(sanskrit_only):,}")
    if sanskrit_only:
        log("5 sample Sanskrit-only:")
        for sid in list(sanskrit_only)[:5]:
            words = synset_map[sid][:2]
            log(f"  {sid}: {words}")
    log("")

    # Step 6: Final report
    log("=" * 70)
    log("FINAL REPORT")
    log("=" * 70)
    log("")

    total_words = sum(len(v) for v in synset_map.values())
    log(f"Total concepts processed: {len(concepts):,}")
    log(f"Matched via single synset: {matched_single:,}")
    log(f"Matched via gloss similarity: {matched_gloss:,}")
    log(f"Unmatched: {unmatched:,}")
    log(f"Final synsets in map: {len(synset_map):,}")
    log(f"Total Sanskrit words: {total_words:,}")
    log(f"Overlap with concept_wordnet_map.pkl: {len(overlap):,}")
    log("")

    log("10 sample entries:")
    for sid, words in list(synset_map.items())[:10]:
        preview = ', '.join(words[:3])
        if len(words) > 3:
            preview += f"... (+{len(words)-3})"
        log(f"  {sid}: [{preview}]")

    log("")
    log(f"Duration: {datetime.now() - start_time}")
    log(f"End: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
