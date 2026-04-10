#!/usr/bin/env python3
"""Parse German OdeNet via wn package and build PWN synset-to-German word mapping.

Uses the wn Python package which should have odenet:1.4 installed.
Maps ILI (Inter-Lingual Index) to PWN 3.0 synset offsets.

Output: data/open_wordnets/odenet_synset_map.pkl
Format: {synset_offset_pos: [german_word1, german_word2, ...], ...}
Example: {"00001740-n": ["Ding", "Sache"], ...}

Zero error suppression. All exceptions logged visibly.
"""

import os
import pickle
import re
import sys
from datetime import datetime
from pathlib import Path

# Paths
OUTPUT_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets")
OUTPUT_FILE = OUTPUT_DIR / "odenet_synset_map.pkl"
CONCEPT_MAP_FILE = Path("/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl")


def log(msg):
    """Print with immediate flush."""
    print(msg, flush=True)


def explore_odenet():
    """Explore OdeNet structure via wn package."""
    log("=" * 70)
    log("STEP 1: EXPLORE ODENET STRUCTURE")
    log("=" * 70)
    log("")

    try:
        import wn
    except ImportError as e:
        log(f"FATAL: Cannot import wn package: {e}")
        log("Install with: pip install wn")
        sys.exit(1)

    # List available wordnets
    log("Available wordnets in wn:")
    for lexicon in wn.lexicons():
        log(f"  - {lexicon.id()} ({lexicon.label()}) - {lexicon.language()}")
    log("")

    # Try to get OdeNet
    try:
        odenet = wn.Wordnet('odenet')
        log(f"OdeNet loaded: {odenet}")
    except wn.Error as e:
        log(f"ERROR: OdeNet not found: {e}")
        log("Attempting to download odenet:1.4...")
        try:
            wn.download('odenet:1.4', progress=False)
            odenet = wn.Wordnet('odenet')
            log("OdeNet downloaded and loaded successfully")
        except Exception as e2:
            log(f"FATAL: Cannot download/load OdeNet: {e2}")
            sys.exit(1)

    # Also get English PWN 3.0 for ILI mapping
    try:
        pwn = wn.Wordnet('ewn', 'en')
    except wn.Error:
        try:
            pwn = wn.Wordnet('oewn', 'en')
        except wn.Error:
            log("WARNING: English WordNet not found for ILI mapping")
            log("Attempting to download English WordNet...")
            try:
                wn.download('ewn:2020', progress=False)
                pwn = wn.Wordnet('ewn', 'en')
            except Exception:
                try:
                    wn.download('oewn:2024', progress=False)
                    pwn = wn.Wordnet('oewn', 'en')
                except Exception as e:
                    log(f"WARNING: Cannot load English WordNet: {e}")
                    pwn = None

    # Explore synset structure
    log("")
    log("OdeNet synset structure exploration:")
    log("")

    synsets = list(odenet.synsets())[:5]
    for i, synset in enumerate(synsets):
        log(f"--- Sample synset {i + 1} ---")
        log(f"  ID: {synset.id()}")
        log(f"  POS: {synset.pos()}")

        # Get words/lemmas
        words = synset.words()
        word_forms = [w.lemma() for w in words]
        log(f"  Words: {word_forms}")

        # Try to get ILI
        try:
            ili = synset.ili()
            log(f"  ILI: {ili}")
        except Exception as e:
            log(f"  ILI: ERROR - {e}")

        # Try to get relations
        try:
            hypernyms = synset.hypernyms()
            log(f"  Hypernyms: {len(hypernyms)}")
        except Exception as e:
            log(f"  Hypernyms: ERROR - {e}")

        log("")

    log(f"Total OdeNet synsets: {len(list(odenet.synsets())):,}")
    log("")

    return odenet, pwn


def ili_to_pwn_offset(ili, pwn=None):
    """Convert ILI to PWN 3.0 offset+pos format.

    ILI format is typically like 'i12345' (where 12345 is the ILI ID).
    PWN 3.0 offset format is like '00001740-n'.

    Strategy:
    1. If we have PWN loaded, find synset by ILI and extract offset
    2. Otherwise, try to parse ILI string directly if it contains offset info
    """
    if ili is None:
        return None

    ili_str = str(ili)

    # Method 1: Use PWN to find synset by ILI
    if pwn:
        try:
            # Find synsets in PWN that have this ILI
            import wn
            # Query all synsets with matching ILI
            for ss in pwn.synsets():
                try:
                    if ss.ili() and str(ss.ili()) == ili_str:
                        # Extract offset from synset ID
                        # PWN synset IDs are like 'ewn-00001740-n' or 'oewn-00001740-n'
                        ss_id = ss.id()
                        match = re.search(r'(\d{8})-([nvasr])', ss_id)
                        if match:
                            return f"{match.group(1)}-{match.group(2)}"
                except Exception:
                    pass
        except Exception:
            pass

    # Method 2: Parse ILI string if it contains PWN offset info
    # Some ILIs encode the offset directly
    match = re.search(r'(\d{8})-([nvasr])', ili_str)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    # Method 3: If ILI is just a number, we can't map it without PWN
    # The ILI number doesn't directly correspond to PWN offset

    return None


def build_synset_map(odenet, pwn):
    """Build PWN synset ID to German words mapping."""
    log("=" * 70)
    log("STEP 2: BUILD SYNSET MAP")
    log("=" * 70)
    log("")

    synset_map = {}
    total_synsets = 0
    mapped_synsets = 0
    skipped_no_ili = 0
    skipped_no_pwn = 0

    # Build ILI -> PWN offset cache from PWN
    log("Building ILI to PWN offset cache...")
    ili_to_offset = {}

    if pwn:
        for ss in pwn.synsets():
            try:
                ili = ss.ili()
                if ili:
                    # Extract offset from synset ID
                    ss_id = ss.id()
                    match = re.search(r'(\d{8})-([nvasr])', ss_id)
                    if match:
                        pwn_id = f"{match.group(1)}-{match.group(2)}"
                        ili_to_offset[str(ili)] = pwn_id
            except Exception:
                pass
        log(f"ILI cache built: {len(ili_to_offset):,} entries")
    else:
        log("WARNING: No PWN available, will attempt direct ILI parsing")
    log("")

    log("Processing OdeNet synsets...")
    start_time = datetime.now()

    for synset in odenet.synsets():
        total_synsets += 1

        # Get German words
        words = synset.words()
        german_words = [w.lemma() for w in words]

        if not german_words:
            continue

        # Get ILI and map to PWN offset
        try:
            ili = synset.ili()
            if not ili:
                skipped_no_ili += 1
                continue

            ili_str = str(ili)

            # Try cache first
            pwn_id = ili_to_offset.get(ili_str)

            # If not in cache, try direct parsing
            if not pwn_id:
                pwn_id = ili_to_pwn_offset(ili, None)

            if not pwn_id:
                skipped_no_pwn += 1
                continue

            # Add to map
            if pwn_id in synset_map:
                for word in german_words:
                    if word not in synset_map[pwn_id]:
                        synset_map[pwn_id].append(word)
            else:
                synset_map[pwn_id] = german_words.copy()

            mapped_synsets += 1

        except Exception as e:
            log(f"ERROR processing synset {synset.id()}: {type(e).__name__}: {e}")

        # Progress
        if total_synsets % 10000 == 0:
            elapsed = datetime.now() - start_time
            log(f"  Processed {total_synsets:,} synsets, {mapped_synsets:,} mapped, elapsed: {elapsed}")

    log("")
    log(f"Total synsets processed: {total_synsets:,}")
    log(f"Synsets mapped to PWN: {mapped_synsets:,}")
    log(f"Skipped (no ILI): {skipped_no_ili:,}")
    log(f"Skipped (no PWN mapping): {skipped_no_pwn:,}")

    return synset_map


def write_output(synset_map):
    """Write pickle file."""
    log("")
    log("=" * 70)
    log("STEP 3: WRITE OUTPUT")
    log("=" * 70)
    log("")

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log(f"Writing {len(synset_map):,} synset mappings to {OUTPUT_FILE}...")

    try:
        with open(OUTPUT_FILE, 'wb') as f:
            pickle.dump(synset_map, f, protocol=pickle.HIGHEST_PROTOCOL)

        output_size = OUTPUT_FILE.stat().st_size
        log(f"Output file written: {OUTPUT_FILE}")
        log(f"Output size: {output_size:,} bytes ({output_size / 1024:.1f} KB)")
        return output_size

    except OSError as e:
        log(f"FATAL: Cannot write output file: {e}")
        raise


def generate_report(synset_map, output_size):
    """Generate final report."""
    log("")
    log("=" * 70)
    log("REPORT")
    log("=" * 70)
    log("")

    # Total synsets mapped
    total_synsets = len(synset_map)
    log(f"Total synsets mapped: {total_synsets:,}")

    # Total words covered
    total_words = sum(len(v) for v in synset_map.values())
    log(f"Total German words: {total_words:,}")

    # Average words per synset
    if total_synsets > 0:
        avg_words = total_words / total_synsets
        log(f"Average words per synset: {avg_words:.2f}")

    # 5 sample entries
    log("")
    log("5 sample entries:")
    sample_items = list(synset_map.items())[:5]
    for synset_id, words in sample_items:
        words_preview = ', '.join(words[:5])
        if len(words) > 5:
            words_preview += f" ... (+{len(words) - 5} more)"
        log(f"  {synset_id}: [{words_preview}]")

    # File size
    log("")
    log(f"Output file size: {output_size:,} bytes ({output_size / 1024:.1f} KB)")

    # Overlap with concept_wordnet_map.pkl
    log("")
    log("Checking overlap with concept_wordnet_map.pkl...")

    if CONCEPT_MAP_FILE.exists():
        try:
            with open(CONCEPT_MAP_FILE, 'rb') as f:
                concept_map = pickle.load(f)

            concept_synsets = set()
            for synset_id in concept_map.keys():
                match = re.search(r'(\d{8})-([nvasr])', str(synset_id))
                if match:
                    norm_id = f"{match.group(1)}-{match.group(2)}"
                    concept_synsets.add(norm_id)

            odenet_synsets = set(synset_map.keys())
            overlap = concept_synsets & odenet_synsets

            log(f"concept_wordnet_map.pkl synsets: {len(concept_synsets):,}")
            log(f"OdeNet synsets: {len(odenet_synsets):,}")
            log(f"Overlap count: {len(overlap):,}")

            if concept_synsets:
                overlap_pct = 100.0 * len(overlap) / len(concept_synsets)
                log(f"Overlap percentage: {overlap_pct:.1f}% of concept_map synsets have OdeNet coverage")

        except Exception as e:
            log(f"ERROR loading concept_wordnet_map.pkl: {type(e).__name__}: {e}")
    else:
        log(f"concept_wordnet_map.pkl not found at {CONCEPT_MAP_FILE}")


def main():
    log("=" * 70)
    log("PARSE GERMAN ODENET - BUILD PWN SYNSET MAP")
    log("=" * 70)

    # Print git HEAD for traceability
    git_head = os.popen('git rev-parse HEAD 2>/dev/null').read().strip()
    if git_head:
        log(f"Git HEAD: {git_head}")

    start_time = datetime.now()
    log(f"Start: {start_time.isoformat()}")
    log("")

    # Step 1: Explore OdeNet structure
    odenet, pwn = explore_odenet()

    # Step 2: Build synset map
    synset_map = build_synset_map(odenet, pwn)

    # Step 3: Write output
    output_size = write_output(synset_map)

    # Generate report
    generate_report(synset_map, output_size)

    end_time = datetime.now()
    duration = end_time - start_time
    log("")
    log(f"Duration: {duration}")
    log(f"End: {end_time.isoformat()}")


if __name__ == "__main__":
    main()
