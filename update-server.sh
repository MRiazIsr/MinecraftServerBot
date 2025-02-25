#!/bin/bash
# update-server.sh - Updates the Minecraft server with latest configurations

# Exit on any error
set -e

echo "Starting Minecraft server update..."

# Path to Minecraft server
MINECRAFT_SERVER_DIR="/home/ubuntu/minecraft-bedrock"

# Copy notification script to server directory
cp minecraft-telegram-notifier.py $MINECRAFT_SERVER_DIR/

# Make sure it's executable
chmod +x $MINECRAFT_SERVER_DIR/minecraft-telegram-notifier.py

# Check if server is running and needs restart
if pgrep -f "bedrock_server" > /dev/null; then
    echo "Server is running. Sending notification about updates..."
    
    # Use environment variables passed from GitHub Actions
    if [ ! -z "$TELEGRAM_BOT_TOKEN" ] && [ ! -z "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d chat_id="${TELEGRAM_CHAT_ID}" \
            -d text="🔄 Minecraft server scripts have been updated!" \
            -d parse_mode="HTML" > /dev/null
    fi
fi

echo "Update completed successfully!"