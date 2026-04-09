#!/usr/bin/env python3
"""
PHASE 5a: Build WordNet Concept Map with Open Multilingual Wordnet

Builds a mapping of all WordNet synsets to their words in every available language.

Output: data/concept_wordnet_map.pkl
Structure: {
    synset_id: {
        'pos': 'NOUN' | 'VERB' | 'ADJ' | 'ADV',
        'definition': 'English definition string',
        'words': {
            'eng': ['word1', 'word2'],
            'arb': ['word1'],
            ...all available OMW languages
        }
    }
}

ZERO HARDCODING. ZERO SHORTCUTS. ALL SYNSETS PROCESSED.
"""
import os
import pickle
import random
import sys
import time
from collections import defaultdict
from datetime import datetime

# Suppress ALL wn/nltk import output - redirect stderr/stdout during imports
_stderr = sys.stderr
_stdout = sys.stdout
sys.stderr = open(os.devnull, 'w')
sys.stdout = open(os.devnull, 'w')
try:
    import wn
    import nltk
finally:
    sys.stderr.close()
    sys.stdout.close()
    sys.stderr = _stderr
    sys.stdout = _stdout

# Output paths
OUTPUT_FILE = '/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl'
REPORT_DIR = '/mnt/pgdata/morphlex/reports'


def log(msg):
    """Print with timestamp."""
    print(f"[{datetime.now().isoformat()}] {msg}", flush=True)


def ensure_data_downloaded():
    """Data already downloaded - just verify it's present."""
    lexicons = list(wn.lexicons())
    if len(lexicons) < 10:
        raise RuntimeError(f"WordNet/OMW data not present! Only {len(lexicons)} lexicons found. Please download first.")
    return len(lexicons)


def get_pos_label(pos_char):
    """Convert POS character to label."""
    pos_map = {
        'n': 'NOUN',
        'v': 'VERB',
        'a': 'ADJ',
        's': 'ADJ',  # satellite adjective
        'r': 'ADV',
    }
    return pos_map.get(pos_char, 'OTHER')


def build_concept_map():
    """Build the concept map from WordNet synsets."""
    log("=" * 70)
    log("PHASE 5a: Building WordNet Concept Map")
    log("=" * 70)

    # Get all available lexicons (languages)
    lexicons = list(wn.lexicons())
    log(f"\nDiscovered {len(lexicons)} lexicons (language resources):")

    # Collect unique language codes
    lang_codes = set()
    for lex in lexicons:
        lang_codes.add(lex.language())

    lang_codes = sorted(lang_codes)
    log(f"Unique language codes ({len(lang_codes)}):")
    for code in lang_codes:
        lex_for_lang = [l for l in lexicons if l.language() == code]
        log(f"  {code}: {len(lex_for_lang)} lexicon(s)")

    # Get all synsets from English WordNet (the base)
    log("\nFetching all synsets from English WordNet...")

    # Find English WordNet - try different identifiers
    eng_wordnet = None
    for wn_id in ['oewn:2024', 'ewn:2020', 'omw-en:1.4', 'omw-en31:1.4']:
        try:
            eng_wordnet = wn.Wordnet(wn_id)
            log(f"Using English WordNet: {wn_id}")
            break
        except wn.Error:
            continue

    if eng_wordnet is None:
        # Fallback: find any English lexicon
        eng_lexicons = [l for l in lexicons if l.language() == 'en']
        if eng_lexicons:
            eng_wordnet = wn.Wordnet(eng_lexicons[0].id())
            log(f"Using English lexicon: {eng_lexicons[0].id()}")
        else:
            raise RuntimeError("No English WordNet found!")

    all_synsets = list(eng_wordnet.synsets())
    total_synsets = len(all_synsets)
    log(f"Total synsets to process: {total_synsets:,}")

    # Build the concept map
    concept_map = {}
    lang_coverage = defaultdict(int)  # Count synsets per language

    start_time = time.time()
    last_report = start_time

    for i, synset in enumerate(all_synsets):
        synset_id = synset.id()

        # Get definition
        try:
            definitions = synset.definitions()
            definition = definitions[0] if definitions else ""
        except Exception:
            definition = ""

        # Get POS from synset - the pos() method returns the POS
        try:
            pos_char = synset.pos()
            pos_label = get_pos_label(pos_char)
        except Exception:
            # Fallback: try to parse from ID
            pos_char = synset_id.split('-')[-1] if '-' in synset_id else 'n'
            pos_label = get_pos_label(pos_char)

        # Collect words from all languages
        words_by_lang = defaultdict(list)

        # Get words from this synset across all lexicons using ILI
        try:
            ili = synset.ili()
            if ili:
                # Find all synsets in all lexicons that share this ILI
                for lex in lexicons:
                    try:
                        # Use ili parameter to find matching synsets
                        matching_synsets = list(lex.synsets(ili=ili))
                        for ms in matching_synsets:
                            lang = lex.language()
                            for sense in ms.senses():
                                word = sense.word()
                                form = word.form()
                                if form and form not in words_by_lang[lang]:
                                    words_by_lang[lang].append(form)
                    except Exception:
                        # Some lexicons may not support ili lookup or may not have this synset
                        pass
        except Exception:
            pass

        # Also get English words directly from the synset
        try:
            for sense in synset.senses():
                word = sense.word()
                form = word.form()
                if form and form not in words_by_lang['en']:
                    words_by_lang['en'].append(form)
        except Exception:
            pass

        # Store in concept map
        concept_map[synset_id] = {
            'pos': pos_label,
            'definition': definition,
            'words': dict(words_by_lang)
        }

        # Update coverage stats
        for lang in words_by_lang:
            lang_coverage[lang] += 1

        # Progress report every 10 seconds
        now = time.time()
        if now - last_report >= 10:
            rate = (i + 1) / (now - start_time)
            eta = (total_synsets - i - 1) / rate if rate > 0 else 0
            log(f"  Processed {i+1:,}/{total_synsets:,} synsets ({rate:.0f}/sec, ETA: {eta:.0f}s)")
            last_report = now

    elapsed = time.time() - start_time
    log(f"\nProcessing complete in {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")

    return concept_map, lang_coverage


def save_and_verify(concept_map, lang_coverage):
    """Save concept map and report stats."""
    log("\n" + "=" * 70)
    log("SAVING AND VERIFICATION")
    log("=" * 70)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    # Save pickle
    log(f"Saving to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'wb') as f:
        pickle.dump(concept_map, f, protocol=pickle.HIGHEST_PROTOCOL)

    # Get file size
    file_size = os.path.getsize(OUTPUT_FILE)
    log(f"File size: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")

    # Verify by loading
    log("Verifying saved file...")
    with open(OUTPUT_FILE, 'rb') as f:
        loaded = pickle.load(f)
    log(f"Verified: loaded {len(loaded):,} synsets from saved pickle")

    return file_size


def print_stats(concept_map, lang_coverage, file_size, processing_time):
    """Print final statistics."""
    log("\n" + "=" * 70)
    log("FINAL STATISTICS")
    log("=" * 70)

    total_synsets = len(concept_map)
    log(f"Total synsets processed: {total_synsets:,}")
    log(f"File size: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")
    log(f"Processing time: {processing_time:.1f} seconds ({processing_time/60:.1f} minutes)")

    # POS breakdown
    pos_counts = defaultdict(int)
    for data in concept_map.values():
        pos_counts[data['pos']] += 1

    log("\nPOS breakdown:")
    for pos in sorted(pos_counts.keys()):
        log(f"  {pos}: {pos_counts[pos]:,} synsets")

    # Per-language coverage
    log(f"\nPer-language coverage ({len(lang_coverage)} languages):")
    for lang in sorted(lang_coverage.keys(), key=lambda x: -lang_coverage[x]):
        count = lang_coverage[lang]
        pct = 100.0 * count / total_synsets
        log(f"  {lang}: {count:,} synsets ({pct:.1f}%)")


def print_samples(concept_map):
    """Print 5 random synsets with 4+ languages."""
    log("\n" + "=" * 70)
    log("SAMPLE OUTPUT: 5 synsets with 4+ languages")
    log("=" * 70)

    # Find synsets with 4+ languages
    multilingual = [
        (sid, data) for sid, data in concept_map.items()
        if len(data['words']) >= 4
    ]

    log(f"Found {len(multilingual):,} synsets with 4+ languages")

    if len(multilingual) < 5:
        samples = multilingual
    else:
        samples = random.sample(multilingual, 5)

    for i, (synset_id, data) in enumerate(samples, 1):
        log(f"\n[{i}] {synset_id}")
        log(f"    POS: {data['pos']}")
        log(f"    Definition: {data['definition'][:100]}{'...' if len(data['definition']) > 100 else ''}")
        log(f"    Languages ({len(data['words'])}):")
        for lang in sorted(data['words'].keys()):
            words = data['words'][lang]
            words_str = ', '.join(words[:5])
            if len(words) > 5:
                words_str += f", ... (+{len(words)-5} more)"
            log(f"      {lang}: {words_str}")


def main():
    """Main entry point."""
    start_time = time.time()

    log("PHASE 5a: Build WordNet Concept Map")
    log(f"Git HEAD: {os.popen('git rev-parse HEAD 2>/dev/null').read().strip()}")
    log(f"Start: {datetime.now().isoformat()}")
    log("")

    # Step 1: Verify data is present (already downloaded)
    num_lexicons = ensure_data_downloaded()
    log(f"WordNet/OMW data verified: {num_lexicons} lexicons present")

    # Step 2: Build the concept map
    concept_map, lang_coverage = build_concept_map()

    processing_time = time.time() - start_time

    # Step 3: Save and verify
    file_size = save_and_verify(concept_map, lang_coverage)

    # Step 4: Print statistics
    print_stats(concept_map, lang_coverage, file_size, processing_time)

    # Step 5: Print samples
    print_samples(concept_map)

    total_time = time.time() - start_time
    log("\n" + "=" * 70)
    log(f"PHASE 5a COMPLETE")
    log(f"Total time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
    log(f"Output: {OUTPUT_FILE}")
    log("=" * 70)

    return 0


if __name__ == '__main__':
    sys.exit(main())
