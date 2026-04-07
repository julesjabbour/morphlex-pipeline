CREATE SCHEMA IF NOT EXISTS lexicon;

CREATE TABLE lexicon.entries (
    id SERIAL PRIMARY KEY,
    language_code VARCHAR(10) NOT NULL,
    word_native TEXT NOT NULL,
    word_translit TEXT,
    lemma TEXT,
    root TEXT,
    stem TEXT,
    pattern TEXT,
    pos VARCHAR(20),
    morph_type VARCHAR(20),
    derived_from_root TEXT,
    derivation_mode VARCHAR(50),
    morphological_features JSONB,
    derivation_type VARCHAR(50),
    compound_components TEXT[],
    source_tool VARCHAR(50),
    confidence FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE lexicon.translations (
    id SERIAL PRIMARY KEY,
    source_entry_id INT REFERENCES lexicon.entries(id),
    target_language VARCHAR(10),
    translation TEXT,
    translation_source VARCHAR(50),
    confidence FLOAT
);

CREATE TABLE lexicon.etymology (
    id SERIAL PRIMARY KEY,
    entry_id INT REFERENCES lexicon.entries(id),
    relation_type VARCHAR(50),
    related_word TEXT,
    related_language VARCHAR(10),
    source VARCHAR(50)
);

CREATE INDEX idx_entries_lang_word ON lexicon.entries(language_code, word_native);
CREATE INDEX idx_entries_root ON lexicon.entries(root);
CREATE INDEX idx_translations_source ON lexicon.translations(source_entry_id);
CREATE INDEX idx_etymology_entry ON lexicon.etymology(entry_id);
