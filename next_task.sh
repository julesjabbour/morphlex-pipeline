cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "========================================================================"
echo "TASK: IDENTIFY PWN VERSION USED BY INDOWORDNET"
echo "========================================================================"
echo ""
echo "PROBLEM: IWN english_id values (like 532338 for 'folk_dance') don't match"
echo "PWN 3.0 offsets. Only 50/11,082 IWN synsets match the PWN 3.0 -> OEWN bridge."
echo "IWN likely uses PWN 1.7 or 2.x."
echo ""

# Run the PWN version identification script
python3 scripts/identify_iwn_pwn_version.py
IDENTIFY_EXIT=$?

if [ $IDENTIFY_EXIT -ne 0 ]; then
    echo "FATAL: PWN version identification failed with exit code $IDENTIFY_EXIT"
    exit 1
fi

echo ""
echo "========================================================================"
echo "TASK COMPLETE"
echo "========================================================================"
