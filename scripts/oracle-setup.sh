#!/usr/bin/env bash
# One-time (and safe to re-run) setup for an Ubuntu 22.04/24.04 server,
# e.g. an Oracle Cloud Always Free Ampere A1 VM.
#   cd ~/BOMerang && bash scripts/oracle-setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Installing Docker Engine + Compose plugin (official Docker repo)"
if ! command -v docker >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER" || true

echo "==> Opening ports 80 and 443 in the server's own firewall"
# Oracle's Ubuntu images ship iptables rules that reject everything except SSH,
# even when the cloud security list allows the port.
if ! command -v netfilter-persistent >/dev/null 2>&1; then
  echo iptables-persistent iptables-persistent/autosave_v4 boolean true | sudo debconf-set-selections
  echo iptables-persistent iptables-persistent/autosave_v6 boolean true | sudo debconf-set-selections
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent netfilter-persistent
fi
for rule in "-p tcp --dport 80" "-p tcp --dport 443" "-p udp --dport 443"; do
  # shellcheck disable=SC2086
  sudo iptables -C INPUT $rule -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 1 $rule -j ACCEPT
done
sudo netfilter-persistent save

echo "==> Checking .env"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "   Created .env from .env.example. Edit it (nano .env) to add ANTHROPIC_API_KEY, then re-run this script."
fi

echo "==> Building and starting BOMerang"
sudo docker compose -f docker-compose.prod.yml up -d --build

echo "==> Waiting for the API to report healthy"
for _ in $(seq 1 60); do
  if curl -fsS http://localhost/api/health >/dev/null 2>&1; then
    curl -fsS http://localhost/api/health; echo
    IP=$(curl -fsS https://ifconfig.me 2>/dev/null || echo "<your-public-ip>")
    echo "==> Done. Open http://$IP"
    exit 0
  fi
  sleep 3
done
echo "API did not come up. Check: sudo docker compose -f docker-compose.prod.yml logs api"
exit 1
