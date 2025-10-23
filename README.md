# Ubuntu 24.04 Docker Kurulum Scripti

Bu repository, Ubuntu 24.04 sunucularında sıfırdan Docker kurulumu yapan otomatik bir script içerir.

## 🚀 Özellikler

- ✅ Ubuntu 24.04 için optimize edilmiş
- ✅ Docker CE (Community Edition) kurulumu
- ✅ Docker Compose (standalone) kurulumu
- ✅ Güvenlik konfigürasyonları
- ✅ Otomatik kullanıcı grubu ekleme
- ✅ Detaylı hata kontrolü ve loglama
- ✅ Renkli çıktı ve kullanıcı dostu arayüz

## 📋 Gereksinimler

- Ubuntu 24.04 (diğer versiyonlar için uyarı verir)
- Sudo yetkisi olan kullanıcı
- İnternet bağlantısı

## 🛠️ Kurulum

### 1. Scripti İndirin

```bash
# Repository'yi klonlayın
git clone https://github.com/your-username/serverbond-docker.git
cd serverbond-docker

# Veya sadece scripti indirin
wget https://raw.githubusercontent.com/your-username/serverbond-docker/main/install.sh
chmod +x install.sh
```

### 2. Scripti Çalıştırın

```bash
./install.sh
```

**ÖNEMLİ:** Scripti root kullanıcısı olarak değil, sudo yetkisi olan normal kullanıcı ile çalıştırın.

## 📝 Script Ne Yapar?

1. **Sistem Kontrolleri**
   - Ubuntu versiyonunu kontrol eder
   - Root kullanıcı kontrolü yapar

2. **Sistem Güncellemesi**
   - Paket listesini günceller
   - Sistem paketlerini yükseltir
   - Gerekli bağımlılıkları yükler

3. **Eski Kurulumları Temizler**
   - Eski Docker kurulumlarını kaldırır
   - Temiz bir kurulum için gerekli dosyaları siler

4. **Docker Kurulumu**
   - Docker'ın resmi GPG anahtarını ekler
   - Docker repository'sini yapılandırır
   - Docker CE, Docker CLI ve containerd yükler

5. **Docker Compose Kurulumu**
   - En son Docker Compose versiyonunu indirir
   - Standalone olarak yükler

6. **Servis Yapılandırması**
   - Docker servisini başlatır ve etkinleştirir
   - Kullanıcıyı docker grubuna ekler
   - Docker daemon konfigürasyonu yapar

7. **Test ve Doğrulama**
   - Kurulumu doğrular
   - Test container çalıştırır

## 🔧 Kurulum Sonrası

Kurulum tamamlandıktan sonra:

1. **Oturumu kapatıp tekrar açın** (docker grubu değişiklikleri için)
2. Docker'ın çalıştığını test edin:

```bash
docker --version
docker-compose --version
docker run hello-world
```

## 🛡️ Güvenlik Önerileri

Script aşağıdaki güvenlik önerilerini içerir:

- Docker socket'ini dışarıya açmayın
- Container'ları root olmayan kullanıcılarla çalıştırın
- Düzenli olarak Docker'ı güncelleyin
- Güvenli base image'lar kullanın
- Production ortamında dikkatli olun

## 🔍 Sorun Giderme

### Docker komutları çalışmıyor

```bash
# Kullanıcının docker grubunda olduğunu kontrol edin
groups $USER

# Docker servisinin çalıştığını kontrol edin
sudo systemctl status docker

# Docker servisini yeniden başlatın
sudo systemctl restart docker
```

### Permission denied hatası

```bash
# Kullanıcıyı docker grubuna manuel olarak ekleyin
sudo usermod -aG docker $USER

# Oturumu kapatıp tekrar açın
```

### Eski Docker kurulumu sorunları

```bash
# Eski kurulumları tamamen temizleyin
sudo apt-get remove docker docker-engine docker.io containerd runc
sudo rm -rf /var/lib/docker
sudo rm -rf /var/lib/containerd
sudo rm -rf /etc/docker

# Scripti tekrar çalıştırın
./install.sh
```

## 📊 Sistem Gereksinimleri

- **RAM:** Minimum 2GB (önerilen 4GB+)
- **Disk:** Minimum 10GB boş alan
- **CPU:** x86_64 mimarisi
- **OS:** Ubuntu 24.04 LTS

## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Commit yapın (`git commit -m 'Add amazing feature'`)
4. Push yapın (`git push origin feature/amazing-feature`)
5. Pull Request oluşturun

## 📄 Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Detaylar için `LICENSE` dosyasına bakın.

## ⚠️ Uyarı

Bu script production ortamında kullanmadan önce test edin. Güvenlik ve performans gereksinimlerinize uygun olup olmadığını kontrol edin.

## 📞 Destek

Sorunlarınız için:
- Issue oluşturun
- Dokümantasyonu kontrol edin
- Docker resmi dokümantasyonuna bakın

---

**Not:** Bu script Ubuntu 24.04 için optimize edilmiştir. Diğer Ubuntu versiyonlarında çalışabilir ancak test edilmemiştir.
