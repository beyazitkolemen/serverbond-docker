#!/usr/bin/env python3
"""
ServerBond Agent - Modular Version
Docker Multi-site Management System
"""
import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Add modules to path
sys.path.append(str(Path(__file__).parent))

from modules.config import load_config
from modules.api import (
    BuildRequest, RedeployRequest, protect, health_check, system_status, get_sites,
    get_site_status, get_site_logs, start_site, stop_site, delete_site,
    update_templates, restart_agent, get_agent_logs, stop_agent, start_agent,
    update_agent, get_agent_info, get_php_versions, update_requirements
)
from modules.base_system import (
    get_base_system_status, restart_base_system, stop_base_system,
    start_base_system, update_systemd_service, get_systemd_status
)
from modules.site_builder import build_site, redeploy_site
from modules.monitoring import monitor
from modules.backup import backup_manager
from modules.logger import logger
from modules.security import validate_build_request, validate_token

# === CONFIG LOADING ===
CONFIG = load_config()

# === CONFIG VARIABLES ===
BASE_DIR = Path(os.getenv("SB_BASE_DIR", CONFIG["paths"]["base_dir"]))
TEMPLATE_DIR = Path(os.getenv("SB_TEMPLATE_DIR", CONFIG["paths"]["template_dir"]))
NETWORK = os.getenv("SB_NETWORK", CONFIG["docker"]["network"])
CONFIG_DIR = Path(os.getenv("SB_CONFIG_DIR", CONFIG["paths"]["config_dir"]))
SHARED_MYSQL = os.getenv("SB_SHARED_MYSQL_CONTAINER", CONFIG["docker"]["shared_mysql_container"])
SHARED_REDIS = os.getenv("SB_SHARED_REDIS_CONTAINER", CONFIG["docker"]["shared_redis_container"])
AGENT_TOKEN = os.getenv("SB_AGENT_TOKEN")
AGENT_PORT = int(os.getenv("SB_AGENT_PORT", CONFIG["agent"]["port"]))

# MySQL root password
MYSQL_ROOT_PASS = (CONFIG_DIR / "mysql_root_password.txt").read_text().strip() if (CONFIG_DIR / "mysql_root_password.txt").exists() else "root"

# === FASTAPI APP ===
app = FastAPI(
    title="ServerBond Agent",
    description="Docker Multi-site Management System",
    version=CONFIG["agent"]["version"]
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === HEALTH CHECK ===
@app.get("/health")
def health():
    return health_check()

# === SYSTEM STATUS ===
@app.get("/status")
def system_status_endpoint(x_agent_token: str = Header(None)):
    return system_status(x_agent_token)

# === SITES MANAGEMENT ===
@app.get("/sites")
def get_sites_endpoint(x_agent_token: str = Header(None)):
    return get_sites(x_agent_token)

@app.get("/sites/{site_name}/status")
def get_site_status_endpoint(site_name: str, x_agent_token: str = Header(None)):
    return get_site_status(site_name, x_agent_token)

@app.get("/sites/{site_name}/logs")
def get_site_logs_endpoint(site_name: str, x_agent_token: str = Header(None)):
    return get_site_logs(site_name, x_agent_token)

@app.post("/sites/{site_name}/start")
def start_site_endpoint(site_name: str, x_agent_token: str = Header(None)):
    return start_site(site_name, x_agent_token)

@app.post("/sites/{site_name}/stop")
def stop_site_endpoint(site_name: str, x_agent_token: str = Header(None)):
    return stop_site(site_name, x_agent_token)

@app.post("/sites/{site_name}/delete")
def delete_site_endpoint(site_name: str, x_agent_token: str = Header(None)):
    return delete_site(site_name, x_agent_token)

# === SITE BUILDING ===
@app.post("/build")
async def build_site_endpoint(req: BuildRequest, x_agent_token: str = Header(None)):
    protect(x_agent_token, AGENT_TOKEN)
    try:
        # Validate request data
        validate_build_request(req.dict())
        
        # Log build attempt
        logger.info(f"Build request received for {req.domain} with framework {req.framework}")
        
        result = await build_site(req, MYSQL_ROOT_PASS)
        
        logger.info(f"Build completed successfully for {req.domain}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Build failed for {req.domain}: {e}")
        raise HTTPException(500, f"Build failed: {e}")

@app.post("/redeploy")
async def redeploy_site_endpoint(req: RedeployRequest, x_agent_token: str = Header(None)):
    protect(x_agent_token, AGENT_TOKEN)
    try:
        return await redeploy_site(req, MYSQL_ROOT_PASS)
    except Exception as e:
        raise HTTPException(500, f"Redeploy failed: {e}")

# === TEMPLATE MANAGEMENT ===
@app.post("/templates/update")
def update_templates_endpoint(x_agent_token: str = Header(None)):
    return update_templates(x_agent_token)

# === AGENT MANAGEMENT ===
@app.post("/restart")
def restart_agent_endpoint(x_agent_token: str = Header(None)):
    return restart_agent(x_agent_token)

@app.post("/stop")
def stop_agent_endpoint(x_agent_token: str = Header(None)):
    return stop_agent(x_agent_token)

@app.post("/start")
def start_agent_endpoint(x_agent_token: str = Header(None)):
    return start_agent(x_agent_token)

@app.post("/update")
def update_agent_endpoint(x_agent_token: str = Header(None)):
    return update_agent(x_agent_token)

@app.get("/logs")
def get_agent_logs_endpoint(x_agent_token: str = Header(None)):
    return get_agent_logs(x_agent_token)

@app.get("/info")
def get_agent_info_endpoint(x_agent_token: str = Header(None)):
    return get_agent_info(x_agent_token)

# === PHP VERSIONS ===
@app.get("/php-versions")
def get_php_versions_endpoint(x_agent_token: str = Header(None)):
    return get_php_versions(x_agent_token)

# === REQUIREMENTS MANAGEMENT ===
@app.post("/requirements/update")
def update_requirements_endpoint(x_agent_token: str = Header(None)):
    return update_requirements(x_agent_token)

# === PRODUCTION MONITORING ===
@app.get("/health/detailed")
def detailed_health_check(x_agent_token: str = Header(None)):
    protect(x_agent_token, AGENT_TOKEN)
    try:
        health_status = monitor.get_system_health()
        return {
            "status": health_status.status,
            "timestamp": health_status.timestamp.isoformat(),
            "uptime": health_status.uptime,
            "metrics": {
                "memory_usage": health_status.memory_usage,
                "cpu_usage": health_status.cpu_usage,
                "disk_usage": health_status.disk_usage
            },
            "details": health_status.details
        }
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        raise HTTPException(500, f"Health check failed: {e}")

@app.get("/monitoring/containers")
def get_container_metrics(x_agent_token: str = Header(None)):
    protect(x_agent_token, AGENT_TOKEN)
    try:
        containers = monitor.get_container_metrics()
        sites = monitor.get_site_metrics()
        return {
            "containers": containers,
            "sites": sites,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Container metrics failed: {e}")
        raise HTTPException(500, f"Metrics collection failed: {e}")

# === BACKUP MANAGEMENT ===
@app.post("/backup/full")
def create_full_backup(x_agent_token: str = Header(None)):
    protect(x_agent_token, AGENT_TOKEN)
    try:
        return backup_manager.create_full_backup()
    except Exception as e:
        logger.error(f"Full backup failed: {e}")
        raise HTTPException(500, f"Backup creation failed: {e}")

@app.post("/backup/site/{site_name}")
def create_site_backup(site_name: str, x_agent_token: str = Header(None)):
    protect(x_agent_token, AGENT_TOKEN)
    try:
        return backup_manager.create_site_backup(site_name)
    except Exception as e:
        logger.error(f"Site backup failed for {site_name}: {e}")
        raise HTTPException(500, f"Site backup failed: {e}")

@app.get("/backup/list")
def list_backups(x_agent_token: str = Header(None)):
    protect(x_agent_token, AGENT_TOKEN)
    try:
        return {"backups": backup_manager.list_backups()}
    except Exception as e:
        logger.error(f"Backup listing failed: {e}")
        raise HTTPException(500, f"Backup listing failed: {e}")

@app.post("/backup/restore/{backup_name}")
def restore_backup(backup_name: str, x_agent_token: str = Header(None)):
    protect(x_agent_token, AGENT_TOKEN)
    try:
        return backup_manager.restore_backup(backup_name)
    except Exception as e:
        logger.error(f"Backup restore failed for {backup_name}: {e}")
        raise HTTPException(500, f"Backup restore failed: {e}")

@app.post("/backup/cleanup")
def cleanup_backups(keep_days: int = 30, x_agent_token: str = Header(None)):
    protect(x_agent_token, AGENT_TOKEN)
    try:
        return backup_manager.cleanup_old_backups(keep_days)
    except Exception as e:
        logger.error(f"Backup cleanup failed: {e}")
        raise HTTPException(500, f"Backup cleanup failed: {e}")

# === BASE SYSTEM MANAGEMENT ===
@app.get("/base-system/status")
def get_base_system_status_endpoint(x_agent_token: str = Header(None)):
    return get_base_system_status(x_agent_token)

@app.post("/base-system/restart")
def restart_base_system_endpoint(x_agent_token: str = Header(None)):
    return restart_base_system(x_agent_token, MYSQL_ROOT_PASS)

@app.post("/base-system/stop")
def stop_base_system_endpoint(x_agent_token: str = Header(None)):
    return stop_base_system(x_agent_token)

@app.post("/base-system/start")
def start_base_system_endpoint(x_agent_token: str = Header(None)):
    return start_base_system(x_agent_token)

# === SYSTEMD MANAGEMENT ===
@app.get("/systemd/status")
def get_systemd_status_endpoint(x_agent_token: str = Header(None)):
    return get_systemd_status(x_agent_token)

@app.post("/systemd/update")
def update_systemd_service_endpoint(x_agent_token: str = Header(None)):
    return update_systemd_service(x_agent_token)

# === MAIN ===
if __name__ == "__main__":
    uvicorn.run(app, host=CONFIG["agent"]["host"], port=AGENT_PORT)
