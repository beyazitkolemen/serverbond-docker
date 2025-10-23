"""
Backup and recovery module for production systems
"""
import json
import shutil
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import HTTPException

class BackupManager:
    """Production backup and recovery manager"""
    
    def __init__(self, backup_dir: str = "/opt/serverbond-backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_full_backup(self) -> Dict[str, Any]:
        """Create full system backup"""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_name = f"serverbond_full_{timestamp}"
            backup_path = self.backup_dir / f"{backup_name}.tar.gz"
            
            # Create backup archive
            with tarfile.open(backup_path, "w:gz") as tar:
                # Backup agent files
                agent_dir = Path("/opt/serverbond-agent")
                if agent_dir.exists():
                    tar.add(agent_dir, arcname="agent")
                
                # Backup config
                config_dir = Path("/opt/serverbond-config")
                if config_dir.exists():
                    tar.add(config_dir, arcname="config")
                
                # Backup sites (without large files)
                sites_dir = Path("/opt/sites")
                if sites_dir.exists():
                    for site in sites_dir.iterdir():
                        if site.is_dir():
                            # Only backup docker-compose.yml and .env files
                            for file in site.glob("*.yml"):
                                tar.add(file, arcname=f"sites/{site.name}/{file.name}")
                            for file in site.glob(".env"):
                                tar.add(file, arcname=f"sites/{site.name}/{file.name}")
                
                # Backup shared services config
                shared_dir = Path("/opt/shared-services")
                if shared_dir.exists():
                    for file in shared_dir.glob("*.yml"):
                        tar.add(file, arcname=f"shared/{file.name}")
            
            # Create backup metadata
            metadata = {
                "backup_name": backup_name,
                "timestamp": timestamp,
                "type": "full",
                "size": backup_path.stat().st_size,
                "created_at": datetime.utcnow().isoformat()
            }
            
            metadata_path = self.backup_dir / f"{backup_name}.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return {
                "status": "success",
                "backup_name": backup_name,
                "backup_path": str(backup_path),
                "size": backup_path.stat().st_size,
                "metadata": metadata
            }
            
        except Exception as e:
            raise HTTPException(500, f"Backup creation failed: {e}")
    
    def create_site_backup(self, site_name: str) -> Dict[str, Any]:
        """Create backup for specific site"""
        try:
            site_dir = Path("/opt/sites") / site_name
            if not site_dir.exists():
                raise HTTPException(404, f"Site {site_name} not found")
            
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_name = f"site_{site_name}_{timestamp}"
            backup_path = self.backup_dir / f"{backup_name}.tar.gz"
            
            with tarfile.open(backup_path, "w:gz") as tar:
                tar.add(site_dir, arcname=site_name)
            
            metadata = {
                "backup_name": backup_name,
                "site_name": site_name,
                "timestamp": timestamp,
                "type": "site",
                "size": backup_path.stat().st_size,
                "created_at": datetime.utcnow().isoformat()
            }
            
            metadata_path = self.backup_dir / f"{backup_name}.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return {
                "status": "success",
                "backup_name": backup_name,
                "site_name": site_name,
                "backup_path": str(backup_path),
                "size": backup_path.stat().st_size,
                "metadata": metadata
            }
            
        except Exception as e:
            raise HTTPException(500, f"Site backup creation failed: {e}")
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups"""
        backups = []
        
        for backup_file in self.backup_dir.glob("*.tar.gz"):
            metadata_file = backup_file.with_suffix('.json')
            
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    backups.append(metadata)
                except:
                    # Fallback for backups without metadata
                    backups.append({
                        "backup_name": backup_file.stem,
                        "timestamp": "unknown",
                        "type": "unknown",
                        "size": backup_file.stat().st_size,
                        "created_at": datetime.fromtimestamp(backup_file.stat().st_mtime).isoformat()
                    })
        
        return sorted(backups, key=lambda x: x.get('created_at', ''), reverse=True)
    
    def restore_backup(self, backup_name: str) -> Dict[str, Any]:
        """Restore from backup"""
        try:
            backup_path = self.backup_dir / f"{backup_name}.tar.gz"
            if not backup_path.exists():
                raise HTTPException(404, f"Backup {backup_name} not found")
            
            # Stop agent before restore
            subprocess.run(["systemctl", "stop", "serverbond-agent"], 
                         capture_output=True, timeout=30)
            
            # Extract backup
            with tarfile.open(backup_path, "r:gz") as tar:
                tar.extractall("/tmp/restore")
            
            # Restore files
            restore_dir = Path("/tmp/restore")
            
            # Restore agent files
            if (restore_dir / "agent").exists():
                shutil.rmtree("/opt/serverbond-agent", ignore_errors=True)
                shutil.copytree(restore_dir / "agent", "/opt/serverbond-agent")
            
            # Restore config
            if (restore_dir / "config").exists():
                shutil.rmtree("/opt/serverbond-config", ignore_errors=True)
                shutil.copytree(restore_dir / "config", "/opt/serverbond-config")
            
            # Restore sites
            if (restore_dir / "sites").exists():
                for site_dir in (restore_dir / "sites").iterdir():
                    target_site = Path("/opt/sites") / site_dir.name
                    target_site.mkdir(parents=True, exist_ok=True)
                    
                    for file in site_dir.iterdir():
                        shutil.copy2(file, target_site / file.name)
            
            # Cleanup
            shutil.rmtree("/tmp/restore", ignore_errors=True)
            
            # Restart agent
            subprocess.run(["systemctl", "start", "serverbond-agent"], 
                         capture_output=True, timeout=30)
            
            return {
                "status": "success",
                "message": f"Backup {backup_name} restored successfully"
            }
            
        except Exception as e:
            raise HTTPException(500, f"Backup restore failed: {e}")
    
    def cleanup_old_backups(self, keep_days: int = 30) -> Dict[str, Any]:
        """Cleanup old backups"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=keep_days)
            deleted_count = 0
            freed_space = 0
            
            for backup_file in self.backup_dir.glob("*.tar.gz"):
                file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                if file_time < cutoff_date:
                    file_size = backup_file.stat().st_size
                    backup_file.unlink()
                    
                    # Also delete metadata file
                    metadata_file = backup_file.with_suffix('.json')
                    if metadata_file.exists():
                        metadata_file.unlink()
                    
                    deleted_count += 1
                    freed_space += file_size
            
            return {
                "status": "success",
                "deleted_count": deleted_count,
                "freed_space": freed_space,
                "message": f"Cleaned up {deleted_count} old backups, freed {freed_space} bytes"
            }
            
        except Exception as e:
            raise HTTPException(500, f"Backup cleanup failed: {e}")

# Global backup manager
backup_manager = BackupManager()
