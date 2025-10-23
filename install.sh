#!/usr/bin/env bash
set -euo pipefail

# Ensure we're running with bash, not sh
if [ -z "${BASH_VERSION:-}" ]; then
    echo "Error: This script requires bash, not sh"
    echo "Please run with: bash $0"
    exit 1
fi

# === UTILITY FUNCTIONS ===
log_info() { 
    echo -e "\033[1;36m[INFO]\033[0m $*"
}

success() { 
    echo -e "\033[1;32m[SUCCESS]\033[0m $*"
}

error() { 
    echo -e "\033[1;31m[ERROR]\033[0m $*" >&2
    exit 1
}

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
  log_info "Mevcut MySQL root şifresi kullanılıyor"
else
  MYSQL_ROOT_PASS="$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)"
  mkdir -p "${CONFIG_DIR}" 2>/dev/null || true
  echo "${MYSQL_ROOT_PASS}" > "${MYSQL_ROOT_PASS_FILE}" 2>/dev/null || true
  chmod 600 "${MYSQL_ROOT_PASS_FILE}" 2>/dev/null || true
  log_info "Yeni MySQL root şifresi oluşturuldu ve kaydedildi"
fi

# === 1️⃣ Root check ===
if [[ $EUID -ne 0 ]]; then
  error "Bu script root olarak çalıştırılmalıdır."
fi

# === 2️⃣ Sistem hazırlığı ===
log_info "Sistem güncelleniyor..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl git jq lsb-release ufw openssl > /dev/null

# === 3️⃣ Docker kurulumu ===
if ! command -v docker >/dev/null 2>&1; then
  log_info "Docker yükleniyor..."
  curl -fsSL https://get.docker.com | bash
  systemctl enable docker
fi

# Docker daemon'ı başlat
log_info "Docker daemon başlatılıyor..."
systemctl start docker
sleep 3

# Docker daemon'ın çalıştığını kontrol et
if ! docker info >/dev/null 2>&1; then
  error "Docker daemon başlatılamadı. Lütfen manuel olarak başlatın: sudo systemctl start docker"
fi

# === 4️⃣ Docker Compose kurulumu ===
if ! command -v docker compose >/dev/null 2>&1; then
  log_info "Docker Compose (v2) kuruluyor..."
  mkdir -p /usr/local/lib/docker/cli-plugins
  curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m) \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi

# === 5️⃣ Ortak network ===
log_info "Shared network oluşturuluyor: ${NETWORK}"
docker network create "${NETWORK}" || true

# === 6️⃣ Dizin yapısı ===
mkdir -p "${BASE_DIR}" "${SITES_DIR}" "${SHARED_DIR}"/{data,backups,logs}

# === 6.5️⃣ Python ortamı (jinja2 için gerekli) ===
log_info "Python ortamı hazırlanıyor..."
apt-get install -y python3 python3-pip python3-venv python3-full python3-dev gcc build-essential > /dev/null

# Requirements dosyasını indir
curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/agent/requirements.txt -o "/tmp/requirements.txt"

# Python paketlerini yükle (externally managed environment için)
log_info "Python paketleri yükleniyor..."

# psutil'i sistem paketinden kurmayı dene (tercih edilen)
log_info "psutil (apt) kuruluyor..."
apt-get install -y -qq python3-psutil > /dev/null || true

# psutil import kontrolü; başarısızsa pip ile yükle
if ! python3 -c "import psutil" >/dev/null 2>&1; then
  log_info "psutil apt ile bulunamadı, pip ile kuruluyor..."
  pip3 install --break-system-packages psutil > /dev/null
fi

# requirements.txt içinden psutil satırını çıkar ve diğer paketleri kur
grep -vi '^psutil' /tmp/requirements.txt > /tmp/requirements.nopsutil.txt || true
log_info "Diğer Python paketleri yükleniyor..."
pip3 install --break-system-packages -r /tmp/requirements.nopsutil.txt > /dev/null

# Jinja2'nin yüklendiğini kontrol et
if ! python3 -c "import jinja2" >/dev/null 2>&1; then
  log_info "Jinja2 manuel olarak yükleniyor..."
  pip3 install --break-system-packages jinja2 > /dev/null
fi

# === 7️⃣ Base sistem kurulumu ===
log_info "Base sistem yapılandırılıyor..."

# Base sistem render script'ini oluştur
cat > /tmp/render_base_system.py << 'PYTHON_EOF'
import json
import sys
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

def main():
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
    mysql_root_pass = sys.argv[1] if len(sys.argv) > 1 else 'default_password'
    shared_dir = sys.argv[2] if len(sys.argv) > 2 else '/opt/shared-services'
    
    base_ctx = {
        'network': config['docker']['network'],
        'shared_mysql_container': config['docker']['shared_mysql_container'],
        'shared_redis_container': config['docker']['shared_redis_container'],
        'traefik_email': config['base_system']['traefik_email'],
        'phpmyadmin_domain': config['base_system']['phpmyadmin_domain'],
        'mysql_root_password': mysql_root_pass
    }

    # Base sistem docker-compose.yml'yi render et
    base_template_path = Path('/opt/serverbond-agent/base')
    if (base_template_path / 'docker-compose.yml.j2').exists():
        env = Environment(loader=FileSystemLoader(str(base_template_path)))
        template = env.get_template('docker-compose.yml.j2')
        content = template.render(base_ctx)
        
        # Docker-compose dosyasını yaz
        with open(f'{shared_dir}/docker-compose.yml', 'w') as f:
            f.write(content)
        print('Base system template rendered successfully')
    else:
        print('Base system template not found, using fallback')
        # Fallback: Basit bir docker-compose.yml oluştur
        fallback_content = f'''version: '3.8'
services:
  shared_mysql:
    image: mysql:8.0
    container_name: shared_mysql
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: {base_ctx['mysql_root_password']}
      MYSQL_DATABASE: shared_db
    volumes:
      - mysql_data:/var/lib/mysql
    networks:
      - {base_ctx['network']}
    ports:
      - "3306:3306"

  shared_redis:
    image: redis:7-alpine
    container_name: shared_redis
    restart: unless-stopped
    networks:
      - {base_ctx['network']}
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
      - --certificatesresolvers.letsencrypt.acme.email={base_ctx['traefik_email']}
      - --certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json
      - --certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - traefik_data:/letsencrypt
    networks:
      - {base_ctx['network']}

  phpmyadmin:
    image: phpmyadmin/phpmyadmin
    container_name: phpmyadmin
    restart: unless-stopped
    environment:
      PMA_HOST: shared_mysql
      PMA_PORT: 3306
    networks:
      - {base_ctx['network']}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.phpmyadmin.rule=Host:pma.serverbond.dev"
      - "traefik.http.routers.phpmyadmin.tls=true"
      - "traefik.http.routers.phpmyadmin.tls.certresolver=letsencrypt"

volumes:
  mysql_data:
  traefik_data:

networks:
  {base_ctx['network']}:
    external: true
'''
        with open(f'{shared_dir}/docker-compose.yml', 'w') as f:
            f.write(fallback_content)
        print('Fallback docker-compose.yml created successfully')

if __name__ == '__main__':
    main()
PYTHON_EOF

# Python script'ini çalıştır
python3 /tmp/render_base_system.py "${MYSQL_ROOT_PASS}" "${SHARED_DIR}"

docker compose -f "${SHARED_DIR}/docker-compose.yml" up -d
success "Base sistem aktif."

# === 8️⃣ Agent kurulumu ===
log_info "ServerBond Agent kuruluyor..."
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
log_info "Template'ler indiriliyor..."
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

# === 9️⃣ Python ortamı (zaten yukarıda kuruldu) ===

# === 🔟 systemd servisi ===
log_info "systemd servisi oluşturuluyor..."

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
log_info "Systemd daemon reload ediliyor..."
systemctl daemon-reload

# Servisi enable et
log_info "Servis enable ediliyor..."
systemctl enable serverbond-agent

# Servisi başlat
log_info "Servis başlatılıyor..."
systemctl start serverbond-agent

# Servis durumunu kontrol et
log_info "Servis durumu kontrol ediliyor..."
sleep 3

if systemctl is-active --quiet serverbond-agent; then
    success "ServerBond Agent başarıyla başlatıldı ✅"
    
    # Servis durumunu göster
    log_info "Servis durumu:"
    systemctl status serverbond-agent --no-pager -l
    
    # Log'ları göster (son 10 satır)
    log_info "Son log'lar:"
    journalctl -u serverbond-agent --no-pager -n 10
else
    error "ServerBond Agent başlatılamadı ❌"
    log_info "Hata detayları:"
    systemctl status serverbond-agent --no-pager -l
    log_info "Log'lar:"
    journalctl -u serverbond-agent --no-pager -n 20
    exit 1
fi

# HTTP health check
log_info "HTTP health check yapılıyor..."
sleep 2
if curl -s http://localhost:${AGENT_PORT}/health >/dev/null; then
    success "Agent HTTP endpoint aktif! ✅"
    log_info "Agent URL: http://$(hostname -I | awk '{print $1}'):${AGENT_PORT}"
else
    error "Agent HTTP endpoint yanıt vermiyor ❌"
    log_info "Port ${AGENT_PORT} kontrol ediliyor..."
    if netstat -tlnp | grep -q ":${AGENT_PORT} "; then
        log_info "Port ${AGENT_PORT} dinleniyor ama health check başarısız"
    else
        log_info "Port ${AGENT_PORT} dinlenmiyor"
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
