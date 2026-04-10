#!/usr/bin/env python3
"""
Replace Modern Greek (el) words in concept_wordnet_map.pkl with Ancient Greek words from AGWN.

STEP 1: Download AGWN data from available sources
STEP 2: Build synset-to-Ancient-Greek lookup
STEP 3: Update concept_wordnet_map.pkl
"""
import os
import pickle
import sys
import urllib.request
import gzip
from collections import defaultdict
from datetime import datetime


def log(msg):
    print(f"{msg}", flush=True)


def download_agwn():
    """Try to download AGWN data from various sources."""
    data_dir = '/mnt/pgdata/morphlex/data/agwn'
    os.makedirs(data_dir, exist_ok=True)

    # First, try the wn package for Ancient Greek
    log("Attempting to download Ancient Greek via wn package...")
    try:
        import wn
        # Check what's available
        available = []
        try:
            # Try to download omw-grc (Ancient Greek from OMW)
            # Redirect output to /dev/null
            _stderr = sys.stderr
            _stdout = sys.stdout
            sys.stderr = open(os.devnull, 'w')
            sys.stdout = open(os.devnull, 'w')
            try:
                wn.download('omw-grc:1.4')
                available.append('omw-grc:1.4')
            except Exception:
                pass
            try:
                wn.download('omw-el:1.4')  # Modern Greek for reference
            except Exception:
                pass
            finally:
                sys.stderr.close()
                sys.stdout.close()
                sys.stderr = _stderr
                sys.stdout = _stdout
        except Exception:
            pass

        # Check what lexicons we have
        lexicons = list(wn.lexicons())
        grc_lexicons = [l for l in lexicons if l.language == 'grc']

        if grc_lexicons:
            log(f"Found Ancient Greek lexicon(s): {[l.id for l in grc_lexicons]}")
            # Extract data from wn
            agwn_data = extract_from_wn(grc_lexicons[0])
            if agwn_data:
                # Save to file
                output_file = os.path.join(data_dir, 'agwn_from_wn.tsv')
                with open(output_file, 'w', encoding='utf-8') as f:
                    for synset_id, lemmas in agwn_data.items():
                        for lemma in lemmas:
                            f.write(f"{synset_id}\t{lemma}\n")
                return output_file, agwn_data
    except ImportError:
        log("wn package not available")
    except Exception as e:
        log(f"wn approach failed: {e}")

    # Try CLARIN-IT direct download
    log("\nTrying CLARIN-IT download...")
    urls_to_try = [
        # Direct file URLs that might work
        'https://dspace-clarin-it.ilc.cnr.it/repository/xmlui/bitstream/handle/20.500.11752/ILC-56/wn-data-grc.tab',
        'https://dspace-clarin-it.ilc.cnr.it/repository/xmlui/bitstream/handle/20.500.11752/ILC-56/agwn.tsv',
    ]

    for url in urls_to_try:
        try:
            log(f"Trying: {url}")
            output_file = os.path.join(data_dir, os.path.basename(url))
            urllib.request.urlretrieve(url, output_file)
            if os.path.exists(output_file) and os.path.getsize(output_file) > 100:
                log(f"Downloaded: {output_file}")
                return output_file, None
        except Exception as e:
            log(f"  Failed: {e}")

    # Try Harvard Greek WordNet API
    log("\nTrying Harvard Greek WordNet API...")
    try:
        # The Harvard API might provide bulk download or allow synset queries
        api_url = 'https://greekwordnet.chs.harvard.edu/api/synsets'
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
            output_file = os.path.join(data_dir, 'harvard_agwn.json')
            with open(output_file, 'wb') as f:
                f.write(data)
            log(f"Downloaded Harvard API data: {len(data)} bytes")
            return output_file, None
    except Exception as e:
        log(f"Harvard API failed: {e}")

    # Last resort: try to get from GitHub or other open sources
    log("\nTrying GitHub/alternative sources...")
    alt_urls = [
        'https://raw.githubusercontent.com/GT4SD/omw-data/main/omw-grc/wn-data-grc.tab',
        'https://github.com/GT4SD/omw-data/raw/main/omw-grc/wn-data-grc.tab',
    ]

    for url in alt_urls:
        try:
            log(f"Trying: {url}")
            output_file = os.path.join(data_dir, 'wn-data-grc.tab')
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read()
                with open(output_file, 'wb') as f:
                    f.write(data)
            if os.path.exists(output_file) and os.path.getsize(output_file) > 100:
                log(f"Downloaded: {output_file} ({os.path.getsize(output_file)} bytes)")
                return output_file, None
        except Exception as e:
            log(f"  Failed: {e}")

    return None, None


def extract_from_wn(lexicon):
    """Extract synset->lemmas mapping from wn lexicon."""
    import wn
    agwn_data = defaultdict(list)

    try:
        wordnet = wn.Wordnet(lexicon.id)
        synsets = list(wordnet.synsets())
        log(f"Found {len(synsets)} synsets in {lexicon.id}")

        for synset in synsets:
            # Get the ILI to map to PWN synsets
            try:
                ili = synset.ili
                if ili:
                    # Try to find the corresponding English synset to get PWN ID
                    eng_synsets = wn.synsets(ili=ili)
                    pwn_id = None
                    for es in eng_synsets:
                        es_lex = es.lexicon()
                        if es_lex.language == 'en':
                            pwn_id = es.id
                            break

                    if pwn_id:
                        for word in synset.words():
                            lemma = word.lemma()
                            if lemma and lemma not in agwn_data[pwn_id]:
                                agwn_data[pwn_id].append(lemma)
            except Exception:
                pass

        return dict(agwn_data)
    except Exception as e:
        log(f"Error extracting from wn: {e}")
        return None


def parse_agwn_file(filepath):
    """Parse AGWN tab file into synset -> lemmas dict."""
    agwn_lookup = defaultdict(list)

    # Detect file type
    if filepath.endswith('.json'):
        import json
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Parse JSON structure (depends on API format)
        if isinstance(data, list):
            for item in data:
                if 'synset' in item and 'lemma' in item:
                    synset_id = item['synset']
                    lemma = item['lemma']
                    if lemma not in agwn_lookup[synset_id]:
                        agwn_lookup[synset_id].append(lemma)
        return dict(agwn_lookup)

    # Tab-separated file
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split('\t')
            if len(parts) >= 2:
                synset_id = parts[0].strip()
                lemma = parts[1].strip()

                # Normalize synset_id format if needed
                # OMW format might be like: "00001740-n" or "eng-30-00001740-n"
                # We need to match with concept_map format

                if lemma and lemma not in agwn_lookup[synset_id]:
                    agwn_lookup[synset_id].append(lemma)

    return dict(agwn_lookup)


def normalize_synset_id(synset_id):
    """Normalize synset ID to match concept_map format."""
    # The concept map uses format like: oewn-00001740-n
    # AGWN might use: 00001740-n or eng-30-00001740-n

    # Extract the core: 8-digit number + POS
    import re
    match = re.search(r'(\d{8})-([nvasr])', synset_id)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return synset_id


def build_normalized_lookup(agwn_lookup):
    """Build a lookup with normalized synset IDs."""
    normalized = defaultdict(list)
    for synset_id, lemmas in agwn_lookup.items():
        norm_id = normalize_synset_id(synset_id)
        for lemma in lemmas:
            if lemma not in normalized[norm_id]:
                normalized[norm_id].append(lemma)
    return dict(normalized)


def update_concept_map(agwn_lookup):
    """Update concept_wordnet_map.pkl with Ancient Greek words."""
    concept_map_path = '/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl'

    log(f"\nLoading {concept_map_path}...")
    with open(concept_map_path, 'rb') as f:
        concept_map = pickle.load(f)
    log(f"Loaded {len(concept_map):,} synsets")

    # Build normalized lookup for matching
    norm_lookup = build_normalized_lookup(agwn_lookup)
    log(f"AGWN normalized lookup has {len(norm_lookup):,} synsets")

    # Stats
    synsets_with_el = 0
    synsets_replaced = 0
    synsets_unchanged = 0
    samples_before_after = []

    for synset_id, data in concept_map.items():
        words = data.get('words', {})
        if 'el' not in words:
            continue

        synsets_with_el += 1
        old_words = words['el']

        # Try to find AGWN match
        norm_id = normalize_synset_id(synset_id)

        if norm_id in norm_lookup:
            new_words = norm_lookup[norm_id]
            words['el'] = new_words
            synsets_replaced += 1

            if len(samples_before_after) < 10:
                samples_before_after.append({
                    'synset_id': synset_id,
                    'old_words': old_words[:3],
                    'new_words': new_words[:3]
                })
        else:
            synsets_unchanged += 1

    # Save updated concept map
    log(f"\nSaving updated concept_wordnet_map.pkl...")
    with open(concept_map_path, 'wb') as f:
        pickle.dump(concept_map, f, protocol=pickle.HIGHEST_PROTOCOL)

    file_size = os.path.getsize(concept_map_path)
    log(f"Saved: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")

    return {
        'synsets_with_el': synsets_with_el,
        'synsets_replaced': synsets_replaced,
        'synsets_unchanged': synsets_unchanged,
        'samples': samples_before_after
    }


def main():
    log("=" * 70)
    log("REPLACE MODERN GREEK WITH ANCIENT GREEK WORDNET")
    log("=" * 70)
    log(f"Git HEAD: {os.popen('git rev-parse HEAD 2>/dev/null').read().strip()}")
    log(f"Start: {datetime.now().isoformat()}")
    log("")

    # STEP 1: Download AGWN
    log("=" * 70)
    log("STEP 1: DOWNLOAD AGWN DATA")
    log("=" * 70)

    downloaded_file, preloaded_data = download_agwn()

    if downloaded_file is None and preloaded_data is None:
        log("\nERROR: Could not download AGWN data from any source!")
        log("Tried:")
        log("  - wn package (omw-grc:1.4)")
        log("  - CLARIN-IT repository")
        log("  - Harvard Greek WordNet API")
        log("  - GitHub alternative sources")
        return 1

    # STEP 2: Build lookup
    log("\n" + "=" * 70)
    log("STEP 2: BUILD SYNSET-TO-ANCIENT-GREEK LOOKUP")
    log("=" * 70)

    if preloaded_data:
        agwn_lookup = preloaded_data
    else:
        log(f"\nParsing: {downloaded_file}")
        file_size = os.path.getsize(downloaded_file)
        log(f"File size: {file_size:,} bytes")
        agwn_lookup = parse_agwn_file(downloaded_file)

    total_synsets = len(agwn_lookup)
    total_lemmas = sum(len(v) for v in agwn_lookup.values())

    log(f"\nTotal synsets covered: {total_synsets:,}")
    log(f"Total lemmas: {total_lemmas:,}")

    # 5 sample entries
    log("\n5 sample entries:")
    sample_items = list(agwn_lookup.items())[:5]
    for synset_id, lemmas in sample_items:
        log(f"  {synset_id}: {', '.join(lemmas[:5])}")

    if total_synsets == 0:
        log("\nERROR: No synsets found in AGWN data!")
        return 1

    # STEP 3: Update concept map
    log("\n" + "=" * 70)
    log("STEP 3: UPDATE CONCEPT MAP")
    log("=" * 70)

    result = update_concept_map(agwn_lookup)

    # Print results
    log("\n" + "=" * 70)
    log("RESULTS")
    log("=" * 70)
    log(f"Synsets with Modern Greek ('el') originally: {result['synsets_with_el']:,}")
    log(f"Synsets replaced with Ancient Greek: {result['synsets_replaced']:,}")
    log(f"Synsets left unchanged (no AGWN match): {result['synsets_unchanged']:,}")

    if result['synsets_with_el'] > 0:
        coverage = 100.0 * result['synsets_replaced'] / result['synsets_with_el']
        log(f"Coverage: {coverage:.1f}%")

    log("\n5 sample before/after:")
    for i, sample in enumerate(result['samples'][:5], 1):
        log(f"  [{i}] {sample['synset_id']}")
        log(f"      Old (Modern Greek): {', '.join(sample['old_words'])}")
        log(f"      New (Ancient Greek): {', '.join(sample['new_words'])}")

    log("\n" + "=" * 70)
    log("COMPLETE")
    log("=" * 70)
    log(f"End: {datetime.now().isoformat()}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
