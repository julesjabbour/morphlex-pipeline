"""Extract {{root|lang|...}} templates from Wiktextract data.

Primary root source for Hebrew (he), Sanskrit (sa), and Ancient Greek (grc).
Scans raw-wiktextract-data.jsonl.gz for etymology templates with name='root'.

Output: data/wiktextract_roots.pkl
Format: {lang_code: {word: [root1, root2, ...]}}
"""

import gzip
import json
import os
import pickle
from collections import defaultdict
from typing import Any

# Paths
WIKTEXTRACT_PATH = '/mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz'
OUTPUT_PATH = '/mnt/pgdata/morphlex/data/wiktextract_roots.pkl'

# Languages we want root data for
TARGET_LANGS = {'he', 'sa', 'grc'}


def extract_root_from_template(template: dict) -> tuple[str, str] | None:
    """
    Extract language code and root from a {{root|...}} template.

    Template format in Wiktextract:
    {
        "name": "root",
        "args": {
            "1": "en",      # Entry language (the word being defined)
            "2": "he",      # Root language (e.g., Hebrew)
            "3": "כ־ת־ב"    # The root
        }
    }

    Returns: (lang_code, root) or None if not applicable
    """
    if not isinstance(template, dict):
        return None

    if template.get('name') != 'root':
        return None

    args = template.get('args', {})
    if not isinstance(args, dict):
        return None

    # args['2'] is the root language, args['3'] is the root
    root_lang = args.get('2', '')
    root_value = args.get('3', '')

    if root_lang in TARGET_LANGS and root_value:
        return (root_lang, root_value)

    return None


def extract_word_from_entry(entry: dict) -> str | None:
    """Extract the word being defined from a Wiktextract entry."""
    # Primary field is 'word'
    word = entry.get('word', '')
    if word:
        return word
    return None


def process_wiktextract_file() -> dict[str, dict[str, list[str]]]:
    """
    Stream through raw-wiktextract-data.jsonl.gz and extract root templates.

    Returns: {lang_code: {word: [roots]}}
    """
    # Structure: lang -> word -> list of roots
    roots_index: dict[str, dict[str, list[str]]] = {
        lang: defaultdict(list) for lang in TARGET_LANGS
    }

    if not os.path.exists(WIKTEXTRACT_PATH):
        print(f"ERROR: Wiktextract file not found: {WIKTEXTRACT_PATH}")
        return roots_index

    entries_processed = 0
    roots_found = 0

    print(f"Scanning {WIKTEXTRACT_PATH} for {{root|...}} templates...")

    with gzip.open(WIKTEXTRACT_PATH, 'rt', encoding='utf-8') as f:
        for line in f:
            entries_processed += 1

            if entries_processed % 100000 == 0:
                print(f"  Processed {entries_processed:,} entries, found {roots_found:,} roots...")

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            word = extract_word_from_entry(entry)
            if not word:
                continue

            # Check etymology_templates field
            etym_templates = entry.get('etymology_templates', [])
            if not isinstance(etym_templates, list):
                continue

            for template in etym_templates:
                result = extract_root_from_template(template)
                if result:
                    lang_code, root = result
                    if root not in roots_index[lang_code][word]:
                        roots_index[lang_code][word].append(root)
                        roots_found += 1

    # Convert defaultdicts to regular dicts for pickling
    final_index = {
        lang: dict(words) for lang, words in roots_index.items()
    }

    print(f"\nExtraction complete:")
    print(f"  Total entries processed: {entries_processed:,}")
    print(f"  Total roots found: {roots_found:,}")
    for lang in TARGET_LANGS:
        word_count = len(final_index.get(lang, {}))
        print(f"  {lang}: {word_count:,} words with roots")

    return final_index


def save_index(index: dict[str, dict[str, list[str]]]) -> None:
    """Save the roots index to pickle file."""
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, 'wb') as f:
        pickle.dump(index, f)

    print(f"\nSaved to {OUTPUT_PATH}")


def main():
    """Main entry point."""
    print("=" * 60)
    print("Wiktextract Root Template Extraction")
    print("=" * 60)
    print(f"Target languages: {', '.join(sorted(TARGET_LANGS))}")
    print()

    index = process_wiktextract_file()
    save_index(index)

    print("\nDone.")


if __name__ == '__main__':
    main()
