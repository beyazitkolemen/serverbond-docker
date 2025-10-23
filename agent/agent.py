#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, json, shlex, asyncio, secrets, subprocess, shutil, sys
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, HTTPException, Header
from pydantic import BaseModel
from jinja2 import Environment, FileSystemLoader
from datetime import datetime

# === CONFIG LOADING ===
def load_config():
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # Fallback config if file doesn't exist
        return {
            "agent": {"name": "ServerBond Agent", "version": "4.0", "port": 8000, "host": "0.0.0.0"},
            "paths": {"base_dir": "/opt/sites", "template_dir": "/opt/serverbond-agent/templates", "config_dir": "/opt/serverbond-config", "agent_dir": "/opt/serverbond-agent"},
            "docker": {"network": "shared_net", "shared_mysql_container": "shared_mysql", "shared_redis_container": "shared_redis"},
            "github": {"agent_url": "https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/agent/agent.py", "templates_url": "https://raw.githubusercontent.com/beyazitkolemen/serverbond-docker/main/templates"},
            "frameworks": {},
            "defaults": {"php_version": "8.3", "node_version": "20", "mysql_charset": "utf8mb4", "mysql_collation": "utf8mb4_unicode_ci"},
            "timeouts": {"docker_inspect": 10, "docker_logs": 30, "docker_compose": 60, "curl_download": 30, "systemctl": 30}
        }

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

# MySQL root şifresini dosyadan oku
MYSQL_ROOT_PASS_FILE = CONFIG_DIR / "mysql_root_password.txt"
if MYSQL_ROOT_PASS_FILE.exists():
    MYSQL_ROOT_PASS = MYSQL_ROOT_PASS_FILE.read_text().strip()
else:
    MYSQL_ROOT_PASS = os.getenv("SB_MYSQL_ROOT_PASSWORD", "root")

app = FastAPI(title=CONFIG["agent"]["name"], version=CONFIG["agent"]["version"])

# === UTILS ===
def log(msg: str): print(f"\033[1;36m[Agent]\033[0m {msg}")

async def run(cmd: str, cwd=None, allow_fail=False):
    proc = await asyncio.create_subprocess_shell(
        cmd, cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    async for line in proc.stdout:
        print(line.decode().rstrip())
    rc = await proc.wait()
    if rc != 0 and not allow_fail:
        raise RuntimeError(f"Command failed: {cmd}")

def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def render(tpl_dir: Path, tpl: str, ctx: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(tpl_dir)))
    return env.get_template(tpl).render(ctx)

async def ensure_network():
    await run(f"docker network create {NETWORK} || true")

async def git_clone(repo: str, dest: Path, branch: str = "main"):
    if (dest / ".git").exists():
        await run(f"git -C {dest} pull")
    else:
        await run(f"git clone -b {shlex.quote(branch)} {shlex.quote(repo)} {dest}")

def detect_framework(path: Path) -> str:
    if (path / "composer.json").exists():
        if (path / "resources/js/Pages").exists():
            return "laravel-inertia"
        return "laravel"
    if (path / "package.json").exists():
        pkg = json.loads((path / "package.json").read_text())
        deps = list(pkg.get("dependencies", {}).keys()) + list(pkg.get("devDependencies", {}).keys())
        if "next" in deps: return "nextjs"
        if "nuxt" in deps: return "nuxt"
        if "react" in deps: return "react"
        if "express" in deps or "fastify" in deps: return "nodeapi"
    if (path / "index.html").exists():
        return "static"
    return "unknown"

async def provision_mysql(db_name, db_user, db_pass):
    charset = CONFIG["defaults"]["mysql_charset"]
    collation = CONFIG["defaults"]["mysql_collation"]
    sql = f"""
    CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET {charset} COLLATE {collation};
    CREATE USER IF NOT EXISTS '{db_user}'@'%' IDENTIFIED BY '{db_pass}';
    GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{db_user}'@'%';
    FLUSH PRIVILEGES;
    """
    cmd = f"docker exec -i {SHARED_MYSQL} mysql -uroot -p{shlex.quote(MYSQL_ROOT_PASS)}"
    proc = await asyncio.create_subprocess_shell(cmd, stdin=asyncio.subprocess.PIPE)
    await proc.communicate(sql.encode())
    log(f"MySQL database '{db_name}' and user '{db_user}' created ✅")

def merge_env(example: Path, overrides: dict) -> str:
    env_data = {}
    if example.exists():
        for line in example.read_text().splitlines():
            if not line or line.startswith("#") or "=" not in line: continue
            k, v = line.split("=", 1); env_data[k.strip()] = v.strip()
    env_data.update(overrides)
    return "\n".join([f"{k}={v}" for k, v in env_data.items()]) + "\n"

def protect(token):
    if AGENT_TOKEN and token != AGENT_TOKEN:
        raise HTTPException(401, "Unauthorized")

def get_container_status(container_name: str) -> str:
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
            capture_output=True, text=True, timeout=CONFIG["timeouts"]["docker_inspect"]
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except:
        return "unknown"

# === SCHEMAS ===
class BuildRequest(BaseModel):
    repo: str
    domain: str
    branch: str = "main"
    php_version: str = "8.3"
    env: dict | None = None
    framework: str | None = None
    db_name: str | None = None
    db_user: str | None = None
    db_pass: str | None = None

class RedeployRequest(BaseModel):
    domain: str
    pull: bool = True
    run_migrations: bool = True
    post_deploy_commands: list[str] = []

# === ENDPOINTS ===
@app.get("/health")
def health(): return {"ok": True, "time": datetime.utcnow().isoformat()}

@app.get("/status")
def system_status(x_agent_token: str = Header(None)):
    protect(x_agent_token)
    try:
        # Docker durumu
        docker_result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True, text=True, timeout=CONFIG["timeouts"]["docker_inspect"]
        )
        docker_version = docker_result.stdout.strip() if docker_result.returncode == 0 else "unknown"
        
        # Shared servislerin durumu
        shared_services = {}
        for service in [SHARED_MYSQL, SHARED_REDIS]:
            status = get_container_status(service)
            shared_services[service] = status
        
        # Site sayısı
        site_count = len([d for d in BASE_DIR.iterdir() if d.is_dir() and (d / "docker-compose.yml").exists()])
        
        return {
            "docker_version": docker_version,
            "shared_services": shared_services,
            "site_count": site_count,
            "base_dir": str(BASE_DIR),
            "template_dir": CONFIG["paths"]["template_dir"],
            "network": NETWORK,
            "time": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to get system status: {e}")

@app.get("/sites")
def list_sites(x_agent_token: str = Header(None)):
    protect(x_agent_token)
    sites = []
    for site_dir in BASE_DIR.iterdir():
        if site_dir.is_dir() and (site_dir / "docker-compose.yml").exists():
            container_status = get_container_status(site_dir.name)
            sites.append({
                "name": site_dir.name,
                "domain": site_dir.name + ".serverbond.dev",
                "status": container_status,
                "path": str(site_dir)
            })
    return {"sites": sites}

@app.post("/build")
async def build(req: BuildRequest, bg: BackgroundTasks, x_agent_token: str = Header(None)):
    protect(x_agent_token)
    bg.add_task(build_site, req)
    return {"status": "queued", "domain": req.domain}

@app.post("/redeploy")
async def redeploy(req: RedeployRequest, bg: BackgroundTasks, x_agent_token: str = Header(None)):
    protect(x_agent_token)
    bg.add_task(redeploy_site, req)
    return {"status": "queued", "domain": req.domain}

@app.get("/sites/{site_name}/status")
def get_site_status(site_name: str, x_agent_token: str = Header(None)):
    protect(x_agent_token)
    site_dir = BASE_DIR / site_name
    if not site_dir.exists() or not (site_dir / "docker-compose.yml").exists():
        raise HTTPException(404, "Site not found")
    
    container_status = get_container_status(site_name)
    return {
        "name": site_name,
        "domain": site_name + ".serverbond.dev",
        "status": container_status,
        "path": str(site_dir)
    }

@app.get("/sites/{site_name}/logs")
def get_site_logs(site_name: str, x_agent_token: str = Header(None)):
    protect(x_agent_token)
    site_dir = BASE_DIR / site_name
    if not site_dir.exists() or not (site_dir / "docker-compose.yml").exists():
        raise HTTPException(404, "Site not found")
    
    try:
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
        raise HTTPException(500, f"Failed to get logs: {e}")

@app.post("/sites/{site_name}/start")
def start_site(site_name: str, x_agent_token: str = Header(None)):
    protect(x_agent_token)
    site_dir = BASE_DIR / site_name
    if not site_dir.exists() or not (site_dir / "docker-compose.yml").exists():
        raise HTTPException(404, "Site not found")
    
    try:
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

@app.post("/sites/{site_name}/stop")
def stop_site(site_name: str, x_agent_token: str = Header(None)):
    protect(x_agent_token)
    site_dir = BASE_DIR / site_name
    if not site_dir.exists() or not (site_dir / "docker-compose.yml").exists():
        raise HTTPException(404, "Site not found")
    
    try:
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

@app.delete("/sites/{site_name}")
def delete_site(site_name: str, x_agent_token: str = Header(None)):
    protect(x_agent_token)
    site_dir = BASE_DIR / site_name
    if not site_dir.exists() or not (site_dir / "docker-compose.yml").exists():
        raise HTTPException(404, "Site not found")
    
    try:
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
            "message": f"Site {site_name} has been deleted successfully"
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to delete site: {e}")

@app.post("/templates/update")
def update_templates(x_agent_token: str = Header(None)):
    protect(x_agent_token)
    try:
        # Template'leri yeniden indir
        template_url = CONFIG["github"]["templates_url"]
        
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
            "message": "Templates updated successfully",
            "frameworks": frameworks
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to update templates: {e}")

@app.post("/restart")
def restart_agent(x_agent_token: str = Header(None)):
    protect(x_agent_token)
    try:
        # systemd servisini yeniden başlat
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

@app.get("/logs")
def get_agent_logs(x_agent_token: str = Header(None)):
    protect(x_agent_token)
    try:
        # systemd loglarını al
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

@app.post("/stop")
def stop_agent(x_agent_token: str = Header(None)):
    protect(x_agent_token)
    try:
        # systemd servisini durdur
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

@app.post("/start")
def start_agent(x_agent_token: str = Header(None)):
    protect(x_agent_token)
    try:
        # systemd servisini başlat
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

@app.post("/update")
def update_agent(x_agent_token: str = Header(None)):
    protect(x_agent_token)
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

@app.get("/info")
def get_agent_info(x_agent_token: str = Header(None)):
    protect(x_agent_token)
    return {
        "name": CONFIG["agent"]["name"],
        "version": CONFIG["agent"]["version"],
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "base_dir": str(BASE_DIR),
        "template_dir": CONFIG["paths"]["template_dir"],
        "network": NETWORK,
        "config_dir": str(CONFIG_DIR),
        "shared_mysql": SHARED_MYSQL,
        "shared_redis": SHARED_REDIS,
        "agent_port": AGENT_PORT,
        "time": datetime.utcnow().isoformat()
    }

# === TASKS ===
async def build_site(req: BuildRequest):
    try:
        app_name = req.domain.split(".")[0]
        app_dir = BASE_DIR / app_name
        src = app_dir / "src"
        tpl = TEMPLATE_DIR
        log(f"🚀 Build starting for {app_name}")
        await ensure_network()

        await git_clone(req.repo, src, branch=req.branch)
        framework = req.framework or detect_framework(src)
        log(f"Framework detected: {framework}")
        
        if framework == "unknown":
            raise ValueError(f"Unknown framework for {req.repo}")

    env_content = merge_env(src / ".env.example", req.env or {})
    if framework.startswith("laravel"):
        env_content += f"""DB_HOST={SHARED_MYSQL}
DB_PORT=3306
DB_DATABASE={req.db_name or f"{app_name}_db"}
DB_USERNAME={req.db_user or f"{app_name}_user"}
DB_PASSWORD={req.db_pass or "secret"}
REDIS_HOST={SHARED_REDIS}
REDIS_PORT=6379
CACHE_DRIVER=redis
SESSION_DRIVER=redis
QUEUE_CONNECTION=redis
"""
    write_file(src / ".env", env_content)

    tpl_dir = tpl / framework
    ctx = {
        "app_name": app_name,
        "domain": req.domain,
        "php_version": req.php_version or CONFIG["defaults"]["php_version"],
        "network": NETWORK,
        "shared_mysql_container": SHARED_MYSQL,
        "shared_redis_container": SHARED_REDIS,
        "db_name": req.db_name or f"{app_name}_db",
        "db_user": req.db_user or f"{app_name}_user",
        "db_password": req.db_pass or "secret",
        "app_key": "base64:" + secrets.token_urlsafe(32),
    }

    # render all templates in framework dir
    for t in tpl_dir.glob("*.j2"):
        out = app_dir / t.name.replace(".j2", "")
        write_file(out, render(tpl_dir, t.name, ctx))
    log("Templates rendered ✅")

    # DB provisioning
    if framework.startswith("laravel"):
        db_name = req.db_name or f"{app_name}_db"
        db_user = req.db_user or f"{app_name}_user"
        db_pass = req.db_pass or "secret"
        await provision_mysql(db_name, db_user, db_pass)

        await run("docker compose build", cwd=app_dir)
        await run("docker compose up -d", cwd=app_dir)
        if framework.startswith("laravel"):
            await run(f"docker exec {app_name} php artisan key:generate || true", allow_fail=True)
            await run(f"docker exec {app_name} php artisan migrate --force || true", allow_fail=True)
        log(f"✅ {app_name} deployed successfully")
    except Exception as e:
        log(f"❌ Build failed for {app_name}: {e}")
        raise

async def redeploy_site(req: RedeployRequest):
    try:
        app_name = req.domain.split(".")[0]
        app_dir = BASE_DIR / app_name
        src = app_dir / "src"
        
        log(f"♻️ Redeploying {app_name}")
        
        # Git pull
        if req.pull:
            await run("git pull", cwd=src)
            log("Git pull completed ✅")
        
        # Docker compose up
        await run("docker compose up -d --build", cwd=app_dir)
        log("Docker containers updated ✅")
        
        # Laravel migrations
        if req.run_migrations:
            await run(f"docker exec {app_name} php artisan migrate --force || true", allow_fail=True)
            log("Laravel migrations completed ✅")
        
        # Panel'den belirlenen post-deploy komutları
        if req.post_deploy_commands:
            log(f"Running {len(req.post_deploy_commands)} post-deploy commands...")
            for i, command in enumerate(req.post_deploy_commands, 1):
                try:
                    # Komut container içinde çalıştırılacaksa container adını ekle
                    if command.startswith("php artisan") or command.startswith("composer") or command.startswith("npm"):
                        container_name = app_name
                        full_command = f"docker exec {container_name} {command}"
                    else:
                        full_command = command
                    
                    log(f"Running command {i}/{len(req.post_deploy_commands)}: {command}")
                    await run(full_command, cwd=app_dir, allow_fail=True)
                    log(f"Command {i} completed ✅")
                except Exception as e:
                    log(f"Command {i} failed: {e}")
        
        log(f"♻️ {app_name} redeployed successfully")
    except Exception as e:
        log(f"❌ Redeploy failed for {app_name}: {e}")
        raise

# === MAIN ===
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=CONFIG["agent"]["host"], port=AGENT_PORT)
