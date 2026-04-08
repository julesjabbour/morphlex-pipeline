#!/bin/bash
# GREEK LEXICON DIAGNOSTIC - Find how to load Greek into Morpheus
# Goal: Inspect Morpheus Docker container, find Latin lexicon config, locate Greek lexicon
# Timestamp: 2026-04-08-greek-lexicon-diagnostic

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== MORPHEUS GREEK LEXICON DIAGNOSTIC ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Step 1: Find Morpheus container
echo "--- Step 1: Docker containers ---"
docker ps --format "table {{.ID}}\t{{.Image}}\t{{.Names}}\t{{.Ports}}" 2>&1
echo ""

echo "--- Step 2: Find Morpheus container name ---"
MORPHEUS_CONTAINER=$(docker ps --format '{{.Names}}' | grep -i morph || docker ps --format '{{.ID}}' | head -1)
echo "Morpheus container: $MORPHEUS_CONTAINER"
echo ""

# Step 3: Inspect container
echo "--- Step 3: Container inspection ---"
docker inspect "$MORPHEUS_CONTAINER" 2>&1 | head -100
echo ""

# Step 4: Check what's inside the container
echo "--- Step 4: Container filesystem - looking for lexicons ---"
echo "Looking for any .lex, .dat, .bin, .txt files in common locations..."
docker exec "$MORPHEUS_CONTAINER" find /app /data /opt /home /var /usr/local -maxdepth 4 -type f \( -name "*.lex" -o -name "*.dat" -o -name "*.bin" -o -name "*greek*" -o -name "*latin*" -o -name "*stemlib*" \) 2>/dev/null | head -50
echo ""

# Step 5: Check Morpheus source directory
echo "--- Step 5: Morpheus app structure ---"
docker exec "$MORPHEUS_CONTAINER" ls -la /app 2>/dev/null || docker exec "$MORPHEUS_CONTAINER" ls -la / 2>/dev/null | head -30
echo ""

# Step 6: Look for stemlib or lexicon directories
echo "--- Step 6: Stemlib directory search ---"
docker exec "$MORPHEUS_CONTAINER" find / -type d -name "stemlib*" 2>/dev/null | head -10
docker exec "$MORPHEUS_CONTAINER" find / -type d -name "*lexicon*" 2>/dev/null | head -10
docker exec "$MORPHEUS_CONTAINER" find / -type d -name "*greek*" 2>/dev/null | head -10
echo ""

# Step 7: Check container entrypoint/command
echo "--- Step 7: Container startup command ---"
docker inspect --format='{{.Config.Cmd}}' "$MORPHEUS_CONTAINER" 2>&1
docker inspect --format='{{.Config.Entrypoint}}' "$MORPHEUS_CONTAINER" 2>&1
echo ""

# Step 8: Check environment variables
echo "--- Step 8: Environment variables ---"
docker exec "$MORPHEUS_CONTAINER" env 2>&1 | grep -iE "morph|lex|greek|latin|stem|data" || echo "(no relevant env vars)"
echo ""

# Step 9: Check if there's a config file
echo "--- Step 9: Config files ---"
docker exec "$MORPHEUS_CONTAINER" cat /app/config.json 2>/dev/null || echo "(no /app/config.json)"
docker exec "$MORPHEUS_CONTAINER" cat /app/config.yml 2>/dev/null || echo "(no /app/config.yml)"
docker exec "$MORPHEUS_CONTAINER" cat /app/settings.json 2>/dev/null || echo "(no /app/settings.json)"
echo ""

# Step 10: Check container mounts/volumes
echo "--- Step 10: Volume mounts ---"
docker inspect --format='{{json .Mounts}}' "$MORPHEUS_CONTAINER" 2>&1 | python3 -m json.tool || echo "(no mounts or parse error)"
echo ""

# Step 11: Direct file exploration
echo "--- Step 11: Root directory structure ---"
docker exec "$MORPHEUS_CONTAINER" ls -la / 2>&1 | head -30
echo ""

echo "--- Step 12: Find all directories with 'lat' or 'grc' or 'greek' ---"
docker exec "$MORPHEUS_CONTAINER" find / -maxdepth 5 -type d \( -name "*lat*" -o -name "*grc*" -o -name "*greek*" \) 2>/dev/null | head -20
echo ""

# Step 13: Look for Morpheus Python code
echo "--- Step 13: Python files in container ---"
docker exec "$MORPHEUS_CONTAINER" find / -name "*.py" -type f 2>/dev/null | head -20
echo ""

# Step 14: Check if there's an API or config for loading lexicons
echo "--- Step 14: API endpoints check ---"
echo "Test Latin (should work):"
curl -s "http://localhost:1315/latin/scribo" | head -c 500
echo ""
echo ""
echo "Test Greek (expected empty):"
curl -s "http://localhost:1315/greek/γραφω" | head -c 500 || echo "(empty or error)"
echo ""
echo ""
echo "Test root endpoint:"
curl -s "http://localhost:1315/" | head -c 500 || echo "(no root endpoint)"
echo ""
echo ""
echo "Test /status or /health:"
curl -s "http://localhost:1315/status" | head -c 200 || echo "(no status)"
curl -s "http://localhost:1315/health" | head -c 200 || echo "(no health)"
echo ""

# Step 15: Check if there's a languages endpoint
echo "--- Step 15: Check for /languages endpoint ---"
curl -s "http://localhost:1315/languages" | head -c 500 || echo "(no languages endpoint)"
echo ""

# Step 16: Docker image details
echo "--- Step 16: Docker image ---"
docker inspect --format='{{.Config.Image}}' "$MORPHEUS_CONTAINER" 2>&1
docker image ls 2>&1 | grep -i morph
echo ""

echo "=== DIAGNOSTIC COMPLETE ==="
echo "End: $(date -Iseconds)"
