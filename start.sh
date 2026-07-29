#!/bin/sh
set -e

python mcp_file_service.py &
FILE_PID=$!

python mcp_calculator_service.py &
CALC_PID=$!

cleanup() {
    kill "$FILE_PID" "$CALC_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Give the MCP servers a moment to bind their ports before the agent connects.
sleep 2

ENV=production exec uvicorn ui_server:app --host 0.0.0.0 --port "${PORT:-8082}"
