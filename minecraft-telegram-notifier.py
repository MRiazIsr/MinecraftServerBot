#!/usr/bin/env python3
import os
import time
import re
import requests
import subprocess
import signal
from datetime import datetime

# Configuration - Read from environment variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SERVER_LOG_PATH = "/home/ubuntu/minecraft-bedrock/log.txt"
POLL_INTERVAL = 1  # seconds between checks

# Check if Telegram configuration is available
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("Warning: Telegram credentials not found in environment variables.")
    print("Notifications will be disabled.")
    NOTIFICATIONS_ENABLED = False
else:
    NOTIFICATIONS_ENABLED = True

def send_telegram_message(message):
    """Send message to Telegram chat using environment variables."""
    if not NOTIFICATIONS_ENABLED:
        print(f"Message not sent (notifications disabled): {message}")
        return
        
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(api_url, data=data)
        if response.status_code != 200:
            print(f"Failed to send Telegram message: {response.text}")
        else:
            print(f"Notification sent: {message}")
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

def setup_log_redirection():
    """Set up redirection of Bedrock server output to our log file."""
    # Check if the server is running through a start_server.sh script
    server_pid = None
    try:
        # Look for bedrock_server process
        output = subprocess.check_output(["pgrep", "-f", "bedrock_server"], universal_newlines=True)
        server_pid = output.strip()
        print(f"Found existing Minecraft server process: {server_pid}")
    except subprocess.CalledProcessError:
        print("No running Minecraft server found.")
    
    # Create or truncate the log file
    with open(SERVER_LOG_PATH, 'w') as f:
        pass
    
    # Check if we can access the server's standard output via its parent process
    if server_pid:
        print("Setting up log redirection...")
        try:
            # This is a bit hacky but can work in some configurations
            # Create a small script to redirect output
            redirect_script = """#!/bin/bash
tail -f /proc/$(pgrep -f bedrock_server)/fd/1 >> {log_file} &
tail -f /proc/$(pgrep -f bedrock_server)/fd/2 >> {log_file} &
""".format(log_file=SERVER_LOG_PATH)
            
            # Write and execute the script
            with open("/tmp/redirect_minecraft.sh", "w") as f:
                f.write(redirect_script)
            
            subprocess.call(["chmod", "+x", "/tmp/redirect_minecraft.sh"])
            subprocess.Popen(["/tmp/redirect_minecraft.sh"], shell=True)
            
            print("Log redirection set up successfully.")
        except Exception as e:
            print(f"Failed to set up log redirection: {e}")

def monitor_server_log():
    """Monitor the log file for player connections."""
    print(f"Starting to monitor log file: {SERVER_LOG_PATH}")
    send_telegram_message("🎮 Minecraft server notification system is now active!")
    
    # Create the log file if it doesn't exist
    if not os.path.exists(SERVER_LOG_PATH):
        open(SERVER_LOG_PATH, 'a').close()
        print(f"Created log file: {SERVER_LOG_PATH}")
    
    # Start from the end of the file
    file_size = os.path.getsize(SERVER_LOG_PATH)
    
    # Precompile regular expressions for better performance
    # Pattern for Bedrock server player connections and disconnections
    player_join_pattern = re.compile(r"Player connected: (.*?)(?:,|$)")
    player_leave_pattern = re.compile(r"Player disconnected: (.*?)(?:,|$)")
    
    try:
        while True:
            # Check if file size has changed
            current_size = os.path.getsize(SERVER_LOG_PATH)
            
            if current_size > file_size:
                with open(SERVER_LOG_PATH, 'r') as f:
                    # Move to the position we last read
                    f.seek(file_size)
                    
                    # Read new content
                    new_content = f.read()
                    
                    # Check for player connections
                    for match in player_join_pattern.finditer(new_content):
                        player_name = match.group(1)
                        send_telegram_message(f"🎮 Player {player_name} has joined the Minecraft server!")
                    
                    # Check for player disconnections
                    for match in player_leave_pattern.finditer(new_content):
                        player_name = match.group(1)
                        send_telegram_message(f"👋 Player {player_name} has left the Minecraft server")
                
                # Update the file position
                file_size = current_size
            
            # Also check directly with server's process
            try:
                # This directly checks server output
                server_check = subprocess.run(
                    ["grep", "-E", "Player (connected|disconnected)", "/proc/$(pgrep -f bedrock_server)/fd/1"],
                    shell=True, capture_output=True, text=True
                )
                if server_check.stdout:
                    for line in server_check.stdout.splitlines():
                        # Processing direct server output
                        join_match = player_join_pattern.search(line)
                        if join_match:
                            player_name = join_match.group(1)
                            send_telegram_message(f"🎮 Player {player_name} has joined the Minecraft server!")
                            
                        leave_match = player_leave_pattern.search(line)
                        if leave_match:
                            player_name = leave_match.group(1)
                            send_telegram_message(f"👋 Player {player_name} has left the Minecraft server")
            except Exception as e:
                # Ignore errors in direct server output check
                pass
            
            # Wait before checking again
            time.sleep(POLL_INTERVAL)
    
    except KeyboardInterrupt:
        print("Monitoring stopped by user.")
        send_telegram_message("🛑 Minecraft server notification system has been stopped.")
    except Exception as e:
        error_message = f"Error in monitoring: {e}"
        print(error_message)
        send_telegram_message(f"⚠️ {error_message}")
        raise

def main():
    print("Minecraft Bedrock Server Telegram Notifier")
    print("------------------------------------------")
    
    # Try to set up log redirection
    setup_log_redirection()
    
    # Begin monitoring
    monitor_server_log()

if __name__ == "__main__":
    # Register signal handlers
    def handle_exit(signum, frame):
        print(f"Received signal {signum}, shutting down...")
        send_telegram_message("🛑 Minecraft server notification system has been stopped.")
        exit(0)
    
    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)
    
    main()