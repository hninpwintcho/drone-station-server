#!/bin/bash
# EC2 Bootstrap — paste into User Data when launching Ubuntu 22.04
set -e

echo "=== Drone Station Server Bootstrap ==="

# Docker
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Allow ubuntu user to use docker
sudo usermod -aG docker ubuntu

# MQTT tools for testing
sudo apt-get install -y mosquitto-clients

echo "=== Bootstrap Complete ==="
echo "Run: cd ~/drone-station-server && docker compose up -d"
