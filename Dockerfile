FROM ubuntu:24.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive

# Update package list and install curl
RUN apt-get update && apt-get install -y curl && apt-get clean

# Expose port
EXPOSE 8000

# Run the install script
RUN curl -fsSL https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/install.sh | bash

# Start shell
CMD ["/bin/bash"]
