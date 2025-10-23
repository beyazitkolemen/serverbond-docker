#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, json, shlex, asyncio
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, HTTPException, Header
from pydantic import BaseModel
from jinja2 import Environment, FileSystemLoader
from datetime import datetime

# === CONFIG ===
BASE_DIR = Path(os.getenv("SB_BASE_DIR", "/opt/sites"))
TEMPLATE_DIR = Path(os.getenv("SB_TEMPLATE_DIR", "/opt/serverbond-agent/templates"))
NETWORK = os.getenv("SB_NETWORK", "shared_net")
MYSQL_ROOT_PASS = os.getenv("SB_MYSQL_ROOT_PASSWORD", "root")
SHARED_MYSQL = os.getenv("SB_SHARED_MYSQL_CONTAINER", "shared_mysql")
SHARED_REDIS = os.getenv("SB_SHARED_REDIS_CONTAINER", "shared_redis")
AGENT_TOKEN = os.getenv("SB_AGENT_TOKEN")
AGENT_PORT = int(os.getenv("SB_AGENT_PORT", 8000))

app = FastAPI(title="ServerBond Agent", version="4.0")

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
    sql = f"""
    CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    CREATE USER IF NOT EXISTS '{db_user}'@'%' IDENTIFIED BY '{db_pass}';
    GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{db_user}'@'%';
    FLUSH PRIVILEGES;
    """
    cmd = f"docker exec -i {SHARED_MYSQL} mysql -uroot -p{shlex.quote(MYSQL_ROOT_PASS)}"
    proc = await asyncio.create_subprocess_shell(cmd, stdin=asyncio.subprocess.PIPE)
    await proc.communicate(sql.encode())

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

# === ENDPOINTS ===
@app.get("/health")
def health(): return {"ok": True, "time": datetime.utcnow().isoformat()}

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

# === TASKS ===
async def build_site(req: BuildRequest):
    app_name = req.domain.split(".")[0]
    app_dir = BASE_DIR / app_name
    src = app_dir / "src"
    tpl = TEMPLATE_DIR
    log(f"🚀 Build starting for {app_name}")
    await ensure_network()

    await git_clone(req.repo, src, branch=req.branch)
    framework = req.framework or detect_framework(src)
    log(f"Framework detected: {framework}")

    env_content = merge_env(src / ".env.example", req.env or {})
    if framework.startswith("laravel"):
        env_content += f"DB_HOST={SHARED_MYSQL}\nREDIS_HOST={SHARED_REDIS}\n"
    write_file(src / ".env", env_content)

    tpl_dir = tpl / framework
    ctx = {
        "app_name": app_name,
        "domain": req.domain,
        "php_version": req.php_version,
        "network": NETWORK,
    }

    # render all templates in framework dir
    for t in tpl_dir.glob("*.j2"):
        out = app_dir / t.name.replace(".j2", "")
        write_file(out, render(tpl_dir, t.name, ctx))
    log("Templates rendered ✅")

    # DB provisioning
    if framework.startswith("laravel") and req.db_name:
        await provision_mysql(req.db_name, req.db_user or f"{app_name}_user", req.db_pass or "secret")
        with open(src / ".env", "a") as f:
            f.write(f"DB_DATABASE={req.db_name}\nDB_USERNAME={req.db_user or app_name}_user\nDB_PASSWORD={req.db_pass or 'secret'}\n")

    await run("docker compose build", cwd=app_dir)
    await run("docker compose up -d", cwd=app_dir)
    if framework.startswith("laravel"):
        await run(f"docker exec {app_name}_app php artisan key:generate || true", allow_fail=True)
        await run(f"docker exec {app_name}_app php artisan migrate --force || true", allow_fail=True)
    log(f"✅ {app_name} deployed successfully")

async def redeploy_site(req: RedeployRequest):
    app_name = req.domain.split(".")[0]
    app_dir = BASE_DIR / app_name
    src = app_dir / "src"
    if req.pull:
        await run("git pull", cwd=src)
    await run("docker compose up -d --build", cwd=app_dir)
    if req.run_migrations:
        await run(f"docker exec {app_name}_app php artisan migrate --force || true", allow_fail=True)
    log(f"♻️ {app_name} redeployed")

# === MAIN ===
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=AGENT_PORT)
