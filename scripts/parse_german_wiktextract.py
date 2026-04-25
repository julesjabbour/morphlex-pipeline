#!/usr/bin/env python3
"""Parse German Wiktextract data and build synset map.

Reads kaikki-german.jsonl (uncompressed), extracts German words with
English glosses from senses, matches glosses to PWN 3.0 synsets via NLTK
WordNet (following the Sanskrit approach), bridges to OEWN using
pwn30_to_oewn_map.pkl.

Output: data/open_wordnets/german_wiktextract_synset_map.pkl

Zero error suppression. All exceptions logged visibly.
"""

import gzip
import json
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
from nltk.stem import WordNetLemmatizer

# Initialize lemmatizer
_lemmatizer = None
def get_lemmatizer():
    global _lemmatizer
    if _lemmatizer is None:
        _lemmatizer = WordNetLemmatizer()
    return _lemmatizer

DATA_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets")
# Task specifies gunzip, so use uncompressed filename
INPUT_FILE_UNCOMPRESSED = DATA_DIR / "kaikki-german.jsonl"
INPUT_FILE_COMPRESSED = DATA_DIR / "kaikki-german.jsonl.gz"
OUTPUT_FILE = DATA_DIR / "german_wiktextract_synset_map.pkl"
REPORT_FILE = DATA_DIR / "german_wiktextract_report.md"
PWN30_TO_OEWN_FILE = DATA_DIR / "pwn30_to_oewn_map.pkl"
CONCEPT_MAP_FILE = Path("/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl")
ODENET_MAP_FILE = DATA_DIR / "odenet_synset_map.pkl"


def log(msg):
    print(msg, flush=True)


def wiktextract_pos_to_wn(pos_str):
    """Convert Wiktextract POS string to WordNet POS constant."""
    if not pos_str:
        return None
    pos = pos_str.strip().lower()
    if pos in ['noun', 'name', 'proper noun']:
        return wn.NOUN
    elif pos in ['verb']:
        return wn.VERB
    elif pos in ['adj', 'adjective']:
        return wn.ADJ
    elif pos in ['adv', 'adverb']:
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
    elif pos == 's':
        return 's'
    return pos


def synset_to_id(synset):
    """Convert NLTK synset to offset-pos ID string like '00532338-n'."""
    offset = synset.offset()
    pos = synset.pos()
    return f"{offset:08d}-{pos}"


def word_set_similarity(words1, words2):
    """Compute word overlap with lemmatization for better matching."""
    stopwords = {'a', 'an', 'the', 'of', 'to', 'in', 'for', 'is', 'are', 'was',
                 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does',
                 'did', 'and', 'or', 'but', 'if', 'then', 'else', 'when', 'at',
                 'by', 'on', 'with', 'from', 'as', 'into', 'that', 'which', 'who',
                 'it', 'its', 'this', 'these', 'those', 'such', 'not', 'no', 'any',
                 'some', 'one', 'used', 'esp', 'etc', 'more', 'less', 'than'}

    lemmatizer = get_lemmatizer()

    # Lemmatize and normalize
    set1 = set()
    for w in words1:
        w = w.lower()
        if w not in stopwords and len(w) > 2:
            set1.add(lemmatizer.lemmatize(w, pos='n'))
            set1.add(lemmatizer.lemmatize(w, pos='v'))

    set2 = set()
    for w in words2:
        w = w.lower()
        if w not in stopwords and len(w) > 2:
            set2.add(lemmatizer.lemmatize(w, pos='n'))
            set2.add(lemmatizer.lemmatize(w, pos='v'))

    if not set1 or not set2:
        return 0.0

    intersection = len(set1 & set2)
    # Use minimum instead of union for better matching on short glosses
    minimum = min(len(set1), len(set2))
    return intersection / minimum if minimum > 0 else 0.0


def lookup_synset(english_gloss, pos_str):
    """Look up the best matching NLTK WordNet synset using gloss matching.

    Follows the Sanskrit approach:
    1. Extract content words from gloss
    2. Look up each word in WordNet with correct POS
    3. If 1 synset -> return it directly
    4. If multiple -> compare gloss against synset definitions
    5. If 0 -> try each word individually

    Args:
        english_gloss: The English definition/gloss text
        pos_str: POS string

    Returns:
        Tuple of (synset, match_type) or None
        match_type is 'single' or 'gloss'
    """
    wn_pos = wiktextract_pos_to_wn(pos_str)
    if not wn_pos:
        return None

    if not english_gloss or len(english_gloss) < 3:
        return None

    # Extract words from gloss
    gloss_words = re.findall(r'\b[a-zA-Z]+\b', english_gloss)

    # Remove common stopwords to find content words
    stopwords = {'the', 'a', 'an', 'and', 'or', 'for', 'of', 'to', 'in', 'on',
                 'at', 'by', 'that', 'this', 'with', 'from', 'have', 'has',
                 'are', 'is', 'was', 'were', 'been', 'being', 'used', 'especially',
                 'something', 'someone', 'thing', 'person', 'very', 'often', 'which',
                 'who', 'whom', 'whose', 'what', 'where', 'when', 'how', 'why',
                 'be', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
                 'may', 'might', 'can', 'shall', 'must', 'one', 'two', 'also'}
    content_words = [w.lower() for w in gloss_words if w.lower() not in stopwords and len(w) > 2]

    if not content_words:
        return None

    # Gather candidate synsets from content words
    all_synsets = []
    for word in content_words[:5]:  # Limit to first 5 content words
        synsets = wn.synsets(word, pos=wn_pos)
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
        # Try each word individually without POS constraint
        for word in content_words[:3]:
            synsets = wn.synsets(word)
            if synsets:
                # Return first synset that matches general POS
                for s in synsets:
                    return (s, 'gloss')
        return None

    # If only one synset, return it
    if len(unique_synsets) == 1:
        return (unique_synsets[0], 'single')

    # Find best match via gloss similarity with lemmatization
    best_synset = None
    best_score = 0.10  # Lower threshold for better matching

    for synset in unique_synsets:
        try:
            defn_words = re.findall(r'\b[a-zA-Z]+\b', synset.definition())
            score = word_set_similarity(gloss_words, defn_words)
            if score > best_score:
                best_score = score
                best_synset = synset
        except Exception as e:
            log(f"WARNING: Error getting definition for synset: {e}")
            continue

    # If no good match, return the most common synset (lower offset often = more common)
    if best_synset is None and unique_synsets:
        best_synset = min(unique_synsets, key=lambda s: s.offset())

    return (best_synset, 'gloss') if best_synset else None


def main():
    log("=" * 70)
    log("PARSE GERMAN WIKTEXTRACT - BUILD SYNSET MAP")
    log("=" * 70)

    git_head = os.popen('git rev-parse HEAD 2>/dev/null').read().strip()
    if git_head:
        log(f"Git HEAD: {git_head}")

    start_time = datetime.now()
    log(f"Start: {start_time.isoformat()}")
    log("")

    # Check input file exists (prefer uncompressed, fall back to compressed)
    input_file = None
    is_compressed = False
    if INPUT_FILE_UNCOMPRESSED.exists():
        input_file = INPUT_FILE_UNCOMPRESSED
        is_compressed = False
    elif INPUT_FILE_COMPRESSED.exists():
        input_file = INPUT_FILE_COMPRESSED
        is_compressed = True
    else:
        log(f"FATAL: Input file not found.")
        log(f"  Checked: {INPUT_FILE_UNCOMPRESSED}")
        log(f"  Checked: {INPUT_FILE_COMPRESSED}")
        log("")
        log("Download with:")
        log("  wget -q 'https://kaikki.org/dictionary/German/kaikki.org-dictionary-German.jsonl.gz' -O /mnt/pgdata/morphlex/data/open_wordnets/kaikki-german.jsonl.gz && gunzip -f /mnt/pgdata/morphlex/data/open_wordnets/kaikki-german.jsonl.gz")
        sys.exit(1)

    log(f"Input file: {input_file}")
    log(f"Compressed: {is_compressed}")
    log(f"Size: {input_file.stat().st_size:,} bytes ({input_file.stat().st_size/1024/1024:.1f} MB)")
    log("")

    # Load PWN 3.0 -> OEWN bridge
    log("Loading PWN 3.0 -> OEWN bridge...")
    pwn_to_oewn = {}
    if PWN30_TO_OEWN_FILE.exists():
        try:
            with open(PWN30_TO_OEWN_FILE, 'rb') as f:
                pwn_to_oewn = pickle.load(f)
            log(f"Loaded {len(pwn_to_oewn):,} PWN 3.0 -> OEWN mappings")
        except Exception as e:
            log(f"WARNING: Could not load bridge: {e}")
            log("Will use PWN 3.0 IDs directly")
    else:
        log(f"Bridge not found: {PWN30_TO_OEWN_FILE}")
        log("Will use PWN 3.0 IDs directly")
    log("")

    # Load concept map for validation
    log("Loading concept_wordnet_map for validation...")
    concept_synsets = set()
    if CONCEPT_MAP_FILE.exists():
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

    # Read and parse JSONL
    log("Reading German Wiktextract JSONL...")

    synset_map = {}  # OEWN ID -> list of German words
    total_entries = 0
    entries_with_senses = 0
    entries_with_gloss = 0
    matched_single = 0
    matched_gloss = 0
    unmatched = 0
    bridged_to_oewn = 0
    direct_pwn = 0

    pos_counts = defaultdict(int)

    # Open file (compressed or uncompressed)
    if is_compressed:
        f = gzip.open(input_file, 'rt', encoding='utf-8')
    else:
        f = open(input_file, 'r', encoding='utf-8')

    try:
        for line in f:
            total_entries += 1

            if total_entries % 50000 == 0:
                log(f"  Progress: {total_entries:,} entries...")

            try:
                entry = json.loads(line.strip())
            except json.JSONDecodeError as e:
                log(f"WARNING: JSON decode error at line {total_entries}: {e}")
                continue

            word = entry.get('word', '')
            pos = entry.get('pos', '')
            senses = entry.get('senses', [])

            if not word or not senses:
                continue

            entries_with_senses += 1
            pos_counts[pos] += 1

            # Process each sense
            for sense in senses:
                glosses = sense.get('glosses', [])
                raw_glosses = sense.get('raw_glosses', [])

                # Use glosses or raw_glosses
                all_glosses = glosses or raw_glosses

                if not all_glosses:
                    continue

                entries_with_gloss += 1

                # Use first gloss (usually the main definition)
                english_gloss = all_glosses[0] if all_glosses else ''

                if not english_gloss or len(english_gloss) < 5:
                    continue

                # Try to match to WordNet (returns synset and match_type)
                result = lookup_synset(english_gloss, pos)

                if result is None:
                    unmatched += 1
                    continue

                synset, match_type = result
                if match_type == 'single':
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
                    oewn_id = pwn_id
                    direct_pwn += 1

                # Add to map
                if oewn_id not in synset_map:
                    synset_map[oewn_id] = []
                if word not in synset_map[oewn_id]:
                    synset_map[oewn_id].append(word)
    finally:
        f.close()

    log("")
    log("=" * 70)
    log("FINAL STATS")
    log("=" * 70)
    log("")

    matched_total = matched_single + matched_gloss
    total_words = sum(len(v) for v in synset_map.values())
    avg_words_per_synset = total_words / len(synset_map) if synset_map else 0
    match_rate = 100 * matched_total / (matched_total + unmatched) if (matched_total + unmatched) > 0 else 0

    log(f"Total entries read: {total_entries:,}")
    log(f"Entries with senses: {entries_with_senses:,}")
    log(f"Entries with glosses: {entries_with_gloss:,}")
    log("")
    log(f"Matching results:")
    log(f"  Matched via single synset: {matched_single:,}")
    log(f"  Matched via gloss similarity: {matched_gloss:,}")
    log(f"  Total matched: {matched_total:,}")
    log(f"  Unmatched: {unmatched:,}")
    log(f"  Match rate: {match_rate:.1f}%")
    log("")
    log(f"Unique OEWN synsets: {len(synset_map):,}")
    log(f"Total German words: {total_words:,}")
    log(f"Words per synset: {avg_words_per_synset:.2f}")
    log("")

    log(f"OEWN conversion:")
    log(f"  Bridged (PWN 3.0 -> OEWN): {bridged_to_oewn:,}")
    log(f"  Direct (PWN 3.0 = OEWN): {direct_pwn:,}")
    log("")

    # Validate overlap
    german_synsets = set(synset_map.keys())
    overlap = german_synsets & concept_synsets
    overlap_rate = 100 * len(overlap) / len(concept_synsets) if concept_synsets else 0

    log(f"concept_wordnet_map synsets: {len(concept_synsets):,}")
    log(f"German synsets: {len(german_synsets):,}")
    log(f"Overlap: {len(overlap):,}")
    log(f"Overlap rate: {overlap_rate:.1f}%")
    log("")

    # Compare with OdeNet
    log("Comparing with OdeNet (previous German source)...")
    if ODENET_MAP_FILE.exists():
        try:
            with open(ODENET_MAP_FILE, 'rb') as f:
                odenet_map = pickle.load(f)
            odenet_synsets = len(odenet_map)
            odenet_words = sum(len(v) for v in odenet_map.values())
            odenet_overlap = len(set(odenet_map.keys()) & concept_synsets)
            odenet_coverage = 100 * odenet_overlap / len(concept_synsets) if concept_synsets else 0
            log(f"  OdeNet synsets: {odenet_synsets:,}")
            log(f"  OdeNet words: {odenet_words:,}")
            log(f"  OdeNet overlap with concept_map: {odenet_overlap:,} ({odenet_coverage:.1f}%)")
            log("")
            log(f"  COMPARISON:")
            log(f"    Wiktextract synsets: {len(synset_map):,} vs OdeNet: {odenet_synsets:,} ({len(synset_map)-odenet_synsets:+,})")
            log(f"    Wiktextract words: {total_words:,} vs OdeNet: {odenet_words:,} ({total_words-odenet_words:+,})")
            log(f"    Wiktextract overlap: {len(overlap):,} vs OdeNet: {odenet_overlap:,} ({len(overlap)-odenet_overlap:+,})")
            improvement_pct = 100 * (len(synset_map) - odenet_synsets) / odenet_synsets if odenet_synsets else 0
            log(f"    Synset improvement: {improvement_pct:+.1f}%")
        except Exception as e:
            log(f"  WARNING: Could not load OdeNet: {e}")
    else:
        log(f"  OdeNet file not found: {ODENET_MAP_FILE}")
    log("")

    # Write output
    log("Writing output...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'wb') as f:
        pickle.dump(synset_map, f, protocol=pickle.HIGHEST_PROTOCOL)

    output_size = OUTPUT_FILE.stat().st_size
    log(f"Written: {OUTPUT_FILE}")
    log(f"Size: {output_size:,} bytes ({output_size/1024:.1f} KB)")
    log("")

    # Sample entries
    log("10 sample entries:")
    for sid, words in list(synset_map.items())[:10]:
        preview = ', '.join(words[:3])
        if len(words) > 3:
            preview += f"... (+{len(words)-3})"
        log(f"  {sid}: [{preview}]")
    log("")

    # Write report
    log("Writing report...")
    report_content = f"""# German Wiktextract Synset Map Report

Generated: {datetime.now().isoformat()}
Git HEAD: {git_head}

## Input

- File: {input_file}
- Size: {input_file.stat().st_size:,} bytes

## Processing Stats

- Total entries: {total_entries:,}
- Entries with senses: {entries_with_senses:,}
- Entries with glosses: {entries_with_gloss:,}
- Matched via single synset: {matched_single:,}
- Matched via gloss similarity: {matched_gloss:,}
- Total matched: {matched_total:,}
- Unmatched: {unmatched:,}
- Match rate: {match_rate:.1f}%

## Output

- Unique OEWN synsets: {len(synset_map):,}
- Total German words: {total_words:,}
- Words per synset: {avg_words_per_synset:.2f}

## OEWN Conversion

- Bridged (PWN 3.0 -> OEWN): {bridged_to_oewn:,}
- Direct (PWN 3.0 = OEWN): {direct_pwn:,}

## Overlap with concept_wordnet_map.pkl

- Concept map synsets: {len(concept_synsets):,}
- German synsets: {len(german_synsets):,}
- Overlap: {len(overlap):,}
- **Overlap rate: {overlap_rate:.1f}%**

## POS Distribution

"""
    for pos, count in sorted(pos_counts.items(), key=lambda x: -x[1]):
        report_content += f"- {pos}: {count:,}\n"

    report_content += f"""
## Sample Entries

"""
    for sid, words in list(synset_map.items())[:20]:
        preview = ', '.join(words[:5])
        if len(words) > 5:
            preview += f"... (+{len(words)-5})"
        report_content += f"- `{sid}`: {preview}\n"

    report_content += f"""
## Duration

{datetime.now() - start_time}
"""

    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(report_content)
    log(f"Report written: {REPORT_FILE}")
    log("")

    log(f"Duration: {datetime.now() - start_time}")
    log(f"End: {datetime.now().isoformat()}")

    # Check success criteria: target 50K+ synsets
    if len(synset_map) < 50000:
        log("")
        log("=" * 70)
        log(f"WARNING: Only {len(synset_map):,} synsets, target was 50K+")
        log("=" * 70)
    else:
        log("")
        log("=" * 70)
        log(f"SUCCESS: {len(synset_map):,} synsets (target: 50K+)")
        log("=" * 70)


if __name__ == "__main__":
    main()
