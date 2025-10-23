FROM ubuntu:24.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    python3 \
    python3-pip \
    docker.io \
    docker-compose \
    supervisor \
    openssl \
    ca-certificates \
    gnupg \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Create directories
RUN mkdir -p \
    /opt/sites \
    /opt/shared-services \
    /var/log/supervisor \
    /etc/supervisor/conf.d

# Copy entrypoint script
COPY entrypoint.sh /opt/serverbond-agent/
RUN chmod +x /opt/serverbond-agent/entrypoint.sh

# Set working directory
WORKDIR /opt/serverbond-agent

# Expose ports
EXPOSE 8000 443 8080 3306 6379

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use entrypoint script
ENTRYPOINT ["/opt/serverbond-agent/entrypoint.sh"]
