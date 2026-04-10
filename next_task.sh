cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "========================================================================"
echo "TASK: DOWNLOAD PWN 2.1 AND BUILD IWN -> OEWN BRIDGE"
echo "========================================================================"
echo ""
echo "PROBLEM: IWN Sanskrit uses PWN 2.1 offsets, but we need OEWN offsets."
echo "SOLUTION: Download PWN 2.1 from Princeton, verify match, build bridge."
echo ""

# Step 1: Download PWN 2.1 and build the full bridge
echo "STEP 1: Download Princeton WordNet 2.1 and build IWN -> OEWN bridge"
echo "--------------------------------------------------------------------"
python3 scripts/download_pwn_and_build_bridge.py
BRIDGE_EXIT=$?

if [ $BRIDGE_EXIT -ne 0 ]; then
    echo "FATAL: Bridge building failed with exit code $BRIDGE_EXIT"
    exit 1
fi

echo ""
echo "========================================================================"
echo "STEP 2: Parse IWN Sanskrit using new bridge"
echo "========================================================================"
echo ""

python3 scripts/parse_iwn_sanskrit.py
PARSE_EXIT=$?

if [ $PARSE_EXIT -ne 0 ]; then
    echo "FATAL: IWN parsing failed with exit code $PARSE_EXIT"
    exit 1
fi

echo ""
echo "========================================================================"
echo "TASK COMPLETE"
echo "========================================================================"
