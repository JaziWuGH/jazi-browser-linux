#!/bin/bash
# Jazi installation script
# Run: bash scripts/install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "╔══════════════════════════════════════════╗"
echo "║   Jazi — AI Browser for Linux  ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ---- Check Python ----
PYTHON=""
for py in python3 python3.10 python3.11 python3.12; do
    if command -v $py &>/dev/null; then
        PYTHON=$py
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "❌ Python 3.10+ required but not found."
    echo "   Install with: sudo apt install python3 python3-pip"
    exit 1
fi

PY_VERSION=$($PYTHON --version 2>&1 | awk '{print $2}')
echo "✓ Python: $PYTHON ($PY_VERSION)"

# ---- Create virtualenv ----
VENV_DIR="$HOME/.jazi/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "→ Creating virtual environment at $VENV_DIR..."
    $PYTHON -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
echo "✓ Virtualenv activated"

# ---- Install dependencies ----
echo "→ Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r "$PROJECT_DIR/requirements.txt" -q
echo "✓ Python packages installed"

# ---- Install Playwright browsers ----
echo "→ Installing Chromium (Playwright)..."
playwright install chromium --with-deps 2>&1 | tail -1
echo "✓ Chromium installed"

# ---- Install jazi CLI ----
echo "→ Installing jazi command..."
pip install -e "$PROJECT_DIR" -q

BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

# Ensure ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "→ Adding $BIN_DIR to PATH..."
    for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
        if [ -f "$rc" ]; then
            grep -q "$BIN_DIR" "$rc" || echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$rc"
        fi
    done
    export PATH="$BIN_DIR:$PATH"
fi

echo "✓ jazi CLI installed"

# ---- Verify ----
echo ""
echo "→ Verifying installation..."
if command -v jazi &>/dev/null; then
    echo "✓ jazi command available"
else
    echo "⚠ jazi not in PATH yet. Run: export PATH=\"$HOME/.local/bin:\$PATH\""
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║          Installation complete!           ║"
echo "╠══════════════════════════════════════════╣"
echo "║                                          ║"
echo "║  Start the server:                       ║"
echo "║    jazi serve                     ║"
echo "║                                          ║"
echo "║  Or start in headless mode:              ║"
echo "║    jazi serve --headless          ║"
echo "║                                          ║"
echo "║  Create a named space for an agent:      ║"
echo "║    jazi space create mytask       ║"
echo "║                                          ║"
echo "║  List spaces:                            ║"
echo "║    jazi space list                ║"
echo "║                                          ║"
echo "║  Run JS tools against a page:            ║"
echo "║    jazi nodejs < script.js        ║"
echo "║                                          ║"
echo "║  API at http://127.0.0.1:9222            ║"
echo "║  Docs at http://127.0.0.1:9222/docs      ║"
echo "╚══════════════════════════════════════════╝"
