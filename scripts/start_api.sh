#!/bin/bash
# Start API Server on port 8080

cd /home/marvell/forex-book-local/sentienx

echo "Starting SENTIENX API Server..."
echo "Port: 8080"
echo "Press Ctrl+C to stop"
echo ""

python3 api_server.py
