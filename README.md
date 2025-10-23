# ServerBond Docker Agent

Bu repository, Ubuntu 24.04 sunucularında sıfırdan ServerBond Docker Agent kurulumu yapan otomatik bir script içerir.

## 🚀 Özellikler

- ✅ Ubuntu 24.04 için optimize edilmiş
- ✅ Docker CE (Community Edition) kurulumu
- ✅ Docker Compose (standalone) kurulumu
- ✅ Traefik reverse proxy kurulumu
- ✅ MySQL ve Redis shared servisleri
- ✅ ServerBond Agent API
- ✅ Çoklu framework desteği (Laravel, Next.js, Nuxt, Node.js, Static)
- ✅ Otomatik SSL sertifikası (Let's Encrypt)
- ✅ phpMyAdmin arayüzü
- ✅ Güvenlik konfigürasyonları
- ✅ Detaylı hata kontrolü ve loglama
- ✅ Renkli çıktı ve kullanıcı dostu arayüz

## 📋 Gereksinimler

- Ubuntu 24.04 (diğer versiyonlar için uyarı verir)
- Root yetkisi
- İnternet bağlantısı
- Minimum 2GB RAM (önerilen 4GB+)
- Minimum 10GB disk alanı

## 🛠️ Kurulum

### Tek Komut ile Kurulum

```bash
# Root olarak çalıştırın
sudo su

# Tek komut ile kurulum
curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/install.sh | bash
```

### Manuel Kurulum

```bash
# Root olarak giriş yapın
sudo su

# Scripti indirin
curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/install.sh -o install.sh
chmod +x install.sh

# Kurulumu başlatın
./install.sh
```

**ÖNEMLİ:** Scripti root kullanıcısı olarak çalıştırın.

## 📝 Script Ne Yapar?

1. **Sistem Hazırlığı**
   - Ubuntu versiyonunu kontrol eder
   - Root kullanıcı kontrolü yapar
   - Sistem paketlerini günceller
   - Gerekli bağımlılıkları yükler

2. **Docker Kurulumu**
   - Docker CE kurulumu
   - Docker Compose kurulumu
   - Docker servisini başlatır ve etkinleştirir

3. **Shared Network ve Servisler**
   - Docker network oluşturur
   - Traefik reverse proxy kurulumu
   - MySQL 8.4 shared servisi
   - Redis shared servisi
   - phpMyAdmin arayüzü

4. **ServerBond Agent**
   - Agent Python scriptini indirir
   - Template'leri GitHub'dan indirir
   - Python bağımlılıklarını yükler
   - systemd servisi oluşturur

5. **Güvenlik ve Firewall**
   - UFW firewall yapılandırması
   - SSL sertifikası için Let's Encrypt
   - Güvenli port ayarları

6. **Template Sistemi**
   - Laravel (PHP 8.3)
   - Laravel Inertia
   - Next.js
   - Nuxt.js
   - Node.js API
   - Static HTML

## 🔧 Kurulum Sonrası

Kurulum tamamlandıktan sonra:

1. **Agent URL'si**: `http://sunucu-ip:8000`
2. **Agent Token**: Kurulum sırasında gösterilir
3. **phpMyAdmin**: `https://pma.serverbond.dev`
4. **MySQL Root Şifresi**: `/opt/serverbond-config/mysql_root_password.txt`

### Yeni Site Ekleme

```bash
# Laravel projesi ekleme (PHP 8.3)
curl -X POST http://localhost:8000/build \
  -H "X-Agent-Token: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "https://github.com/username/project.git",
    "domain": "project.serverbond.dev",
    "framework": "laravel",
    "php_version": "8.3",
    "db_name": "project_db",
    "db_user": "project_user",
    "db_pass": "secret123"
  }'

# Laravel projesi ekleme (PHP 8.1)
curl -X POST http://localhost:8000/build \
  -H "X-Agent-Token: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "https://github.com/username/legacy-project.git",
    "domain": "legacy.serverbond.dev",
    "framework": "laravel",
    "php_version": "8.1",
    "db_name": "legacy_db",
    "db_user": "legacy_user",
    "db_pass": "secret123"
  }'

# Next.js projesi ekleme
curl -X POST http://localhost:8000/build \
  -H "X-Agent-Token: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "https://github.com/username/nextjs-app.git",
    "domain": "app.serverbond.dev",
    "framework": "nextjs"
  }'
```

## 🛡️ Güvenlik Önerileri

- Agent Token'ı güvenli tutun
- MySQL root şifresini düzenli olarak değiştirin
- SSL sertifikalarını düzenli olarak yenileyin
- Firewall kurallarını kontrol edin
- Container'ları düzenli olarak güncelleyin

## 🔍 Sorun Giderme

### Agent çalışmıyor

```bash
# Agent servisini kontrol edin
sudo systemctl status serverbond-agent

# Agent loglarını görüntüleyin
sudo journalctl -u serverbond-agent -f

# Agent'ı yeniden başlatın
sudo systemctl restart serverbond-agent
```

### Docker servisleri çalışmıyor

```bash
# Docker servisini kontrol edin
sudo systemctl status docker

# Shared servisleri kontrol edin
docker ps -a

# Shared servisleri yeniden başlatın
cd /opt/shared-services
docker compose up -d
```

### Template'ler indirilmiyor

```bash
# Template'leri manuel olarak indirin
cd /opt/serverbond-agent
rm -rf templates
mkdir -p templates

# Template'leri tekrar indirin
curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/templates/laravel/docker-compose.yml.j2 -o templates/laravel/docker-compose.yml.j2
# ... diğer template'ler için benzer komutlar
```

## 📊 Desteklenen Framework'ler

- **Laravel**: PHP 8.0/8.1/8.2/8.3/8.4, Nginx, MySQL, Redis
- **Laravel Inertia**: PHP 8.0/8.1/8.2/8.3/8.4, Nginx, MySQL, Redis, Vite
- **Next.js**: Node.js 20, Standalone build
- **Nuxt.js**: Node.js 20, SSR/SSG
- **Node.js API**: Express/Fastify, TypeScript
- **Static**: Nginx, HTML/CSS/JS

## 🐘 PHP Versiyon Desteği

Sistem aşağıdaki PHP versiyonlarını destekler:

- **PHP 8.1**: Eski projeler için
- **PHP 8.2**: Stabil versiyon
- **PHP 8.3**: Varsayılan versiyon (önerilen)
- **PHP 8.4**: En yeni versiyon

### PHP Versiyonlarını Görüntüleme

```bash
# Mevcut PHP versiyonlarını listele
curl -X GET http://localhost:8000/php-versions \
  -H "X-Agent-Token: YOUR_TOKEN"
```

### PHP Versiyonu ile Site Oluşturma

```bash
# Belirli PHP versiyonu ile Laravel projesi
curl -X POST http://localhost:8000/build \
  -H "X-Agent-Token: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "https://github.com/username/project.git",
    "domain": "project.serverbond.dev",
    "framework": "laravel",
    "php_version": "8.2"
  }'
```

## 🔧 Base Sistem Yönetimi

Base sistem (Traefik, MySQL, Redis, phpMyAdmin) ayrı olarak yönetilebilir:

### Base Sistem Durumu

```bash
# Base sistem container'larının durumunu kontrol et
curl -X GET http://localhost:8000/base-system/status \
  -H "X-Agent-Token: YOUR_TOKEN"
```

### Base Sistem Kontrolü

```bash
# Base sistemi yeniden başlat
curl -X POST http://localhost:8000/base-system/restart \
  -H "X-Agent-Token: YOUR_TOKEN"

# Base sistemi durdur
curl -X POST http://localhost:8000/base-system/stop \
  -H "X-Agent-Token: YOUR_TOKEN"

# Base sistemi başlat
curl -X POST http://localhost:8000/base-system/start \
  -H "X-Agent-Token: YOUR_TOKEN"
```

## ⚙️ Systemd Servis Yönetimi

Systemd servis dosyası da template olarak yönetilebilir:

### Systemd Servis Durumu

```bash
# Systemd servis durumunu kontrol et
curl -X GET http://localhost:8000/systemd/status \
  -H "X-Agent-Token: YOUR_TOKEN"
```

### Systemd Servis Güncelleme

```bash
# Systemd servis dosyasını güncelle
curl -X POST http://localhost:8000/systemd/update \
  -H "X-Agent-Token: YOUR_TOKEN"
```

## 🏗️ Modüler Yapı

Agent.py dosyası modüler yapıya bölünmüştür:

```
agent/
├── agent.py              # Ana FastAPI uygulaması
├── config.json           # Konfigürasyon dosyası
├── modules/
│   ├── __init__.py       # Modül başlatıcı
│   ├── config.py         # Konfigürasyon yönetimi
│   ├── utils.py          # Yardımcı fonksiyonlar
│   ├── templates.py      # Template rendering
│   ├── api.py            # API endpoint'leri
│   ├── base_system.py    # Base sistem yönetimi
│   └── site_builder.py   # Site oluşturma ve deployment
└── agent_old.py          # Eski versiyon (yedek)
```

### Modül Açıklamaları

- **config.py**: Konfigürasyon yükleme ve yönetimi
- **utils.py**: Genel yardımcı fonksiyonlar (log, file operations, container status)
- **templates.py**: Jinja2 template rendering ve Laravel .env oluşturma
- **api.py**: Tüm API endpoint'leri (sites, agent, templates)
- **base_system.py**: Base sistem ve systemd yönetimi
- **site_builder.py**: Site oluşturma, deployment ve framework setup

## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Commit yapın (`git commit -m 'Add amazing feature'`)
4. Push yapın (`git push origin feature/amazing-feature`)
5. Pull Request oluşturun

## 📄 Lisans

Bu proje MIT lisansı altında lisanslanmıştır.

## ⚠️ Uyarı

Bu script production ortamında kullanmadan önce test edin. Güvenlik ve performans gereksinimlerinize uygun olup olmadığını kontrol edin.

## 📞 Destek

Sorunlarınız için:
- GitHub Issues oluşturun
- Dokümantasyonu kontrol edin
- Agent loglarını inceleyin

---

**Not:** Bu script Ubuntu 24.04 için optimize edilmiştir. Diğer Ubuntu versiyonlarında çalışabilir ancak test edilmemiştir.
