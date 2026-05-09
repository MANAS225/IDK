#!/bin/bash
set -e
echo "Installing dependencies..."
pip install -r requirements.txt -q
echo "Starting backend..."
python backend.py &
BACKEND_PID=$!
sleep 2
echo "Starting sensor simulator..."
python sensor_sim.py &
SIM_PID=$!
sleep 1
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  NEXUS IQ is ready at http://localhost:5000  ║"
echo "║  Login: admin@hmi.com / password123          ║"
echo "║  Press Ctrl+C to stop all services.          ║"
echo "╚══════════════════════════════════════════╝"
echo ""
python app.py
kill $BACKEND_PID $SIM_PID 2>/dev/null
