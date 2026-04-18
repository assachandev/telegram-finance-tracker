#!/usr/bin/env bash
set -e

echo "🤖 Finance Tracker Bot — Setup"
echo "================================"

# Check .env exists
if [ ! -f .env ]; then
    echo ""
    echo "❌ .env file not found."
    echo "   Run: cp .env.example .env"
    echo "   Then fill in your values and run this script again."
    exit 1
fi

# Load and validate required variables
set -a
source .env
set +a

missing=()
for var in TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID; do
    if [ -z "${!var}" ]; then
        missing+=("$var")
    fi
done

if [ ${#missing[@]} -gt 0 ]; then
    echo ""
    echo "❌ Missing required variables in .env:"
    for var in "${missing[@]}"; do
        echo "   - $var"
    done
    exit 1
fi

# Check Docker
if ! command -v docker &>/dev/null; then
    echo ""
    echo "❌ Docker is not installed. Install it from https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker compose version &>/dev/null; then
    echo ""
    echo "❌ Docker Compose plugin not found. Make sure Docker is up to date."
    exit 1
fi

# Create data directory if using default local path
HOST_DATA_DIR="${HOST_DATA_DIR:-./data}"
if [ ! -d "$HOST_DATA_DIR" ]; then
    mkdir -p "$HOST_DATA_DIR"
    echo "✅ Created data directory: $HOST_DATA_DIR"
fi

echo ""
echo "✅ All checks passed. Building and starting bot..."
echo ""

docker compose up -d --build

echo ""
echo "✅ Bot is running!"
echo ""
echo "Useful commands:"
echo "  View logs:   docker compose logs -f"
echo "  Stop bot:    docker compose down"
echo "  Restart:     docker compose restart"
