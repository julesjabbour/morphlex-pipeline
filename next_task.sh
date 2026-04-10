cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "========================================================================"
echo "TASK: REPLACE GERMAN ODENET WITH WIKTEXTRACT-BASED PARSER"
echo "========================================================================"
echo ""
echo "PROBLEM: OdeNet only has 19,447 synsets (16.1% overlap) - too small."
echo "         Wiktextract has full German dictionary with English glosses."
echo ""

# Step 1: Download German Wiktextract data
echo "STEP 1: Download German Wiktextract data"
echo "--------------------------------------------------------------------"

# Check if file already exists
if [ -f "/mnt/pgdata/morphlex/data/open_wordnets/kaikki-german.jsonl" ]; then
    echo "  File already exists: kaikki-german.jsonl"
    ls -lh /mnt/pgdata/morphlex/data/open_wordnets/kaikki-german.jsonl
else
    echo "  Downloading kaikki.org-dictionary-German.jsonl.gz..."
    wget -q 'https://kaikki.org/dictionary/German/kaikki.org-dictionary-German.jsonl.gz' \
        -O /mnt/pgdata/morphlex/data/open_wordnets/kaikki-german.jsonl.gz
    WGET_EXIT=$?
    if [ $WGET_EXIT -ne 0 ]; then
        echo "FATAL: wget failed with exit code $WGET_EXIT"
        exit 1
    fi
    echo "  Downloaded successfully"
    ls -lh /mnt/pgdata/morphlex/data/open_wordnets/kaikki-german.jsonl.gz

    echo ""
    echo "  Decompressing..."
    gunzip -f /mnt/pgdata/morphlex/data/open_wordnets/kaikki-german.jsonl.gz
    GUNZIP_EXIT=$?
    if [ $GUNZIP_EXIT -ne 0 ]; then
        echo "FATAL: gunzip failed with exit code $GUNZIP_EXIT"
        exit 1
    fi
    echo "  Decompressed successfully"
    ls -lh /mnt/pgdata/morphlex/data/open_wordnets/kaikki-german.jsonl
fi

# Step 2: Ensure NLTK and WordNet are installed
echo ""
echo "STEP 2: Ensure NLTK WordNet is available"
echo "--------------------------------------------------------------------"
pip install nltk --break-system-packages > /dev/null 2>&1
python3 -c "import nltk; nltk.download('wordnet', quiet=True); nltk.download('omw-1.4', quiet=True)" > /dev/null 2>&1
echo "  NLTK WordNet ready"

# Step 3: Run the German Wiktextract parser
echo ""
echo "STEP 3: Run German Wiktextract parser"
echo "--------------------------------------------------------------------"
echo ""

python3 scripts/parse_german_wiktextract.py
SCRIPT_EXIT=$?

if [ $SCRIPT_EXIT -ne 0 ]; then
    echo ""
    echo "FATAL: Script failed with exit code $SCRIPT_EXIT"
    exit 1
fi

# Step 4: Verify output
echo ""
echo "STEP 4: Verify output"
echo "--------------------------------------------------------------------"

PKL_FILE="/mnt/pgdata/morphlex/data/open_wordnets/german_wiktextract_synset_map.pkl"
if [ ! -f "$PKL_FILE" ]; then
    echo "FATAL: Output pkl file not found: $PKL_FILE"
    exit 1
fi

echo "  Output pkl exists:"
ls -lh "$PKL_FILE"

echo ""
echo "  Report file:"
cat /mnt/pgdata/morphlex/data/open_wordnets/german_wiktextract_report.md

echo ""
echo "========================================================================"
echo "TASK COMPLETE"
echo "========================================================================"
