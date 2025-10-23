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
    docker.io \
    docker-compose \
    supervisor

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

# === 7. Create Docker Network ===
log "Creating Docker network..."
docker network create "$NETWORK" 2>/dev/null || log "Network already exists"

# === 8. Generate Base System ===
log "Generating base system configuration..."

# Generate MySQL password
MYSQL_ROOT_PASS="$(openssl rand -base64 32 | tr -d '=+/' | cut -c1-25)"
echo "$MYSQL_ROOT_PASS" > "$SHARED_DIR/mysql_root_password.txt"

# === 9. Start Base Services ===
log "Starting base services..."

# Check if services are already running
if docker ps --format "{{.Names}}" | grep -q "shared_mysql\|shared_redis\|traefik"; then
    log "Base services already running"
else
    # Start MySQL
    log "Starting MySQL..."
    docker run -d --name shared_mysql --network $NETWORK \
        -e MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASS \
        -e MYSQL_DATABASE=shared_db \
        -p 3306:3306 \
        mysql:8.0 || log "MySQL container already exists"
    
    # Start Redis
    log "Starting Redis..."
    docker run -d --name shared_redis --network $NETWORK \
        -p 6379:6379 \
        redis:7-alpine || log "Redis container already exists"
    
    # Start Traefik
    log "Starting Traefik..."
    docker run -d --name traefik --network $NETWORK \
        -p 443:443 -p 8080:8080 \
        -v /var/run/docker.sock:/var/run/docker.sock:ro \
        traefik:v3.0 \
        --api.dashboard=true \
        --api.insecure=true \
        --providers.docker=true \
        --providers.docker.exposedbydefault=false \
        --entrypoints.websecure.address=:443 || log "Traefik container already exists"
    
    success "Base services started"
fi

# === 10. Setup Supervisor ===
log "Setting up supervisor..."

# Create supervisor log directory
mkdir -p /var/log/supervisor

# Copy supervisor configuration
cp "$AGENT_DIR/supervisord.conf" /etc/supervisor/conf.d/serverbond-agent.conf

# Copy systemd service file
cp "$AGENT_DIR/serverbond-agent.service" /etc/systemd/system/

# Start service with supervisor
log "Starting agent with supervisor..."
supervisorctl reread
supervisorctl update
supervisorctl start serverbond-agent

# === 11. Start Agent ===
log "Starting agent with supervisor..."

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

# Start supervisor service
systemctl start serverbond-agent.service

# === 12. Health Check ===
log "Performing health check..."
sleep 5

# Check if supervisor service is running
if systemctl is-active --quiet serverbond-agent.service; then
    success "ServerBond Agent service is running!"
    
    # Test HTTP endpoint
    if curl -s http://localhost:$AGENT_PORT/health >/dev/null 2>&1; then
        success "Agent HTTP endpoint is active!"
        log "Agent URL: http://$(hostname -I | awk '{print $1}'):$AGENT_PORT"
    else
        warn "Agent HTTP endpoint not responding"
    fi
    
    # Show service info
    log "Service status: systemctl status serverbond-agent"
    log "Log files: /var/log/supervisor/serverbond-agent*.log"
    log "Supervisor control: supervisorctl -c $AGENT_DIR/supervisord.conf"
    
else
    error "Failed to start ServerBond Agent service"
    log "Check service status: systemctl status serverbond-agent"
    log "Check logs: journalctl -u serverbond-agent -f"
fi

# === 13. Final Information ===
success "ServerBond Agent installation completed!"
log "Agent is running on port $AGENT_PORT"
log "Base services: MySQL (3306), Redis (6379), Traefik (80/443/8080)"
log "Agent directory: $AGENT_DIR"
log "Sites directory: $SITES_DIR"
log "Shared services: $SHARED_DIR"

echo
log "Next steps:"
log "1. Access Traefik dashboard: http://$(hostname -I | awk '{print $1}'):8080"
log "2. Create your first site using the agent API"
log "3. Check agent logs: tail -f /var/log/supervisor/serverbond-agent.log"
log "4. Service management:"
log "   - Status: systemctl status serverbond-agent"
log "   - Stop: systemctl stop serverbond-agent"
log "   - Start: systemctl start serverbond-agent"
log "   - Restart: systemctl restart serverbond-agent"
log "5. Supervisor control:"
log "   - Status: supervisorctl -c $AGENT_DIR/supervisord.conf status"
log "   - Restart: supervisorctl -c $AGENT_DIR/supervisord.conf restart serverbond-agent"
log "   - Logs: supervisorctl -c $AGENT_DIR/supervisord.conf tail serverbond-agent"