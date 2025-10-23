# ServerBond Agent - Docker Setup

Bu dokümantasyon, ServerBond Agent'ı Docker container'da Ubuntu 24.04 ile çalıştırmak için gerekli adımları açıklar. Container içinde GitHub'dan install.sh scripti çalıştırılır.

## 🚀 Hızlı Başlangıç

### 1. Gereksinimler
- Docker
- Docker Compose
- En az 4GB RAM
- En az 10GB disk alanı

### 2. Kurulum
```bash
# Repository'yi klonlayın
git clone https://github.com/beyazitkolemen/serverbond-docker.git
cd serverbond-docker

# Docker Compose ile başlatın
docker-compose up -d

# Logları takip edin
docker-compose logs -f serverbond-agent
```

### 3. Nasıl Çalışır?
1. **Ubuntu 24.04** container'ı oluşturulur
2. **GitHub'dan** install.sh scripti indirilir: `curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/install.sh | bash`
3. **install.sh** scripti çalıştırılır
4. **Agent** supervisor ile başlatılır
5. **Bağımsız Ubuntu sunucu** gibi davranır

### 4. Servisleri Kontrol Edin
```bash
# Container durumu
docker-compose ps

# Agent health check
curl http://localhost:8000/health

# Traefik dashboard
open http://localhost:8080
```

## 📋 Servisler

### Agent API
- **URL**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health

### Traefik Dashboard
- **URL**: http://localhost:8080
- **Özellikler**: Reverse proxy, SSL termination, load balancing

### MySQL Database
- **Host**: localhost
- **Port**: 3306
- **Database**: shared_db
- **Password**: `/opt/shared-services/mysql_root_password.txt`

### Redis Cache
- **Host**: localhost
- **Port**: 6379
- **Özellikler**: Session storage, caching

## 🔧 Yönetim Komutları

### Container Yönetimi
```bash
# Başlat
docker-compose up -d

# Durdur
docker-compose down

# Restart
docker-compose restart

# Logları görüntüle
docker-compose logs -f

# Container'a bağlan
docker-compose exec serverbond-agent bash
```

### Agent Yönetimi
```bash
# Agent durumu
curl http://localhost:8000/status

# Agent'ı güncelle
curl -X POST http://localhost:8000/update

# Agent'ı restart et
curl -X POST http://localhost:8000/restart

# Supervisor durumu
curl http://localhost:8000/supervisor-status
```

### Supervisor Yönetimi
```bash
# Container'a bağlan
docker-compose exec serverbond-agent bash

# Supervisor durumu
supervisorctl -c /opt/serverbond-agent/agent/supervisord.conf status

# Agent restart
supervisorctl -c /opt/serverbond-agent/agent/supervisord.conf restart serverbond-agent

# Logları takip et
supervisorctl -c /opt/serverbond-agent/agent/supervisord.conf tail serverbond-agent
```

## 🌐 Site Oluşturma

### 1. Yeni Site Oluştur
```bash
curl -X POST http://localhost:8000/build \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-laravel-app",
    "framework": "laravel",
    "domain": "my-app.local"
  }'
```

### 2. Site Durumunu Kontrol Et
```bash
curl http://localhost:8000/sites/my-laravel-app/status
```

### 3. Site'i Başlat
```bash
curl -X POST http://localhost:8000/sites/my-laravel-app/start
```

## 📁 Volume Yapısı

```
serverbond-sites/          # Site dosyaları
serverbond-shared/         # Paylaşılan servisler
serverbond-logs/           # Log dosyaları
serverbond-supervisor/     # Supervisor logları
docker-data/               # Docker-in-Docker verileri
```

## 🔍 Troubleshooting

### 1. Container Başlamıyor
```bash
# Logları kontrol et
docker-compose logs serverbond-agent

# Container'a bağlan
docker-compose exec serverbond-agent bash

# Supervisor durumu
supervisorctl -c /opt/serverbond-agent/agent/supervisord.conf status
```

### 2. Agent API Yanıt Vermiyor
```bash
# Health check
curl http://localhost:8000/health

# Port kontrolü
docker-compose ps

# Network kontrolü
docker network ls
```

### 3. Docker-in-Docker Sorunu
```bash
# Docker socket kontrolü
docker-compose exec serverbond-agent docker info

# Container restart
docker-compose restart docker-in-docker
```

### 4. Log Dosyaları
```bash
# Agent logları
docker-compose exec serverbond-agent tail -f /var/log/supervisor/serverbond-agent.log

# Supervisor logları
docker-compose exec serverbond-agent tail -f /var/log/supervisor/supervisord.log

# System logları
docker-compose logs -f
```

## 🚀 Production Kullanımı

### 1. Environment Variables
```bash
# .env dosyası oluşturun
cat > .env << EOF
SB_AGENT_TOKEN=your-secure-token-here
SB_AGENT_PORT=8000
MYSQL_ROOT_PASSWORD=your-mysql-password
EOF
```

### 2. Docker Compose Override
```yaml
# docker-compose.override.yml
version: '3.8'
services:
  serverbond-agent:
    environment:
      - SB_AGENT_TOKEN=${SB_AGENT_TOKEN}
      - SB_AGENT_PORT=${SB_AGENT_PORT}
    volumes:
      - ./custom-templates:/opt/serverbond-agent/templates
```

### 3. SSL Sertifikası
```bash
# Let's Encrypt ile SSL
docker-compose exec serverbond-agent bash
# Traefik dashboard'da SSL konfigürasyonu yapın
```

## 📊 Monitoring

### 1. Health Checks
```bash
# Agent health
curl http://localhost:8000/health

# System status
curl http://localhost:8000/status

# Git status
curl http://localhost:8000/git-status
```

### 2. Log Monitoring
```bash
# Real-time logs
docker-compose logs -f serverbond-agent

# Supervisor logs
docker-compose exec serverbond-agent supervisorctl -c /opt/serverbond-agent/agent/supervisord.conf tail -f serverbond-agent
```

## 🔄 Güncelleme

### 1. Agent Güncelleme
```bash
# GitHub'dan güncelle
curl -X POST http://localhost:8000/update

# Manuel restart
curl -X POST http://localhost:8000/restart
```

### 2. Container Güncelleme
```bash
# Yeni image çek
docker-compose pull

# Container'ları yeniden başlat
docker-compose up -d
```

## 🛡️ Güvenlik

### 1. Token Güvenliği
```bash
# Güçlü token oluştur
openssl rand -hex 32

# Environment variable olarak ayarla
export SB_AGENT_TOKEN=your-secure-token
```

### 2. Network Güvenliği
```bash
# Sadece gerekli portları aç
# docker-compose.yml'de ports bölümünü düzenleyin
```

### 3. Volume Güvenliği
```bash
# Volume'ları şifrele
docker volume create --driver local \
  --opt type=tmpfs \
  --opt device=tmpfs \
  serverbond-secure
```

Bu Docker setup ile ServerBond Agent'ı kolayca çalıştırabilir ve yönetebilirsiniz!
