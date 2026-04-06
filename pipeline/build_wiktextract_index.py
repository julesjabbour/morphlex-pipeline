"""Build precomputed wiktextract reverse lookup index.

ONE-TIME script that streams the 2.4GB raw-wiktextract-data.jsonl.gz
and builds a reverse lookup index: {lang_code: {foreign_word: [english_concepts]}}

This eliminates the need to load the entire file on every analyzer call.
"""

import gzip
import json
import pickle
import sys
from pathlib import Path


DEFAULT_TARGET_LANGS = ['ar', 'he', 'ja', 'zh', 'de', 'tr', 'sa', 'la', 'grc', 'ine-pro']


def build_index(
    input_path: str,
    output_path: str,
    target_langs: list[str] = None
) -> dict:
    """
    Stream wiktextract data and build reverse lookup index.

    Args:
        input_path: Path to raw-wiktextract-data.jsonl.gz
        output_path: Path to save pickle index
        target_langs: List of language codes to include

    Returns:
        Stats dict with counts
    """
    if target_langs is None:
        target_langs = DEFAULT_TARGET_LANGS

    # Structure: {lang_code: {foreign_word: [english_concepts]}}
    index = {lang: {} for lang in target_langs}

    entry_count = 0
    translation_count = 0

    print(f"Streaming {input_path}...")
    print(f"Target languages: {target_langs}")

    with gzip.open(input_path, 'rt', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if line_num % 100000 == 0:
                print(f"  Processed {line_num:,} lines, {entry_count:,} English entries...")

            try:
                entry = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            # Only process English entries
            if entry.get('lang_code') != 'en':
                continue

            word = entry.get('word', '').strip()
            if not word:
                continue

            entry_count += 1

            # Extract translations
            translations = entry.get('translations', [])
            if not translations:
                continue

            pos = entry.get('pos', '')

            # Extract definitions from senses[].glosses[]
            definitions = []
            for sense in entry.get('senses', []):
                glosses = sense.get('glosses', [])
                definitions.extend(glosses)

            # Extract etymology
            etymology = []
            for tmpl in entry.get('etymology_templates', []):
                etym_info = {
                    'name': tmpl.get('name', ''),
                    'args': tmpl.get('args', {})
                }
                if etym_info['name']:
                    etymology.append(etym_info)

            etymology_text = entry.get('etymology_text', '')

            # Build english concept data
            english_concept = {
                'english_word': word,
                'pos': pos,
                'definitions': definitions[:5],  # Limit to first 5
                'etymology': etymology[:10],  # Limit etymology templates
                'etymology_text': etymology_text[:2000] if etymology_text else ''  # Limit text
            }

            # Process translations for target languages
            for trans in translations:
                lang_code = trans.get('code', '')
                trans_word = trans.get('word', '')

                if lang_code not in target_langs or not trans_word:
                    continue

                # Add to reverse index
                if trans_word not in index[lang_code]:
                    index[lang_code][trans_word] = []

                # Avoid duplicate concepts for same word
                existing_words = [c['english_word'] for c in index[lang_code][trans_word]]
                if word not in existing_words:
                    index[lang_code][trans_word].append(english_concept)
                    translation_count += 1

    # Save as pickle
    print(f"\nSaving index to {output_path}...")
    with open(output_path, 'wb') as f:
        pickle.dump(index, f, protocol=pickle.HIGHEST_PROTOCOL)

    # Get file size
    output_size = Path(output_path).stat().st_size / (1024 * 1024)

    stats = {
        'total_english_entries': entry_count,
        'total_translations': translation_count,
        'index_size_mb': round(output_size, 2),
        'words_per_lang': {lang: len(words) for lang, words in index.items()}
    }

    return stats


if __name__ == '__main__':
    input_path = '/mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz'
    output_path = '/mnt/pgdata/morphlex/data/wiktextract_index.pkl'

    if len(sys.argv) > 1:
        input_path = sys.argv[1]
    if len(sys.argv) > 2:
        output_path = sys.argv[2]

    print("=== BUILDING WIKTEXTRACT INDEX ===")
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print()

    stats = build_index(input_path, output_path)

    print()
    print("=== INDEX BUILD COMPLETE ===")
    print(f"English entries processed: {stats['total_english_entries']:,}")
    print(f"Total translations indexed: {stats['total_translations']:,}")
    print(f"Index file size: {stats['index_size_mb']} MB")
    print()
    print("Words per language:")
    for lang, count in sorted(stats['words_per_lang'].items(), key=lambda x: -x[1]):
        print(f"  {lang}: {count:,} words")
