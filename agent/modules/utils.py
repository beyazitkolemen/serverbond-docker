"""
Production-ready utility functions module
"""
import os
import subprocess
import shlex
import asyncio
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from .logger import log
from .security import SecurityValidator

def write_file(path: str, content: str, mode: str = 'w', backup: bool = True) -> bool:
    """Safely write content to file with backup"""
    try:
        file_path = Path(path)
        
        # Create backup if file exists and backup is requested
        if backup and file_path.exists():
            backup_path = file_path.with_suffix(f"{file_path.suffix}.backup")
            shutil.copy2(file_path, backup_path)
            log(f"Created backup: {backup_path}")
        
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        file_path.write_text(content, encoding='utf-8')
        log(f"File written successfully: {file_path}")
        return True
        
    except Exception as e:
        log(f"Failed to write file {path}: {e}", level="ERROR")
        return False

def get_container_status(container_name: str, timeout: int = 10) -> str:
    """Get Docker container status with error handling"""
    try:
        # Sanitize container name
        container_name = SecurityValidator.sanitize_filename(container_name)
        
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
            capture_output=True, text=True, timeout=timeout
        )
        
        if result.returncode == 0:
            status = result.stdout.strip()
            log(f"Container {container_name} status: {status}")
            return status
        else:
            log(f"Failed to get container status for {container_name}: {result.stderr}", level="WARNING")
            return "unknown"
    except subprocess.TimeoutExpired:
        log(f"Timeout getting container status for {container_name}", level="WARNING")
        return "timeout"
    except Exception as e:
        log(f"Error getting container status for {container_name}: {e}", level="ERROR")
        return "error"

def detect_framework(path: Path) -> str:
    """Detect framework type from project files with enhanced detection"""
    try:
        if not path.exists() or not path.is_dir():
            log(f"Invalid path for framework detection: {path}", level="WARNING")
            return "unknown"
        
        # Check for Laravel
        if (path / "composer.json").exists():
            try:
                composer_content = (path / "composer.json").read_text(encoding='utf-8')
                if "laravel/framework" in composer_content:
                    if "inertiajs/inertia" in composer_content:
                        log(f"Detected Laravel Inertia at {path}")
                        return "laravel-inertia"
                    log(f"Detected Laravel at {path}")
                    return "laravel"
            except Exception as e:
                log(f"Error reading composer.json: {e}", level="WARNING")
        
        # Check for Node.js frameworks
        if (path / "package.json").exists():
            try:
                package_content = (path / "package.json").read_text(encoding='utf-8')
                if "next" in package_content:
                    log(f"Detected Next.js at {path}")
                    return "nextjs"
                if "nuxt" in package_content:
                    log(f"Detected Nuxt.js at {path}")
                    return "nuxt"
                if "express" in package_content or "fastify" in package_content:
                    log(f"Detected Node.js API at {path}")
                    return "nodeapi"
            except Exception as e:
                log(f"Error reading package.json: {e}", level="WARNING")
        
        # Check for static site
        if (path / "index.html").exists():
            log(f"Detected static site at {path}")
            return "static"
        
        log(f"No framework detected at {path}", level="WARNING")
        return "unknown"
        
    except Exception as e:
        log(f"Error in framework detection: {e}", level="ERROR")
        return "unknown"

async def provision_mysql(db_name: str, db_user: str, db_pass: str, mysql_root_pass: str, 
                         shared_mysql_container: str, charset: str = "utf8mb4", 
                         collation: str = "utf8mb4_unicode_ci") -> bool:
    """Provision MySQL database and user with enhanced error handling"""
    try:
        # Validate inputs
        if not all([db_name, db_user, db_pass, mysql_root_pass, shared_mysql_container]):
            log("Missing required parameters for MySQL provisioning", level="ERROR")
            return False
        
        # Sanitize inputs
        db_name = SecurityValidator.sanitize_filename(db_name)
        db_user = SecurityValidator.sanitize_filename(db_user)
        
        # Check if container is running
        container_status = get_container_status(shared_mysql_container)
        if container_status != "running":
            log(f"MySQL container {shared_mysql_container} is not running: {container_status}", level="ERROR")
            return False
        
        # Prepare SQL
        sql = f"""
        CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET {charset} COLLATE {collation};
        CREATE USER IF NOT EXISTS '{db_user}'@'%' IDENTIFIED BY '{db_pass}';
        GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{db_user}'@'%';
        FLUSH PRIVILEGES;
        """
        
        # Execute SQL
        cmd = f"docker exec -i {shared_mysql_container} mysql -uroot -p{shlex.quote(mysql_root_pass)}"
        proc = await asyncio.create_subprocess_shell(
            cmd, 
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate(sql.encode())
        
        if proc.returncode == 0:
            log(f"MySQL database '{db_name}' and user '{db_user}' created successfully ✅")
            return True
        else:
            log(f"MySQL provisioning failed: {stderr.decode()}", level="ERROR")
            return False
            
    except Exception as e:
        log(f"Error in MySQL provisioning: {e}", level="ERROR")
        return False
