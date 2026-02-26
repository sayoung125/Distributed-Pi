#!/bin/bash
# Setup script for Raspberry Pi nodes
# Run this on each Pi after flashing Raspberry Pi OS

set -e

echo "=== Distributed Pi Video Analytics - Node Setup ==="
echo ""

# Update system
echo "[1/5] Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Docker
echo "[2/5] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
    sudo usermod -aG docker "$USER"
    echo "Docker installed. You may need to log out and back in for group changes."
else
    echo "Docker already installed."
fi

# Install Docker Compose plugin
echo "[3/5] Installing Docker Compose..."
if ! docker compose version &> /dev/null; then
    sudo apt-get install -y docker-compose-plugin
else
    echo "Docker Compose already installed."
fi

# Install git
echo "[4/5] Installing git..."
sudo apt-get install -y git

# Enable camera (for Pi 1)
echo "[5/5] Enabling camera interface..."
if [ -f /boot/firmware/config.txt ]; then
    if ! grep -q "start_x=1" /boot/firmware/config.txt; then
        echo "start_x=1" | sudo tee -a /boot/firmware/config.txt
        echo "gpu_mem=128" | sudo tee -a /boot/firmware/config.txt
        echo "Camera enabled. Reboot required."
    fi
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Clone the repo:  git clone <your-repo-url> ~/video-analytics"
echo "  2. cd ~/video-analytics"
echo "  3. Create .env file with MQTT_BROKER_HOST=<pi-zero-ip>"
echo "  4. Run: ./scripts/deploy.sh <pi-number>"
echo ""
echo "Pi Zero (broker): ./scripts/deploy.sh zero"
echo "Pi 1 (processor): ./scripts/deploy.sh 1"
echo "Pi 2 (vision):    ./scripts/deploy.sh 2"
echo "Pi 3 (intel):     ./scripts/deploy.sh 3"
echo "Pi 4 (dashboard): ./scripts/deploy.sh 4"
