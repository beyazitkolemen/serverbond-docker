#!/usr/bin/env bash
set -euo pipefail

# === MVP ServerBond Agent Installer ===
# Simple, modern, and reliable installation script

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
    python3-venv \
    python3-dev \
    gcc \
    build-essential \
    ca-certificates \
    gnupg \
    lsb-release

# === 4. Install Docker ===
log "Installing Docker..."
if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker $USER 2>/dev/null || true
else
    log "Docker already installed"
fi

# Start Docker if not running
if ! docker info >/dev/null 2>&1; then
    log "Starting Docker daemon..."
    systemctl start docker 2>/dev/null || service docker start 2>/dev/null || true
    sleep 3
fi

# === 5. Install Python Dependencies ===
log "Installing Python dependencies..."
pip3 install --break-system-packages -q \
    jinja2 \
    psutil \
    requests \
    docker \
    flask

# === 6. Create Directories ===
log "Creating directories..."
mkdir -p "$AGENT_DIR" "$SITES_DIR" "$SHARED_DIR" "$SITES_DIR"

# === 7. Download Agent Files ===
log "Downloading agent files..."
cd /tmp
git clone -q https://github.com/beyazitkolemen/serverbond-docker.git

# Copy agent files
cp -r serverbond-docker/agent/* "$AGENT_DIR/"
cp -r serverbond-docker/templates "$AGENT_DIR/"
cp -r serverbond-docker/base "$AGENT_DIR/"

# Cleanup
rm -rf serverbond-docker

# === 8. Create Docker Network ===
log "Creating Docker network..."
docker network create "$NETWORK" 2>/dev/null || log "Network already exists"

# === 9. Generate Base System ===
log "Generating base system configuration..."

# Generate MySQL password
MYSQL_ROOT_PASS="$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)"
echo "$MYSQL_ROOT_PASS" > "$SHARED_DIR/mysql_root_password.txt"

# Create simple docker-compose.yml
cat > "$SHARED_DIR/docker-compose.yml" << EOF
version: '3.8'
services:
  shared_mysql:
    image: mysql:8.0
    container_name: shared_mysql
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: $MYSQL_ROOT_PASS
      MYSQL_DATABASE: shared_db
    volumes:
      - mysql_data:/var/lib/mysql
    networks:
      - $NETWORK
    ports:
      - "3306:3306"

  shared_redis:
    image: redis:7-alpine
    container_name: shared_redis
    restart: unless-stopped
    networks:
      - $NETWORK
    ports:
      - "6379:6379"

  traefik:
    image: traefik:v3.0
    container_name: traefik
    restart: unless-stopped
    command:
      - --api.dashboard=true
      - --api.insecure=true
      - --providers.docker=true
      - --providers.docker.exposedbydefault=false
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - traefik_data:/letsencrypt
    networks:
      - $NETWORK

volumes:
  mysql_data:
  traefik_data:

networks:
  $NETWORK:
    external: true
EOF

# === 10. Start Base Services ===
log "Starting base services..."
cd "$SHARED_DIR"

# Check if services are already running
if docker compose ps --services --filter "status=running" | grep -q "shared_mysql\|shared_redis\|traefik"; then
    log "Base services already running"
else
    docker compose up -d
    success "Base services started"
fi

# === 11. Create Systemd Service ===
log "Creating systemd service..."
cat > /etc/systemd/system/serverbond-agent.service << EOF
[Unit]
Description=ServerBond Agent
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=$AGENT_DIR
ExecStart=/usr/bin/python3 $AGENT_DIR/agent.py
Restart=always
RestartSec=5

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

# === 12. Start Agent Service ===
log "Starting agent service..."
systemctl daemon-reload
systemctl enable serverbond-agent
systemctl start serverbond-agent

# === 13. Health Check ===
log "Performing health check..."
sleep 5

if systemctl is-active --quiet serverbond-agent; then
    success "ServerBond Agent is running!"
    
    # Test HTTP endpoint
    if curl -s http://localhost:$AGENT_PORT/health >/dev/null 2>&1; then
        success "Agent HTTP endpoint is active!"
        log "Agent URL: http://$(hostname -I | awk '{print $1}'):$AGENT_PORT"
    else
        warn "Agent HTTP endpoint not responding"
    fi
    
    # Show service status
    log "Service status:"
    systemctl status serverbond-agent --no-pager -l
    
else
    error "Failed to start ServerBond Agent"
fi

# === 14. Final Information ===
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
log "3. Check agent logs: journalctl -u serverbond-agent -f"