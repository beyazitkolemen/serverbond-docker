# Laravel Dockerfile Template
FROM php:8.3-fpm-alpine

# Sistem paketlerini yükle
RUN apk add --no-cache \
    nginx \
    supervisor \
    git \
    curl \
    libpng-dev \
    libjpeg-turbo-dev \
    freetype-dev \
    libzip-dev \
    zip \
    unzip \
    oniguruma-dev \
    libxml2-dev \
    icu-dev \
    autoconf \
    g++ \
    make \
    nodejs \
    npm

# PHP extension'larını yükle
RUN docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j$(nproc) \
        pdo_mysql \
        mbstring \
        zip \
        exif \
        pcntl \
        gd \
        intl \
        opcache \
        bcmath

# Composer'ı yükle
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

# Nginx konfigürasyonu
COPY nginx.conf /etc/nginx/nginx.conf

# Supervisor konfigürasyonu
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Çalışma dizini
WORKDIR /var/www/html

# Uygulama dosyalarını kopyala
COPY . .

# Composer bağımlılıklarını yükle
RUN composer install --no-dev --optimize-autoloader --no-interaction

# NPM bağımlılıklarını yükle ve build et
RUN npm ci --only=production && npm run build

# Laravel optimizasyonları
RUN php artisan config:cache \
    && php artisan route:cache \
    && php artisan view:cache

# İzinleri ayarla
RUN chown -R www-data:www-data /var/www/html \
    && chmod -R 755 /var/www/html/storage \
    && chmod -R 755 /var/www/html/bootstrap/cache

# Port
EXPOSE 80

# Supervisor ile servisleri başlat
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
