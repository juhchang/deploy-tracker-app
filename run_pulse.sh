#!/bin/bash
# Refresh all Market Pulse data and recompute composite.
# Run from the project root: bash run_pulse.sh

set -e
cd "$(dirname "$0")"

echo "=== Market Pulse Refresh ==="
python3 scripts/fetch_vix.py        || echo "WARNING: fetch_vix.py failed — skipping"
python3 scripts/fetch_fear_greed.py || echo "WARNING: fetch_fear_greed.py failed — skipping"
python3 scripts/fetch_breadth.py    || echo "WARNING: fetch_breadth.py failed — skipping"
python3 scripts/fetch_spread.py     || echo "WARNING: fetch_spread.py failed — skipping"
python3 scripts/fetch_aaii.py       || echo "WARNING: fetch_aaii.py failed — skipping"
python3 scripts/fetch_pcr.py        || echo "WARNING: fetch_pcr.py failed — skipping"
python3 scripts/fetch_hvrank_spx.py || echo "WARNING: fetch_hvrank_spx.py failed — skipping"
python3 scripts/pulse_composite.py
echo ""
echo "Done — open deploy.html and tap the Pulse tab."
