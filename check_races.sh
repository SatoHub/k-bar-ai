#!/bin/bash
# Check all 36 races for null/missing post_position, bracket_number, jockey

API_BASE="http://133.117.72.213/api/v1"
OUTDIR="C:/Users/unoen/projects/k-bar-ai/race_check_results"
PYTHON="/c/Users/unoen/AppData/Local/Programs/Python/Python312/python.exe"
mkdir -p "$OUTDIR"

RACE_IDS=(
  202610011101 202609010301 202606020101
  202610011102 202609010302 202606020102
  202609010303 202610011103 202606020103
  202609010304 202610011104 202606020104
  202609010305 202610011105 202606020105
  202606020106 202609010306 202610011106
  202609010307 202606020107 202610011107
  202609010308 202610011108 202606020108
  202606020109 202609010309 202610011109
  202606020110 202609010310 202610011110
  202609010311 202606020111 202610011111
  202609010312 202610011112 202606020112
)

echo "Fetching all 36 races..."

# Step 1: Download all race JSONs
for RACE_ID in "${RACE_IDS[@]}"; do
  curl -s -u admin:kbar2026ai "${API_BASE}/races/${RACE_ID}" -o "$OUTDIR/${RACE_ID}.json"
done

echo "All races downloaded. Analyzing..."
echo ""

# Step 2: Analyze with Python
$PYTHON "C:/Users/unoen/projects/k-bar-ai/analyze_races.py"
