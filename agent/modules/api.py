"""
API endpoints module
"""
import os
import subprocess
import shutil
import sys
from pathlib import Path
from datetime import datetime
from fastapi import HTTPException, Header
from pydantic import BaseModel

from .config import CONFIG
from .utils import log, write_file, get_container_status, detect_framework, provision_mysql
from .templates import render, generate_laravel_env

# === SCHEMAS ===
class BuildRequest(BaseModel):
    repo: str
    domain: str
    framework: str = None
    php_version: str = None
    db_name: str = None
    db_user: str = None
    db_pass: str = None

class RedeployRequest(BaseModel):
    domain: str

# === AUTHENTICATION ===
def protect(token: str, agent_token: str):
    """Protect endpoint with agent token"""
    if agent_token and token != agent_token:
        raise HTTPException(401, "Unauthorized")

# === HEALTH CHECK ===
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "time": datetime.utcnow().isoformat()}

# === SYSTEM STATUS ===
def system_status(agent_token: str):
    """Get system status"""
    protect(agent_token, agent_token)
    try:
        # Docker durumu
        docker_result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True, text=True, timeout=CONFIG["timeouts"]["docker_inspect"]
        )
        docker_version = docker_result.stdout.strip() if docker_result.returncode == 0 else "unknown"
        
        # Shared servislerin durumu
        shared_services = {}
        for service in [CONFIG["docker"]["shared_mysql_container"], CONFIG["docker"]["shared_redis_container"]]:
            shared_services[service] = get_container_status(service, CONFIG["timeouts"]["docker_inspect"])
        
        # Site sayısı
        sites_dir = Path(CONFIG["paths"]["base_dir"])
        site_count = len([d for d in sites_dir.iterdir() if d.is_dir()]) if sites_dir.exists() else 0
        
        return {
            "docker_version": docker_version,
            "shared_services": shared_services,
            "site_count": site_count,
            "base_dir": CONFIG["paths"]["base_dir"],
            "template_dir": CONFIG["paths"]["template_dir"],
            "network": CONFIG["docker"]["network"],
            "time": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to get system status: {e}")

# === SITES MANAGEMENT ===
def get_sites(agent_token: str):
    """Get all deployed sites"""
    protect(agent_token, agent_token)
    try:
        sites_dir = Path(CONFIG["paths"]["base_dir"])
        if not sites_dir.exists():
            return {"sites": []}
        
        sites = []
        for site_dir in sites_dir.iterdir():
            if site_dir.is_dir() and (site_dir / "docker-compose.yml").exists():
                site_name = site_dir.name
                status = get_container_status(site_name, CONFIG["timeouts"]["docker_inspect"])
                sites.append({
                    "name": site_name,
                    "status": status,
                    "path": str(site_dir)
                })
        
        return {"sites": sites}
    except Exception as e:
        raise HTTPException(500, f"Failed to get sites: {e}")

def get_site_status(site_name: str, agent_token: str):
    """Get specific site status"""
    protect(agent_token, agent_token)
    try:
        status = get_container_status(site_name, CONFIG["timeouts"]["docker_inspect"])
        return {
            "name": site_name,
            "status": status,
            "time": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to get site status: {e}")

def get_site_logs(site_name: str, agent_token: str):
    """Get site logs"""
    protect(agent_token, agent_token)
    try:
        site_dir = Path(CONFIG["paths"]["base_dir"]) / site_name
        if not site_dir.exists() or not (site_dir / "docker-compose.yml").exists():
            raise HTTPException(404, "Site not found")
        
        result = subprocess.run(
            ["docker", "logs", "--tail", "100", site_name],
            capture_output=True, text=True, timeout=CONFIG["timeouts"]["docker_logs"]
        )
        return {
            "name": site_name,
            "logs": result.stdout,
            "error": result.stderr if result.returncode != 0 else None
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to get site logs: {e}")

def start_site(site_name: str, agent_token: str):
    """Start a site"""
    protect(agent_token, agent_token)
    try:
        site_dir = Path(CONFIG["paths"]["base_dir"]) / site_name
        if not site_dir.exists() or not (site_dir / "docker-compose.yml").exists():
            raise HTTPException(404, "Site not found")
        
        result = subprocess.run(
            ["docker", "compose", "up", "-d"],
            cwd=site_dir, capture_output=True, text=True, timeout=CONFIG["timeouts"]["docker_compose"]
        )
        return {
            "name": site_name,
            "status": "started",
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to start site: {e}")

def stop_site(site_name: str, agent_token: str):
    """Stop a site"""
    protect(agent_token, agent_token)
    try:
        site_dir = Path(CONFIG["paths"]["base_dir"]) / site_name
        if not site_dir.exists() or not (site_dir / "docker-compose.yml").exists():
            raise HTTPException(404, "Site not found")
        
        result = subprocess.run(
            ["docker", "compose", "down"],
            cwd=site_dir, capture_output=True, text=True, timeout=CONFIG["timeouts"]["docker_compose"]
        )
        return {
            "name": site_name,
            "status": "stopped",
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to stop site: {e}")

def delete_site(site_name: str, agent_token: str):
    """Delete a site"""
    protect(agent_token, agent_token)
    try:
        site_dir = Path(CONFIG["paths"]["base_dir"]) / site_name
        if not site_dir.exists() or not (site_dir / "docker-compose.yml").exists():
            raise HTTPException(404, "Site not found")
        
        # Önce container'ları durdur
        subprocess.run(
            ["docker", "compose", "down", "-v"],
            cwd=site_dir, capture_output=True, text=True, timeout=CONFIG["timeouts"]["docker_compose"]
        )
        
        # Site dizinini sil
        shutil.rmtree(site_dir)
        
        return {
            "name": site_name,
            "status": "deleted",
            "message": "Site deleted successfully"
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to delete site: {e}")

# === TEMPLATE MANAGEMENT ===
def update_templates(agent_token: str):
    """Update all templates from GitHub"""
    protect(agent_token, agent_token)
    try:
        # Template'leri yeniden indir
        template_url = CONFIG["github"]["templates_url"]
        
        # Base sistem template'lerini indir
        base_dir = Path(CONFIG["paths"]["template_dir"]).parent / "base"
        base_dir.mkdir(parents=True, exist_ok=True)
        
        base_template_url = "https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/base"
        
        # Docker compose template
        result = subprocess.run(
            ["curl", "-fsSL", f"{base_template_url}/docker-compose.yml.j2", "-o", str(base_dir / "docker-compose.yml.j2")],
            capture_output=True, text=True, timeout=CONFIG["timeouts"]["curl_download"]
        )
        if result.returncode != 0:
            log(f"Failed to download base system template: {result.stderr}")
        
        # Systemd service template
        result = subprocess.run(
            ["curl", "-fsSL", f"{base_template_url}/serverbond-agent.service.j2", "-o", str(base_dir / "serverbond-agent.service.j2")],
            capture_output=True, text=True, timeout=CONFIG["timeouts"]["curl_download"]
        )
        if result.returncode != 0:
            log(f"Failed to download systemd service template: {result.stderr}")
        
        # Her framework için template'leri indir
        frameworks = ["laravel", "laravel-inertia", "nextjs", "nodeapi", "nuxt", "static"]
        
        for framework in frameworks:
            framework_dir = Path(CONFIG["paths"]["template_dir"]) / framework
            framework_dir.mkdir(parents=True, exist_ok=True)
            
            # Template dosyalarını config'den al
            template_files = CONFIG["frameworks"].get(framework, {}).get("template_files", [])
            
            for template_file in template_files:
                url = f"{template_url}/{framework}/{template_file}"
                result = subprocess.run(
                    ["curl", "-fsSL", url, "-o", str(framework_dir / template_file)],
                    capture_output=True, text=True, timeout=CONFIG["timeouts"]["curl_download"]
                )
                if result.returncode != 0:
                    log(f"Failed to download {template_file}: {result.stderr}")
        
        return {
            "status": "updated",
            "message": "Templates updated successfully"
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to update templates: {e}")

# === AGENT MANAGEMENT ===
def restart_agent(agent_token: str):
    """Restart agent service"""
    protect(agent_token, agent_token)
    try:
        result = subprocess.run(
            ["systemctl", "restart", "serverbond-agent"],
            capture_output=True, text=True, timeout=CONFIG["timeouts"]["systemctl"]
        )
        
        if result.returncode == 0:
            return {
                "status": "restarted",
                "message": "Agent restarted successfully"
            }
        else:
            raise HTTPException(500, f"Failed to restart agent: {result.stderr}")
    except Exception as e:
        raise HTTPException(500, f"Failed to restart agent: {e}")

def get_agent_logs(agent_token: str):
    """Get agent logs"""
    protect(agent_token, agent_token)
    try:
        result = subprocess.run(
            ["journalctl", "-u", "serverbond-agent", "--no-pager", "-n", "100"],
            capture_output=True, text=True, timeout=CONFIG["timeouts"]["systemctl"]
        )
        
        return {
            "logs": result.stdout,
            "error": result.stderr if result.returncode != 0 else None
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to get agent logs: {e}")

def stop_agent(agent_token: str):
    """Stop agent service"""
    protect(agent_token, agent_token)
    try:
        result = subprocess.run(
            ["systemctl", "stop", "serverbond-agent"],
            capture_output=True, text=True, timeout=CONFIG["timeouts"]["systemctl"]
        )
        
        if result.returncode == 0:
            return {
                "status": "stopped",
                "message": "Agent stopped successfully"
            }
        else:
            raise HTTPException(500, f"Failed to stop agent: {result.stderr}")
    except Exception as e:
        raise HTTPException(500, f"Failed to stop agent: {e}")

def start_agent(agent_token: str):
    """Start agent service"""
    protect(agent_token, agent_token)
    try:
        result = subprocess.run(
            ["systemctl", "start", "serverbond-agent"],
            capture_output=True, text=True, timeout=CONFIG["timeouts"]["systemctl"]
        )
        
        if result.returncode == 0:
            return {
                "status": "started",
                "message": "Agent started successfully"
            }
        else:
            raise HTTPException(500, f"Failed to start agent: {result.stderr}")
    except Exception as e:
        raise HTTPException(500, f"Failed to start agent: {e}")

def update_agent(agent_token: str):
    """Update agent from GitHub"""
    protect(agent_token, agent_token)
    try:
        # Agent'ı güncelle
        result = subprocess.run(
            ["curl", "-fsSL", CONFIG["github"]["agent_url"], "-o", "/tmp/agent.py"],
            capture_output=True, text=True, timeout=CONFIG["timeouts"]["curl_download"]
        )
        
        if result.returncode == 0:
            # Yeni agent'ı kopyala
            agent_path = Path(CONFIG["paths"]["agent_dir"]) / "agent.py"
            shutil.copy("/tmp/agent.py", str(agent_path))
            os.chmod(str(agent_path), 0o755)
            
            # Agent'ı yeniden başlat
            subprocess.run(["systemctl", "restart", "serverbond-agent"], capture_output=True, text=True, timeout=CONFIG["timeouts"]["systemctl"])
            
            return {
                "status": "updated",
                "message": "Agent updated and restarted successfully"
            }
        else:
            raise HTTPException(500, f"Failed to download new agent: {result.stderr}")
    except Exception as e:
        raise HTTPException(500, f"Failed to update agent: {e}")

def get_agent_info(agent_token: str):
    """Get agent information"""
    protect(agent_token, agent_token)
    return {
        "name": CONFIG["agent"]["name"],
        "version": CONFIG["agent"]["version"],
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "base_dir": CONFIG["paths"]["base_dir"],
        "template_dir": CONFIG["paths"]["template_dir"],
        "network": CONFIG["docker"]["network"],
        "config_dir": CONFIG["paths"]["config_dir"],
        "shared_mysql": CONFIG["docker"]["shared_mysql_container"],
        "shared_redis": CONFIG["docker"]["shared_redis_container"],
        "agent_port": CONFIG["agent"]["port"],
        "time": datetime.utcnow().isoformat()
    }

def get_php_versions(agent_token: str):
    """Get available PHP versions"""
    protect(agent_token, agent_token)
    return {
        "available_versions": list(CONFIG["php_versions"].keys()),
        "default_version": CONFIG["defaults"]["php_version"],
        "versions": CONFIG["php_versions"]
    }
