#!/usr/bin/env bash
set -euo pipefail

log() { echo -e "\033[1;36m[INFO]\033[0m $*"; }

log "=== Docker Agent API kurulumu başlatılıyor ==="

apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip docker.io

mkdir -p /opt/docker-agent
cd /opt/docker-agent

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install fastapi uvicorn docker python-dotenv

cat > /opt/docker-agent/app.py <<'EOF'
from fastapi import FastAPI, HTTPException, Depends, Header
import docker, os

API_TOKEN = os.getenv("AGENT_TOKEN", "secret-token")

app = FastAPI(title="Docker Agent API", version="1.0")
client = docker.from_env()

def verify_token(x_token: str = Header(...)):
    if x_token != API_TOKEN:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return True

@app.get("/containers", dependencies=[Depends(verify_token)])
def list_containers():
    containers = client.containers.list(all=True)
    return [{"id": c.id[:12], "name": c.name, "status": c.status, "image": c.image.tags} for c in containers]

@app.post("/containers/run", dependencies=[Depends(verify_token)])
def run_container(image: str, name: str = None):
    try:
        container = client.containers.run(image, name=name, detach=True)
        return {"id": container.id[:12], "name": container.name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/containers/stop/{container_id}", dependencies=[Depends(verify_token)])
def stop_container(container_id: str):
    try:
        container = client.containers.get(container_id)
        container.stop()
        return {"status": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
EOF

cat > /etc/systemd/system/docker-agent.service <<'EOF'
[Unit]
Description=Docker Agent API
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/docker-agent
Environment="AGENT_TOKEN=your_secure_token_here"
ExecStart=/opt/docker-agent/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable docker-agent
systemctl start docker-agent

log "Docker Agent API başarıyla kuruldu! Port: 8000"
