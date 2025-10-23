#!/usr/bin/env bash
set -euo pipefail

# === MVP ServerBond Agent Installer ===
# Minimal, simple, and reliable installation script
# Version: 2.0.0
# Date: $(date +%Y-%m-%d)
# Author: ServerBond Team

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }

# === Configuration ===
AGENT_DIR="/opt/serverbond-agent"
SITES_DIR="/opt/sites"
SHARED_DIR="/opt/shared-services"
NETWORK="shared_net"
AGENT_PORT=8000
AGENT_TOKEN="${AGENT_TOKEN:-$(openssl rand -hex 16)}"

# === 1. Root Check ===
if [[ $EUID -ne 0 ]]; then
    error "This script must be run as root. Use: sudo $0"
fi

log "Starting ServerBond Agent installation..."
log "Installer Version: 2.0.0"
log "Installation Date: $(date)"

# === 2. Update System ===
log "Updating system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq

# === 3. Install Dependencies ===
log "Installing dependencies..."
apt-get install -y -qq \
    curl \
    git \
    python3 \
    python3-pip \
    systemd \
    systemd-sysv \
    dbus \
    dbus-user-session

# === 4. Install Python Dependencies ===
log "Installing Python dependencies..."
pip3 install --break-system-packages -q \
    fastapi \
    uvicorn[standard] \
    docker \
    psutil \
    jinja2 \
    requests

# === 5. Create Directories ===
log "Creating directories..."
mkdir -p "$AGENT_DIR" "$SITES_DIR" "$SHARED_DIR"

# === 6. Download Agent Files ===
log "Downloading agent files..."
cd /tmp
git clone -q https://github.com/beyazitkolemen/serverbond-docker.git

# Copy agent files
cp -r serverbond-docker/agent/* "$AGENT_DIR/"
cp -r serverbond-docker/templates "$AGENT_DIR/"

# Cleanup
rm -rf serverbond-docker

# === 7. Setup Systemd Service ===
log "Setting up systemd service..."

# Ensure systemd is running
log "Starting systemd..."
systemctl daemon-reexec || log "Systemd daemon already running"

# Create systemd service file
cat > /etc/systemd/system/serverbond-agent.service << EOF
[Unit]
Description=ServerBond Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$AGENT_DIR/agent
ExecStart=/usr/bin/python3 $AGENT_DIR/agent/agent.py
Restart=always
RestartSec=10
Environment=SB_BASE_DIR=$SITES_DIR
Environment=SB_TEMPLATE_DIR=$AGENT_DIR/templates
Environment=SB_NETWORK=$NETWORK
Environment=SB_CONFIG_DIR=/opt/serverbond-config
Environment=SB_SHARED_MYSQL_CONTAINER=shared_mysql
Environment=SB_SHARED_REDIS_CONTAINER=shared_redis
Environment=SB_AGENT_TOKEN=$AGENT_TOKEN
Environment=SB_AGENT_PORT=$AGENT_PORT
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=$AGENT_DIR

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start service
log "Starting ServerBond Agent service..."
systemctl daemon-reload

# Enable service for auto-start
systemctl enable serverbond-agent.service

# Start service
systemctl start serverbond-agent.service

# Wait for service to start
sleep 5

# Check service status
if systemctl is-active --quiet serverbond-agent.service; then
    success "ServerBond Agent is running in background!"
    log "Service status: systemctl status serverbond-agent"
    log "Service logs: journalctl -u serverbond-agent -f"
    log "Service management:"
    log "  - Stop: systemctl stop serverbond-agent"
    log "  - Start: systemctl start serverbond-agent"
    log "  - Restart: systemctl restart serverbond-agent"
    log "  - Status: systemctl status serverbond-agent"
else
    error "Failed to start ServerBond Agent service"
    log "Check logs: journalctl -u serverbond-agent"
    log "Check service status: systemctl status serverbond-agent"
    exit 1
fi