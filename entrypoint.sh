#!/bin/bash
set -euo pipefail

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

log "Starting ServerBond Agent in Docker container..."

# === 1. Download and Run Install Script from GitHub ===
log "Downloading and running install script from GitHub..."
curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/install.sh | bash

# === 2. Health Check ===
log "Performing health check..."
sleep 10

# Check if agent is running
if systemctl is-active --quiet serverbond-agent.service; then
    success "ServerBond Agent service is running!"
    
    # Test HTTP endpoint
    if curl -s http://localhost:8000/health >/dev/null 2>&1; then
        success "Agent HTTP endpoint is active!"
        log "Agent URL: http://localhost:8000"
        log "Traefik Dashboard: http://localhost:8080"
    else
        warn "Agent HTTP endpoint not responding"
    fi
    
    # Show service info
    log "Service status:"
    systemctl status serverbond-agent --no-pager
    
else
    error "Failed to start ServerBond Agent service"
    log "Check service status: systemctl status serverbond-agent"
    log "Check logs: journalctl -u serverbond-agent -f"
fi

# === 3. Keep Container Running ===
log "Container is ready and running..."
log "Available services:"
log "- Agent API: http://localhost:8000"
log "- Traefik Dashboard: http://localhost:8080"
log "- MySQL: localhost:3306"
log "- Redis: localhost:6379"
log "- Sites: https://localhost (via Traefik)"

# Keep the container running
tail -f /var/log/serverbond-agent.log
