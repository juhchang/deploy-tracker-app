#!/bin/bash
# Refresh all Market Pulse data and recompute composite.
# Run from the project root: bash run_pulse.sh

set -e
cd "$(dirname "$0")"

echo "=== Market Pulse Refresh ==="
python3 scripts/fetch_vix.py
python3 scripts/fetch_fear_greed.py
python3 scripts/fetch_breadth.py
python3 scripts/fetch_spread.py
python3 scripts/fetch_aaii.py
python3 scripts/fetch_pcr.py
python3 scripts/fetch_hvrank_spx.py
python3 scripts/pulse_composite.py
echo ""
echo "Done — open deploy.html and tap the Pulse tab."
