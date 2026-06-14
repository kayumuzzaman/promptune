#!/bin/bash
# Promptune installer
# Usage: curl -fsSL https://raw.githubusercontent.com/kayumuzzaman/promptune/main/install.sh | bash
#
# Safer alternative:
#   curl -fsSL https://raw.githubusercontent.com/kayumuzzaman/promptune/main/install.sh -o install.sh
#   bash install.sh

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[promptune]${NC} $1"; }
warn()  { echo -e "${YELLOW}[promptune]${NC} $1"; }
error() { echo -e "${RED}[promptune]${NC} $1" >&2; }

# --- Precondition checks (before set -e, for graceful error messages) ---

check_os() {
    local os
    os="$(uname)"
    if [ "$os" != "Darwin" ] && [ "$os" != "Linux" ]; then
        error "Promptune supports macOS and Linux (detected: $os)."
        exit 1
    fi
}

check_not_root() {
    # Use PROMPTUNE_FAKE_EUID for testing, fall back to real EUID
    local euid="${PROMPTUNE_FAKE_EUID:-$EUID}"
    if [ "$euid" = "0" ]; then
        error "Do not run this installer as root."
        error "Run without sudo: curl -fsSL <url> | bash"
        exit 1
    fi
}

check_python() {
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is not installed."
        error "Install Python 3.9+ from https://www.python.org/downloads/"
        exit 1
    fi

    local version
    version="$(python3 -c 'import sys; print(sys.version_info.major, sys.version_info.minor)')"
    local major minor
    major="$(echo "$version" | cut -d' ' -f1)"
    minor="$(echo "$version" | cut -d' ' -f2)"

    if [ "$major" -lt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -lt 9 ]; }; then
        error "Python 3.9+ is required (found: $(python3 --version))."
        error "Install a newer version from https://www.python.org/downloads/"
        exit 1
    fi
    info "Found $(python3 --version)"
}

# Run precondition checks
check_os
check_not_root
check_python

# --- Main install (strict mode after precondition checks) ---
set -euo pipefail

install_pipx() {
    if command -v pipx &> /dev/null; then
        info "pipx is already installed."
        return 0
    fi

    info "Installing pipx..."
    python3 -m pip install --user pipx 2>/dev/null || {
        error "Failed to install pipx. Check your Python/pip setup."
        exit 1
    }
    python3 -m pipx ensurepath 2>/dev/null || true
    # Add common pipx binary locations to PATH for this session
    export PATH="$HOME/.local/bin:$PATH"

    if ! command -v pipx &> /dev/null; then
        warn "pipx installed but not found in PATH."
        warn "You may need to restart your shell or run: export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
}

install_promptune() {
    info "Installing promptune from PyPI..."
    if command -v promptune &> /dev/null; then
        info "promptune is already installed. Upgrading..."
        pipx upgrade promptune 2>/dev/null || pipx install --force promptune || {
            error "Failed to upgrade promptune."
            exit 1
        }
    else
        pipx install promptune || {
            error "Failed to install promptune."
            error "This could be a network issue. Check your internet connection and try again."
            exit 1
        }
    fi
}

verify_install() {
    if command -v promptune &> /dev/null; then
        local version
        version="$(promptune --version 2>/dev/null || promptune version 2>/dev/null || echo 'unknown')"
        info "promptune $version installed successfully!"
        return 0
    fi
    # Try with explicit path
    if [ -x "$HOME/.local/bin/promptune" ]; then
        info "promptune installed at ~/.local/bin/promptune"
        return 0
    fi
    warn "promptune installed but not found in PATH."
    warn "Try: export PATH=\"\$HOME/.local/bin:\$PATH\""
    return 0
}

print_next_steps() {
    echo ""
    info "--- Next Steps ---"
    echo ""
    echo "  1. Configure your API key:"
    echo "     promptune config init"
    echo ""
    echo "  2. You need an API key for at least one provider:"
    echo "     - Claude:     https://console.anthropic.com/"
    echo "     - OpenAI:     https://platform.openai.com/"
    echo "     - OpenRouter:  https://openrouter.ai/"
    echo ""
    echo "  3. Set up the shell widget (add to ~/.zshrc):"
    echo "     eval \"\$(promptune shell-init)\""
    echo ""
    echo "  4. Press Ctrl+E in your terminal to enhance prompts!"
    echo ""
    if [ "$(uname)" = "Linux" ]; then
        echo "  Linux — for the system-wide hotkey daemon, also install:"
        echo "     X11:     sudo apt install xclip xdotool"
        echo "     Wayland: sudo apt install wl-clipboard   (+ add yourself to the 'input' group)"
        echo "     and:     pipx inject promptune python-xlib dbus-next evdev"
        echo ""
    fi
}

check_ollama() {
    echo ""
    info "--- Ollama Status ---"

    # Check if ollama binary exists
    local ollama_path
    ollama_path="$(command -v ollama 2>/dev/null || echo "")"
    if [ -z "$ollama_path" ]; then
        warn "MISS: Ollama not found"
        echo "      Install: https://ollama.com/download"
        echo "      Then run: ollama pull qwen2.5:3b"
        return 0
    fi
    info "OK:   Ollama found at $ollama_path"

    # Check if server is running
    if ! curl -s --max-time 3 http://localhost:11434/api/tags > /dev/null 2>&1; then
        warn "MISS: Ollama server not running"
        echo "      Start with: ollama serve"
        return 0
    fi
    info "OK:   Ollama server running"

    # Check if model is available
    local model="qwen2.5:3b"
    if curl -s --max-time 3 http://localhost:11434/api/tags 2>/dev/null | grep -q "$model"; then
        info "OK:   Model $model available"
    else
        warn "MISS: Model $model not available"
        echo "      Run: ollama pull $model"
    fi
}

install_pipx
install_promptune
verify_install
print_next_steps

# Ollama status check (informational only)
check_ollama 2>/dev/null || true
