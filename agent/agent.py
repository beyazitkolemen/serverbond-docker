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
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

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

# === PYDANTIC MODELS ===
class SiteInfo(BaseModel):
    name: str
    framework: str
    path: str
    status: str
    running: bool
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "my-laravel-app",
                "framework": "laravel",
                "path": "/opt/sites/my-laravel-app",
                "status": "running",
                "running": True
            }
        }

class SiteStatus(BaseModel):
    name: str
    framework: str
    path: str
    status: str
    running: bool
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "my-laravel-app",
                "framework": "laravel",
                "path": "/opt/sites/my-laravel-app",
                "status": "running",
                "running": True
            }
        }

class BuildSiteRequest(BaseModel):
    name: str
    framework: str = "laravel"
    domain: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "my-new-site",
                "framework": "laravel",
                "domain": "my-new-site.local"
            }
        }

class BuildSiteResponse(BaseModel):
    message: str
    path: str
    framework: str
    domain: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Site my-new-site created successfully",
                "path": "/opt/sites/my-new-site",
                "framework": "laravel",
                "domain": "my-new-site.local"
            }
        }

class HealthResponse(BaseModel):
    status: str
    agent: str
    version: str
    docker: bool
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "agent": "ServerBond Agent MVP",
                "version": "1.0",
                "docker": True
            }
        }

class SystemStatus(BaseModel):
    base_system: dict
    sites: List[SiteInfo]
    total_sites: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "base_system": {
                    "mysql": {"status": "running", "running": True},
                    "redis": {"status": "running", "running": True},
                    "traefik": {"status": "running", "running": True}
                },
                "sites": [
                    {
                        "name": "my-laravel-app",
                        "framework": "laravel",
                        "path": "/opt/sites/my-laravel-app",
                        "status": "running",
                        "running": True
                    }
                ],
                "total_sites": 1
            }
        }

class SiteLogs(BaseModel):
    logs: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "logs": "2024-01-01 12:00:00 [INFO] Starting Laravel application\n2024-01-01 12:00:01 [INFO] Application started successfully"
            }
        }

class MessageResponse(BaseModel):
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Site my-laravel-app started successfully"
            }
        }

# === FASTAPI APP ===
app = FastAPI(
    title="ServerBond Agent",
    description="Docker Multi-site Management System",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === UTILITY FUNCTIONS ===

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

@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        agent="ServerBond Agent MVP",
        version="1.0",
        docker=docker_client.ping()
    )

@app.get("/status", response_model=SystemStatus)
async def status():
    """System status"""
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
                    
                    sites.append(SiteInfo(
                        name=site_name,
                        framework=framework,
                        path=str(site_dir),
                        status=container_status["status"],
                        running=container_status["running"]
                    ))
        
        return SystemStatus(
            base_system={
                "mysql": mysql_status,
                "redis": redis_status,
                "traefik": traefik_status
            },
            sites=sites,
            total_sites=len(sites)
        )
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sites", response_model=List[SiteInfo])
async def get_sites():
    """Get all sites"""
    try:
        sites = []
        if BASE_DIR.exists():
            for site_dir in BASE_DIR.iterdir():
                if site_dir.is_dir():
                    site_name = site_dir.name
                    framework = detect_framework(site_dir)
                    container_status = get_container_status(site_name)
                    
                    sites.append(SiteInfo(
                        name=site_name,
                        framework=framework,
                        path=str(site_dir),
                        status=container_status["status"],
                        running=container_status["running"]
                    ))
        
        return sites
    except Exception as e:
        logger.error(f"Error getting sites: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sites/{site_name}/status", response_model=SiteStatus)
async def get_site_status(site_name: str):
    """Get specific site status"""
    try:
        site_path = BASE_DIR / site_name
        if not site_path.exists():
            raise HTTPException(status_code=404, detail="Site not found")
        
        framework = detect_framework(site_path)
        container_status = get_container_status(site_name)
        
        return SiteStatus(
            name=site_name,
            framework=framework,
            path=str(site_path),
            status=container_status["status"],
            running=container_status["running"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting site status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sites/{site_name}/logs", response_model=SiteLogs)
async def get_site_logs(site_name: str):
    """Get site logs"""
    try:
        container = docker_client.containers.get(site_name)
        logs = container.logs(tail=100).decode('utf-8')
        return SiteLogs(logs=logs)
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail="Container not found")
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sites/{site_name}/start", response_model=MessageResponse)
async def start_site(site_name: str):
    """Start a site"""
    try:
        site_path = BASE_DIR / site_name
        if not site_path.exists():
            raise HTTPException(status_code=404, detail="Site not found")
        
        # Start with docker compose
        result = subprocess.run(
            ["docker", "compose", "up", "-d"],
            cwd=site_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return MessageResponse(message=f"Site {site_name} started successfully")
        else:
            raise HTTPException(status_code=500, detail=result.stderr)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting site: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sites/{site_name}/stop", response_model=MessageResponse)
async def stop_site(site_name: str):
    """Stop a site"""
    try:
        site_path = BASE_DIR / site_name
        if not site_path.exists():
            raise HTTPException(status_code=404, detail="Site not found")
        
        # Stop with docker compose
        result = subprocess.run(
            ["docker", "compose", "down"],
            cwd=site_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return MessageResponse(message=f"Site {site_name} stopped successfully")
        else:
            raise HTTPException(status_code=500, detail=result.stderr)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping site: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/sites/{site_name}", response_model=MessageResponse)
async def delete_site(site_name: str):
    """Delete a site"""
    try:
        site_path = BASE_DIR / site_name
        if not site_path.exists():
            raise HTTPException(status_code=404, detail="Site not found")
        
        # Stop and remove containers
        subprocess.run(["docker", "compose", "down", "-v"], cwd=site_path)
        
        # Remove directory
        import shutil
        shutil.rmtree(site_path)
        
        return MessageResponse(message=f"Site {site_name} deleted successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting site: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/build", response_model=BuildSiteResponse)
async def build_site(data: BuildSiteRequest):
    """Build a new site"""
    try:
        site_name = data.name
        framework = data.framework
        domain = data.domain or f"{site_name}.local"
        
        if not site_name:
            raise HTTPException(status_code=400, detail="Site name is required")
        
        site_path = BASE_DIR / site_name
        if site_path.exists():
            raise HTTPException(status_code=400, detail="Site already exists")
        
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
        
        return BuildSiteResponse(
            message=f"Site {site_name} created successfully",
            path=str(site_path),
            framework=framework,
            domain=domain
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error building site: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# === MAIN ===
if __name__ == "__main__":
    logger.info("Starting ServerBond Agent MVP...")
    logger.info(f"Base directory: {BASE_DIR}")
    logger.info(f"Template directory: {TEMPLATE_DIR}")
    logger.info(f"Network: {NETWORK}")
    logger.info(f"Port: {AGENT_PORT}")
    
    uvicorn.run(app, host="0.0.0.0", port=AGENT_PORT)