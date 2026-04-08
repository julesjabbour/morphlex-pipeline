#!/usr/bin/env python3
"""
Hardcoding Audit Test - Tests 270 NEW words through all language adapters.

These words have NEVER appeared in any previous test. If any adapter returns
correct results for original test words but fails on these, it's hardcoded.
"""

import sys
import traceback
from datetime import datetime

# Add parent directory for imports
sys.path.insert(0, '/mnt/pgdata/morphlex')

from analyzers.arabic import analyze_arabic
from analyzers.turkish import analyze_turkish
from analyzers.german import analyze_german
from analyzers.english import analyze_english
from analyzers.latin import analyze_latin
from analyzers.chinese import analyze_chinese
from analyzers.japanese import analyze_japanese
from analyzers.hebrew import analyze_hebrew
from analyzers.greek import analyze_greek


# Test words - NEVER seen before in any test
ARABIC_WORDS = [
    'ثعلب', 'جبل', 'نهر', 'سحاب', 'قمر', 'ذهب', 'فضة', 'حديد', 'نحاس', 'رمل',
    'تراب', 'ريح', 'برق', 'رعد', 'ثلج', 'عسل', 'لبن', 'زيت', 'خبز', 'ملح',
    'سكين', 'حبل', 'جسر', 'سقف', 'باب', 'نافذة', 'درج', 'حائط', 'أرض', 'سماء'
]

TURKISH_WORDS = [
    'tilki', 'dağ', 'nehir', 'bulut', 'altın', 'gümüş', 'demir', 'bakır', 'kum', 'toprak',
    'rüzgar', 'yıldırım', 'gök gürültüsü', 'kar', 'bal', 'süt', 'yağ', 'ekmek', 'tuz', 'bıçak',
    'ip', 'köprü', 'çatı', 'kapı', 'pencere', 'merdiven', 'duvar', 'yer', 'gök', 'deniz'
]

GERMAN_WORDS = [
    'Fuchsbau', 'Bergwerk', 'Flussbett', 'Wolkenkratzer', 'Mondschein', 'Goldschmied',
    'Silbermine', 'Eisenbahn', 'Kupferdraht', 'Sandburg', 'Erdreich', 'Windmühle',
    'Blitzableiter', 'Donnerschlag', 'Schneeball', 'Honigbiene', 'Milchstraße', 'Ölgemälde',
    'Brotmesser', 'Salzwasser', 'Taschenmesser', 'Seilbahn', 'Brückenbau', 'Dachziegel',
    'Türklinke', 'Fensterladen', 'Treppenhaus', 'Mauerwerk', 'Erdbeben', 'Himmelszelt'
]

ENGLISH_WORDS = [
    'butterfly', 'earthquake', 'constellation', 'microscope', 'refrigerator', 'civilization',
    'ambassador', 'archipelago', 'bibliography', 'catastrophe', 'encyclopedia', 'fundamental',
    'hemisphere', 'illumination', 'jurisdiction', 'kaleidoscope', 'labyrinth', 'metamorphosis',
    'nomenclature', 'observatory', 'paradox', 'quarantine', 'resurrection', 'surveillance',
    'thermometer', 'undergraduate', 'ventilation', 'waterfall', 'xylophone', 'zoology'
]

LATIN_WORDS = [
    'aquila', 'bellum', 'caelum', 'deus', 'equus', 'flumen', 'gladius', 'homo', 'ignis', 'iudex',
    'lux', 'mare', 'nox', 'orbis', 'pax', 'rex', 'sal', 'tempus', 'urbs', 'ventus',
    'vita', 'arma', 'caput', 'dens', 'ferrum', 'gens', 'hasta', 'iter', 'lex', 'mons'
]

CHINESE_WORDS = [
    '蝴蝶', '地震', '星座', '显微镜', '冰箱', '文明', '大使', '群岛', '书目', '灾难',
    '百科全书', '基本', '半球', '照明', '管辖', '万花筒', '迷宫', '变态', '命名', '天文台',
    '矛盾', '隔离', '复活', '监视', '温度计', '本科生', '通风', '瀑布', '木琴', '动物学'
]

JAPANESE_WORDS = [
    '蝶', '地震', '星座', '顕微鏡', '冷蔵庫', '文明', '大使', '群島', '参考文献', '大災害',
    '百科事典', '基本', '半球', '照明', '管轄', '万華鏡', '迷路', '変態', '命名法', '天文台',
    '逆説', '検疫', '復活', '監視', '温度計', '学部生', '換気', '滝', '木琴', '動物学'
]

GREEK_WORDS = [
    'λόγος', 'ψυχή', 'σοφία', 'ἀρετή', 'πόλις', 'θάλασσα', 'ἥλιος', 'σελήνη', 'ἄνεμος', 'πῦρ',
    'γῆ', 'ἀήρ', 'ζῷον', 'φυτόν', 'λίθος', 'ξύλον', 'σίδηρος', 'χρυσός', 'ἄργυρος', 'χαλκός',
    'ἄρτος', 'οἶνος', 'μέλι', 'γάλα', 'ἅλς', 'ποταμός', 'ὄρος', 'νῆσος', 'ὁδός', 'ναῦς'
]

HEBREW_WORDS = [
    'פרפר', 'רעידת אדמה', 'כוכב', 'מיקרוסקופ', 'מקרר', 'תרבות', 'שגריר', 'ארכיפלג',
    'ביבליוגרפיה', 'אסון', 'אנציקלופדיה', 'יסודי', 'חצי כדור', 'תאורה', 'סמכות', 'קליידוסקופ',
    'מבוך', 'מטמורפוזה', 'מונחון', 'מצפה כוכבים', 'פרדוקס', 'הסגר', 'תחייה', 'מעקב',
    'מדחום', 'סטודנט', 'אוורור', 'מפל מים', 'קסילופון', 'זואולוגיה'
]


def test_adapter(name: str, adapter_func, words: list, tool_name: str) -> dict:
    """Test an adapter with a list of words."""
    non_empty = 0
    empty = 0
    crashed = []
    results_detail = []

    for word in words:
        try:
            results = adapter_func(word)
            if results and any(r.get('root') for r in results):
                non_empty += 1
                root = next((r.get('root') for r in results if r.get('root')), '')
                results_detail.append((word, root, 'OK'))
            else:
                empty += 1
                results_detail.append((word, '', 'EMPTY'))
        except Exception as e:
            crashed.append((word, str(e)))
            results_detail.append((word, '', f'CRASH: {e}'))

    return {
        'name': name,
        'tool': tool_name,
        'total': len(words),
        'non_empty': non_empty,
        'empty': empty,
        'crashed': crashed,
        'details': results_detail
    }


def main():
    print("=== HARDCODING AUDIT TEST ===")
    print(f"Start: {datetime.now().isoformat()}")
    print()

    # Define test cases: (name, adapter, words, tool)
    test_cases = [
        ('Arabic', analyze_arabic, ARABIC_WORDS, 'CAMeL'),
        ('Turkish', analyze_turkish, TURKISH_WORDS, 'Zeyrek'),
        ('German', analyze_german, GERMAN_WORDS, 'CharSplit'),
        ('English', analyze_english, ENGLISH_WORDS, 'spaCy'),
        ('Latin', analyze_latin, LATIN_WORDS, 'Morpheus'),
        ('Chinese', analyze_chinese, CHINESE_WORDS, 'CEDICT'),
        ('Japanese', analyze_japanese, JAPANESE_WORDS, 'MeCab'),
        ('Greek', analyze_greek, GREEK_WORDS, 'Morpheus'),
        ('Hebrew', analyze_hebrew, HEBREW_WORDS, 'Hspell'),
    ]

    all_results = []
    total_non_empty = 0
    total_empty = 0
    total_crashed = 0

    for name, adapter, words, tool in test_cases:
        print(f"--- {name} ({len(words)} words, {tool}) ---")
        result = test_adapter(name, adapter, words, tool)
        all_results.append(result)

        # Print first 5 results as sample
        for word, root, status in result['details'][:5]:
            if root:
                print(f"  {word}: root='{root}' [{status}]")
            else:
                print(f"  {word}: [{status}]")
        if len(result['details']) > 5:
            print(f"  ... ({len(result['details']) - 5} more)")

        print(f"  Summary: {result['non_empty']} non-empty, {result['empty']} empty, {len(result['crashed'])} crashed")
        print()

        total_non_empty += result['non_empty']
        total_empty += result['empty']
        total_crashed += len(result['crashed'])

    # Print crashes if any
    has_crashes = any(r['crashed'] for r in all_results)
    if has_crashes:
        print("=== CRASHES ===")
        for r in all_results:
            if r['crashed']:
                print(f"{r['name']}:")
                for word, error in r['crashed']:
                    print(f"  {word}: {error[:100]}")
        print()

    # Final summary
    print("=== AUDIT SUMMARY ===")
    print(f"Languages tested: {len(test_cases)}")
    print(f"Total words: {sum(len(words) for _, _, words, _ in test_cases)}")
    print(f"Non-empty roots: {total_non_empty}")
    print(f"Empty roots: {total_empty}")
    print(f"Crashes: {total_crashed}")
    print()

    # Per-language summary table
    print("Per-language results:")
    for r in all_results:
        pct = (r['non_empty'] / r['total'] * 100) if r['total'] > 0 else 0
        status = "OK" if r['non_empty'] > 0 else "SUSPICIOUS"
        print(f"  {r['name']:10} ({r['tool']:10}): {r['non_empty']:2}/{r['total']} ({pct:5.1f}%) [{status}]")

    print()
    print(f"End: {datetime.now().isoformat()}")
    print("=== AUDIT COMPLETE ===")


if __name__ == '__main__':
    main()
