#!/bin/bash
# Deploy script for a specific Pi node
# Usage: ./scripts/deploy.sh <pi-number>
# Example: ./scripts/deploy.sh 1

set -e

PI_NUM="$1"

if [ -z "$PI_NUM" ]; then
    echo "Usage: $0 <pi-number>"
    echo "  Options: zero, 1, 2, 3, 4"
    exit 1
fi

# Map pi number to directory
case "$PI_NUM" in
    zero|0)
        DIR="pi-zero-broker"
        NAME="MQTT Broker"
        ;;
    1)
        DIR="pi1-processor"
        NAME="Edge Processor"
        ;;
    2)
        DIR="pi2-vision"
        NAME="Vision Detector"
        ;;
    3)
        DIR="pi3-intelligence"
        NAME="Intelligence Layer"
        ;;
    4)
        DIR="pi4-dashboard"
        NAME="Dashboard"
        ;;
    *)
        echo "Unknown Pi number: $PI_NUM"
        echo "Options: zero, 1, 2, 3, 4"
        exit 1
        ;;
esac

COMPOSE_FILE="$DIR/docker-compose.yml"

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "Error: $COMPOSE_FILE not found"
    echo "Are you in the project root directory?"
    exit 1
fi

echo "=== Deploying $NAME (Pi $PI_NUM) ==="
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
