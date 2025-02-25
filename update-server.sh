#!/bin/bash
# update-server.sh - Updates the Minecraft server with latest configurations and sets up the notification bot

# Exit on any error
set -e

echo "Starting Minecraft server update..."

# Path to Minecraft server
MINECRAFT_SERVER_DIR="/home/ubuntu/minecraft-bedrock"
MINECRAFT_SCRIPTS_DIR="/home/ubuntu/minecraft-scripts"

# Ensure scripts directory exists
mkdir -p $MINECRAFT_SCRIPTS_DIR

# Copy notification script to server directory if needed
cp minecraft-telegram-notifier.py $MINECRAFT_SERVER_DIR/
chmod +x $MINECRAFT_SERVER_DIR/minecraft-telegram-notifier.py

# Copy standalone message sender if it exists
if [ -f "telegram-notify.py" ]; then
  cp telegram-notify.py $MINECRAFT_SERVER_DIR/
  chmod +x $MINECRAFT_SERVER_DIR/telegram-notify.py
fi

# Check if we have Telegram credentials
if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
  echo "Warning: Telegram credentials not provided. Notification service will not be configured."
else
  echo "Setting up Telegram notification service..."
  
  # Create configuration file with environment variables
  echo "TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}" > /home/ubuntu/.minecraft-bot-env
  echo "TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}" >> /home/ubuntu/.minecraft-bot-env
  chmod 600 /home/ubuntu/.minecraft-bot-env
  
  # Create systemd service file
  cat > /tmp/minecraft-bot.service << EOF
[Unit]
Description=Minecraft Telegram Notification Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=${MINECRAFT_SERVER_DIR}
EnvironmentFile=/home/ubuntu/.minecraft-bot-env
ExecStart=/usr/bin/python3 ${MINECRAFT_SERVER_DIR}/minecraft-telegram-notifier.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

  # Install and enable the service
  sudo mv /tmp/minecraft-bot.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable minecraft-bot
  
  # Restart the service to apply changes
  sudo systemctl restart minecraft-bot
  
  # Send a test notification
  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="${TELEGRAM_CHAT_ID}" \
    -d text="🔄 Minecraft server notification system has been updated!" \
    -d parse_mode="HTML" > /dev/null
    
  echo "Notification service configured and restarted."
fi

# Check if server is running
if pgrep -f "bedrock_server" > /dev/null; then
  echo "Minecraft server is currently running."
else
  echo "Warning: Minecraft server is not running."
fi

echo "Update completed successfully!"