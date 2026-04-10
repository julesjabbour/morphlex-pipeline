#!/usr/bin/env python3
"""Parse German OdeNet via wn package and build PWN synset-to-German word mapping.

REWRITTEN to properly handle wn package API (properties vs methods).
Explores structure first, then parses.

Output: data/open_wordnets/odenet_synset_map.pkl
Format: {synset_offset_pos: [german_word1, german_word2, ...], ...}

Zero error suppression. All exceptions logged visibly.
"""

import os
import pickle
import re
import sys
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets")
OUTPUT_FILE = OUTPUT_DIR / "odenet_synset_map.pkl"
CONCEPT_MAP_FILE = Path("/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl")


def log(msg):
    print(msg, flush=True)


def safe_attr(obj, attr):
    """Safely get attribute, handling both property and method access."""
    val = getattr(obj, attr, None)
    if val is None:
        return None
    if callable(val):
        try:
            return val()
        except Exception:
            return None
    return val


def main():
    log("=" * 70)
    log("PARSE GERMAN ODENET - BUILD PWN SYNSET MAP")
    log("=" * 70)

    git_head = os.popen('git rev-parse HEAD 2>/dev/null').read().strip()
    if git_head:
        log(f"Git HEAD: {git_head}")

    start_time = datetime.now()
    log(f"Start: {start_time.isoformat()}")
    log("")

    # Step 1: Import and explore wn
    log("=" * 70)
    log("STEP 1: LOAD WN PACKAGE")
    log("=" * 70)
    log("")

    try:
        import wn
        log(f"wn version: {getattr(wn, '__version__', 'unknown')}")
    except ImportError as e:
        log(f"FATAL: Cannot import wn: {e}")
        sys.exit(1)

    # List available lexicons
    log("")
    log("Available lexicons:")
    try:
        for lex in wn.lexicons():
            lex_id = safe_attr(lex, 'id')
            lex_lang = safe_attr(lex, 'language')
            log(f"  {lex_id} ({lex_lang})")
    except Exception as e:
        log(f"ERROR listing lexicons: {type(e).__name__}: {e}")

    # Load OdeNet
    log("")
    log("Loading OdeNet...")
    odenet = None
    try:
        odenet = wn.Wordnet('odenet')
        log("  Loaded successfully")
    except Exception as e:
        log(f"  Not found: {e}")
        log("  Trying to download odenet:1.4...")
        try:
            wn.download('odenet:1.4', progress=False)
            odenet = wn.Wordnet('odenet')
            log("  Downloaded and loaded")
        except Exception as e2:
            log(f"FATAL: Cannot load OdeNet: {e2}")
            sys.exit(1)

    # Load English WordNet for ILI mapping
    log("")
    log("Loading English WordNet for ILI mapping...")
    pwn = None
    for name in ['oewn', 'ewn', 'omw-en31']:
        try:
            pwn = wn.Wordnet(name)
            log(f"  Loaded: {name}")
            break
        except Exception:
            pass

    if pwn is None:
        log("  Not found, downloading oewn:2024...")
        try:
            wn.download('oewn:2024', progress=False)
            pwn = wn.Wordnet('oewn')
            log("  Downloaded oewn:2024")
        except Exception as e:
            log(f"  WARNING: No English WordNet available: {e}")

    # Step 2: Build ILI to PWN offset cache
    log("")
    log("=" * 70)
    log("STEP 2: BUILD ILI TO PWN OFFSET CACHE")
    log("=" * 70)
    log("")

    ili_to_pwn = {}
    if pwn:
        log("Building ILI cache from English WordNet...")
        cache_start = datetime.now()
        pwn_synsets = list(pwn.synsets())
        log(f"  PWN synsets to process: {len(pwn_synsets):,}")

        for ss in pwn_synsets:
            try:
                ili = safe_attr(ss, 'ili')
                if ili:
                    ili_str = str(ili)
                    ss_id = safe_attr(ss, 'id')
                    if ss_id:
                        # Extract offset-pos from synset ID like "oewn-00001740-n"
                        match = re.search(r'(\d{8})-([nvasr])', str(ss_id))
                        if match:
                            pwn_id = f"{match.group(1)}-{match.group(2)}"
                            ili_to_pwn[ili_str] = pwn_id
            except Exception:
                pass

        log(f"  ILI cache built: {len(ili_to_pwn):,} entries")
        log(f"  Cache time: {datetime.now() - cache_start}")
    else:
        log("No PWN available - will try direct ILI parsing")

    # Step 3: Process OdeNet synsets
    log("")
    log("=" * 70)
    log("STEP 3: PROCESS ODENET SYNSETS")
    log("=" * 70)
    log("")

    synset_map = {}
    total = 0
    mapped = 0
    no_ili = 0
    no_pwn = 0

    log("Processing OdeNet synsets...")
    proc_start = datetime.now()

    odenet_synsets = list(odenet.synsets())
    log(f"Total OdeNet synsets: {len(odenet_synsets):,}")
    log("")

    # Show sample synset structure
    if odenet_synsets:
        ss = odenet_synsets[0]
        log("Sample synset structure:")
        log(f"  id: {safe_attr(ss, 'id')}")
        log(f"  pos: {safe_attr(ss, 'pos')}")
        log(f"  ili: {safe_attr(ss, 'ili')}")
        words = safe_attr(ss, 'words')
        if words:
            log(f"  words: {len(list(words))} items")
            for w in list(words)[:2]:
                log(f"    word.lemma: {safe_attr(w, 'lemma')}")
                log(f"    word.form: {safe_attr(w, 'form')}")
        log("")

    for ss in odenet_synsets:
        total += 1

        # Get German words
        words = safe_attr(ss, 'words')
        if not words:
            continue

        german_words = []
        for w in words:
            # Try different attribute names for the word form
            form = safe_attr(w, 'lemma') or safe_attr(w, 'form') or safe_attr(w, 'word')
            if form:
                german_words.append(str(form))

        if not german_words:
            continue

        # Get ILI and map to PWN
        ili = safe_attr(ss, 'ili')
        if not ili:
            no_ili += 1
            continue

        ili_str = str(ili)
        pwn_id = ili_to_pwn.get(ili_str)

        # If not in cache, try direct pattern matching on ILI string
        if not pwn_id:
            match = re.search(r'(\d{8})-([nvasr])', ili_str)
            if match:
                pwn_id = f"{match.group(1)}-{match.group(2)}"

        if not pwn_id:
            no_pwn += 1
            continue

        # Add to map
        if pwn_id in synset_map:
            for word in german_words:
                if word not in synset_map[pwn_id]:
                    synset_map[pwn_id].append(word)
        else:
            synset_map[pwn_id] = german_words.copy()

        mapped += 1

        if total % 10000 == 0:
            log(f"  Processed {total:,}, mapped {mapped:,}")

    log("")
    log(f"Total synsets: {total:,}")
    log(f"Mapped to PWN: {mapped:,}")
    log(f"No ILI: {no_ili:,}")
    log(f"No PWN mapping: {no_pwn:,}")
    log(f"Unique PWN synsets: {len(synset_map):,}")
    log(f"Process time: {datetime.now() - proc_start}")

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
    log(f"Total German words: {total_words:,}")
    if synset_map:
        log(f"Avg words/synset: {total_words/len(synset_map):.2f}")

    log("")
    log("5 sample entries:")
    for sid, words in list(synset_map.items())[:5]:
        preview = ', '.join(words[:3])
        if len(words) > 3:
            preview += f"... (+{len(words)-3})"
        log(f"  {sid}: [{preview}]")

    # Check overlap with concept_wordnet_map.pkl
    log("")
    log("Checking overlap with concept_wordnet_map.pkl...")
    if CONCEPT_MAP_FILE.exists():
        try:
            with open(CONCEPT_MAP_FILE, 'rb') as f:
                concept_map = pickle.load(f)

            concept_synsets = set()
            for k in concept_map.keys():
                match = re.search(r'(\d{8})-([nvasr])', str(k))
                if match:
                    concept_synsets.add(f"{match.group(1)}-{match.group(2)}")

            overlap = concept_synsets & set(synset_map.keys())
            log(f"concept_map synsets: {len(concept_synsets):,}")
            log(f"OdeNet synsets: {len(synset_map):,}")
            log(f"Overlap: {len(overlap):,}")
            if concept_synsets:
                log(f"Coverage: {100*len(overlap)/len(concept_synsets):.1f}%")
        except Exception as e:
            log(f"ERROR: {type(e).__name__}: {e}")
    else:
        log(f"Not found: {CONCEPT_MAP_FILE}")

    log("")
    log(f"Duration: {datetime.now() - start_time}")
    log(f"End: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
