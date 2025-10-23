"""
Utility functions module
"""
import os
import subprocess
import shlex
import asyncio
from pathlib import Path
from datetime import datetime

def log(message):
    """Log message with timestamp"""
    print(f"[{datetime.utcnow().isoformat()}] {message}")

def write_file(path, content):
    """Write content to file"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content, encoding='utf-8')

def get_container_status(container_name: str, timeout: int = 10) -> str:
    """Get Docker container status"""
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except:
        return "unknown"

def detect_framework(path: Path) -> str:
    """Detect framework type from project files"""
    if (path / "composer.json").exists():
        deps = (path / "composer.json").read_text()
        if "laravel/framework" in deps:
            if "inertiajs/inertia" in deps:
                return "laravel-inertia"
            return "laravel"
    
    if (path / "package.json").exists():
        deps = (path / "package.json").read_text()
        if "next" in deps: return "nextjs"
        if "nuxt" in deps: return "nuxt"
        if "express" in deps or "fastify" in deps: return "nodeapi"
    
    if (path / "index.html").exists():
        return "static"
    
    return "unknown"

async def provision_mysql(db_name, db_user, db_pass, mysql_root_pass, shared_mysql_container, charset="utf8mb4", collation="utf8mb4_unicode_ci"):
    """Provision MySQL database and user"""
    sql = f"""
    CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET {charset} COLLATE {collation};
    CREATE USER IF NOT EXISTS '{db_user}'@'%' IDENTIFIED BY '{db_pass}';
    GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{db_user}'@'%';
    FLUSH PRIVILEGES;
    """
    cmd = f"docker exec -i {shared_mysql_container} mysql -uroot -p{shlex.quote(mysql_root_pass)}"
    proc = await asyncio.create_subprocess_shell(cmd, stdin=asyncio.subprocess.PIPE)
    await proc.communicate(sql.encode())
    log(f"MySQL database '{db_name}' and user '{db_user}' created ✅")
