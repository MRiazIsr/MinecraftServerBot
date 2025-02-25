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
SERVER_LOG_PATH = "/home/ubuntu/minecraft-bedrock/log.txt"  # This is the actual log file found on your server
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

def check_log_file():
    """Check if the log file exists and is accessible."""
    if not os.path.exists(SERVER_LOG_PATH):
        print(f"Warning: Log file {SERVER_LOG_PATH} does not exist.")
        print("Creating an empty log file for monitoring.")
        try:
            # Try to create the file if it doesn't exist
            open(SERVER_LOG_PATH, 'a').close()
            print(f"Created log file: {SERVER_LOG_PATH}")
        except Exception as e:
            print(f"Error creating log file: {e}")
            return False
    
    # Check if the file is readable
    if not os.access(SERVER_LOG_PATH, os.R_OK):
        print(f"Warning: Log file {SERVER_LOG_PATH} is not readable.")
        return False
        
    print(f"Log file {SERVER_LOG_PATH} is accessible.")
    
    # Check for server process
    try:
        output = subprocess.check_output(["pgrep", "-f", "bedrock_server"], universal_newlines=True)
        server_pid = output.strip()
        print(f"Found existing Minecraft server process: {server_pid}")
    except subprocess.CalledProcessError:
        print("No running Minecraft server found.")
    
    return True

def monitor_server_log():
    """Monitor the log file for player connections."""
    print(f"Starting to monitor log file: {SERVER_LOG_PATH}")
    send_telegram_message("🎮 Minecraft server notification system is now active!")
    
    # Start from the end of the file
    file_size = os.path.getsize(SERVER_LOG_PATH)
    print(f"Starting monitoring from position {file_size} in log file")
    
    # Precompile regular expressions for better performance
    # These patterns match Bedrock server player connection events
    player_join_patterns = [
        re.compile(r"Player connected: (.*?)(?:,|$)"),           # Standard format
        re.compile(r"Player (.*?) has connected"),                # Alternate format
        re.compile(r"(.*?) joined the game"),                     # Java-like format
        re.compile(r"(?:Player|Client) (.*?) connected"),         # Another variant
        re.compile(r"\[INFO\].*? (.*?) joined the game")          # Log format with INFO prefix
    ]
    
    player_leave_patterns = [
        re.compile(r"Player disconnected: (.*?)(?:,|$)"),         # Standard format
        re.compile(r"Player (.*?) has disconnected"),             # Alternate format
        re.compile(r"(.*?) left the game"),                       # Java-like format
        re.compile(r"(?:Player|Client) (.*?) disconnected"),      # Another variant
        re.compile(r"\[INFO\].*? (.*?) left the game")            # Log format with INFO prefix
    ]
    
    try:
        while True:
            # Check if file size has changed
            try:
                current_size = os.path.getsize(SERVER_LOG_PATH)
                
                if current_size > file_size:
                    print(f"Log file changed: {file_size} -> {current_size} bytes")
                    with open(SERVER_LOG_PATH, 'r', errors='replace') as f:
                        # Move to the position we last read
                        f.seek(file_size)
                        
                        # Read new content
                        new_content = f.read()
                        
                        # Debug - print what we're reading
                        if new_content.strip():
                            print(f"New log content: {new_content.strip()}")
                        
                        # Process each line separately
                        for line in new_content.splitlines():
                            # Check for player connections with all patterns
                            for pattern in player_join_patterns:
                                match = pattern.search(line)
                                if match:
                                    player_name = match.group(1)
                                    print(f"Detected player join: {player_name}")
                                    send_telegram_message(f"🎮 Player {player_name} has joined the Minecraft server!")
                                    break
                            
                            # Check for player disconnections with all patterns
                            for pattern in player_leave_patterns:
                                match = pattern.search(line)
                                if match:
                                    player_name = match.group(1)
                                    print(f"Detected player leave: {player_name}")
                                    send_telegram_message(f"👋 Player {player_name} has left the Minecraft server")
                                    break
                    
                    # Update the file position
                    file_size = current_size
            
            except Exception as e:
                print(f"Error reading log file: {e}")
                # If the file becomes inaccessible, wait and retry
                time.sleep(5)
                continue
            
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
    
    # Check log file accessibility
    if check_log_file():
        # Begin monitoring
        monitor_server_log()
    else:
        print("ERROR: Cannot access log file. Notification system cannot start.")
        send_telegram_message("⚠️ Minecraft notification system failed to start: Cannot access log file.")

if __name__ == "__main__":
    # Register signal handlers
    def handle_exit(signum, frame):
        print(f"Received signal {signum}, shutting down...")
        send_telegram_message("🛑 Minecraft server notification system has been stopped.")
        exit(0)
    
    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)
    
    main()