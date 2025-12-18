#!/bin/bash
#
# Talk2YourServer - Systemd Service Installer
# Run with: sudo ./install-service.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "  Talk2YourServer Service Installer"
echo "=========================================="
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}This script requires sudo. Running with sudo...${NC}"
    exec sudo "$0" "$@"
fi

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SERVICE_TEMPLATE="$PROJECT_DIR/systemd/talk2yourserver.service"
TARGET="/etc/systemd/system/talk2yourserver.service"

# Detect current user (the one who ran sudo)
CURRENT_USER="${SUDO_USER:-$USER}"
USER_HOME=$(eval echo ~$CURRENT_USER)

echo "Configuration:"
echo "  User: $CURRENT_USER"
echo "  Home: $USER_HOME"
echo "  Project: $PROJECT_DIR"
echo

# Check if template exists
if [ ! -f "$SERVICE_TEMPLATE" ]; then
    echo -e "${RED}Error: Service template not found at $SERVICE_TEMPLATE${NC}"
    exit 1
fi

# Check if .env exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${YELLOW}Warning: .env file not found. Copy .env.example to .env and configure it.${NC}"
fi

# Create logs directory
echo "[1/7] Creating logs directory..."
mkdir -p "$PROJECT_DIR/logs"
chown "$CURRENT_USER:$CURRENT_USER" "$PROJECT_DIR/logs"

# Stop any existing service
echo "[2/7] Stopping existing service (if any)..."
systemctl stop talk2yourserver 2>/dev/null || true

# Stop any running bot processes
echo "[3/7] Stopping existing bot processes..."
pkill -f "python.*bot.py" 2>/dev/null || true
sleep 2

# Copy and configure service file
echo "[4/7] Installing systemd service..."
sed -e "s|YOUR_USERNAME|$CURRENT_USER|g" \
    -e "s|/home/YOUR_USERNAME/talk2yourServer|$PROJECT_DIR|g" \
    "$SERVICE_TEMPLATE" > "$TARGET"

# Reload systemd
echo "[5/7] Reloading systemd daemon..."
systemctl daemon-reload

# Enable service (start on boot)
echo "[6/7] Enabling service for auto-start on boot..."
systemctl enable talk2yourserver.service

# Start service
echo "[7/7] Starting service..."
systemctl start talk2yourserver.service

# Wait and check status
sleep 3

echo
echo "=========================================="
echo -e "  ${GREEN}Installation Complete!${NC}"
echo "=========================================="
echo
systemctl status talk2yourserver.service --no-pager | head -12
echo
echo "Useful commands:"
echo "  sudo systemctl status talk2yourserver   # Check status"
echo "  sudo systemctl restart talk2yourserver  # Restart"
echo "  sudo systemctl stop talk2yourserver     # Stop"
echo "  sudo journalctl -u talk2yourserver -f   # Live logs"
echo "  tail -f $PROJECT_DIR/logs/bot.log       # Bot logs"
echo

# Optional: Add passwordless sudo for service management
echo "To manage the service without password, run:"
echo "  echo '$CURRENT_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart talk2yourserver, /bin/systemctl stop talk2yourserver, /bin/systemctl start talk2yourserver, /bin/systemctl status talk2yourserver' | sudo tee /etc/sudoers.d/talk2yourserver"
echo
