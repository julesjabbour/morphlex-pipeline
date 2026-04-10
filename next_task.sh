cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "========================================================================"
echo "TASK: FIX SANSKRIT SYNSET MAPPING USING NLTK WORDNET GLOSS MATCHING"
echo "========================================================================"
echo ""
echo "PROBLEM: IWN Sanskrit uses PWN 2.1 offsets. Princeton 2.1->3.0 mapping"
echo "         files weren't found at expected paths (only 50 mappings built)."
echo ""
echo "SOLUTION: Use NLTK WordNet (which IS PWN 3.0) to match English words"
echo "          and glosses directly, bypassing the broken 2.1->3.0 mapping."
echo ""

# Step 1: Install NLTK
echo "STEP 1: Install NLTK"
echo "--------------------------------------------------------------------"
pip install nltk --break-system-packages > /dev/null 2>&1
INSTALL_EXIT=$?
if [ $INSTALL_EXIT -ne 0 ]; then
    echo "FATAL: NLTK install failed with exit code $INSTALL_EXIT"
    exit 1
fi
echo "  NLTK installed"

# Step 2: Download WordNet data (silently)
echo ""
echo "STEP 2: Download WordNet data"
echo "--------------------------------------------------------------------"
python3 -c "import nltk; nltk.download('wordnet', quiet=True); nltk.download('omw-1.4', quiet=True)" > /dev/null 2>&1
DOWNLOAD_EXIT=$?
if [ $DOWNLOAD_EXIT -ne 0 ]; then
    echo "FATAL: WordNet download failed with exit code $DOWNLOAD_EXIT"
    exit 1
fi
echo "  WordNet data downloaded"

# Step 3: Run the fix script
echo ""
echo "STEP 3: Run Sanskrit NLTK gloss matching"
echo "--------------------------------------------------------------------"
echo ""

python3 scripts/fix_sanskrit_nltk_gloss.py
SCRIPT_EXIT=$?

if [ $SCRIPT_EXIT -ne 0 ]; then
    echo "FATAL: Script failed with exit code $SCRIPT_EXIT"
    exit 1
fi

echo ""
echo "========================================================================"
echo "TASK COMPLETE"
echo "========================================================================"
