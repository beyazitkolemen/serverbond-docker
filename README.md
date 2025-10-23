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
# Laravel projesi ekleme
curl -X POST http://localhost:8000/build \
  -H "X-Agent-Token: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "https://github.com/username/project.git",
    "domain": "project.serverbond.dev",
    "framework": "laravel",
    "db_name": "project_db",
    "db_user": "project_user",
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

- **Laravel**: PHP 8.3, Nginx, MySQL, Redis
- **Laravel Inertia**: PHP 8.3, Nginx, MySQL, Redis, Vite
- **Next.js**: Node.js 20, Standalone build
- **Nuxt.js**: Node.js 20, SSR/SSG
- **Node.js API**: Express/Fastify, TypeScript
- **Static**: Nginx, HTML/CSS/JS

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
