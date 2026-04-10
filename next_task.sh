cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "========================================================================"
echo "TASK: WN PACKAGE API AUDIT + REBUILD PWN30 -> OEWN BRIDGE"
echo "========================================================================"
echo ""

# Step 1: Run the full wn package API audit
echo "STEP 1: WN PACKAGE API AUDIT"
echo "============================"
python3 scripts/wn_api_audit.py
AUDIT_EXIT=$?

if [ $AUDIT_EXIT -ne 0 ]; then
    echo "FATAL: API audit failed with exit code $AUDIT_EXIT"
    exit 1
fi

echo ""
echo "Audit file contents:"
echo "--------------------"
cat /mnt/pgdata/morphlex/data/open_wordnets/wn_api_audit.txt
echo ""
echo ""

# Step 2: Build the PWN 3.0 -> OEWN bridge map using ILI
echo "STEP 2: BUILD BRIDGE MAP"
echo "========================"
python3 scripts/build_pwn30_to_oewn_bridge.py
BRIDGE_EXIT=$?

if [ $BRIDGE_EXIT -ne 0 ]; then
    echo "FATAL: Bridge builder failed with exit code $BRIDGE_EXIT"
    exit 1
fi

echo ""
echo ""

# Step 3: Run the Sanskrit parser which uses the bridge
echo "STEP 3: RUN SANSKRIT PARSER (WITH BRIDGE)"
echo "=========================================="
python3 scripts/parse_iwn_sanskrit.py
SANSKRIT_EXIT=$?

if [ $SANSKRIT_EXIT -ne 0 ]; then
    echo "FATAL: Sanskrit parser failed with exit code $SANSKRIT_EXIT"
    exit 1
fi

echo ""
echo "========================================================================"
echo "TASK COMPLETE"
echo "========================================================================"
echo ""
echo "Output files:"
ls -la /mnt/pgdata/morphlex/data/open_wordnets/wn_api_audit.txt
ls -la /mnt/pgdata/morphlex/data/open_wordnets/pwn30_to_oewn_map.pkl
ls -la /mnt/pgdata/morphlex/data/open_wordnets/sanskrit_synset_map.pkl
