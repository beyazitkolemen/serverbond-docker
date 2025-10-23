#!/usr/bin/env bash
set -euo pipefail

# === GLOBAL CONFIG ===
AGENT_VERSION="3.0"
BASE_DIR="/opt/serverbond-agent"
SITES_DIR="/opt/sites"
SHARED_DIR="/opt/shared-services"
NETWORK="shared_net"
AGENT_PORT=8000
CONFIG_DIR="/opt/serverbond-config"
AGENT_TOKEN="${AGENT_TOKEN:-$(openssl rand -hex 16)}"
UBUNTU_CODENAME="$(lsb_release -cs 2>/dev/null || echo 'noble')"

# === MySQL Root Password Generation ===
MYSQL_ROOT_PASS_FILE="${CONFIG_DIR}/mysql_root_password.txt"
if [[ -f "${MYSQL_ROOT_PASS_FILE}" ]]; then
  MYSQL_ROOT_PASS="$(cat ${MYSQL_ROOT_PASS_FILE})"
  log "Mevcut MySQL root şifresi kullanılıyor"
else
  MYSQL_ROOT_PASS="$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)"
  mkdir -p "${CONFIG_DIR}"
  echo "${MYSQL_ROOT_PASS}" > "${MYSQL_ROOT_PASS_FILE}"
  chmod 600 "${MYSQL_ROOT_PASS_FILE}"
  log "Yeni MySQL root şifresi oluşturuldu ve kaydedildi"
fi

log() { echo -e "\033[1;36m[INFO]\033[0m $*"; }
success() { echo -e "\033[1;32m[SUCCESS]\033[0m $*"; }
error() { echo -e "\033[1;31m[ERROR]\033[0m $*" >&2; exit 1; }

# === 1️⃣ Root check ===
if [[ $EUID -ne 0 ]]; then
  error "Bu script root olarak çalıştırılmalıdır."
fi

# === 2️⃣ Sistem hazırlığı ===
log "Sistem güncelleniyor..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl git jq lsb-release ufw openssl > /dev/null

# === 3️⃣ Docker kurulumu ===
if ! command -v docker >/dev/null 2>&1; then
  log "Docker yükleniyor..."
  curl -fsSL https://get.docker.com | bash
  systemctl enable docker
fi

# === 4️⃣ Docker Compose kurulumu ===
if ! command -v docker compose >/dev/null 2>&1; then
  log "Docker Compose (v2) kuruluyor..."
  mkdir -p /usr/local/lib/docker/cli-plugins
  curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m) \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi

# === 5️⃣ Ortak network ===
log "Shared network oluşturuluyor: ${NETWORK}"
docker network create "${NETWORK}" || true

# === 6️⃣ Dizin yapısı ===
mkdir -p "${BASE_DIR}" "${SITES_DIR}" "${SHARED_DIR}"/{data,backups,logs}

# === 7️⃣ Traefik kurulumu ===
log "Traefik reverse proxy yapılandırılıyor..."
cat > "${SHARED_DIR}/docker-compose.yml" <<EOF
version: '3.9'
services:
  traefik:
    image: traefik:v3.0
    container_name: traefik
    restart: always
    command:
      - "--api.dashboard=true"
      - "--api.insecure=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--certificatesresolvers.mytls.acme.tlschallenge=true"
      - "--certificatesresolvers.mytls.acme.email=admin@serverbond.dev"
      - "--certificatesresolvers.mytls.acme.storage=/letsencrypt/acme.json"
      - "--accesslog=true"
      - "--log.level=INFO"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./letsencrypt:/letsencrypt
    networks:
      - ${NETWORK}

  mysql:
    image: mysql:8.4
    container_name: shared_mysql
    restart: always
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASS}
    volumes:
      - ./data/mysql:/var/lib/mysql
      - ./backups:/backups
    networks: [${NETWORK}]

  redis:
    image: redis:7
    container_name: shared_redis
    restart: always
    command: ["redis-server", "--save", "60", "1", "--loglevel", "warning"]
    volumes:
      - ./data/redis:/data
    networks: [${NETWORK}]

  phpmyadmin:
    image: phpmyadmin:latest
    container_name: phpmyadmin
    environment:
      PMA_HOST: shared_mysql
      PMA_USER: root
      PMA_PASSWORD: ${MYSQL_ROOT_PASS}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.pma.rule=Host(\`pma.serverbond.dev\`)"
      - "traefik.http.routers.pma.entrypoints=websecure"
      - "traefik.http.routers.pma.tls.certresolver=mytls"
    networks: [${NETWORK}]

networks:
  ${NETWORK}:
    external: true
EOF

docker compose -f "${SHARED_DIR}/docker-compose.yml" up -d
success "Traefik ve shared servisler aktif."

# === 8️⃣ Agent kurulumu ===
log "ServerBond Agent kuruluyor..."
if [[ ! -f "/opt/serverbond-agent/agent.py" ]]; then
  curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/agent/agent.py -o "/opt/serverbond-agent/agent.py"
fi

# Config dosyasını indir
curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/agent/config.json -o "/opt/serverbond-agent/config.json"

# Agent dosyasını çalıştırılabilir yap
chmod +x "/opt/serverbond-agent/agent.py"

# === 8️⃣ Template'leri indir ===
log "Template'ler indiriliyor..."
mkdir -p "/opt/serverbond-agent/templates"

# Template dosyalarını GitHub'dan indir
TEMPLATE_URL="https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/templates"

# Laravel template
mkdir -p "/opt/serverbond-agent/templates/laravel"
curl -fsSL "${TEMPLATE_URL}/laravel/docker-compose.yml.j2" -o "/opt/serverbond-agent/templates/laravel/docker-compose.yml.j2"
curl -fsSL "${TEMPLATE_URL}/laravel/Dockerfile.j2" -o "/opt/serverbond-agent/templates/laravel/Dockerfile.j2"
curl -fsSL "${TEMPLATE_URL}/laravel/nginx.conf.j2" -o "/opt/serverbond-agent/templates/laravel/nginx.conf.j2"
curl -fsSL "${TEMPLATE_URL}/laravel/supervisord.conf.j2" -o "/opt/serverbond-agent/templates/laravel/supervisord.conf.j2"

# Laravel Inertia template
mkdir -p "/opt/serverbond-agent/templates/laravel-inertia"
curl -fsSL "${TEMPLATE_URL}/laravel-inertia/docker-compose.yml.j2" -o "/opt/serverbond-agent/templates/laravel-inertia/docker-compose.yml.j2"
curl -fsSL "${TEMPLATE_URL}/laravel-inertia/Dockerfile.j2" -o "/opt/serverbond-agent/templates/laravel-inertia/Dockerfile.j2"
curl -fsSL "${TEMPLATE_URL}/laravel-inertia/nginx.conf.j2" -o "/opt/serverbond-agent/templates/laravel-inertia/nginx.conf.j2"
curl -fsSL "${TEMPLATE_URL}/laravel-inertia/supervisord.conf.j2" -o "/opt/serverbond-agent/templates/laravel-inertia/supervisord.conf.j2"

# Next.js template
mkdir -p "/opt/serverbond-agent/templates/nextjs"
curl -fsSL "${TEMPLATE_URL}/nextjs/docker-compose.yml.j2" -o "/opt/serverbond-agent/templates/nextjs/docker-compose.yml.j2"
curl -fsSL "${TEMPLATE_URL}/nextjs/Dockerfile.j2" -o "/opt/serverbond-agent/templates/nextjs/Dockerfile.j2"
curl -fsSL "${TEMPLATE_URL}/nextjs/next.config.js.j2" -o "/opt/serverbond-agent/templates/nextjs/next.config.js.j2"

# Node.js API template
mkdir -p "/opt/serverbond-agent/templates/nodeapi"
curl -fsSL "${TEMPLATE_URL}/nodeapi/docker-compose.yml.j2" -o "/opt/serverbond-agent/templates/nodeapi/docker-compose.yml.j2"
curl -fsSL "${TEMPLATE_URL}/nodeapi/Dockerfile.j2" -o "/opt/serverbond-agent/templates/nodeapi/Dockerfile.j2"
curl -fsSL "${TEMPLATE_URL}/nodeapi/package.json.j2" -o "/opt/serverbond-agent/templates/nodeapi/package.json.j2"
curl -fsSL "${TEMPLATE_URL}/nodeapi/tsconfig.json.j2" -o "/opt/serverbond-agent/templates/nodeapi/tsconfig.json.j2"

# Nuxt template
mkdir -p "/opt/serverbond-agent/templates/nuxt"
curl -fsSL "${TEMPLATE_URL}/nuxt/docker-compose.yml.j2" -o "/opt/serverbond-agent/templates/nuxt/docker-compose.yml.j2"
curl -fsSL "${TEMPLATE_URL}/nuxt/Dockerfile.j2" -o "/opt/serverbond-agent/templates/nuxt/Dockerfile.j2"
curl -fsSL "${TEMPLATE_URL}/nuxt/nuxt.config.ts.j2" -o "/opt/serverbond-agent/templates/nuxt/nuxt.config.ts.j2"

# Static template
mkdir -p "/opt/serverbond-agent/templates/static"
curl -fsSL "${TEMPLATE_URL}/static/docker-compose.yml.j2" -o "/opt/serverbond-agent/templates/static/docker-compose.yml.j2"
curl -fsSL "${TEMPLATE_URL}/static/Dockerfile.j2" -o "/opt/serverbond-agent/templates/static/Dockerfile.j2"
curl -fsSL "${TEMPLATE_URL}/static/nginx.conf.j2" -o "/opt/serverbond-agent/templates/static/nginx.conf.j2"
curl -fsSL "${TEMPLATE_URL}/static/index.html.j2" -o "/opt/serverbond-agent/templates/static/index.html.j2"

success "Template'ler başarıyla indirildi."

# === 9️⃣ Python ortamı ===
apt-get install -y python3 python3-pip > /dev/null
pip3 install fastapi uvicorn jinja2 pydantic aiofiles > /dev/null

# === 🔟 systemd servisi ===
log "systemd servisi oluşturuluyor..."
cat > /etc/systemd/system/serverbond-agent.service <<EOF
[Unit]
Description=ServerBond Agent (Docker Multi-site)
After=network-online.target docker.service
Wants=docker.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/serverbond-agent/agent.py
WorkingDirectory=/opt/serverbond-agent
Restart=always
RestartSec=3
User=root
Group=root
Environment=SB_BASE_DIR=${SITES_DIR}
Environment=SB_TEMPLATE_DIR=/opt/serverbond-agent/templates
Environment=SB_NETWORK=${NETWORK}
Environment=SB_CONFIG_DIR=${CONFIG_DIR}
Environment=SB_SHARED_MYSQL_CONTAINER=shared_mysql
Environment=SB_SHARED_REDIS_CONTAINER=shared_redis
Environment=SB_AGENT_TOKEN=${AGENT_TOKEN}
Environment=SB_AGENT_PORT=${AGENT_PORT}
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now serverbond-agent

success "ServerBond Agent yüklendi."
log "Agent çalışıyor mu kontrol ediliyor..."
sleep 3
if curl -s http://localhost:8000/health >/dev/null; then
  success "Agent aktif! ✅"
else
  error "Agent servisi başlatılamadı. 'journalctl -u serverbond-agent' ile logları kontrol et."
fi

# === 11️⃣ Firewall yapılandırması ===
ufw allow 22/tcp
ufw allow 80,443/tcp
ufw allow ${AGENT_PORT}/tcp
ufw --force enable

# === 12️⃣ Son bilgi ===
cat <<INFO

✅ Kurulum tamamlandı!

Agent URL     : http://$(hostname -I | awk '{print $1}'):${AGENT_PORT}
Agent Token   : ${AGENT_TOKEN}

Shared Servisler:
  - MySQL       : shared_mysql (root şifresi: ${CONFIG_DIR}/mysql_root_password.txt)
  - Redis       : shared_redis
  - phpMyAdmin  : https://pma.serverbond.dev
  - Traefik     : https://<sunucu-ip> (dashboard port 8080 opsiyonel)

ÖNEMLİ BİLGİLER:
  - MySQL root şifresi: ${CONFIG_DIR}/mysql_root_password.txt dosyasında saklanıyor
  - Şifre dosyası sadece root tarafından okunabilir (chmod 600)
  - Agent Token: ${AGENT_TOKEN}

Yeni site eklemek için Panel veya API üzerinden şu endpoint'i çağır:
POST /build  (Agent)

Örnek:
curl -X POST http://localhost:${AGENT_PORT}/build \\
  -H "X-Agent-Token: ${AGENT_TOKEN}" \\
  -H "Content-Type: application/json" \\
  -d '{"repo":"https://github.com/org/project.git","domain":"project.serverbond.dev"}'

INFO
