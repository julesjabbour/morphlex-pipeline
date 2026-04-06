"""Pipeline Orchestrator for dispatching morphological analysis across multiple languages."""

import logging
import os
import pickle
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

# Path to forward translations index
FORWARD_TRANSLATIONS_PATH = '/mnt/pgdata/morphlex/data/forward_translations.pkl'


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

        # Languages that need English→native translation before calling adapter
        self.needs_translation = {'he', 'sa', 'grc'}

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

    def _translate_word(self, english_word: str, target_lang: str) -> Optional[str]:
        """Translate English word to target language using forward_translations.pkl."""
        translations = self._load_forward_translations()
        word_lower = english_word.lower().strip()
        word_trans = translations.get(word_lower, {})
        return word_trans.get(target_lang)

    def analyze(self, word: str, language: str) -> list[dict]:
        """
        Analyze a word using the appropriate language adapter.

        For languages that need native script input (he, sa, grc), the English word
        is first translated to the target language using forward_translations.pkl.

        Args:
            word: The word to analyze (English for most adapters)
            language: Language code ('ar', 'tr', 'de', 'en', 'la', 'zh', 'he', 'sa', 'grc', 'ja', 'ine-pro')

        Returns:
            List of analysis result dicts
        """
        if language not in self.adapters:
            logger.error(f"Unsupported language code: {language}")
            return []

        adapter = self.adapters[language]

        # For he, sa, grc: translate English→native script first
        word_to_analyze = word
        if language in self.needs_translation:
            translated = self._translate_word(word, language)
            if translated:
                word_to_analyze = translated
            else:
                # No translation found - skip this word for this language
                return []

        try:
            results = adapter(word_to_analyze)
            return results if results else []
        except Exception as e:
            logger.error(f"Error analyzing '{word_to_analyze}' ({language}): {e}")
            return []

    def batch_analyze(self, word_list: list[tuple[str, str]]) -> list[dict]:
        """
        Analyze multiple words across different languages.

        Args:
            word_list: List of (word, language_code) tuples

        Returns:
            Flat list of all analysis results
        """
        all_results = []
        for word, language in word_list:
            try:
                results = self.analyze(word, language)
                all_results.extend(results)
            except Exception as e:
                logger.error(f"Error in batch processing '{word}' ({language}): {e}")
                continue
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
                    stem, pattern, pos, morphological_features, derivation_type,
                    compound_components, source_tool, confidence
                ) VALUES (
                    %(language_code)s, %(word_native)s, %(word_translit)s, %(lemma)s, %(root)s,
                    %(stem)s, %(pattern)s, %(pos)s, %(morphological_features)s, %(derivation_type)s,
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
