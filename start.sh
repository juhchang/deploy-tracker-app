#!/bin/bash

# Options Dashboard — startup script
# Run with: ./start.sh

cd "$(dirname "$0")"

# Check if already running
if lsof -ti:5000 > /dev/null 2>&1; then
  echo "Server already running at http://localhost:5000"
  open http://localhost:5000
  exit 0
fi

echo "Starting Options Dashboard..."
python3 app.py &
SERVER_PID=$!

# Wait for server to be ready
for i in {1..10}; do
  sleep 0.5
  if curl -s http://localhost:5000/api/config > /dev/null 2>&1; then
    echo "Ready at http://localhost:5000"
    open http://localhost:5000
    wait $SERVER_PID
    exit 0
  fi
done

echo "Server did not start in time — check for errors above"
wait $SERVER_PID
