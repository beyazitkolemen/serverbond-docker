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
    python3-pip

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

# === 7. Start Agent ===
log "Starting ServerBond Agent..."

# Set environment variables
export SB_BASE_DIR=$SITES_DIR
export SB_TEMPLATE_DIR=$AGENT_DIR/templates
export SB_NETWORK=$NETWORK
export SB_CONFIG_DIR=/opt/serverbond-config
export SB_SHARED_MYSQL_CONTAINER=shared_mysql
export SB_SHARED_REDIS_CONTAINER=shared_redis
export SB_AGENT_TOKEN=$AGENT_TOKEN
export SB_AGENT_PORT=$AGENT_PORT
export PYTHONUNBUFFERED=1
export PYTHONPATH=$AGENT_DIR

# Start agent directly
log "Starting agent with python3..."
cd $AGENT_DIR/agent
python3 agent.py