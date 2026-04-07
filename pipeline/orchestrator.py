"""Pipeline Orchestrator for dispatching morphological analysis across multiple languages."""

import json
import logging
import os
import pickle
import time
import unicodedata
import urllib.request
import urllib.error
from datetime import datetime
from typing import Any, Optional

import psycopg2
from psycopg2.extras import Json

from analyzers.arabic import analyze_arabic
from analyzers.turkish import analyze_turkish
from analyzers.german import analyze_german
from analyzers.english import analyze_english
from analyzers.latin import analyze_latin
from analyzers.chinese import analyze_chinese
from analyzers.greek import analyze_greek
from analyzers.japanese import analyze_japanese
from analyzers.hebrew import analyze_hebrew
from analyzers.sanskrit import analyze_sanskrit
from analyzers.pie import analyze_pie

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Slack webhook URL path
WEBHOOK_URL_PATH = '/mnt/pgdata/morphlex/.webhook_url'


def post_slack_progress(message: str) -> bool:
    """
    Post a progress update to Slack.

    Problem 7: Tasks >60s need progress updates every 2 minutes.

    Args:
        message: Progress message to post

    Returns:
        True if posted successfully, False otherwise
    """
    try:
        if not os.path.exists(WEBHOOK_URL_PATH):
            logger.warning(f"Webhook URL file not found: {WEBHOOK_URL_PATH}")
            return False

        with open(WEBHOOK_URL_PATH, 'r') as f:
            webhook_url = f.read().strip()

        if not webhook_url or not webhook_url.startswith('https://'):
            logger.warning("Invalid webhook URL")
            return False

        data = json.dumps({'text': message}).encode('utf-8')
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        urllib.request.urlopen(req, timeout=30)
        return True
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        logger.error(f"Slack post failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Slack post error: {e}")
        return False

# Path to forward translations index
FORWARD_TRANSLATIONS_PATH = '/mnt/pgdata/morphlex/data/forward_translations.pkl'


def strip_diacritics(text: str) -> str:
    """Remove diacritics/macrons from text (e.g., māter → mater)."""
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')


def consolidate_arabic_duplicates(results: list[dict]) -> list[dict]:
    """
    Problem 4: Consolidate Arabic duplicate rows from CAMeL diacritization.

    CAMeL produces 7+ analyses per word with different diacritization readings.
    This consolidates them by unique (lemma, root, pos) combination.

    Args:
        results: List of Arabic analysis results

    Returns:
        Consolidated list with duplicates merged
    """
    if not results:
        return results

    # Group by (lemma, root, pos)
    groups = {}
    for r in results:
        key = (r.get('lemma', ''), r.get('root', ''), r.get('pos', ''))
        if key not in groups:
            groups[key] = {
                'result': r.copy(),
                'diac_forms': [],
                'count': 0
            }
        # Collect diacritization forms
        diac = r.get('_diac_form', '')
        if diac and diac not in groups[key]['diac_forms']:
            groups[key]['diac_forms'].append(diac)
        groups[key]['count'] += 1

    # Build consolidated results
    consolidated = []
    for key, group in groups.items():
        result = group['result']
        # Remove internal field
        result.pop('_diac_form', None)
        # Add diacritization variants as a feature
        if group['diac_forms']:
            if 'morphological_features' not in result or result['morphological_features'] is None:
                result['morphological_features'] = {}
            result['morphological_features']['diac_variants'] = group['diac_forms']
            result['morphological_features']['variant_count'] = group['count']
        # Adjust confidence based on consolidation
        result['confidence'] = 1.0 / len(groups)
        consolidated.append(result)

    return consolidated


class PipelineOrchestrator:
    """Orchestrates morphological analysis across multiple language adapters."""

    def __init__(self):
        """Initialize the orchestrator with language code to adapter mapping."""
        self.adapters: dict[str, Any] = {
            'ar': analyze_arabic,
            'tr': analyze_turkish,
            'de': analyze_german,
            'en': analyze_english,
            'la': analyze_latin,
            'zh': analyze_chinese,
            'grc': analyze_greek,
            'ja': analyze_japanese,
            'he': analyze_hebrew,
            'sa': analyze_sanskrit,
            'ine-pro': analyze_pie,
        }

        # Languages that need Arabic→native translation before calling adapter
        # ALL non-Arabic languages must be translated - Arabic is the anchor language
        self.needs_translation = {'tr', 'de', 'en', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro'}

        # Forward translations cache
        self._forward_translations: Optional[dict] = None

    def _load_forward_translations(self) -> dict:
        """Load forward translations index on first use."""
        if self._forward_translations is None:
            if os.path.exists(FORWARD_TRANSLATIONS_PATH):
                with open(FORWARD_TRANSLATIONS_PATH, 'rb') as f:
                    self._forward_translations = pickle.load(f)
            else:
                logger.warning(f"Forward translations not found: {FORWARD_TRANSLATIONS_PATH}")
                self._forward_translations = {}
        return self._forward_translations

    def _translate_word(self, arabic_word: str, target_lang: str) -> Optional[str]:
        """Translate Arabic word to target language using forward_translations.pkl.

        For Arabic anchor mode, the pickle file maps Arabic words to translations
        in all other languages.
        """
        translations = self._load_forward_translations()
        word_normalized = arabic_word.strip()
        word_trans = translations.get(word_normalized, {})
        return word_trans.get(target_lang)

    def analyze(self, word: str, language: str, consolidate_arabic: bool = True) -> list[dict]:
        """
        Analyze a word using the appropriate language adapter.

        For Arabic anchor mode:
        - Arabic (ar) input goes directly to CAMeL
        - All other languages receive translated words from Arabic→X via forward_translations.pkl
        - PIE (ine-pro) uses Arabic→English, then English→PIE lookup

        Args:
            word: The word to analyze (Arabic script for Arabic anchor mode)
            language: Language code ('ar', 'tr', 'de', 'en', 'la', 'zh', 'he', 'sa', 'grc', 'ja', 'ine-pro')
            consolidate_arabic: If True, consolidate Arabic duplicate rows (Problem 4)

        Returns:
            List of analysis result dicts
        """
        if language not in self.adapters:
            logger.error(f"Unsupported language code: {language}")
            return []

        adapter = self.adapters[language]

        # For all non-Arabic languages: translate Arabic→target language first
        word_to_analyze = word
        if language in self.needs_translation:
            # PIE requires two-step: Arabic→English, then English→PIE lookup
            if language == 'ine-pro':
                english_word = self._translate_word(word, 'en')
                if english_word:
                    word_to_analyze = english_word
                else:
                    # No English translation - cannot lookup PIE
                    return []
            else:
                translated = self._translate_word(word, language)
                if translated:
                    word_to_analyze = translated
                    # Latin/Morpheus only accepts ASCII - strip macrons/diacritics
                    if language == 'la':
                        word_to_analyze = strip_diacritics(word_to_analyze)
                else:
                    # No translation found - skip this word for this language
                    return []

        try:
            results = adapter(word_to_analyze)
            results = results if results else []

            # Problem 4: Consolidate Arabic duplicates
            if language == 'ar' and consolidate_arabic and results:
                results = consolidate_arabic_duplicates(results)

            return results
        except Exception as e:
            logger.error(f"Error analyzing '{word_to_analyze}' ({language}): {e}")
            return []

    def batch_analyze(self, word_list: list[tuple[str, str]], post_progress: bool = True) -> list[dict]:
        """
        Analyze multiple words across different languages.

        Problem 7: Posts Slack progress updates every 2 minutes for tasks >60s.

        Args:
            word_list: List of (word, language_code) tuples
            post_progress: If True, post progress updates to Slack

        Returns:
            Flat list of all analysis results
        """
        all_results = []
        total = len(word_list)
        start_time = time.time()
        last_progress_time = start_time
        progress_interval = 120  # 2 minutes

        for i, (word, language) in enumerate(word_list):
            try:
                results = self.analyze(word, language)
                all_results.extend(results)
            except Exception as e:
                logger.error(f"Error in batch processing '{word}' ({language}): {e}")
                continue

            # Problem 7: Progress updates every 2 minutes
            elapsed = time.time() - start_time
            time_since_progress = time.time() - last_progress_time

            if post_progress and elapsed > 60 and time_since_progress >= progress_interval:
                progress_pct = ((i + 1) / total) * 100
                rate = (i + 1) / elapsed
                eta = (total - i - 1) / rate if rate > 0 else 0
                msg = (
                    f"📊 Progress: {i+1}/{total} ({progress_pct:.1f}%) | "
                    f"Results: {len(all_results)} | "
                    f"Rate: {rate:.1f}/s | "
                    f"ETA: {eta/60:.1f}min"
                )
                post_slack_progress(msg)
                last_progress_time = time.time()

        return all_results

    def insert_to_db(self, results: list[dict], db_config: dict) -> None:
        """
        Batch insert analysis results into lexicon.entries table.

        Args:
            results: List of analysis result dicts
            db_config: Database connection config with host, dbname, user, password
        """
        if not results:
            logger.warning("No results to insert")
            return

        conn = None
        try:
            conn = psycopg2.connect(**db_config)
            cur = conn.cursor()

            insert_sql = """
                INSERT INTO lexicon.entries (
                    language_code, word_native, word_translit, lemma, root,
                    stem, pattern, pos, morph_type, derived_from_root, derivation_mode,
                    morphological_features, derivation_type,
                    compound_components, source_tool, confidence
                ) VALUES (
                    %(language_code)s, %(word_native)s, %(word_translit)s, %(lemma)s, %(root)s,
                    %(stem)s, %(pattern)s, %(pos)s, %(morph_type)s, %(derived_from_root)s, %(derivation_mode)s,
                    %(morphological_features)s, %(derivation_type)s,
                    %(compound_components)s, %(source_tool)s, %(confidence)s
                )
            """

            # Prepare records with all required fields
            records = []
            for r in results:
                record = {
                    'language_code': r.get('language_code'),
                    'word_native': r.get('word_native'),
                    'word_translit': r.get('word_translit'),
                    'lemma': r.get('lemma'),
                    'root': r.get('root'),
                    'stem': r.get('stem'),
                    'pattern': r.get('pattern'),
                    'pos': r.get('pos'),
                    'morph_type': r.get('morph_type'),
                    'derived_from_root': r.get('derived_from_root'),
                    'derivation_mode': r.get('derivation_mode'),
                    'morphological_features': Json(r.get('morphological_features')) if r.get('morphological_features') else None,
                    'derivation_type': r.get('derivation_type'),
                    'compound_components': r.get('compound_components'),
                    'source_tool': r.get('source_tool'),
                    'confidence': r.get('confidence'),
                }
                records.append(record)

            cur.executemany(insert_sql, records)
            conn.commit()
            logger.info(f"Inserted {len(records)} records into lexicon.entries")

        except Exception as e:
            logger.error(f"Database insertion error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
