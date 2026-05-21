#!/bin/bash
# SearXNG self-hosted setup — runs as docker container on VPS.
# Listens on 127.0.0.1:8888 (localhost only). Sonya core uses
# SONYA_SEARXNG_URL=http://127.0.0.1:8888 to query it.
#
# Run once: bash ~/Sonya/deploy/searxng/setup.sh
# Restart:  docker restart sonya-searxng

set -e

CONTAINER_NAME="sonya-searxng"
PORT="8888"
CONFIG_DIR="$HOME/.sonya/searxng"

mkdir -p "$CONFIG_DIR"

# Generate a fresh secret key on first setup
if [ ! -f "$CONFIG_DIR/settings.yml" ]; then
    SECRET=$(head -c 32 /dev/urandom | base64 | tr -d '=+/')
    cp "$HOME/Sonya/deploy/searxng/settings.yml" "$CONFIG_DIR/settings.yml"
    sed -i "s|secret_key: \"change-me-via-deploy-script\"|secret_key: \"$SECRET\"|" "$CONFIG_DIR/settings.yml"
    echo "=> Generated fresh secret_key"
fi

# Stop and remove existing container if any
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "=> Stopping existing container..."
    docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
    docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
fi

# Pull latest image
echo "=> Pulling SearXNG image..."
docker pull searxng/searxng:latest

# Run container — bound to localhost only, settings mounted read-only
echo "=> Starting SearXNG on 127.0.0.1:${PORT}..."
docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    -p "127.0.0.1:${PORT}:8080" \
    -v "$CONFIG_DIR:/etc/searxng:rw" \
    -e BASE_URL="http://localhost:${PORT}/" \
    -e INSTANCE_NAME="sonya-search" \
    searxng/searxng:latest

echo "=> Waiting for SearXNG to come up..."
sleep 5

# Health check
if curl -s -f -o /dev/null "http://127.0.0.1:${PORT}/healthz"; then
    echo "=> SearXNG is up at http://127.0.0.1:${PORT}"
else
    echo "!! SearXNG might not be ready yet, check: docker logs ${CONTAINER_NAME}"
fi

# Test JSON search
echo "=> Testing JSON API..."
RESULT=$(curl -s "http://127.0.0.1:${PORT}/search?q=test&format=json" 2>/dev/null | head -c 200)
if echo "$RESULT" | grep -q '"results"'; then
    echo "=> JSON API works"
else
    echo "!! JSON API check failed. Response preview: $RESULT"
fi

echo ""
echo "=> Add to ~/Sonya/.env (if not already there):"
echo "   SONYA_SEARXNG_URL=http://127.0.0.1:${PORT}"
echo ""
echo "=> Then restart Sonya: sudo systemctl restart sonya"
