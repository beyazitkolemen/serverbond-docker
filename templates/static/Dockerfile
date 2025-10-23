# Static Site Dockerfile Template
FROM nginx:alpine

# Nginx konfigürasyonu
COPY nginx.conf /etc/nginx/nginx.conf

# Static dosyaları kopyala
COPY . /usr/share/nginx/html

# İzinleri ayarla
RUN chown -R nginx:nginx /usr/share/nginx/html \
    && chmod -R 755 /usr/share/nginx/html

# Port
EXPOSE 80

# Nginx'i başlat
CMD ["nginx", "-g", "daemon off;"]
