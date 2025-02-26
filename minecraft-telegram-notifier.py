#!/usr/bin/env python3
import os
import time
import re
import requests
import subprocess
import signal
from datetime import datetime
import json
import socket

# Configuration - Read from environment variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SERVER_LOG_PATH = "/home/ubuntu/minecraft-bedrock/logs.txt"  # This is the actual log file found on your server
POLL_INTERVAL = 1  # seconds between checks
SERVER_IP = os.environ.get("SERVER_IP", "127.0.0.1")  # Your server's public IP
SERVER_PORT = os.environ.get("SERVER_PORT", "19132")  # Default Bedrock port

# Check if Telegram configuration is available
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("Warning: Telegram credentials not found in environment variables.")
    print("Notifications will be disabled.")
    NOTIFICATIONS_ENABLED = False
else:
    NOTIFICATIONS_ENABLED = True

def send_telegram_message(message, chat_id=None):
    """Send message to Telegram chat using environment variables."""
    if not NOTIFICATIONS_ENABLED and not chat_id:
        print(f"Message not sent (notifications disabled): {message}")
        return
    
    # If no specific chat_id is provided, use the default one
    if not chat_id:
        chat_id = TELEGRAM_CHAT_ID
        
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(api_url, data=data)
        if response.status_code != 200:
            print(f"Failed to send Telegram message: {response.text}")
        else:
            print(f"Notification sent to {chat_id}: {message}")
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

def is_server_online():
    """Check if the Minecraft server is online using socket connection."""
    try:
        # For Bedrock, we typically can't do a direct TCP check as it uses UDP
        # So we'll check if the bedrock_server process is running
        subprocess.check_output(["pgrep", "-f", "bedrock_server"], universal_newlines=True)
        return True
    except subprocess.CalledProcessError:
        # Process not found
        return False
    except Exception as e:
        print(f"Error checking server status: {e}")
        return False

def get_current_players():
    """Get a list of currently connected players by parsing recent log entries."""
    try:
        # This uses a simple approach by checking recent log entries
        # A more robust solution would be to integrate with the server API if available
        
        # Read the last 1000 lines of the log file
        output = subprocess.check_output(["tail", "-n", "1000", SERVER_LOG_PATH], universal_newlines=True)
        
        # Find all player connections
        connected_players = []
        disconnected_players = []
        
        # These patterns match Bedrock server player connection events
        player_join_patterns = [
            re.compile(r"Player connected: (.*?)(?:,|$)"),
            re.compile(r"Player (.*?) has connected"),
            re.compile(r"(.*?) joined the game"),
            re.compile(r"(?:Player|Client) (.*?) connected"),
            re.compile(r"\[INFO\].*? (.*?) joined the game")
        ]
        
        player_leave_patterns = [
            re.compile(r"Player disconnected: (.*?)(?:,|$)"),
            re.compile(r"Player (.*?) has disconnected"),
            re.compile(r"(.*?) left the game"),
            re.compile(r"(?:Player|Client) (.*?) disconnected"),
            re.compile(r"\[INFO\].*? (.*?) left the game")
        ]
        
        # Process each line
        for line in output.splitlines():
            # Check for player connections
            for pattern in player_join_patterns:
                match = pattern.search(line)
                if match:
                    player_name = match.group(1)
                    if player_name not in connected_players:
                        connected_players.append(player_name)
            
            # Check for player disconnections
            for pattern in player_leave_patterns:
                match = pattern.search(line)
                if match:
                    player_name = match.group(1)
                    if player_name in connected_players:
                        disconnected_players.append(player_name)
        
        # Filter out disconnected players
        current_players = [p for p in connected_players if p not in disconnected_players]
        return current_players
    
    except Exception as e:
        print(f"Error getting player list: {e}")
        return []

def handle_telegram_commands(update):
    """Handle incoming Telegram commands."""
    try:
        # Extract message content and chat ID
        message = update.get("message", {})
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        
        if not text or not chat_id:
            return
        
        # Handle /info command
        if text.startswith("/info"):
            # Check server status
            server_status = "Online ✅" if is_server_online() else "Offline ❌"
            
            # Get player information
            player_list = get_current_players()
            player_count = len(player_list)
            
            # Create response message
            response = f"<b>Server Status:</b> {server_status}\n"
            response += f"<b>Server IP:</b> <code>{SERVER_IP}:{SERVER_PORT}</code>\n"
            
            if server_status == "Online ✅":
                response += f"<b>Players Online:</b> {player_count}\n"
                if player_count > 0:
                    response += "\n<b>Players:</b>\n"
                    for player in player_list:
                        response += f"• {player}\n"
            
            # Send the response
            send_telegram_message(response, chat_id)
            print(f"Responded to /info command from chat {chat_id}")
        
        # Handle /help command
        elif text.startswith("/help"):
            help_text = """
<b>Available Commands:</b>
• /info - Show server status, IP, and online players
• /help - Show this help message
"""
            send_telegram_message(help_text, chat_id)
            print(f"Responded to /help command from chat {chat_id}")
    
    except Exception as e:
        print(f"Error handling command: {e}")

def setup_telegram_webhook():
    """Set up a Telegram webhook to receive commands."""
    # This is optional - for a simple bot, polling might be easier
    # Implement this if you want to set up a webhook
    pass

def start_command_listener():
    """Start a background thread to listen for Telegram commands."""
    # Using long polling to listen for updates
    last_update_id = 0
    
    print("Starting Telegram command listener...")
    
    while True:
        try:
            # Get updates from Telegram
            api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            params = {
                "offset": last_update_id + 1,
                "timeout": 30
            }
            
            response = requests.get(api_url, params=params)
            if response.status_code == 200:
                updates = response.json().get("result", [])
                
                for update in updates:
                    # Process the update
                    update_id = update.get("update_id")
                    last_update_id = max(last_update_id, update_id)
                    
                    # Handle commands
                    handle_telegram_commands(update)
            
            time.sleep(1)  # Small delay to avoid hammering the API
        
        except Exception as e:
            print(f"Error in command listener: {e}")
            time.sleep(5)  # Wait a bit longer on error

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
        # Start the command listener in a separate thread
        import threading
        command_thread = threading.Thread(target=start_command_listener, daemon=True)
        command_thread.start()
        
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