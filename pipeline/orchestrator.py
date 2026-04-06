"""Pipeline Orchestrator for dispatching morphological analysis across multiple languages."""

import logging
from typing import Any

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
        }

    def analyze(self, word: str, language: str) -> list[dict]:
        """
        Analyze a word using the appropriate language adapter.

        Args:
            word: The word to analyze
            language: Language code ('ar', 'tr', 'de', 'en', 'la', 'zh')

        Returns:
            List of analysis result dicts
        """
        if language not in self.adapters:
            logger.error(f"Unsupported language code: {language}")
            return []

        adapter = self.adapters[language]
        try:
            results = adapter(word)
            return results if results else []
        except Exception as e:
            logger.error(f"Error analyzing '{word}' ({language}): {e}")
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
