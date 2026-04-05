"""Translation Alignment Layer for cross-language lexicon translation."""

import logging
import time
from typing import Any

import psycopg2

from google.cloud import translate_v2 as translate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# All pipeline languages
PIPELINE_LANGUAGES = ['ar', 'tr', 'de', 'en', 'la', 'zh', 'fr', 'he', 'el', 'sa']

# Maximum strings per API call
BATCH_SIZE = 128

# Track character count for cost estimation
_total_characters_translated = 0


def get_character_count() -> int:
    """Return the total number of characters sent to the translation API."""
    return _total_characters_translated


def translate_batch(texts: list[str], target_lang: str) -> list[str]:
    """
    Translate a batch of texts to the target language using Google Cloud Translate.

    Args:
        texts: List of strings to translate
        target_lang: Target language code (e.g., 'en', 'ar', 'de')

    Returns:
        List of translated strings in the same order as input
    """
    global _total_characters_translated

    if not texts:
        return []

    client = translate.Client()
    translations = []

    # Track characters for cost
    char_count = sum(len(t) for t in texts)
    _total_characters_translated += char_count

    # Exponential backoff for rate limits
    max_retries = 5
    base_delay = 1.0

    for attempt in range(max_retries):
        try:
            results = client.translate(texts, target_language=target_lang)
            # Results are returned in same order as input
            for result in results:
                translations.append(result['translatedText'])
            return translations
        except Exception as e:
            error_str = str(e).lower()
            if 'rate' in error_str or 'quota' in error_str or '429' in str(e):
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Rate limit hit, retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                logger.error(f"Translation API error: {e}")
                raise

    raise Exception(f"Failed to translate after {max_retries} retries due to rate limiting")


def _get_existing_translations(cur, entry_ids: list[int], target_lang: str) -> set[int]:
    """Check which entry IDs already have translations for the target language."""
    if not entry_ids:
        return set()

    placeholders = ','.join(['%s'] * len(entry_ids))
    cur.execute(
        f"""SELECT source_entry_id FROM lexicon.translations
            WHERE source_entry_id IN ({placeholders}) AND target_language = %s""",
        entry_ids + [target_lang]
    )
    return {row[0] for row in cur.fetchall()}


def translate_entries(entries: list[dict], target_languages: list[str], db_config: dict) -> None:
    """
    Translate lexicon entries to target languages and store in database.

    Args:
        entries: List of dicts with 'id', 'word_native', 'language_code' keys
        target_languages: List of language codes to translate into
        db_config: Database connection config with host, dbname, user, password

    Each entry is translated to all target languages except its own language.
    Results are inserted into lexicon.translations table.
    """
    global _total_characters_translated

    if not entries:
        logger.warning("No entries to translate")
        return

    conn = None
    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()

        total_inserted = 0
        total_skipped = 0

        for target_lang in target_languages:
            # Filter entries that need translation to this target language
            # Skip entries that are already in the target language
            entries_to_translate = [
                e for e in entries if e.get('language_code') != target_lang
            ]

            if not entries_to_translate:
                continue

            # Check cache - which translations already exist
            entry_ids = [e['id'] for e in entries_to_translate]
            existing = _get_existing_translations(cur, entry_ids, target_lang)

            # Filter out already-translated entries
            entries_needing_translation = [
                e for e in entries_to_translate if e['id'] not in existing
            ]

            skipped = len(entries_to_translate) - len(entries_needing_translation)
            total_skipped += skipped

            if skipped > 0:
                logger.info(f"Skipped {skipped} existing translations for {target_lang}")

            if not entries_needing_translation:
                continue

            # Batch translations in groups of BATCH_SIZE
            for i in range(0, len(entries_needing_translation), BATCH_SIZE):
                batch = entries_needing_translation[i:i + BATCH_SIZE]
                texts = [e['word_native'] for e in batch]

                try:
                    translations = translate_batch(texts, target_lang)
                except Exception as e:
                    logger.error(f"Failed to translate batch to {target_lang}: {e}")
                    continue

                # Insert translations into database
                insert_sql = """
                    INSERT INTO lexicon.translations
                    (source_entry_id, target_language, translation, translation_source, confidence)
                    VALUES (%s, %s, %s, %s, %s)
                """

                records = []
                for entry, translation in zip(batch, translations):
                    records.append((
                        entry['id'],
                        target_lang,
                        translation,
                        'google_translate',
                        0.8
                    ))

                cur.executemany(insert_sql, records)
                conn.commit()
                total_inserted += len(records)

                logger.info(
                    f"Inserted {len(records)} translations to {target_lang} "
                    f"(total chars: {_total_characters_translated})"
                )

        logger.info(
            f"Translation complete: {total_inserted} inserted, {total_skipped} skipped (cached), "
            f"total characters: {_total_characters_translated}"
        )

    except Exception as e:
        logger.error(f"Translation error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def translate_all_entries(db_config: dict, limit: int = None) -> None:
    """
    Fetch entries from database and translate to all pipeline languages.

    Args:
        db_config: Database connection config
        limit: Optional limit on number of entries to process
    """
    conn = None
    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()

        query = "SELECT id, word_native, language_code FROM lexicon.entries"
        if limit:
            query += f" LIMIT {limit}"

        cur.execute(query)
        entries = [
            {'id': row[0], 'word_native': row[1], 'language_code': row[2]}
            for row in cur.fetchall()
        ]
        conn.close()

        # Translate to all pipeline languages
        translate_entries(entries, PIPELINE_LANGUAGES, db_config)

    except Exception as e:
        logger.error(f"Error fetching entries: {e}")
        raise
    finally:
        if conn:
            conn.close()
