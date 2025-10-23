"""
Site building and deployment module
"""
import os
import secrets
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from fastapi import HTTPException

from .config import load_config

# Load config
CONFIG = load_config()
from .utils import log, write_file, detect_framework, provision_mysql
from .templates import render, generate_laravel_env

async def build_site(req, mysql_root_pass: str):
    """Build and deploy a new site"""
    try:
        app_name = req.domain.split(".")[0]
        app_dir = Path(CONFIG["paths"]["base_dir"]) / app_name
        app_dir.mkdir(parents=True, exist_ok=True)
        
        # Git clone
        log(f"📥 Cloning {req.repo}...")
        result = subprocess.run(
            ["git", "clone", req.repo, str(app_dir)],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            raise Exception(f"Git clone failed: {result.stderr}")
        
        # Framework detection
        if not req.framework:
            req.framework = detect_framework(app_dir)
            if req.framework == "unknown":
                raise Exception("Could not detect framework")
        
        log(f"🔍 Detected framework: {req.framework}")
        
        # Framework-specific setup
        if req.framework in ["laravel", "laravel-inertia"]:
            await setup_laravel_site(req, app_dir, app_name, mysql_root_pass)
        elif req.framework == "nextjs":
            await setup_nextjs_site(req, app_dir, app_name)
        elif req.framework == "nuxt":
            await setup_nuxt_site(req, app_dir, app_name)
        elif req.framework == "nodeapi":
            await setup_nodeapi_site(req, app_dir, app_name)
        elif req.framework == "static":
            await setup_static_site(req, app_dir, app_name)
        
        # Render templates
        await render_site_templates(req, app_dir, app_name)
        
        # Start containers
        log(f"🚀 Starting containers for {app_name}...")
        result = subprocess.run(
            ["docker", "compose", "up", "-d"],
            cwd=app_dir, capture_output=True, text=True, timeout=CONFIG["timeouts"]["docker_compose"]
        )
        if result.returncode != 0:
            raise Exception(f"Failed to start containers: {result.stderr}")
        
        log(f"✅ {app_name} deployed successfully!")
        return {"status": "success", "message": f"Site {app_name} deployed successfully"}
        
    except Exception as e:
        log(f"❌ Build failed for {app_name}: {e}")
        raise

async def setup_laravel_site(req, app_dir: Path, app_name: str, mysql_root_pass: str):
    """Setup Laravel site"""
    # Database provisioning
    if req.framework in ["laravel", "laravel-inertia"]:
        db_name = req.db_name or f"{app_name}_db"
        db_user = req.db_user or f"{app_name}_user"
        db_pass = req.db_pass or "secret"
        
        await provision_mysql(
            db_name, db_user, db_pass, mysql_root_pass,
            CONFIG["docker"]["shared_mysql_container"],
            CONFIG["defaults"]["mysql_charset"],
            CONFIG["defaults"]["mysql_collation"]
        )
        
        # Generate .env file
        env_content = generate_laravel_env(
            app_name, req.domain, db_name, db_user, db_pass,
            CONFIG["docker"]["shared_mysql_container"],
            CONFIG["docker"]["shared_redis_container"]
        )
        write_file(app_dir / ".env", env_content)
        
        # Install dependencies
        log(f"📦 Installing Laravel dependencies...")
        result = subprocess.run(
            ["docker", "run", "--rm", "-v", f"{app_dir}:/app", "-w", "/app", "composer:latest", "install", "--no-dev"],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            log(f"Warning: Composer install failed: {result.stderr}")

async def setup_nextjs_site(req, app_dir: Path, app_name: str):
    """Setup Next.js site"""
    # Install dependencies
    log(f"📦 Installing Next.js dependencies...")
    result = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{app_dir}:/app", "-w", "/app", f"node:{CONFIG['defaults']['node_version']}", "npm", "install"],
        capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0:
        log(f"Warning: npm install failed: {result.stderr}")

async def setup_nuxt_site(req, app_dir: Path, app_name: str):
    """Setup Nuxt.js site"""
    # Install dependencies
    log(f"📦 Installing Nuxt.js dependencies...")
    result = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{app_dir}:/app", "-w", "/app", f"node:{CONFIG['defaults']['node_version']}", "npm", "install"],
        capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0:
        log(f"Warning: npm install failed: {result.stderr}")

async def setup_nodeapi_site(req, app_dir: Path, app_name: str):
    """Setup Node.js API site"""
    # Install dependencies
    log(f"📦 Installing Node.js dependencies...")
    result = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{app_dir}:/app", "-w", "/app", f"node:{CONFIG['defaults']['node_version']}", "npm", "install"],
        capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0:
        log(f"Warning: npm install failed: {result.stderr}")

async def setup_static_site(req, app_dir: Path, app_name: str):
    """Setup static site"""
    log(f"📁 Setting up static site...")
    # Static sites don't need special setup
    pass

async def render_site_templates(req, app_dir: Path, app_name: str):
    """Render site templates"""
    tpl = Path(CONFIG["paths"]["template_dir"])
    framework = req.framework
    
    # PHP versiyon bilgilerini al ve validate et
    php_version = req.php_version or CONFIG["defaults"]["php_version"]
    if php_version not in CONFIG["php_versions"]:
        raise ValueError(f"Unsupported PHP version: {php_version}. Available versions: {list(CONFIG['php_versions'].keys())}")
    php_config = CONFIG["php_versions"][php_version]
    
    ctx = {
        "app_name": app_name,
        "domain": req.domain,
        "php_version": php_version,
        "php_image": php_config["image"],
        "php_extensions": php_config["extensions"],
        "network": CONFIG["docker"]["network"],
        "shared_mysql_container": CONFIG["docker"]["shared_mysql_container"],
        "shared_redis_container": CONFIG["docker"]["shared_redis_container"],
        "db_name": req.db_name or f"{app_name}_db",
        "db_user": req.db_user or f"{app_name}_user",
        "db_password": req.db_pass or "secret",
        "app_key": "base64:" + secrets.token_urlsafe(32),
    }
    
    # render all templates in framework dir
    tpl_dir = tpl / framework
    for t in tpl_dir.glob("*.j2"):
        out = app_dir / t.name.replace(".j2", "")
        write_file(out, render(tpl_dir, t.name, ctx))

async def redeploy_site(req, mysql_root_pass: str):
    """Redeploy an existing site"""
    try:
        app_name = req.domain.split(".")[0]
        app_dir = Path(CONFIG["paths"]["base_dir"]) / app_name
        
        if not app_dir.exists():
            raise Exception("Site not found")
        
        # Stop existing containers
        log(f"🛑 Stopping existing containers for {app_name}...")
        subprocess.run(
            ["docker", "compose", "down"],
            cwd=app_dir, capture_output=True, text=True, timeout=CONFIG["timeouts"]["docker_compose"]
        )
        
        # Pull latest changes
        log(f"📥 Pulling latest changes for {app_name}...")
        result = subprocess.run(
            ["git", "pull"],
            cwd=app_dir, capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            log(f"Warning: Git pull failed: {result.stderr}")
        
        # Re-render templates
        await render_site_templates(req, app_dir, app_name)
        
        # Start containers
        log(f"🚀 Starting containers for {app_name}...")
        result = subprocess.run(
            ["docker", "compose", "up", "-d"],
            cwd=app_dir, capture_output=True, text=True, timeout=CONFIG["timeouts"]["docker_compose"]
        )
        if result.returncode != 0:
            raise Exception(f"Failed to start containers: {result.stderr}")
        
        log(f"♻️ {app_name} redeployed successfully")
        return {"status": "success", "message": f"Site {app_name} redeployed successfully"}
        
    except Exception as e:
        log(f"❌ Redeploy failed for {app_name}: {e}")
        raise
