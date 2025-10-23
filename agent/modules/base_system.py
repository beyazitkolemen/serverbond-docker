"""
Base system management module
"""
import subprocess
from pathlib import Path
from datetime import datetime
from fastapi import HTTPException

from .config import load_config

# Load config
CONFIG = load_config()
from .utils import get_container_status, write_file, log
from .templates import render

def get_base_system_status(agent_token: str):
    """Get base system status"""
    try:
        # Base sistem container'larının durumunu kontrol et
        base_containers = ["traefik", CONFIG["docker"]["shared_mysql_container"], CONFIG["docker"]["shared_redis_container"], "phpmyadmin"]
        container_statuses = {}
        
        for container in base_containers:
            container_statuses[container] = get_container_status(container, CONFIG["timeouts"]["docker_inspect"])
        
        return {
            "containers": container_statuses,
            "network": CONFIG["docker"]["network"],
            "shared_services_dir": CONFIG["base_system"]["shared_services_dir"],
            "time": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to get base system status: {e}")

def restart_base_system(agent_token: str, mysql_root_pass: str):
    """Restart base system"""
    try:
        # Base sistem docker-compose dosyasını render et
        base_dir = Path(CONFIG["base_system"]["shared_services_dir"])
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # Base sistem context'i hazırla
        base_ctx = {
            "network": CONFIG["docker"]["network"],
            "shared_mysql_container": CONFIG["docker"]["shared_mysql_container"],
            "shared_redis_container": CONFIG["docker"]["shared_redis_container"],
            "traefik_email": CONFIG["base_system"]["traefik_email"],
            "phpmyadmin_domain": CONFIG["base_system"]["phpmyadmin_domain"],
            "mysql_root_password": mysql_root_pass
        }
        
        # Base sistem docker-compose.yml'yi render et
        base_template = Path(CONFIG["paths"]["template_dir"]).parent / "base" / "docker-compose.yml.j2"
        if base_template.exists():
            base_compose_content = render(base_template.parent, "docker-compose.yml.j2", base_ctx)
            write_file(base_dir / "docker-compose.yml", base_compose_content)
            
            # Base sistemi yeniden başlat
            result = subprocess.run(
                ["docker", "compose", "down"],
                cwd=base_dir, capture_output=True, text=True, timeout=CONFIG["timeouts"]["docker_compose"]
            )
            
            result = subprocess.run(
                ["docker", "compose", "up", "-d"],
                cwd=base_dir, capture_output=True, text=True, timeout=CONFIG["timeouts"]["docker_compose"]
            )
            
            return {
                "status": "restarted",
                "message": "Base system restarted successfully",
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None
            }
        else:
            raise HTTPException(404, "Base system template not found")
    except Exception as e:
        raise HTTPException(500, f"Failed to restart base system: {e}")

def stop_base_system(agent_token: str):
    """Stop base system"""
    try:
        base_dir = Path(CONFIG["base_system"]["shared_services_dir"])
        result = subprocess.run(
            ["docker", "compose", "down"],
            cwd=base_dir, capture_output=True, text=True, timeout=CONFIG["timeouts"]["docker_compose"]
        )
        
        return {
            "status": "stopped",
            "message": "Base system stopped successfully",
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to stop base system: {e}")

def start_base_system(agent_token: str):
    """Start base system"""
    try:
        base_dir = Path(CONFIG["base_system"]["shared_services_dir"])
        result = subprocess.run(
            ["docker", "compose", "up", "-d"],
            cwd=base_dir, capture_output=True, text=True, timeout=CONFIG["timeouts"]["docker_compose"]
        )
        
        return {
            "status": "started",
            "message": "Base system started successfully",
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to start base system: {e}")

def update_systemd_service(agent_token: str):
    """Update systemd service"""
    try:
        # Systemd servis template'ini render et
        service_template_path = Path(CONFIG["paths"]["template_dir"]).parent / "base" / "serverbond-agent.service.j2"
        if not service_template_path.exists():
            raise HTTPException(404, "Systemd service template not found")
        
        # Systemd servis context'i hazırla
        service_ctx = {
            "agent_name": CONFIG["agent"]["name"],
            "agent_dir": CONFIG["paths"]["agent_dir"],
            "base_dir": CONFIG["paths"]["base_dir"],
            "template_dir": CONFIG["paths"]["template_dir"],
            "network": CONFIG["docker"]["network"],
            "config_dir": CONFIG["paths"]["config_dir"],
            "shared_mysql_container": CONFIG["docker"]["shared_mysql_container"],
            "shared_redis_container": CONFIG["docker"]["shared_redis_container"],
            "agent_token": agent_token,
            "agent_port": CONFIG["agent"]["port"]
        }
        
        # Systemd servis dosyasını render et
        service_content = render(service_template_path.parent, "serverbond-agent.service.j2", service_ctx)
        
        # Systemd servis dosyasını yaz
        service_file_path = Path("/etc/systemd/system/serverbond-agent.service")
        write_file(service_file_path, service_content)
        
        # Systemd daemon'ı reload et
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True, text=True, timeout=CONFIG["timeouts"]["systemctl"])
        
        return {
            "status": "updated",
            "message": "Systemd service updated successfully",
            "service_file": str(service_file_path)
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to update systemd service: {e}")

def get_systemd_status(agent_token: str):
    """Get systemd status"""
    try:
        # Systemd servis durumunu kontrol et
        result = subprocess.run(
            ["systemctl", "is-active", "serverbond-agent"],
            capture_output=True, text=True, timeout=CONFIG["timeouts"]["systemctl"]
        )
        
        # Systemd servis detaylarını al
        status_result = subprocess.run(
            ["systemctl", "status", "serverbond-agent", "--no-pager"],
            capture_output=True, text=True, timeout=CONFIG["timeouts"]["systemctl"]
        )
        
        return {
            "service": "serverbond-agent",
            "status": result.stdout.strip(),
            "details": status_result.stdout,
            "error": status_result.stderr if status_result.returncode != 0 else None
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to get systemd status: {e}")
