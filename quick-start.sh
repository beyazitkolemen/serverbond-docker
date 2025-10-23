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

log "ServerBond Agent - Quick Start with Docker"
log "=========================================="
log "This will create an Ubuntu 24.04 container (independent server) and run:"
log "curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/install.sh | bash"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    error "Docker is not installed. Please install Docker first."
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    error "Docker Compose is not installed. Please install Docker Compose first."
fi

log "Starting ServerBond Agent with Docker..."

# Build and start containers
log "Building and starting containers..."
docker-compose up -d --build

# Wait for services to be ready
log "Waiting for services to be ready..."
sleep 30

# Check if agent is running
log "Checking agent status..."
if curl -s http://localhost:8000/health >/dev/null 2>&1; then
    success "ServerBond Agent is running!"
    log "Agent URL: http://localhost:8000"
    log "Traefik Dashboard: http://localhost:8080"
    log "MySQL: localhost:3306"
    log "Redis: localhost:6379"
else
    warn "Agent is not responding yet. Check logs with: docker-compose logs -f"
fi

log "Container management commands:"
log "- View logs: docker-compose logs -f"
log "- Stop: docker-compose down"
log "- Restart: docker-compose restart"
log "- Status: docker-compose ps"

success "ServerBond Agent setup completed!"
