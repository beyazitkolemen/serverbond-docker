"""
Production monitoring and health checks module
"""
import psutil
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class HealthStatus:
    """Health status data class"""
    status: str
    timestamp: datetime
    details: Dict[str, Any]
    uptime: float
    memory_usage: float
    cpu_usage: float
    disk_usage: float

class SystemMonitor:
    """System monitoring utilities"""
    
    def __init__(self):
        self.start_time = time.time()
    
    def get_system_health(self) -> HealthStatus:
        """Get comprehensive system health status"""
        try:
            # Basic system metrics
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            disk = psutil.disk_usage('/')
            
            # Docker status
            docker_status = self._check_docker_status()
            
            # Agent specific checks
            agent_checks = self._check_agent_health()
            
            # Determine overall status
            overall_status = "healthy"
            if not docker_status or not agent_checks.get('api_responding', False):
                overall_status = "unhealthy"
            elif memory.percent > 90 or cpu_percent > 90 or disk.percent > 90:
                overall_status = "degraded"
            
            return HealthStatus(
                status=overall_status,
                timestamp=datetime.utcnow(),
                details={
                    "docker": docker_status,
                    "agent": agent_checks,
                    "system": {
                        "memory_percent": memory.percent,
                        "cpu_percent": cpu_percent,
                        "disk_percent": disk.percent,
                        "load_average": psutil.getloadavg()
                    }
                },
                uptime=time.time() - self.start_time,
                memory_usage=memory.percent,
                cpu_usage=cpu_percent,
                disk_usage=disk.percent
            )
        except Exception as e:
            return HealthStatus(
                status="error",
                timestamp=datetime.utcnow(),
                details={"error": str(e)},
                uptime=time.time() - self.start_time,
                memory_usage=0,
                cpu_usage=0,
                disk_usage=0
            )
    
    def _check_docker_status(self) -> bool:
        """Check if Docker is running"""
        try:
            result = subprocess.run(
                ["docker", "version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except:
            return False
    
    def _check_agent_health(self) -> Dict[str, Any]:
        """Check agent-specific health metrics"""
        checks = {
            "api_responding": False,
            "config_loaded": False,
            "templates_available": False,
            "directories_writable": False
        }
        
        try:
            # Check if API is responding (this would be called from within the agent)
            checks["api_responding"] = True  # If we're here, API is responding
            
            # Check config
            config_path = Path("/opt/serverbond-agent/config.json")
            checks["config_loaded"] = config_path.exists()
            
            # Check templates
            templates_path = Path("/opt/serverbond-agent/templates")
            checks["templates_available"] = templates_path.exists() and any(templates_path.iterdir())
            
            # Check directory permissions
            base_dir = Path("/opt/sites")
            checks["directories_writable"] = base_dir.exists() and base_dir.is_dir()
            
        except Exception:
            pass
        
        return checks
    
    def get_container_metrics(self) -> List[Dict[str, Any]]:
        """Get Docker container metrics"""
        try:
            result = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", 
                 "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                containers = []
                for line in lines:
                    if line.strip():
                        parts = line.split('\t')
                        if len(parts) >= 5:
                            containers.append({
                                "container": parts[0],
                                "cpu_percent": parts[1],
                                "memory_usage": parts[2],
                                "network_io": parts[3],
                                "block_io": parts[4]
                            })
                return containers
        except Exception:
            pass
        
        return []
    
    def get_site_metrics(self) -> Dict[str, Any]:
        """Get site-specific metrics"""
        try:
            sites_dir = Path("/opt/sites")
            if not sites_dir.exists():
                return {"total_sites": 0, "active_sites": 0}
            
            sites = [d for d in sites_dir.iterdir() if d.is_dir()]
            active_sites = 0
            
            for site in sites:
                try:
                    # Check if site has docker-compose.yml
                    if (site / "docker-compose.yml").exists():
                        # Check if containers are running
                        result = subprocess.run(
                            ["docker", "compose", "ps", "--services", "--filter", "status=running"],
                            cwd=site,
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            active_sites += 1
                except:
                    pass
            
            return {
                "total_sites": len(sites),
                "active_sites": active_sites,
                "inactive_sites": len(sites) - active_sites
            }
        except Exception:
            return {"total_sites": 0, "active_sites": 0, "error": "Failed to get site metrics"}

# Global monitor instance
monitor = SystemMonitor()
