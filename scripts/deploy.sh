#!/bin/bash
# Deploy script for a specific Pi node
# Usage: ./scripts/deploy.sh <pi-name>
#
# Hardware mapping:
#   Pi Zero       -> MQTT Broker
#   Pi 3          -> Intelligence Layer (Ollama/TinyLlama)
#   Pi 4 2GB      -> Vision Detector (YOLOv8-nano)
#   Pi 4 4GB      -> Frame Processor + Web Dashboard

set -e

PI_NAME="$1"

if [ -z "$PI_NAME" ]; then
    echo "Usage: $0 <pi-name>"
    echo "  Options: zero, pi3, pi4-2gb, pi4-4gb"
    exit 1
fi

# Map pi name to directory
case "$PI_NAME" in
    zero|pi-zero)
        DIR="pi-zero-broker"
        NAME="MQTT Broker (Pi Zero)"
        ;;
    pi3|3)
        DIR="pi3-intelligence"
        NAME="Intelligence Layer (Pi 3)"
        ;;
    pi4-2gb)
        DIR="pi4-2gb-vision"
        NAME="Vision Detector (Pi 4 2GB)"
        ;;
    pi4-4gb)
        DIR="pi4-4gb-dashboard"
        NAME="Processor + Dashboard (Pi 4 4GB)"
        ;;
    *)
        echo "Unknown Pi name: $PI_NAME"
        echo "Options: zero, pi3, pi4-2gb, pi4-4gb"
        exit 1
        ;;
esac

COMPOSE_FILE="$DIR/docker-compose.yml"

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "Error: $COMPOSE_FILE not found"
    echo "Are you in the project root directory?"
    exit 1
fi

echo "=== Deploying $NAME ==="
echo "Compose file: $COMPOSE_FILE"
echo ""

# Load .env if it exists
if [ -f .env ]; then
    echo "Loading .env file..."
    set -a
    source .env
    set +a
fi

# Build and start
echo "Building and starting containers..."
docker compose -f "$COMPOSE_FILE" up -d --build

echo ""
echo "=== $NAME deployed successfully ==="
docker compose -f "$COMPOSE_FILE" ps
