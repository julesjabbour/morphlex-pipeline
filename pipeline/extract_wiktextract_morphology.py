#!/usr/bin/env python3
"""
PHASE 3: Full Wiktextract Morphology Extraction

Processes the ENTIRE 2.4GB Wiktextract dump and extracts:
- morph_type: ROOT / DERIVATION / COMPOUND / COMPOUND+DERIVATION / OTHER
- derived_from_root: source root for derived words
- derivation_mode: prefix, suffix, infix, confix, circumfix, ablaut, pattern
- compound_components: list of component roots for compounds
- etymology_chain: list of {lang, word} for ancestor forms

Template mapping:
- Derivation: af, affix, prefix, suffix, confix, circumfix, infix
- Compound: compound, com
- Etymology: inh (inherited), bor (borrowed), der (derived), cog (cognate)

Output: wiktextract_morphology.pkl
Structure: {lang: {word: {morph_type, derived_from_root, derivation_mode,
                         compound_components, etymology_chain}}}

ZERO HARDCODING. ZERO SHORTCUTS. FULL DUMP PROCESSING.
"""
import gzip
import json
import pickle
import random
import sys
import time
from collections import defaultdict
from datetime import datetime

DATA_FILE = '/mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz'
OUTPUT_FILE = '/mnt/pgdata/morphlex/data/wiktextract_morphology.pkl'
REPORT_DIR = '/mnt/pgdata/morphlex/reports'

# All 11 target languages
TARGET_LANGS = {'en', 'ar', 'tr', 'de', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro'}

# Template categories
DERIVATION_TEMPLATES = {'af', 'affix', 'prefix', 'suffix', 'confix', 'circumfix', 'infix'}
COMPOUND_TEMPLATES = {'compound', 'com'}
ETYMOLOGY_TEMPLATES = {'inh', 'bor', 'der', 'cog'}

# Map template names to derivation modes
TEMPLATE_TO_MODE = {
    'prefix': 'prefix',
    'suffix': 'suffix',
    'infix': 'infix',
    'confix': 'confix',
    'circumfix': 'circumfix',
    'af': 'affix',
    'affix': 'affix',
}


def extract_derivation_info(templates):
    """
    Extract derivation data from etymology_templates.

    Returns: (derived_from_root, derivation_mode) or (None, None)

    Template structure: {"name": "suffix", "args": {"1": "en", "2": "base", "3": "-ness"}}
    For 'af'/'affix': args may have multiple morphemes
    """
    derived_from = None
    mode = None

    for tmpl in templates:
        if not isinstance(tmpl, dict):
            continue
        name = tmpl.get('name', '')
        if name not in DERIVATION_TEMPLATES:
            continue

        args = tmpl.get('args', {})
        if not args:
            continue

        # Determine derivation mode from template name
        mode = TEMPLATE_TO_MODE.get(name, 'affix')

        # Extract the base/root word (usually arg '2' is the base, '1' is language)
        # For prefix/suffix: arg 2 is base, arg 3 is affix
        # For af/affix: multiple args represent morpheme breakdown

        if name in ('prefix', 'suffix', 'infix'):
            # Args: 1=lang, 2=base, 3=affix
            derived_from = args.get('2', '')
        elif name in ('confix', 'circumfix'):
            # Args: 1=lang, 2=prefix, 3=root, 4=suffix
            derived_from = args.get('3', args.get('2', ''))
        elif name in ('af', 'affix'):
            # af/affix can have variable args: 1=lang, then morphemes
            # Find the first non-affix component (doesn't start with -)
            for key in sorted(args.keys()):
                if key == '1':  # skip language code
                    continue
                val = args.get(key, '')
                if val and not val.startswith('-') and not val.endswith('-'):
                    derived_from = val
                    break

        if derived_from:
            break  # Use first derivation template found

    return (derived_from, mode)


def extract_compound_components(templates):
    """
    Extract compound components from etymology_templates.

    Returns: list of component words or empty list

    Template structure: {"name": "compound", "args": {"1": "en", "2": "word1", "3": "word2"}}
    """
    components = []

    for tmpl in templates:
        if not isinstance(tmpl, dict):
            continue
        name = tmpl.get('name', '')
        if name not in COMPOUND_TEMPLATES:
            continue

        args = tmpl.get('args', {})
        if not args:
            continue

        # Compound args: 1=lang, 2,3,4...=components
        for key in sorted(args.keys()):
            if key == '1':  # skip language code
                continue
            val = args.get(key, '')
            if val and isinstance(val, str):
                # Skip alt/tr keys and empty strings
                if key.isdigit() and val.strip():
                    components.append(val.strip())

        if components:
            break  # Use first compound template found

    return components


def extract_etymology_chain(templates):
    """
    Extract etymology chain from inh/bor/der/cog templates.

    Returns: list of {lang: str, word: str} dicts

    Template structure: {"name": "inh", "args": {"1": "en", "2": "enm", "3": "word"}}
    Where: 1=current lang, 2=ancestor lang, 3=ancestor word
    """
    chain = []

    for tmpl in templates:
        if not isinstance(tmpl, dict):
            continue
        name = tmpl.get('name', '')
        if name not in ETYMOLOGY_TEMPLATES:
            continue

        args = tmpl.get('args', {})
        if not args:
            continue

        # Etymology args: 1=current lang, 2=source lang, 3=source word
        source_lang = args.get('2', '')
        source_word = args.get('3', '')

        if source_lang and source_word:
            chain.append({
                'type': name,  # inh/bor/der/cog
                'lang': source_lang,
                'word': source_word
            })

    return chain


def classify_morph_type(has_derivation, has_compound, etymology_chain):
    """
    Classify morphological type based on extracted data.

    Returns: ROOT / DERIVATION / COMPOUND / COMPOUND+DERIVATION / OTHER
    """
    if has_compound and has_derivation:
        return 'COMPOUND+DERIVATION'
    elif has_compound:
        return 'COMPOUND'
    elif has_derivation:
        return 'DERIVATION'
    elif etymology_chain:
        # Has etymology but no affix/compound templates - likely a root or inherited form
        return 'ROOT'
    else:
        return 'OTHER'


def main():
    start_time = time.time()
    print(f"[{datetime.now().isoformat()}] PHASE 3: Full Wiktextract Morphology Extraction")
    print(f"=" * 70)
    print(f"Input: {DATA_FILE}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Target languages: {sorted(TARGET_LANGS)}")
    print(f"Derivation templates: {sorted(DERIVATION_TEMPLATES)}")
    print(f"Compound templates: {sorted(COMPOUND_TEMPLATES)}")
    print(f"Etymology templates: {sorted(ETYMOLOGY_TEMPLATES)}")
    print(f"=" * 70)
    print()

    # Data structure: {lang: {word: {morph_type, derived_from_root, derivation_mode,
    #                                compound_components, etymology_chain}}}
    morphology_data = defaultdict(dict)

    # Statistics per language
    stats = {lang: {
        'total_entries': 0,
        'with_morph_type': 0,
        'with_derivation': 0,
        'with_compound': 0,
        'with_etymology': 0,
        'type_counts': defaultdict(int)
    } for lang in TARGET_LANGS}

    # For sampling: collect word keys per language
    word_samples = {lang: [] for lang in TARGET_LANGS}

    line_count = 0
    entries_processed = 0

    try:
        print(f"[{datetime.now().isoformat()}] Opening gzip file...")
        with gzip.open(DATA_FILE, 'rt', encoding='utf-8') as f:
            for line in f:
                line_count += 1

                # Progress report every 500K lines
                if line_count % 500000 == 0:
                    elapsed = time.time() - start_time if time.time() - start_time > 0 else 1
                    rate = line_count / elapsed
                    print(f"  [{datetime.now().isoformat()}] Processed {line_count:,} lines "
                          f"({rate:.0f} lines/sec), {entries_processed:,} entries extracted...")

                try:
                    entry = json.loads(line.strip())
                except json.JSONDecodeError as e:
                    print(f"  WARNING: JSON decode error at line {line_count}: {e}")
                    continue

                lang = entry.get('lang_code', '')
                if lang not in TARGET_LANGS:
                    continue

                word = entry.get('word', '')
                if not word:
                    continue

                stats[lang]['total_entries'] += 1

                templates = entry.get('etymology_templates', [])

                # Extract all morphology data
                derived_from, derivation_mode = extract_derivation_info(templates)
                compound_components = extract_compound_components(templates)
                etymology_chain = extract_etymology_chain(templates)

                # Classify morphological type
                has_derivation = bool(derived_from)
                has_compound = bool(compound_components)
                morph_type = classify_morph_type(has_derivation, has_compound, etymology_chain)

                # Only store if we have any useful data
                if has_derivation or has_compound or etymology_chain:
                    morphology_data[lang][word] = {
                        'morph_type': morph_type,
                        'derived_from_root': derived_from,
                        'derivation_mode': derivation_mode,
                        'compound_components': compound_components,
                        'etymology_chain': etymology_chain
                    }
                    entries_processed += 1
                    word_samples[lang].append(word)

                    # Update statistics
                    stats[lang]['with_morph_type'] += 1
                    stats[lang]['type_counts'][morph_type] += 1
                    if has_derivation:
                        stats[lang]['with_derivation'] += 1
                    if has_compound:
                        stats[lang]['with_compound'] += 1
                    if etymology_chain:
                        stats[lang]['with_etymology'] += 1

    except FileNotFoundError:
        print(f"FATAL ERROR: File not found: {DATA_FILE}")
        sys.exit(1)
    except Exception as e:
        print(f"FATAL ERROR during processing: {type(e).__name__}: {e}")
        raise

    elapsed_time = time.time() - start_time

    print()
    print(f"[{datetime.now().isoformat()}] Processing complete")
    print(f"=" * 70)
    print(f"Total lines processed: {line_count:,}")
    print(f"Total entries extracted: {entries_processed:,}")
    print(f"Processing time: {elapsed_time:.1f} seconds ({elapsed_time/60:.1f} minutes)")
    print(f"Rate: {line_count/elapsed_time:.0f} lines/second")
    print()

    # Per-language statistics
    print(f"=" * 70)
    print("PER-LANGUAGE STATISTICS")
    print(f"=" * 70)
    for lang in sorted(TARGET_LANGS):
        s = stats[lang]
        print(f"\n{lang.upper()}:")
        print(f"  Total entries in dump: {s['total_entries']:,}")
        print(f"  With morph_type: {s['with_morph_type']:,}")
        print(f"  With derivation data: {s['with_derivation']:,}")
        print(f"  With compound data: {s['with_compound']:,}")
        print(f"  With etymology chains: {s['with_etymology']:,}")
        if s['type_counts']:
            print(f"  Type breakdown:")
            for mtype, count in sorted(s['type_counts'].items()):
                print(f"    {mtype}: {count:,}")

    # Random samples per language
    print()
    print(f"=" * 70)
    print("20-WORD RANDOM SAMPLE PER LANGUAGE")
    print(f"=" * 70)
    for lang in sorted(TARGET_LANGS):
        print(f"\n{lang.upper()} SAMPLES:")
        words = word_samples[lang]
        if not words:
            print("  (no entries extracted for this language)")
            continue

        sample_words = random.sample(words, min(20, len(words)))
        for i, word in enumerate(sample_words, 1):
            data = morphology_data[lang][word]
            print(f"  [{i:2d}] '{word}'")
            print(f"       morph_type: {data['morph_type']}")
            if data['derived_from_root']:
                print(f"       derived_from: '{data['derived_from_root']}' (mode: {data['derivation_mode']})")
            if data['compound_components']:
                print(f"       compound_components: {data['compound_components']}")
            if data['etymology_chain']:
                chain_str = ', '.join(f"{e['type']}:{e['lang']}:{e['word']}"
                                      for e in data['etymology_chain'][:3])
                if len(data['etymology_chain']) > 3:
                    chain_str += f" (+{len(data['etymology_chain'])-3} more)"
                print(f"       etymology_chain: {chain_str}")

    # Save to pickle
    print()
    print(f"[{datetime.now().isoformat()}] Saving to {OUTPUT_FILE}...")

    # Convert defaultdict to regular dict for pickle
    final_data = {lang: dict(words) for lang, words in morphology_data.items()}

    with open(OUTPUT_FILE, 'wb') as f:
        pickle.dump(final_data, f, protocol=pickle.HIGHEST_PROTOCOL)

    # Verify the saved file
    with open(OUTPUT_FILE, 'rb') as f:
        verification = pickle.load(f)

    total_verified = sum(len(words) for words in verification.values())
    print(f"Verification: loaded {total_verified:,} entries from saved pickle")

    # Final summary
    print()
    print(f"=" * 70)
    print("FINAL SUMMARY")
    print(f"=" * 70)
    print(f"Total lines processed: {line_count:,}")
    print(f"Total entries extracted: {entries_processed:,}")
    print(f"Processing time: {elapsed_time:.1f} seconds ({elapsed_time/60:.1f} minutes)")
    print(f"Output file: {OUTPUT_FILE}")
    print()
    print("Per-language entry counts:")
    for lang in sorted(TARGET_LANGS):
        count = len(morphology_data.get(lang, {}))
        print(f"  {lang}: {count:,} entries")

    total_entries = sum(len(words) for words in morphology_data.values())
    print(f"\nGRAND TOTAL: {total_entries:,} morphology entries extracted")
    print(f"[{datetime.now().isoformat()}] PHASE 3 COMPLETE")


if __name__ == '__main__':
    main()
