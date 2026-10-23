#!/bin/bash
# SENTIENX Stop Script - Gracefully shutdown

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="${SCRIPT_DIR}/.sentienx.pid"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Stopping SENTIENX...${NC}\n"

# Kill trading bot if running
if [ -f "$PID_FILE" ]; then
    BOT_PID=$(grep "BOT:" "$PID_FILE" | cut -d':' -f2)
    if [ -n "$BOT_PID" ] && ps -p "$BOT_PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}Stopping Trading Bot (PID: $BOT_PID)...${NC}"
        kill $BOT_PID 2>/dev/null || true
        sleep 1
        if ps -p "$BOT_PID" > /dev/null 2>&1; then
            echo -e "${YELLOW}Force killing Bot...${NC}"
            kill -9 $BOT_PID 2>/dev/null || true
        fi
        echo -e "${GREEN}Trading Bot stopped${NC}"
    fi
    rm -f "$PID_FILE"
else
    echo -e "${YELLOW}No SENTIENX process found${NC}"
fi

# Kill Streamlit if running on port 8501
if lsof -Pi :8501 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}Stopping Dashboard...${NC}"
    STREAMLIT_PID=$(lsof -Pi :8501 -sTCP:LISTEN -t)
    kill $STREAMLIT_PID 2>/dev/null || true
    sleep 1
    echo -e "${GREEN}Dashboard stopped${NC}"
fi

echo -e "${GREEN}SENTIENX stopped${NC}\n"
