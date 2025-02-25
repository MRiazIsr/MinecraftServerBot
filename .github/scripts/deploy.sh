#!/bin/bash
# deploy.sh - Minecraft Bedrock server deployment script

# Exit on any error
set -e

echo "Starting deployment process..."

# Check if we're in the right directory
if [ ! -f "bedrock_server" ]; then
    echo "Error: Not in minecraft-bedrock directory"
    exit 1
fi

# Check if Telegram env variables are set
if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
    echo "Warning: Telegram environment variables not set. Notifications will be disabled."
    NOTIFICATIONS_ENABLED=false
else
    NOTIFICATIONS_ENABLED=true
fi

# Function to send Telegram messages
send_telegram_notification() {
    if [ "$NOTIFICATIONS_ENABLED" = true ]; then
        MESSAGE="$1"
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d chat_id="${TELEGRAM_CHAT_ID}" \
            -d text="${MESSAGE}" \
            -d parse_mode="HTML" > /dev/null
        echo "Notification sent: ${MESSAGE}"
    else
        echo "Notification skipped (disabled): $1"
    fi
}

# Create backup
echo "Creating backup of world data..."
BACKUP_DIR="backups"
BACKUP_FILE="world_backup_$(date +%Y%m%d_%H%M%S).tar.gz"

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

# Backup the worlds directory
tar -czf "$BACKUP_DIR/$BACKUP_FILE" worlds/

echo "Backup created: $BACKUP_DIR/$BACKUP_FILE"

# Pull latest changes from git
echo "Pulling latest changes from repository..."
git pull

# Apply any configuration changes
echo "Applying configuration changes..."

# Check if server is running
if pgrep -f "bedrock_server" > /dev/null; then
    echo "Server is currently running. Restarting..."
    
    # Send warning to players
    send_telegram_notification "🔄 Server will restart in 60 seconds for updates. Please prepare to disconnect."
    
    # Wait 60 seconds
    sleep 60
    
    # Find and kill the Minecraft server process
    PID=$(pgrep -f "bedrock_server")
    echo "Stopping server (PID: $PID)..."
    kill $PID
    
    # Wait for server to fully stop
    while kill -0 $PID 2>/dev/null; do
        echo "Waiting for server to stop..."
        sleep 5
    done
    
    echo "Server stopped. Starting again..."
    
    # Start server
    nohup ./start_server.sh > /dev/null 2>&1 &
    
    # Notify about restart
    send_telegram_notification "✅ Server has been updated and restarted!"
else
    echo "Server is not running. Starting it..."
    nohup ./start_server.sh > /dev/null 2>&1 &
    
    # Notify about start
    send_telegram_notification "✅ Server has been updated and started!"
fi

echo "Deployment completed successfully!"