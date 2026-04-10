cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "========================================================================"
echo "TASK: BUILD PWN 3.0 -> OEWN BRIDGE AND FIX SANSKRIT PARSER"
echo "========================================================================"
echo ""

# Step 1: Build the PWN 3.0 -> OEWN bridge map using ILI
echo "STEP 1: BUILD BRIDGE MAP"
echo "========================"
python3 scripts/build_pwn30_to_oewn_bridge.py
BRIDGE_EXIT=$?

if [ $BRIDGE_EXIT -ne 0 ]; then
    echo "FATAL: Bridge builder failed with exit code $BRIDGE_EXIT"
    exit 1
fi

echo ""
echo ""

# Step 2: Run the Sanskrit parser which now uses the bridge
echo "STEP 2: RUN SANSKRIT PARSER (WITH BRIDGE)"
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
ls -la /mnt/pgdata/morphlex/data/open_wordnets/pwn30_to_oewn_map.pkl
ls -la /mnt/pgdata/morphlex/data/open_wordnets/sanskrit_synset_map.pkl
