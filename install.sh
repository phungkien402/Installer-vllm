#!/usr/bin/env bash
# install.sh — bootstrap ehc-installer trên server BV
#
# Usage (sau khi clone repo):
#   cd ehc-installer
#   bash install.sh
#
# Hoặc 1 lệnh (chưa clone):
#   curl -fsSL https://raw.githubusercontent.com/phungkien402/ehc-installer/main/install.sh | bash

set -euo pipefail

REPO="${EHC_REPO:-https://github.com/phungkien402/ehc-installer.git}"
BRANCH="${EHC_BRANCH:-main}"
INSTALL_DIR="${EHC_INSTALL_DIR:-$HOME/ehc-installer}"

color() { printf "\033[%sm%s\033[0m\n" "$1" "$2"; }
ok()    { color "32" "✓ $1"; }
info()  { color "36" "→ $1"; }
warn()  { color "33" "⚠ $1"; }
err()   { color "31" "✗ $1"; }

info "EHC Installer bootstrap"

# 1. Detect OS
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    OS_ID="$ID"
    OS_VER="$VERSION_ID"
    info "OS: $OS_ID $OS_VER"
else
    err "Unsupported OS"
    exit 1
fi

if [[ "$OS_ID" != "ubuntu" ]] || [[ "$OS_VER" != "22.04" && "$OS_VER" != "24.04" ]]; then
    warn "Phase 1 chỉ test trên Ubuntu 22.04/24.04. Tiếp tục..."
fi

# 2. Ensure prereqs (Python 3.10+ + git + curl)
info "Checking Python + git + curl..."
NEED_INSTALL=()
command -v python3 >/dev/null || NEED_INSTALL+=("python3")
command -v pip3 >/dev/null    || NEED_INSTALL+=("python3-pip")
command -v git >/dev/null     || NEED_INSTALL+=("git")
command -v curl >/dev/null    || NEED_INSTALL+=("curl")

if (( ${#NEED_INSTALL[@]} > 0 )); then
    info "Installing: ${NEED_INSTALL[*]}"
    sudo apt-get update -qq
    sudo apt-get install -y python3 python3-pip python3-venv git curl
fi

PYVER=$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
ok "Python $PYVER"

# 3. Clone or update repo
if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Repo exists at $INSTALL_DIR, pulling updates..."
    cd "$INSTALL_DIR"
    git fetch --all
    git checkout "$BRANCH"
    git pull origin "$BRANCH" || true
else
    info "Cloning ehc-installer → $INSTALL_DIR"
    git clone -b "$BRANCH" "$REPO" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# 4. Setup venv
VENV="$INSTALL_DIR/.venv"
if [[ ! -d "$VENV" ]]; then
    info "Creating venv..."
    python3 -m venv "$VENV"
fi
# shellcheck disable=SC1090
source "$VENV/bin/activate"

info "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -e .

ok "ehc-installer installed"

# 5. Create wrapper so `ehc` works without activating venv
WRAPPER=/usr/local/bin/ehc
if [[ -w /usr/local/bin ]] || sudo -n true 2>/dev/null; then
    sudo tee "$WRAPPER" > /dev/null <<EOF
#!/usr/bin/env bash
exec "$VENV/bin/ehc" "\$@"
EOF
    sudo chmod +x "$WRAPPER"
    ok "Wrapper: $WRAPPER"
else
    warn "Cannot create /usr/local/bin/ehc (need sudo)."
    warn "Activate venv manually: source $VENV/bin/activate"
fi

echo
ok "Bootstrap complete!"
echo
info "Next steps:"
echo "  ehc                  # Launch TUI"
echo "  ehc deps check       # Check environment"
echo "  ehc --help           # All commands"
