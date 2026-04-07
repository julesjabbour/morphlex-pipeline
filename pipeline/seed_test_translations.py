#!/usr/bin/env python3
"""
Seed forward_translations.pkl with test Arabic words and their translations.

This creates the minimum viable translation data needed to test the Arabic anchor
pipeline with 10 test words across all 11 languages.

Arabic test words: water, fire, hand, eye, stone, heart, sun, moon, tree, blood
"""

import os
import pickle

OUTPUT_PATH = "/mnt/pgdata/morphlex/data/forward_translations.pkl"

# 10 Arabic test words with translations to all 10 target languages
# Format: {arabic_word: {lang_code: translation}}
TEST_TRANSLATIONS = {
    # water (maa')
    'ماء': {
        'en': 'water',
        'tr': 'su',
        'de': 'Wasser',
        'la': 'aqua',
        'zh': '水',
        'ja': '水',
        'he': 'מים',
        'sa': 'जल',
        'grc': 'ὕδωρ',
        'ine-pro': '*wed-'
    },
    # fire (naar)
    'نار': {
        'en': 'fire',
        'tr': 'ateş',
        'de': 'Feuer',
        'la': 'ignis',
        'zh': '火',
        'ja': '火',
        'he': 'אש',
        'sa': 'अग्नि',
        'grc': 'πῦρ',
        'ine-pro': '*péh₂wr̥'
    },
    # hand (yad)
    'يد': {
        'en': 'hand',
        'tr': 'el',
        'de': 'Hand',
        'la': 'manus',
        'zh': '手',
        'ja': '手',
        'he': 'יד',
        'sa': 'हस्त',
        'grc': 'χείρ',
        'ine-pro': '*ǵʰes-r-'
    },
    # eye ('ayn)
    'عين': {
        'en': 'eye',
        'tr': 'göz',
        'de': 'Auge',
        'la': 'oculus',
        'zh': '眼',
        'ja': '目',
        'he': 'עין',
        'sa': 'अक्षि',
        'grc': 'ὀφθαλμός',
        'ine-pro': '*h₃ekʷ-'
    },
    # stone (hajar)
    'حجر': {
        'en': 'stone',
        'tr': 'taş',
        'de': 'Stein',
        'la': 'lapis',
        'zh': '石',
        'ja': '石',
        'he': 'אבן',
        'sa': 'अश्मन्',
        'grc': 'λίθος',
        'ine-pro': '*h₂éḱmō'
    },
    # heart (qalb)
    'قلب': {
        'en': 'heart',
        'tr': 'kalp',
        'de': 'Herz',
        'la': 'cor',
        'zh': '心',
        'ja': '心',
        'he': 'לב',
        'sa': 'हृदय',
        'grc': 'καρδία',
        'ine-pro': '*ḱḗr'
    },
    # sun (shams)
    'شمس': {
        'en': 'sun',
        'tr': 'güneş',
        'de': 'Sonne',
        'la': 'sol',
        'zh': '太阳',
        'ja': '太陽',
        'he': 'שמש',
        'sa': 'सूर्य',
        'grc': 'ἥλιος',
        'ine-pro': '*sóh₂wl̥'
    },
    # moon (qamar)
    'قمر': {
        'en': 'moon',
        'tr': 'ay',
        'de': 'Mond',
        'la': 'luna',
        'zh': '月',
        'ja': '月',
        'he': 'ירח',
        'sa': 'चन्द्र',
        'grc': 'σελήνη',
        'ine-pro': '*mḗh₁n̥s'
    },
    # tree (shajara)
    'شجرة': {
        'en': 'tree',
        'tr': 'ağaç',
        'de': 'Baum',
        'la': 'arbor',
        'zh': '树',
        'ja': '木',
        'he': 'עץ',
        'sa': 'वृक्ष',
        'grc': 'δένδρον',
        'ine-pro': '*dóru'
    },
    # blood (dam)
    'دم': {
        'en': 'blood',
        'tr': 'kan',
        'de': 'Blut',
        'la': 'sanguis',
        'zh': '血',
        'ja': '血',
        'he': 'דם',
        'sa': 'रक्त',
        'grc': 'αἷμα',
        'ine-pro': '*h₁ésh₂r̥'
    }
}


def seed_translations():
    """Create forward_translations.pkl with test Arabic words."""
    print("=== SEEDING FORWARD TRANSLATIONS (Arabic Anchor Test Data) ===")
    print(f"Output: {OUTPUT_PATH}")
    print(f"Arabic words: {len(TEST_TRANSLATIONS)}")
    print()

    # Show what we're seeding
    for ar_word, trans in TEST_TRANSLATIONS.items():
        en_word = trans.get('en', '?')
        lang_count = len(trans)
        print(f"  {ar_word} ({en_word}): {lang_count} translations")

    # Ensure directory exists
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    # Save pickle
    with open(OUTPUT_PATH, 'wb') as f:
        pickle.dump(TEST_TRANSLATIONS, f)

    file_size = os.path.getsize(OUTPUT_PATH)
    print(f"\nSaved {file_size} bytes to {OUTPUT_PATH}")

    # Verify
    with open(OUTPUT_PATH, 'rb') as f:
        loaded = pickle.load(f)
    print(f"Verified: {len(loaded)} Arabic words loaded back")

    return TEST_TRANSLATIONS


if __name__ == '__main__':
    seed_translations()
