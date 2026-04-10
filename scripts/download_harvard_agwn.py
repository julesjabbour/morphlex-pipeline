#!/usr/bin/env python3
"""Download all Ancient Greek lemmas from Harvard Greek WordNet API.

Paginates through /api/lemmas (112,512 lemmas, ~1,126 pages).
For each lemma, extracts synset mappings.
Builds lookup: pwn_offset_pos -> list of Ancient Greek lemmas.
"""

import os
import sys
import json
import time
import pickle
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from collections import defaultdict

BASE_URL = "https://greekwordnet.chs.harvard.edu"
DELAY = 0.1  # 100ms between API calls

def fetch_json(url, max_retries=3):
    """Fetch JSON from URL with retries."""
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 MorphlexPipeline/1.0'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"  Retry {attempt+1}/{max_retries} after {wait}s: {e}")
                time.sleep(wait)
            else:
                raise
    return None

def main():
    print("=" * 70)
    print("DOWNLOAD ALL ANCIENT GREEK LEMMAS FROM HARVARD API")
    print("=" * 70)
    print(f"Git HEAD: {os.popen('git rev-parse HEAD').read().strip()}")
    start_time = datetime.now()
    print(f"Start: {start_time.isoformat()}")
    print()

    # Ensure output directory exists
    output_dir = Path("/mnt/pgdata/morphlex/data/agwn")
    output_dir.mkdir(parents=True, exist_ok=True)

    # STEP 1: Check structure of /api/lemmas
    print("=" * 70)
    print("STEP 1: CHECK IF SYNSETS ARE INLINE IN /api/lemmas")
    print("=" * 70)

    first_page = fetch_json(f"{BASE_URL}/api/lemmas/?limit=100&offset=0")
    total_count = first_page.get('count', 0)
    print(f"Total lemmas: {total_count:,}")
    print(f"Pages needed: {(total_count + 99) // 100:,}")

    # Check first result for synsets
    first_result = first_page['results'][0] if first_page['results'] else {}
    result_keys = list(first_result.keys())
    print(f"Lemma entry keys: {result_keys}")

    has_inline_synsets = 'synsets' in first_result
    print(f"Synsets inline: {has_inline_synsets}")

    if has_inline_synsets:
        print("\nSynsets ARE inline - proceeding with single-pass download")
    else:
        print("\nSynsets NOT inline - will need separate synset queries")
        print("First, collecting all unique lemma+pos pairs...")

    print()

    # STEP 2: Paginate through all lemmas
    print("=" * 70)
    print("STEP 2: PAGINATE THROUGH /api/lemmas")
    print("=" * 70)

    all_lemmas = []  # List of (lemma, pos, uri) tuples
    page = 0
    url = f"{BASE_URL}/api/lemmas/?limit=100&offset=0"

    while url:
        page += 1
        data = fetch_json(url)

        for entry in data.get('results', []):
            lemma = entry.get('lemma', '')
            pos = entry.get('pos', '')
            uri = entry.get('uri', '')
            synsets_data = entry.get('synsets', None)

            all_lemmas.append({
                'lemma': lemma,
                'pos': pos,
                'uri': uri,
                'synsets': synsets_data  # Will be None if not inline
            })

        url = data.get('next')

        # Progress every 100 pages
        if page % 100 == 0:
            print(f"  Page {page:,}: collected {len(all_lemmas):,} lemmas")

        if url:
            time.sleep(DELAY)

    print(f"\nTotal pages fetched: {page:,}")
    print(f"Total lemma entries: {len(all_lemmas):,}")

    # Count unique lemma+pos pairs
    unique_lemma_pos = set((l['lemma'], l['pos']) for l in all_lemmas)
    print(f"Unique lemma+pos pairs: {len(unique_lemma_pos):,}")

    print()

    # STEP 3: Get synsets (either from inline data or separate queries)
    print("=" * 70)
    print("STEP 3: EXTRACT SYNSET MAPPINGS")
    print("=" * 70)

    # Build lookup: synset_id -> list of lemmas
    synset_to_lemmas = defaultdict(set)
    lemma_to_synsets = defaultdict(set)

    if has_inline_synsets:
        # Extract from inline data
        print("Extracting synsets from inline data...")
        processed = 0
        for entry in all_lemmas:
            lemma = entry['lemma']
            pos = entry['pos']
            synsets_data = entry.get('synsets')

            if synsets_data:
                # synsets can be a dict with 'literal' and/or other keys
                if isinstance(synsets_data, dict):
                    for sense_type, synset_list in synsets_data.items():
                        if isinstance(synset_list, list):
                            for syn in synset_list:
                                offset = syn.get('offset', '')
                                syn_pos = syn.get('pos', pos)
                                if offset:
                                    # Format: XXXXXXXX-p (e.g., 00001740-n)
                                    synset_id = f"{offset.zfill(8)}-{syn_pos}"
                                    synset_to_lemmas[synset_id].add(lemma)
                                    lemma_to_synsets[lemma].add(synset_id)
                elif isinstance(synsets_data, list):
                    for syn in synsets_data:
                        offset = syn.get('offset', '')
                        syn_pos = syn.get('pos', pos)
                        if offset:
                            synset_id = f"{offset.zfill(8)}-{syn_pos}"
                            synset_to_lemmas[synset_id].add(lemma)
                            lemma_to_synsets[lemma].add(synset_id)

            processed += 1
            if processed % 10000 == 0:
                print(f"  Processed {processed:,} / {len(all_lemmas):,}")

        print(f"Processed all {len(all_lemmas):,} entries")

    else:
        # Need to query synsets separately for each unique lemma+pos
        num_pairs = len(unique_lemma_pos)
        print(f"Need to query {num_pairs:,} unique lemma+pos pairs")

        if num_pairs > 50000:
            print(f"\nERROR: Too many API calls required ({num_pairs:,})")
            print("Stopping to avoid excessive API usage.")
            print("Consider alternative data sources.")

            # Save what we have so far
            lemmas_file = output_dir / "harvard_all_lemmas.json"
            with open(lemmas_file, 'w', encoding='utf-8') as f:
                json.dump(all_lemmas, f, ensure_ascii=False)
            print(f"\nSaved lemmas to: {lemmas_file}")
            print(f"File size: {lemmas_file.stat().st_size:,} bytes")

            print(f"\nEnd: {datetime.now().isoformat()}")
            sys.exit(1)

        # Proceed with synset queries
        print(f"Proceeding with {num_pairs:,} synset queries...")
        queried = 0

        for lemma, pos in sorted(unique_lemma_pos):
            # URL-encode the lemma
            encoded_lemma = urllib.request.quote(lemma, safe='')
            url = f"{BASE_URL}/api/lemmas/{encoded_lemma}/{pos}/synsets"

            try:
                data = fetch_json(url)

                # The response contains synsets for this lemma
                results = data.get('results', [])
                for result in results:
                    synsets_data = result.get('synsets', {})

                    if isinstance(synsets_data, dict):
                        for sense_type, synset_list in synsets_data.items():
                            if isinstance(synset_list, list):
                                for syn in synset_list:
                                    offset = syn.get('offset', '')
                                    syn_pos = syn.get('pos', pos)
                                    if offset:
                                        synset_id = f"{offset.zfill(8)}-{syn_pos}"
                                        synset_to_lemmas[synset_id].add(lemma)
                                        lemma_to_synsets[lemma].add(synset_id)
                    elif isinstance(synsets_data, list):
                        for syn in synsets_data:
                            offset = syn.get('offset', '')
                            syn_pos = syn.get('pos', pos)
                            if offset:
                                synset_id = f"{offset.zfill(8)}-{syn_pos}"
                                synset_to_lemmas[synset_id].add(lemma)
                                lemma_to_synsets[lemma].add(synset_id)

            except Exception as e:
                # Skip failed queries
                pass

            queried += 1
            if queried % 100 == 0:
                print(f"  Queried {queried:,} / {num_pairs:,} lemma+pos pairs, {len(synset_to_lemmas):,} synsets found")

            time.sleep(DELAY)

        print(f"\nQueried all {num_pairs:,} lemma+pos pairs")

    # Convert sets to lists for pickle serialization
    synset_lookup = {k: sorted(list(v)) for k, v in synset_to_lemmas.items()}

    print(f"\nTotal unique synsets: {len(synset_lookup):,}")
    print(f"Total lemmas with synsets: {len(lemma_to_synsets):,}")

    print()

    # STEP 4: Save pickle file
    print("=" * 70)
    print("STEP 4: SAVE LOOKUP FILE")
    print("=" * 70)

    pkl_file = output_dir / "agwn_synset_lookup.pkl"
    with open(pkl_file, 'wb') as f:
        pickle.dump(synset_lookup, f)

    pkl_size = pkl_file.stat().st_size
    print(f"Saved: {pkl_file}")
    print(f"File size: {pkl_size:,} bytes ({pkl_size/1024:.1f} KB)")

    print()

    # STEP 5: Check overlap with concept_wordnet_map.pkl
    print("=" * 70)
    print("STEP 5: CHECK OVERLAP WITH concept_wordnet_map.pkl")
    print("=" * 70)

    concept_map_file = Path("/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl")
    if concept_map_file.exists():
        with open(concept_map_file, 'rb') as f:
            concept_map = pickle.load(f)

        # Extract synset IDs from concept map
        concept_synsets = set()
        for concept_id, lang_data in concept_map.items():
            for lang, word_list in lang_data.items():
                for word_info in word_list:
                    if isinstance(word_info, dict) and 'synset_id' in word_info:
                        concept_synsets.add(word_info['synset_id'])
                    elif isinstance(word_info, tuple) and len(word_info) >= 2:
                        concept_synsets.add(word_info[1])

        agwn_synsets = set(synset_lookup.keys())
        overlap = agwn_synsets & concept_synsets

        print(f"Synsets in concept_wordnet_map.pkl: {len(concept_synsets):,}")
        print(f"Synsets in AGWN: {len(agwn_synsets):,}")
        print(f"Overlap: {len(overlap):,}")
        print(f"Coverage: {100*len(overlap)/len(concept_synsets):.1f}% of concept map synsets have AGWN data")
    else:
        print(f"concept_wordnet_map.pkl not found at {concept_map_file}")
        overlap = set()

    print()

    # STEP 6: Report summary
    print("=" * 70)
    print("STEP 6: SUMMARY REPORT")
    print("=" * 70)

    print(f"Total lemmas downloaded: {len(all_lemmas):,}")
    print(f"Unique synsets covered: {len(synset_lookup):,}")
    print(f"Overlap with concept map: {len(overlap):,}")
    print(f"Pickle file size: {pkl_size:,} bytes")

    print(f"\n10 sample entries (synset_id -> Ancient Greek lemmas):")
    for i, (synset_id, lemmas) in enumerate(sorted(synset_lookup.items())[:10]):
        print(f"  {synset_id}: {', '.join(lemmas[:5])}{'...' if len(lemmas) > 5 else ''}")

    print()
    end_time = datetime.now()
    duration = end_time - start_time
    print(f"Duration: {duration}")
    print(f"End: {end_time.isoformat()}")

if __name__ == "__main__":
    main()
