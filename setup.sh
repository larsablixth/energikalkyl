#!/bin/bash
# Setup script for Energikalkyl
# Run: bash setup.sh

set -e

echo "=== Energikalkyl Setup ==="

# Install pip if missing
if ! python3 -m pip --version &>/dev/null; then
    echo "Installing pip..."
    python3 -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', '/tmp/get-pip.py')"
    python3 /tmp/get-pip.py --user --break-system-packages
    rm -f /tmp/get-pip.py
fi

export PATH="$HOME/.local/bin:$PATH"

# Install dependencies
echo "Installing dependencies..."
pip install --user --break-system-packages -r requirements.txt

# Tibber token
if [ ! -f .tibber_token ]; then
    echo ""
    echo "Tibber API-token saknas."
    echo "Hämta din token på https://developer.tibber.com/"
    read -p "Klistra in din Tibber-token: " token
    echo "$token" > .tibber_token
    echo "Token sparad i .tibber_token"
fi

# Start app
echo ""
echo "Startar Energikalkyl..."
streamlit run app.py --server.headless true
