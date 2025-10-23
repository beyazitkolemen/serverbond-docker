# 🚀 ServerBond Production Deployment Guide

Bu doküman ServerBond sisteminin production ortamında güvenli ve performanslı bir şekilde kurulumu için detaylı rehberdir.

## 📋 Ön Gereksinimler

### Sistem Gereksinimleri
- **OS**: Ubuntu 20.04+ / Debian 11+ / CentOS 8+
- **RAM**: Minimum 4GB, Önerilen 8GB+
- **Disk**: Minimum 50GB SSD
- **CPU**: Minimum 2 core, Önerilen 4+ core
- **Network**: Statik IP adresi önerilir

### Yazılım Gereksinimleri
- Docker 20.10+
- Docker Compose 2.0+
- Python 3.8+
- Git
- curl
- systemd

## 🔧 Production Kurulumu

### 1. Sistem Hazırlığı

```bash
# Sistem güncellemesi
sudo apt update && sudo apt upgrade -y

# Gerekli paketlerin kurulumu
sudo apt install -y curl git python3 python3-pip docker.io docker-compose

# Docker servisini başlat
sudo systemctl start docker
sudo systemctl enable docker

# Kullanıcıyı docker grubuna ekle
sudo usermod -aG docker $USER
```

### 2. Güvenlik Yapılandırması

```bash
# Firewall yapılandırması
sudo ufw enable
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 8000/tcp  # Agent API

# SSH güvenliği
sudo sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

### 3. ServerBond Kurulumu

```bash
# Tek komutla kurulum
curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/install.sh | bash
```

### 4. Production Yapılandırması

```bash
# Agent token'ı güçlendir
sudo sed -i 's/SB_AGENT_TOKEN=.*/SB_AGENT_TOKEN=$(openssl rand -hex 32)/' /etc/systemd/system/serverbond-agent.service

# Systemd servisini yeniden yükle
sudo systemctl daemon-reload
sudo systemctl restart serverbond-agent
```

## 🔒 Güvenlik Yapılandırması

### 1. SSL/TLS Sertifikaları

```bash
# Let's Encrypt kurulumu
sudo apt install -y certbot

# Traefik için SSL sertifikası
sudo certbot certonly --standalone -d your-domain.com
```

### 2. Agent Token Güvenliği

```bash
# Güçlü token oluştur
AGENT_TOKEN=$(openssl rand -hex 32)
echo "SB_AGENT_TOKEN=$AGENT_TOKEN" | sudo tee -a /etc/environment

# Token'ı güvenli yerde sakla
echo "Agent Token: $AGENT_TOKEN" | sudo tee /root/agent-token.txt
sudo chmod 600 /root/agent-token.txt
```

### 3. Database Güvenliği

```bash
# MySQL root şifresini güçlendir
MYSQL_ROOT_PASS=$(openssl rand -base64 32)
echo "$MYSQL_ROOT_PASS" | sudo tee /opt/serverbond-config/mysql_root_password.txt
sudo chmod 600 /opt/serverbond-config/mysql_root_password.txt
```

## 📊 Monitoring ve Logging

### 1. Log Yönetimi

```bash
# Log rotation yapılandırması
sudo tee /etc/logrotate.d/serverbond <<EOF
/var/log/serverbond/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
}
EOF
```

### 2. System Monitoring

```bash
# Htop kurulumu
sudo apt install -y htop

# Docker stats monitoring
watch docker stats
```

### 3. Health Checks

```bash
# Agent health check
curl -f http://localhost:8000/health || echo "Agent down"

# Detailed health check
curl -H "X-Agent-Token: YOUR_TOKEN" http://localhost:8000/health/detailed
```

## 💾 Backup Stratejisi

### 1. Otomatik Backup

```bash
# Backup script oluştur
sudo tee /usr/local/bin/serverbond-backup.sh <<'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/serverbond-backups"
mkdir -p $BACKUP_DIR

# Full backup
curl -X POST -H "X-Agent-Token: YOUR_TOKEN" \
  http://localhost:8000/backup/full

# Cleanup old backups
curl -X POST -H "X-Agent-Token: YOUR_TOKEN" \
  http://localhost:8000/backup/cleanup?keep_days=30
EOF

sudo chmod +x /usr/local/bin/serverbond-backup.sh

# Cron job ekle
echo "0 2 * * * /usr/local/bin/serverbond-backup.sh" | sudo crontab -
```

### 2. Database Backup

```bash
# MySQL backup script
sudo tee /usr/local/bin/mysql-backup.sh <<'EOF'
#!/bin/bash
BACKUP_DIR="/opt/serverbond-backups/mysql"
mkdir -p $BACKUP_DIR

# MySQL dump
docker exec shared_mysql mysqldump --all-databases > $BACKUP_DIR/mysql_$(date +%Y%m%d_%H%M%S).sql

# Cleanup old dumps
find $BACKUP_DIR -name "mysql_*.sql" -mtime +7 -delete
EOF

sudo chmod +x /usr/local/bin/mysql-backup.sh
```

## 🚀 Performance Optimizasyonu

### 1. Docker Optimizasyonu

```bash
# Docker daemon yapılandırması
sudo tee /etc/docker/daemon.json <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "live-restore": true
}
EOF

sudo systemctl restart docker
```

### 2. System Limits

```bash
# System limits yapılandırması
sudo tee -a /etc/security/limits.conf <<EOF
* soft nofile 65536
* hard nofile 65536
* soft nproc 32768
* hard nproc 32768
EOF
```

### 3. Kernel Parameters

```bash
# Kernel parameters
sudo tee -a /etc/sysctl.conf <<EOF
vm.max_map_count=262144
fs.file-max=65536
net.core.somaxconn=65535
EOF

sudo sysctl -p
```

## 🔧 Maintenance

### 1. Güncelleme Stratejisi

```bash
# Agent güncelleme
curl -X POST -H "X-Agent-Token: YOUR_TOKEN" \
  http://localhost:8000/update

# Template güncelleme
curl -X POST -H "X-Agent-Token: YOUR_TOKEN" \
  http://localhost:8000/templates/update

# Requirements güncelleme
curl -X POST -H "X-Agent-Token: YOUR_TOKEN" \
  http://localhost:8000/requirements/update
```

### 2. Log Temizleme

```bash
# Log temizleme script
sudo tee /usr/local/bin/cleanup-logs.sh <<'EOF'
#!/bin/bash
# Docker log temizleme
docker system prune -f

# System log temizleme
sudo journalctl --vacuum-time=7d

# Agent log temizleme
find /var/log/serverbond -name "*.log" -mtime +30 -delete
EOF

sudo chmod +x /usr/local/bin/cleanup-logs.sh
```

## 🚨 Troubleshooting

### 1. Yaygın Sorunlar

```bash
# Agent durumu kontrol
sudo systemctl status serverbond-agent

# Agent logları
sudo journalctl -u serverbond-agent -f

# Docker durumu
docker ps -a
docker logs CONTAINER_NAME
```

### 2. Performance Sorunları

```bash
# Sistem kaynakları
htop
df -h
free -h

# Docker kaynakları
docker stats

# Network durumu
netstat -tlnp | grep :8000
```

### 3. Recovery

```bash
# Backup listesi
curl -H "X-Agent-Token: YOUR_TOKEN" \
  http://localhost:8000/backup/list

# Backup restore
curl -X POST -H "X-Agent-Token: YOUR_TOKEN" \
  http://localhost:8000/backup/restore/BACKUP_NAME
```

## 📈 Monitoring Dashboard

### 1. Prometheus + Grafana

```yaml
# docker-compose.monitoring.yml
version: '3.8'
services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
  
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

### 2. Health Check Endpoints

```bash
# Basic health
curl http://localhost:8000/health

# Detailed health
curl -H "X-Agent-Token: YOUR_TOKEN" \
  http://localhost:8000/health/detailed

# Container metrics
curl -H "X-Agent-Token: YOUR_TOKEN" \
  http://localhost:8000/monitoring/containers
```

## 🔐 Security Checklist

- [ ] Firewall yapılandırıldı
- [ ] SSH güvenliği sağlandı
- [ ] Agent token güçlendirildi
- [ ] Database şifreleri güçlendirildi
- [ ] SSL sertifikaları kuruldu
- [ ] Log rotation yapılandırıldı
- [ ] Backup stratejisi uygulandı
- [ ] Monitoring kuruldu
- [ ] Performance optimizasyonu yapıldı

## 📞 Support

- **GitHub Issues**: [serverbond-docker/issues](https://github.com/beyazitkolemen/serverbond-docker/issues)
- **Documentation**: [README.md](README.md)
- **API Documentation**: `http://your-server:8000/docs`

---

**Not**: Bu rehber production ortamı için hazırlanmıştır. Test ortamında önce deneyiniz.
