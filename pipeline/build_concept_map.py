#!/usr/bin/env python3
"""
PHASE 5a: Build WordNet Concept Map with Open Multilingual Wordnet

Uses the ILI (Inter-Lingual Index) to link concepts across all OMW languages.
The ILI is the bridge that connects the same concept in different languages.

Output: data/concept_wordnet_map.pkl
Structure: {
    synset_id: {
        'pos': 'NOUN' | 'VERB' | 'ADJ' | 'ADV',
        'definition': 'English definition string',
        'words': {
            'en': ['word1', 'word2'],
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

# Suppress ALL wn import output
_stderr = sys.stderr
_stdout = sys.stdout
sys.stderr = open(os.devnull, 'w')
sys.stdout = open(os.devnull, 'w')
try:
    import wn
finally:
    sys.stderr.close()
    sys.stdout.close()
    sys.stderr = _stderr
    sys.stdout = _stdout

# Output paths
OUTPUT_FILE = '/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl'


def log(msg):
    """Print with timestamp."""
    print(f"[{datetime.now().isoformat()}] {msg}", flush=True)


def get_pos_label(pos_char):
    """Convert POS character to label."""
    pos_map = {
        'n': 'NOUN',
        'v': 'VERB',
        'a': 'ADJ',
        's': 'ADJ',
        'r': 'ADV',
    }
    return pos_map.get(pos_char, 'OTHER')


def build_concept_map():
    """Build the concept map from WordNet synsets using ILI cross-language lookup."""
    log("=" * 70)
    log("PHASE 5a: Building WordNet Concept Map (ILI-based)")
    log("=" * 70)

    # Get all available lexicons and their languages
    lexicons = list(wn.lexicons())
    log(f"\nDiscovered {len(lexicons)} lexicons")

    # Build language code set from lexicons
    lang_codes = set()
    for lex in lexicons:
        lang_codes.add(lex.language)
    lang_codes = sorted(lang_codes)
    log(f"Unique language codes: {len(lang_codes)}")
    log(f"Languages: {', '.join(lang_codes)}")

    # Find English WordNet for base synsets
    eng_wordnet = None
    for wn_id in ['oewn:2024', 'ewn:2020', 'omw-en:1.4', 'omw-en31:1.4']:
        try:
            eng_wordnet = wn.Wordnet(wn_id)
            log(f"Using English WordNet: {wn_id}")
            break
        except wn.Error:
            continue

    if eng_wordnet is None:
        eng_lexicons = [l for l in lexicons if l.language == 'en']
        if eng_lexicons:
            eng_wordnet = wn.Wordnet(eng_lexicons[0].id)
            log(f"Using English lexicon: {eng_lexicons[0].id}")
        else:
            raise RuntimeError("No English WordNet found!")

    all_synsets = list(eng_wordnet.synsets())
    total_synsets = len(all_synsets)
    log(f"Total English synsets to process: {total_synsets:,}")

    # Build the concept map
    concept_map = {}
    lang_coverage = defaultdict(int)

    start_time = time.time()

    for synset in all_synsets:
        synset_id = synset.id

        # Get definition
        try:
            definition = synset.definition() or ""
        except Exception:
            definition = ""

        # Get POS
        try:
            pos_char = synset.pos
            pos_label = get_pos_label(pos_char)
        except Exception:
            pos_char = synset_id.split('-')[-1] if '-' in synset_id else 'n'
            pos_label = get_pos_label(pos_char)

        # Collect words from all languages using ILI
        words_by_lang = defaultdict(list)

        # THE KEY FIX: Use ILI to find synsets in ALL languages
        # wn.synsets(ili=ili) searches ALL loaded lexicons
        try:
            ili = synset.ili
            if ili:
                # Get all synsets across ALL lexicons that share this ILI
                matching_synsets = wn.synsets(ili=ili)
                for ms in matching_synsets:
                    # Get language from the synset's lexicon
                    try:
                        ms_lexicon = ms.lexicon()
                        lang = ms_lexicon.language
                    except Exception:
                        # Fallback: try to get from synset id pattern
                        continue

                    # Collect words from this synset
                    try:
                        for word in ms.words():
                            form = word.lemma()
                            if form and form not in words_by_lang[lang]:
                                words_by_lang[lang].append(form)
                    except Exception:
                        pass
        except Exception:
            pass

        # Also ensure English words from the original synset are included
        try:
            for word in synset.words():
                form = word.lemma()
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

    elapsed = time.time() - start_time
    log(f"Processing complete in {elapsed:.1f}s")

    return concept_map, lang_coverage, elapsed


def main():
    """Main entry point."""
    log("PHASE 5a: Build WordNet Concept Map")
    log(f"Git HEAD: {os.popen('git rev-parse HEAD 2>/dev/null').read().strip()}")
    log(f"Start: {datetime.now().isoformat()}")
    log("")

    # Verify data present
    lexicons = list(wn.lexicons())
    if len(lexicons) < 10:
        raise RuntimeError(f"WordNet/OMW data not present! Only {len(lexicons)} lexicons.")
    log(f"WordNet/OMW data verified: {len(lexicons)} lexicons present")

    # Build the concept map
    concept_map, lang_coverage, processing_time = build_concept_map()

    # Save pickle
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    log(f"\nSaving to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'wb') as f:
        pickle.dump(concept_map, f, protocol=pickle.HIGHEST_PROTOCOL)

    file_size = os.path.getsize(OUTPUT_FILE)

    # Verify
    with open(OUTPUT_FILE, 'rb') as f:
        loaded = pickle.load(f)
    log(f"Verified: {len(loaded):,} synsets saved")

    # Print stats
    log("\n" + "=" * 70)
    log("FINAL STATISTICS")
    log("=" * 70)
    log(f"Total synsets: {len(concept_map):,}")
    log(f"File size: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")
    log(f"Processing time: {processing_time:.1f}s")

    # POS breakdown
    pos_counts = defaultdict(int)
    for data in concept_map.values():
        pos_counts[data['pos']] += 1
    log("\nPOS breakdown:")
    for pos in sorted(pos_counts.keys()):
        log(f"  {pos}: {pos_counts[pos]:,}")

    # Per-language coverage
    log(f"\nPer-language coverage ({len(lang_coverage)} languages):")
    for lang in sorted(lang_coverage.keys(), key=lambda x: -lang_coverage[x]):
        count = lang_coverage[lang]
        pct = 100.0 * count / len(concept_map)
        log(f"  {lang}: {count:,} ({pct:.1f}%)")

    # 5 samples with 4+ languages
    log("\n" + "=" * 70)
    log("SAMPLES: 5 synsets with 4+ languages")
    log("=" * 70)
    multilingual = [(sid, d) for sid, d in concept_map.items() if len(d['words']) >= 4]
    log(f"Found {len(multilingual):,} synsets with 4+ languages")
    if len(multilingual) > 0:
        samples = random.sample(multilingual, min(5, len(multilingual)))
        for i, (sid, data) in enumerate(samples, 1):
            log(f"\n[{i}] {sid} ({data['pos']})")
            defn = data['definition']
            if len(defn) > 80:
                defn = defn[:77] + "..."
            log(f"    Def: {defn}")
            for lang in sorted(data['words'].keys())[:8]:
                words = data['words'][lang][:3]
                log(f"    {lang}: {', '.join(words)}")
    else:
        log("No multilingual synsets found!")

    log("\n" + "=" * 70)
    log("PHASE 5a COMPLETE")
    log("=" * 70)
    return 0


if __name__ == '__main__':
    sys.exit(main())
