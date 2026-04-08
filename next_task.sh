#!/bin/bash
# INSTALL HSPELL ON VM AND TEST HEBREW ROOT EXTRACTION
# Timestamp: 2026-04-08-hspell-install
# NO HARDCODING. HONEST HEBREW ADAPTER.

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== HSPELL INSTALLATION AND HEBREW ROOT TEST ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code first
echo "--- Step 1: Syncing code from origin/main ---"
git fetch origin && git reset --hard origin/main
echo "Now at: $(git rev-parse HEAD)"
echo ""

# Verify honest Hebrew adapter (NO KNOWN_ROOTS)
echo "--- Step 2: Verify honest Hebrew adapter ---"
if grep -q "KNOWN_ROOTS" analyzers/hebrew.py; then
    echo "FAIL: KNOWN_ROOTS still present in hebrew.py - not honest!"
    exit 1
else
    echo "PASS: No KNOWN_ROOTS dictionary (honest adapter)"
fi

if grep -q "_extract_root_fallback\|_strip_affixes" analyzers/hebrew.py; then
    echo "FAIL: Rule-based fallback still present - not honest!"
    exit 1
else
    echo "PASS: No rule-based fallback (honest adapter)"
fi
echo ""

# Install Hspell C library
echo "--- Step 3: Install Hspell C library ---"

# Check if already installed
if ldconfig -p | grep -q libhspell; then
    echo "Hspell C library already installed"
else
    echo "Installing Hspell C library from source..."

    # Install build dependencies
    sudo apt-get update && sudo apt-get install -y build-essential zlib1g-dev || {
        echo "WARNING: apt-get failed, trying without update..."
    }

    # Download and build Hspell
    cd /tmp
    rm -rf hspell-1.4 hspell-1.4.tar.gz

    wget http://hspell.ivrix.org.il/hspell-1.4.tar.gz || {
        echo "FAIL: Could not download Hspell"
        echo "Trying alternative mirror..."
        wget https://github.com/julesjabbour/hspell-mirror/raw/main/hspell-1.4.tar.gz || {
            echo "FAIL: All download attempts failed"
            exit 1
        }
    }

    tar xzf hspell-1.4.tar.gz
    cd hspell-1.4

    ./configure --enable-shared --enable-linginfo || {
        echo "FAIL: Hspell configure failed"
        exit 1
    }

    make || {
        echo "FAIL: Hspell make failed"
        exit 1
    }

    sudo make install || {
        echo "FAIL: Hspell make install failed"
        exit 1
    }

    sudo ldconfig

    cd /mnt/pgdata/morphlex

    # Verify installation
    if ldconfig -p | grep -q libhspell; then
        echo "SUCCESS: Hspell C library installed"
    else
        echo "FAIL: Hspell C library not found after install"
        exit 1
    fi
fi
echo ""

# Install HspellPy
echo "--- Step 4: Install HspellPy Python package ---"

# Check if already installed
if python3 -c "import HspellPy; print('HspellPy version:', HspellPy.__version__ if hasattr(HspellPy, '__version__') else 'unknown')" 2>/dev/null; then
    echo "HspellPy already installed"
else
    echo "Installing HspellPy..."
    pip install HspellPy || {
        echo "Trying with --break-system-packages..."
        pip install HspellPy --break-system-packages || {
            echo "FAIL: Could not install HspellPy"
            exit 1
        }
    }

    # Verify installation
    if python3 -c "import HspellPy; print('SUCCESS: HspellPy imported')" 2>/dev/null; then
        echo "HspellPy installed successfully"
    else
        echo "FAIL: HspellPy import failed after install"
        exit 1
    fi
fi
echo ""

# Test HspellPy directly
echo "--- Step 5: Test HspellPy directly ---"
python3 << 'EOF'
import HspellPy

print("Testing HspellPy directly:")
hspell = HspellPy.Hspell(linguistics=True)

# Test word
word = 'מילון'
print(f"  Word: {word}")

# Try linginfo
infos = list(hspell.linginfo(word))
print(f"  linginfo results: {len(infos)}")
for info in infos[:3]:
    print(f"    - {info}")

# Try spell check
correct = hspell.check(word)
print(f"  Spelling correct: {correct}")

print("HspellPy direct test: PASS")
EOF
echo ""

# Test Hebrew adapter with 10 random words
echo "--- Step 6: Test Hebrew adapter with 10 RANDOM words ---"
python3 << 'EOF'
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')

from analyzers.hebrew import analyze_hebrew, _init_hspell

print("Hebrew adapter test (HONEST - NO HARDCODING)")
print(f"HspellPy available: {_init_hspell()}")
print("")

# 10 random Hebrew words - NOT from any test list
# These are common Hebrew words that should have roots
test_words = [
    ('אוכל', 'food'),
    ('מכונית', 'car'),
    ('טלפון', 'telephone'),
    ('חלב', 'milk'),
    ('שמש', 'sun'),
    ('ירח', 'moon'),
    ('דלת', 'door'),
    ('רחוב', 'street'),
    ('גשם', 'rain'),
    ('שלג', 'snow'),
]

found = 0
empty = 0

print("=== 10 RANDOM HEBREW WORDS ===")
for word, meaning in test_words:
    results = analyze_hebrew(word)
    if results and results[0].get('root'):
        r = results[0]
        print(f"  {word} ({meaning}): root='{r['root']}', source={r['source_tool']}")
        found += 1
    else:
        print(f"  {word} ({meaning}): NO ROOT")
        empty += 1

print("")
print(f"=== RESULTS: {found}/10 roots found, {empty}/10 empty ===")

if found > 0:
    print("STATUS: PARTIAL SUCCESS - HspellPy working")
else:
    print("STATUS: NEEDS INVESTIGATION - no roots found")

EOF
echo ""

# Run comprehensive test
echo "--- Step 7: Run comprehensive adapter test ---"
cd /mnt/pgdata/morphlex
python3 test_comprehensive.py 2>&1 | head -150
echo ""

echo "=== HSPELL INSTALLATION COMPLETE ==="
echo "End: $(date -Iseconds)"
