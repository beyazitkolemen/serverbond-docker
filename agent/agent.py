#!/usr/bin/env python3
"""
ServerBond Agent - MVP Version
Simple Docker Multi-site Management System
"""
import os
import sys
import json
import docker
import subprocess
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

# Add modules to path
sys.path.append(str(Path(__file__).parent))

from modules.logger import logger

# === CONFIGURATION ===
BASE_DIR = Path(os.getenv("SB_BASE_DIR", "/opt/sites"))
TEMPLATE_DIR = Path(os.getenv("SB_TEMPLATE_DIR", "/opt/serverbond-agent/templates"))
NETWORK = os.getenv("SB_NETWORK", "shared_net")
AGENT_TOKEN = os.getenv("SB_AGENT_TOKEN", "default_token")
AGENT_PORT = int(os.getenv("SB_AGENT_PORT", "8000"))

# Initialize Docker client
try:
    docker_client = docker.from_env()
except Exception as e:
    logger.error(f"Failed to initialize Docker client: {e}")
    sys.exit(1)

# === FLASK APP ===
app = Flask(__name__)
CORS(app)

# === UTILITY FUNCTIONS ===
def validate_token():
    """Validate agent token"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token != AGENT_TOKEN:
        return False
    return True

def get_container_status(container_name):
    """Get container status"""
    try:
        container = docker_client.containers.get(container_name)
        return {
            "status": container.status,
            "running": container.status == "running",
            "ports": container.ports,
            "created": container.attrs["Created"]
        }
    except docker.errors.NotFound:
        return {"status": "not_found", "running": False}
    except Exception as e:
        logger.error(f"Error getting container status: {e}")
        return {"status": "error", "running": False}

def detect_framework(site_path):
    """Detect framework from site files"""
    site_path = Path(site_path)
    
    if (site_path / "composer.json").exists():
        return "laravel"
    elif (site_path / "package.json").exists():
        with open(site_path / "package.json") as f:
            package = json.load(f)
            if "next" in package.get("dependencies", {}):
                return "nextjs"
            elif "nuxt" in package.get("dependencies", {}):
                return "nuxt"
            else:
                return "nodeapi"
    elif (site_path / "index.html").exists():
        return "static"
    else:
        return "unknown"

# === API ENDPOINTS ===

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "agent": "ServerBond Agent MVP",
        "version": "1.0",
        "docker": docker_client.ping()
    })

@app.route('/status', methods=['GET'])
def status():
    """System status"""
    if not validate_token():
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        # Base system status
        mysql_status = get_container_status("shared_mysql")
        redis_status = get_container_status("shared_redis")
        traefik_status = get_container_status("traefik")
        
        # Get all sites
        sites = []
        if BASE_DIR.exists():
            for site_dir in BASE_DIR.iterdir():
                if site_dir.is_dir():
                    site_name = site_dir.name
                    framework = detect_framework(site_dir)
                    container_status = get_container_status(site_name)
                    
                    sites.append({
                        "name": site_name,
                        "framework": framework,
                        "path": str(site_dir),
                        "status": container_status["status"],
                        "running": container_status["running"]
                    })
        
        return jsonify({
            "base_system": {
                "mysql": mysql_status,
                "redis": redis_status,
                "traefik": traefik_status
            },
            "sites": sites,
            "total_sites": len(sites)
        })
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/sites', methods=['GET'])
def get_sites():
    """Get all sites"""
    if not validate_token():
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        sites = []
        if BASE_DIR.exists():
            for site_dir in BASE_DIR.iterdir():
                if site_dir.is_dir():
                    site_name = site_dir.name
                    framework = detect_framework(site_dir)
                    container_status = get_container_status(site_name)
                    
                    sites.append({
                        "name": site_name,
                        "framework": framework,
                        "path": str(site_dir),
                        "status": container_status["status"],
                        "running": container_status["running"]
                    })
        
        return jsonify({"sites": sites})
    except Exception as e:
        logger.error(f"Error getting sites: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/sites/<site_name>/status', methods=['GET'])
def get_site_status(site_name):
    """Get specific site status"""
    if not validate_token():
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        site_path = BASE_DIR / site_name
        if not site_path.exists():
            return jsonify({"error": "Site not found"}), 404
        
        framework = detect_framework(site_path)
        container_status = get_container_status(site_name)
        
        return jsonify({
            "name": site_name,
            "framework": framework,
            "path": str(site_path),
            "status": container_status["status"],
            "running": container_status["running"]
        })
    except Exception as e:
        logger.error(f"Error getting site status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/sites/<site_name>/logs', methods=['GET'])
def get_site_logs(site_name):
    """Get site logs"""
    if not validate_token():
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        container = docker_client.containers.get(site_name)
        logs = container.logs(tail=100).decode('utf-8')
        return jsonify({"logs": logs})
    except docker.errors.NotFound:
        return jsonify({"error": "Container not found"}), 404
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/sites/<site_name>/start', methods=['POST'])
def start_site(site_name):
    """Start a site"""
    if not validate_token():
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        site_path = BASE_DIR / site_name
        if not site_path.exists():
            return jsonify({"error": "Site not found"}), 404
        
        # Start with docker compose
        result = subprocess.run(
            ["docker", "compose", "up", "-d"],
            cwd=site_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return jsonify({"message": f"Site {site_name} started successfully"})
        else:
            return jsonify({"error": result.stderr}), 500
    except Exception as e:
        logger.error(f"Error starting site: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/sites/<site_name>/stop', methods=['POST'])
def stop_site(site_name):
    """Stop a site"""
    if not validate_token():
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        site_path = BASE_DIR / site_name
        if not site_path.exists():
            return jsonify({"error": "Site not found"}), 404
        
        # Stop with docker compose
        result = subprocess.run(
            ["docker", "compose", "down"],
            cwd=site_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return jsonify({"message": f"Site {site_name} stopped successfully"})
        else:
            return jsonify({"error": result.stderr}), 500
    except Exception as e:
        logger.error(f"Error stopping site: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/sites/<site_name>/delete', methods=['DELETE'])
def delete_site(site_name):
    """Delete a site"""
    if not validate_token():
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        site_path = BASE_DIR / site_name
        if not site_path.exists():
            return jsonify({"error": "Site not found"}), 404
        
        # Stop and remove containers
        subprocess.run(["docker", "compose", "down", "-v"], cwd=site_path)
        
        # Remove directory
        import shutil
        shutil.rmtree(site_path)
        
        return jsonify({"message": f"Site {site_name} deleted successfully"})
    except Exception as e:
        logger.error(f"Error deleting site: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/build', methods=['POST'])
def build_site():
    """Build a new site"""
    if not validate_token():
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        data = request.get_json()
        site_name = data.get('name')
        framework = data.get('framework', 'laravel')
        domain = data.get('domain', f"{site_name}.local")
        
        if not site_name:
            return jsonify({"error": "Site name is required"}), 400
        
        site_path = BASE_DIR / site_name
        if site_path.exists():
            return jsonify({"error": "Site already exists"}), 400
        
        # Create site directory
        site_path.mkdir(parents=True, exist_ok=True)
        
        # Copy template files
        template_path = TEMPLATE_DIR / framework
        if template_path.exists():
            import shutil
            for template_file in template_path.iterdir():
                if template_file.is_file():
                    shutil.copy2(template_file, site_path)
        
        # Create basic docker-compose.yml if not exists
        if not (site_path / "docker-compose.yml").exists():
            compose_content = f"""version: '3.8'
services:
  {site_name}:
    image: nginx:alpine
    container_name: {site_name}
    restart: unless-stopped
    ports:
      - "80"
    volumes:
      - ./:/var/www/html
    networks:
      - {NETWORK}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.{site_name}.rule=Host(`{domain}`)"
      - "traefik.http.routers.{site_name}.entrypoints=web"

networks:
  {NETWORK}:
    external: true
"""
            with open(site_path / "docker-compose.yml", "w") as f:
                f.write(compose_content)
        
        return jsonify({
            "message": f"Site {site_name} created successfully",
            "path": str(site_path),
            "framework": framework,
            "domain": domain
        })
    except Exception as e:
        logger.error(f"Error building site: {e}")
        return jsonify({"error": str(e)}), 500

# === MAIN ===
if __name__ == "__main__":
    logger.info("Starting ServerBond Agent MVP...")
    logger.info(f"Base directory: {BASE_DIR}")
    logger.info(f"Template directory: {TEMPLATE_DIR}")
    logger.info(f"Network: {NETWORK}")
    logger.info(f"Port: {AGENT_PORT}")
    
    app.run(host='0.0.0.0', port=AGENT_PORT, debug=False)