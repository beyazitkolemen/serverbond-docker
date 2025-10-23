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

# === 7️⃣ Base sistem kurulumu ===
log "Base sistem yapılandırılıyor..."
# Base sistem template'ini render et ve kur
python3 -c "
import json
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

# Config'i yükle
config_path = Path('/opt/serverbond-agent/config.json')
if config_path.exists():
    with open(config_path, 'r') as f:
        config = json.load(f)
else:
    config = {
        'base_system': {
            'traefik_email': 'admin@serverbond.dev',
            'phpmyadmin_domain': 'pma.serverbond.dev'
        },
        'docker': {
            'network': 'shared_net',
            'shared_mysql_container': 'shared_mysql',
            'shared_redis_container': 'shared_redis'
        }
    }

# Base sistem context'i hazırla
base_ctx = {
    'network': config['docker']['network'],
    'shared_mysql_container': config['docker']['shared_mysql_container'],
    'shared_redis_container': config['docker']['shared_redis_container'],
    'traefik_email': config['base_system']['traefik_email'],
    'phpmyadmin_domain': config['base_system']['phpmyadmin_domain'],
    'mysql_root_password': '${MYSQL_ROOT_PASS}'
}

# Base sistem docker-compose.yml'yi render et
base_template_path = Path('/opt/serverbond-agent/base')
if (base_template_path / 'docker-compose.yml.j2').exists():
    env = Environment(loader=FileSystemLoader(str(base_template_path)))
    template = env.get_template('docker-compose.yml.j2')
    content = template.render(base_ctx)
    
    # Docker-compose dosyasını yaz
    with open('${SHARED_DIR}/docker-compose.yml', 'w') as f:
        f.write(content)
    print('Base system template rendered successfully')
else:
    print('Base system template not found, using fallback')
"

docker compose -f "${SHARED_DIR}/docker-compose.yml" up -d
success "Base sistem aktif."

# === 8️⃣ Agent kurulumu ===
log "ServerBond Agent kuruluyor..."
if [[ ! -f "/opt/serverbond-agent/agent.py" ]]; then
  curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/agent/agent.py -o "/opt/serverbond-agent/agent.py"
fi

# Config dosyasını indir
curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/agent/config.json -o "/opt/serverbond-agent/config.json"

# Agent modules dizinini oluştur
mkdir -p "/opt/serverbond-agent/modules"

# Agent modules dosyalarını indir
curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/agent/modules/__init__.py -o "/opt/serverbond-agent/modules/__init__.py"
curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/agent/modules/config.py -o "/opt/serverbond-agent/modules/config.py"
curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/agent/modules/utils.py -o "/opt/serverbond-agent/modules/utils.py"
curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/agent/modules/templates.py -o "/opt/serverbond-agent/modules/templates.py"
curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/agent/modules/api.py -o "/opt/serverbond-agent/modules/api.py"
curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/agent/modules/base_system.py -o "/opt/serverbond-agent/modules/base_system.py"
curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/agent/modules/site_builder.py -o "/opt/serverbond-agent/modules/site_builder.py"

# Agent dosyasını çalıştırılabilir yap
chmod +x "/opt/serverbond-agent/agent.py"

# === 8️⃣ Template'leri indir ===
log "Template'ler indiriliyor..."
mkdir -p "/opt/serverbond-agent/templates"
mkdir -p "/opt/serverbond-agent/base"

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

# Base sistem template'lerini indir
curl -fsSL "https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/base/docker-compose.yml.j2" -o "/opt/serverbond-agent/base/docker-compose.yml.j2"
curl -fsSL "https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/base/serverbond-agent.service.j2" -o "/opt/serverbond-agent/base/serverbond-agent.service.j2"

success "Template'ler başarıyla indirildi."

# === 9️⃣ Python ortamı ===
apt-get install -y python3 python3-pip > /dev/null

# Requirements dosyasını indir
curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/agent/requirements.txt -o "/tmp/requirements.txt"

# Python paketlerini yükle
pip3 install -r /tmp/requirements.txt > /dev/null

# === 🔟 systemd servisi ===
log "systemd servisi oluşturuluyor..."

# Systemd servis dosyasını oluştur
cat > /etc/systemd/system/serverbond-agent.service <<EOF
[Unit]
Description=ServerBond Agent (Docker Multi-site)
Documentation=https://github.com/beyazitkolemen/serverbond-docker
After=network-online.target docker.service
Wants=docker.service
Requires=docker.service

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/serverbond-agent
ExecStart=/usr/bin/python3 /opt/serverbond-agent/agent.py
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=3
StartLimitBurst=5
StartLimitInterval=60s

# Environment variables
Environment=SB_BASE_DIR=${SITES_DIR}
Environment=SB_TEMPLATE_DIR=/opt/serverbond-agent/templates
Environment=SB_NETWORK=${NETWORK}
Environment=SB_CONFIG_DIR=${CONFIG_DIR}
Environment=SB_SHARED_MYSQL_CONTAINER=shared_mysql
Environment=SB_SHARED_REDIS_CONTAINER=shared_redis
Environment=SB_AGENT_TOKEN=${AGENT_TOKEN}
Environment=SB_AGENT_PORT=${AGENT_PORT}
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=/opt/serverbond-agent

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/serverbond-agent /opt/sites /opt/shared-services /var/lib/docker

# Resource limits
LimitNOFILE=65536
LimitNPROC=32768

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=serverbond-agent

[Install]
WantedBy=multi-user.target
EOF

# Systemd daemon'ı reload et
log "Systemd daemon reload ediliyor..."
systemctl daemon-reload

# Servisi enable et
log "Servis enable ediliyor..."
systemctl enable serverbond-agent

# Servisi başlat
log "Servis başlatılıyor..."
systemctl start serverbond-agent

# Servis durumunu kontrol et
log "Servis durumu kontrol ediliyor..."
sleep 3

if systemctl is-active --quiet serverbond-agent; then
    success "ServerBond Agent başarıyla başlatıldı ✅"
    
    # Servis durumunu göster
    log "Servis durumu:"
    systemctl status serverbond-agent --no-pager -l
    
    # Log'ları göster (son 10 satır)
    log "Son log'lar:"
    journalctl -u serverbond-agent --no-pager -n 10
else
    error "ServerBond Agent başlatılamadı ❌"
    log "Hata detayları:"
    systemctl status serverbond-agent --no-pager -l
    log "Log'lar:"
    journalctl -u serverbond-agent --no-pager -n 20
    exit 1
fi

# HTTP health check
log "HTTP health check yapılıyor..."
sleep 2
if curl -s http://localhost:${AGENT_PORT}/health >/dev/null; then
    success "Agent HTTP endpoint aktif! ✅"
    log "Agent URL: http://$(hostname -I | awk '{print $1}'):${AGENT_PORT}"
else
    error "Agent HTTP endpoint yanıt vermiyor ❌"
    log "Port ${AGENT_PORT} kontrol ediliyor..."
    if netstat -tlnp | grep -q ":${AGENT_PORT} "; then
        log "Port ${AGENT_PORT} dinleniyor ama health check başarısız"
    else
        log "Port ${AGENT_PORT} dinlenmiyor"
    fi
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
