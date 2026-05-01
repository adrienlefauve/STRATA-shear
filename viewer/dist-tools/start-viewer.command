#!/bin/bash
# STRATA Mean-Shear Viewer — local launcher
# Double-click this file. It starts a local web server, opens your browser
# to the viewer, and keeps running until you close the Terminal window.

set -e
cd "$(dirname "$0")/.."  # parent of dist-tools/ → the deposit root

# Pick a free port (8000, then 8001, …)
PORT=8000
while lsof -i ":$PORT" >/dev/null 2>&1; do
  PORT=$((PORT + 1))
done

URL="http://localhost:$PORT/index.html"

echo "================================================"
echo " STRATA Mean-Shear Viewer"
echo "================================================"
echo ""
echo " Serving on: $URL"
echo ""
echo " Close this window to stop the viewer."
echo ""
echo "================================================"
echo ""

# Open browser after a short delay
( sleep 1 && open "$URL" ) &

# Start server (Python 3 first, fall back to Python 2)
if command -v python3 >/dev/null 2>&1; then
  python3 -m http.server "$PORT"
elif command -v python >/dev/null 2>&1; then
  python -m SimpleHTTPServer "$PORT"
else
  echo "ERROR: Python is not installed. Install Python 3 and try again."
  read -n 1 -s -r -p "Press any key to close..."
  exit 1
fi
