#!/usr/bin/env bash
set -euo pipefail

# === MVP ServerBond Agent Installer ===
# Minimal, simple, and reliable installation script

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
    docker.io \
    docker-compose

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

# === 9. Start Base Services ===
log "Starting base services..."
cd "$SHARED_DIR"

# Check if services are already running
if docker ps --format "table {{.Names}}" | grep -q "shared_mysql\\|shared_redis\\|traefik"; then
    log "Base services already running"
else
    # Start services manually
    docker run -d --name shared_mysql --network $NETWORK -e MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASS -e MYSQL_DATABASE=shared_db -p 3306:3306 mysql:8.0
    docker run -d --name shared_redis --network $NETWORK -p 6379:6379 redis:7-alpine
    docker run -d --name traefik --network $NETWORK -p 80:80 -p 443:443 -p 8080:8080 -v /var/run/docker.sock:/var/run/docker.sock:ro traefik:v3.0 --api.dashboard=true --api.insecure=true --providers.docker=true --providers.docker.exposedbydefault=false --entrypoints.web.address=:80 --entrypoints.websecure.address=:443
    success "Base services started"
fi

# === 10. Start Agent ===
log "Starting agent..."

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

# Start agent in background
cd $AGENT_DIR
nohup python3 agent.py > /var/log/serverbond-agent.log 2>&1 &
AGENT_PID=$!
echo $AGENT_PID > /var/run/serverbond-agent.pid

# === 11. Health Check ===
log "Performing health check..."
sleep 5

# Check if agent is running
if kill -0 $AGENT_PID 2>/dev/null; then
    success "ServerBond Agent is running! (PID: $AGENT_PID)"
    
    # Test HTTP endpoint
    if curl -s http://localhost:$AGENT_PORT/health >/dev/null 2>&1; then
        success "Agent HTTP endpoint is active!"
        log "Agent URL: http://$(hostname -I | awk '{print $1}'):$AGENT_PORT"
    else
        warn "Agent HTTP endpoint not responding"
    fi
    
    # Show agent info
    log "Agent PID: $AGENT_PID"
    log "Log file: /var/log/serverbond-agent.log"
    
else
    error "Failed to start ServerBond Agent"
    log "Check logs: tail -f /var/log/serverbond-agent.log"
fi

# === 12. Final Information ===
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
log "3. Check agent logs: tail -f /var/log/serverbond-agent.log"
log "4. Stop agent: kill \$(cat /var/run/serverbond-agent.pid)"
log "5. Start agent: cd $AGENT_DIR && nohup python3 agent.py > /var/log/serverbond-agent.log 2>&1 &"