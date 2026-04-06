"""Japanese morphological analyzer using fugashi (MeCab wrapper)."""

from fugashi import Tagger

# Initialize the tagger once at module level
_tagger = Tagger()

# POS tag mapping from MeCab Japanese POS to English
_POS_MAP = {
    '名詞': 'noun',
    '動詞': 'verb',
    '形容詞': 'adjective',
    '副詞': 'adverb',
    '助詞': 'particle',
    '助動詞': 'auxiliary_verb',
    '接続詞': 'conjunction',
    '感動詞': 'interjection',
    '連体詞': 'adnominal',
    '接頭詞': 'prefix',
    '接尾詞': 'suffix',
    '記号': 'symbol',
    'フィラー': 'filler',
}


def analyze_japanese(word: str) -> list[dict]:
    """
    Analyze a Japanese word and return morphological analyses.

    Uses fugashi (MeCab wrapper) for morphological analysis.
    Handles compound words by returning each morpheme as a separate result.

    Args:
        word: Japanese word to analyze

    Returns:
        List of dicts matching the lexicon.entries schema columns
    """
    results = []

    if not word or not word.strip():
        return results

    try:
        # Parse the word with MeCab
        parsed = _tagger(word)

        for node in parsed:
            # Skip empty nodes
            if not node.surface:
                continue

            # Extract lemma (dictionary form)
            lemma = ''
            if hasattr(node.feature, 'lemma') and node.feature.lemma:
                lemma = node.feature.lemma
            else:
                # Fallback to surface form if lemma not available
                lemma = node.surface

            # Extract POS
            pos_raw = ''
            pos = ''
            if hasattr(node.feature, 'pos1') and node.feature.pos1:
                pos_raw = node.feature.pos1
                pos = _POS_MAP.get(pos_raw, pos_raw)

            # Extract reading (kana or pronunciation)
            reading = ''
            if hasattr(node.feature, 'kana') and node.feature.kana:
                reading = node.feature.kana
            elif hasattr(node.feature, 'pron') and node.feature.pron:
                reading = node.feature.pron

            # Build morphological features
            features = {}

            # Add detailed POS info if available
            if hasattr(node.feature, 'pos2') and node.feature.pos2:
                features['pos_detail1'] = node.feature.pos2
            if hasattr(node.feature, 'pos3') and node.feature.pos3:
                features['pos_detail2'] = node.feature.pos3
            if hasattr(node.feature, 'pos4') and node.feature.pos4:
                features['pos_detail3'] = node.feature.pos4

            # Add conjugation info if available
            if hasattr(node.feature, 'cType') and node.feature.cType:
                features['conjugation_type'] = node.feature.cType
            if hasattr(node.feature, 'cForm') and node.feature.cForm:
                features['conjugation_form'] = node.feature.cForm

            # Add reading to features
            if reading:
                features['reading'] = reading

            result = {
                'language_code': 'ja',
                'word_native': node.surface,
                'lemma': lemma,
                'pos': pos,
                'morphological_features': features if features else None,
                'source_tool': 'mecab',
                'confidence': 1.0,
            }

            results.append(result)

    except Exception as e:
        # Log error but don't crash - return empty results
        import logging
        logging.error(f"Error analyzing Japanese word '{word}': {e}")

    return results
