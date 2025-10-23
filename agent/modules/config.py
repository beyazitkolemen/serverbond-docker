"""
Configuration management module
"""
import json
from pathlib import Path

def load_config():
    """Load configuration from config.json or use fallback"""
    config_path = Path(__file__).parent.parent / "config.json"
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
