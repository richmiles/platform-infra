#!/bin/bash
set -euo pipefail

# Platform Infrastructure Setup Script
# Run this on a fresh Ubuntu 22.04 droplet

echo "=== Platform Infrastructure Setup ==="

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    echo "Please run as a regular user (not root). The script will use sudo when needed."
    exit 1
fi

# Update system
echo ">>> Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Docker
if ! command -v docker &> /dev/null; then
    echo ">>> Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    echo ">>> Docker installed. You'll need to log out and back in for group changes to take effect."
else
    echo ">>> Docker already installed"
fi

# Install fail2ban
if ! command -v fail2ban-client &> /dev/null; then
    echo ">>> Installing fail2ban..."
    sudo apt install -y fail2ban
    sudo systemctl enable fail2ban
    sudo systemctl start fail2ban
else
    echo ">>> fail2ban already installed"
fi

# Configure UFW firewall
echo ">>> Configuring firewall..."
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw --force enable

# Create deploy user (optional, for non-root deployments)
if ! id "deploy" &>/dev/null; then
    echo ">>> Creating deploy user..."
    sudo useradd -m -s /bin/bash -G docker deploy
    echo ">>> Set a password for deploy user with: sudo passwd deploy"
fi

# Clone or update platform-infra repo
REPO_DIR="/opt/platform-infra"
if [[ -d "$REPO_DIR" ]]; then
    echo ">>> Updating platform-infra repo..."
    cd "$REPO_DIR"
    sudo git pull
else
    echo ">>> Cloning platform-infra repo..."
    sudo git clone https://github.com/richmiles/platform-infra.git "$REPO_DIR"
    sudo chown -R "$USER:$USER" "$REPO_DIR"
fi

cd "$REPO_DIR"

# Check for .env file
if [[ ! -f .env ]]; then
    echo ">>> Creating .env from template..."
    cp .env.example .env
    echo ""
    echo "!!! IMPORTANT: Edit $REPO_DIR/.env with real passwords before starting services !!!"
    echo ""
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Log out and back in (for docker group)"
echo "2. cd $REPO_DIR"
echo "3. Edit .env with secure passwords"
echo "4. Update init-db.sql with matching passwords"
echo "5. Run: docker compose up -d"
echo ""
