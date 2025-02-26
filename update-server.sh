#!/bin/bash
# update-server.sh - Updates the Minecraft server with latest configurations and sets up the notification bot

# Exit on any error
set -e

echo "Starting Minecraft server update..."

# Add this near the beginning of your update-server.sh script
echo "Installing Minecraft server logger..."
cat > ${MINECRAFT_SERVER_DIR}/minecraft-logger.sh << 'EOF'
#!/bin/bash
# This script captures Minecraft Bedrock server output to logs.txt

# Path configuration
SERVER_DIR="/home/ubuntu/minecraft-bedrock"
SERVER_EXECUTABLE="./bedrock_server"
LOG_FILE="$SERVER_DIR/logs.txt"

# Make sure we're in the server directory
cd "$SERVER_DIR"

# Start the server and pipe its output to both the console and the log file
"$SERVER_EXECUTABLE" 2>&1 | tee -a "$LOG_FILE"
EOF

chmod +x ${MINECRAFT_SERVER_DIR}/minecraft-logger.sh

# Also ensure log file has proper permissions
sudo chown ubuntu:ubuntu ${MINECRAFT_SERVER_DIR}/logs.txt
sudo chmod 644 ${MINECRAFT_SERVER_DIR}/logs.txt

# Path to Minecraft server
MINECRAFT_SERVER_DIR="/home/ubuntu/minecraft-bedrock"
MINECRAFT_SCRIPTS_DIR="/home/ubuntu/minecraft-scripts"

# Ensure scripts directory exists
mkdir -p $MINECRAFT_SCRIPTS_DIR

# Copy API module and notification script to server directory
cp bedrock_server_api.py $MINECRAFT_SERVER_DIR/
cp minecraft-telegram-notifier.py $MINECRAFT_SERVER_DIR/
chmod +x $MINECRAFT_SERVER_DIR/minecraft-telegram-notifier.py

# Copy standalone message sender if it exists
if [ -f "telegram-notify.py" ]; then
  cp telegram-notify.py $MINECRAFT_SERVER_DIR/
  chmod +x $MINECRAFT_SERVER_DIR/telegram-notify.py
fi

# Check if log file exists and create it if necessary
LOGS_FILE="$MINECRAFT_SERVER_DIR/logs.txt"
if [ ! -f "$LOGS_FILE" ]; then
  echo "Creating empty log file at $LOGS_FILE"
  touch "$LOGS_FILE"
  chmod 644 "$LOGS_FILE"
fi

# Check if we have Telegram credentials
if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
  echo "Warning: Telegram credentials not provided. Notification service will not be configured."
else
  echo "Setting up Telegram notification service..."
  
  # Create configuration file with environment variables
  echo "TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}" > /home/ubuntu/.minecraft-bot-env
  echo "TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}" >> /home/ubuntu/.minecraft-bot-env
  echo "SERVER_IP=$(curl -s http://checkip.amazonaws.com || echo '127.0.0.1')" >> /home/ubuntu/.minecraft-bot-env
  chmod 600 /home/ubuntu/.minecraft-bot-env
  
  # Check if Python packages are installed
  echo "Checking required Python packages..."
  pip3 install --user requests

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
  
  # Stop the service if it's already running
  sudo systemctl stop minecraft-bot || true
  
  # Restart the service to apply changes
  sleep 2
  sudo systemctl start minecraft-bot
  sleep 2
  
  # Check if the service started correctly
  if sudo systemctl is-active --quiet minecraft-bot; then
    echo "Notification service started successfully."
  else
    echo "WARNING: Notification service failed to start. Checking logs..."
    sudo journalctl -u minecraft-bot -n 20
  fi
  
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