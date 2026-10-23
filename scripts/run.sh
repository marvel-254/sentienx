#!/bin/bash
# SENTIENX Run Script - Start everything

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}SENTIENX Trading Bot${NC}"
echo -e "${BLUE}================================${NC}\n"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 not found${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo -e "${GREEN}Python: $PYTHON_VERSION${NC}"

# Install dependencies if needed
if ! python3 -c "import streamlit" 2>/dev/null; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    python3 -m pip install -q -r requirements.txt
    echo -e "${GREEN}Dependencies installed${NC}"
fi

# Export environment
export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH}"
export DERIV_APP_ID="${DERIV_APP_ID:-YOUR_DERIV_APP_ID}"
export DERIV_API_TOKEN="${DERIV_API_TOKEN:-YOUR_DERIV_API_TOKEN}"
export DERIV_ENV="${DERIV_ENV:-real}"

# Create PID file for stop script
PID_FILE="${SCRIPT_DIR}/.sentienx.pid"

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}SENTIENX already running (PID: $OLD_PID)${NC}"
        echo -e "${YELLOW}Run: bash stop.sh${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}Starting SENTIENX...${NC}\n"

# Start trading bot in background
echo -e "${BLUE}Starting Trading Bot...${NC}"
python3 trading_bot.py --interval 60 > /dev/null 2>&1 &
BOT_PID=$!
echo "BOT:$BOT_PID" > "$PID_FILE"
echo -e "${GREEN}Trading Bot started (PID: $BOT_PID)${NC}"

# Wait for bot to initialize
sleep 2

# Start Streamlit dashboard
echo -e "${BLUE}Starting Unified Dashboard...${NC}"
echo -e "${YELLOW}Dashboard available at: http://localhost:8501${NC}\n"

streamlit run dashboard/unified_dashboard.py \
  --logger.level=info \
  --client.showErrorDetails=false \
  --server.headless=true \
  --server.port=8501 \
  --server.address=0.0.0.0
