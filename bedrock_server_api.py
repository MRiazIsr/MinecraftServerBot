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
import threading
import sys

# Add error handling for import
try:
    from bedrock_server_api import BedrockServerAPI
    print("Successfully imported BedrockServerAPI")
except ImportError as e:
    print(f"ERROR: Failed to import BedrockServerAPI: {e}")
    print("Current directory:", os.getcwd())
    print("Files in directory:", os.listdir('.'))
    sys.exit(1)

# Configuration - Read from environment variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SERVER_LOG_PATH = os.path.join(os.getcwd(), "logs.txt")  # Use current directory
SERVER_PATH = os.getcwd()  # Use current directory
SERVER_IP = os.environ.get("SERVER_IP", "127.0.0.1")  # Your server's public IP
SERVER_PORT = int(os.environ.get("SERVER_PORT", "19132"))  # Default Bedrock port

print(f"Configuration loaded:")
print(f"- Server path: {SERVER_PATH}")
print(f"- Log path: {SERVER_LOG_PATH}")
print(f"- Server IP: {SERVER_IP}")
print(f"- Server port: {SERVER_PORT}")
print(f"- Telegram bot configured: {bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)}")

# Check if Telegram configuration is available
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("Warning: Telegram credentials not found in environment variables.")
    print("Notifications will be disabled.")
    NOTIFICATIONS_ENABLED = False
else:
    NOTIFICATIONS_ENABLED = True

# Initialize the server API
try:
    server_api = BedrockServerAPI(
        server_path=SERVER_PATH,
        log_path=SERVER_LOG_PATH,
        server_port=SERVER_PORT
    )
    print("Server API initialized successfully")
except Exception as e:
    print(f"ERROR: Failed to initialize server API: {e}")
    sys.exit(1)

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

def handle_telegram_commands(update):
    """Handle incoming Telegram commands."""
    try:
        # Extract message content and chat ID
        message = update.get("message", {})
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        
        if not text or not chat_id:
            return
        
        # Log all received commands
        print(f"Received command from chat {chat_id}: {text}")
        
        # Handle /info command
        if text.startswith("/info"):
            # Check server status
            server_status = "Online ✅" if server_api.is_server_running() else "Offline ❌"
            
            # Get player information
            player_list = server_api.get_online_players()
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
• /start - Start the Minecraft server
• /stop - Stop the Minecraft server
• /cmd <command> - Run a Minecraft server command
• /restart - Restart the notification bot
• /debug - Show debug information
"""
            send_telegram_message(help_text, chat_id)
            print(f"Responded to /help command from chat {chat_id}")
            
        # Handle /start command
        elif text.startswith("/start"):
            if server_api.is_server_running():
                send_telegram_message("⚠️ Minecraft server is already running", chat_id)
            else:
                send_telegram_message("🔄 Starting Minecraft server...", chat_id)
                success = server_api.start_server()
                if success:
                    send_telegram_message("✅ Minecraft server started successfully", chat_id)
                else:
                    send_telegram_message("❌ Failed to start Minecraft server", chat_id)
        
        # Handle /stop command
        elif text.startswith("/stop"):
            if not server_api.is_server_running():
                send_telegram_message("⚠️ Minecraft server is not running", chat_id)
            else:
                send_telegram_message("🔄 Stopping Minecraft server...", chat_id)
                success = server_api.stop_server()
                if success:
                    send_telegram_message("✅ Minecraft server stopped successfully", chat_id)
                else:
                    send_telegram_message("❌ Failed to stop Minecraft server", chat_id)
                    
        # Handle /cmd command
        elif text.startswith("/cmd "):
            if not server_api.is_server_running():
                send_telegram_message("⚠️ Cannot run command: Minecraft server is not running", chat_id)
            else:
                command = text[5:].strip()  # Remove "/cmd " prefix
                if not command:
                    send_telegram_message("⚠️ Please specify a command to run", chat_id)
                else:
                    send_telegram_message(f"🔄 Running command: <code>{command}</code>", chat_id)
                    success = server_api.run_command(command)
                    if success:
                        send_telegram_message("✅ Command sent successfully", chat_id)
                    else:
                        send_telegram_message("❌ Failed to send command", chat_id)
                        
        # Handle /restart command (restart the bot)
        elif text.startswith("/restart"):
            send_telegram_message("🔄 Restarting the notification bot...", chat_id)
            print("Restart command received, exiting process...")
            # The systemd service will restart the bot
            os._exit(0)
            
        # Handle /debug command
        elif text.startswith("/debug"):
            debug_info = f"""
<b>Debug Information:</b>
• <b>Bot Version:</b> 1.0
• <b>Server Path:</b> <code>{SERVER_PATH}</code>
• <b>Log Path:</b> <code>{SERVER_LOG_PATH}</code>
• <b>Server IP:</b> <code>{SERVER_IP}</code>
• <b>Server Port:</b> <code>{SERVER_PORT}</code>
• <b>Server Running:</b> {server_api.is_server_running()}
• <b>Log File Exists:</b> {os.path.exists(SERVER_LOG_PATH)}
• <b>Log File Size:</b> {os.path.getsize(SERVER_LOG_PATH) if os.path.exists(SERVER_LOG_PATH) else 0} bytes
• <b>Current Directory:</b> <code>{os.getcwd()}</code>
• <b>Python Version:</b> <code>{sys.version}</code>
"""
            send_telegram_message(debug_info, chat_id)
            print(f"Responded to /debug command from chat {chat_id}")
    
    except Exception as e:
        error_message = f"⚠️ Error processing command: {str(e)}"
        print(f"Error handling command: {e}")
        try:
            send_telegram_message(error_message, chat_id)
        except:
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

def setup_server_event_handlers():
    """Set up handlers for server events."""
    try:
        # Player join event
        server_api.on('player_join', lambda data: 
            send_telegram_message(f"🎮 Player {data['player']} has joined the Minecraft server!")
        )
        
        # Player leave event
        server_api.on('player_leave', lambda data: 
            send_telegram_message(f"👋 Player {data['player']} has left the Minecraft server")
        )
        
        # Chat message event
        server_api.on('chat_message', lambda data: 
            send_telegram_message(f"💬 <b>{data['player']}</b>: {data['message']}")
        )
        
        # Server start event
        server_api.on('server_start', lambda data: 
            send_telegram_message("🟢 Minecraft server has started")
        )
        
        # Server stop event
        server_api.on('server_stop', lambda data: 
            send_telegram_message("🔴 Minecraft server has stopped")
        )
        
        print("Server event handlers set up successfully")
    except Exception as e:
        print(f"Error setting up event handlers: {e}")

def main():
    print("Minecraft Bedrock Server Telegram Notifier v1.0")
    print("----------------------------------------------")
    
    # Set up server event handlers
    setup_server_event_handlers()
    
    # Start the log monitor
    try:
        server_api.start_log_monitor()
        print("Log monitor started successfully")
    except Exception as e:
        print(f"Error starting log monitor: {e}")
        send_telegram_message(f"⚠️ Error starting log monitor: {str(e)}")
        # Continue anyway - we might still be able to send commands
    
    # Send startup notification
    send_telegram_message("🎮 Minecraft server notification system is now active!")
    
    # Start the command listener
    start_command_listener()

if __name__ == "__main__":
    # Register signal handlers
    def handle_exit(signum, frame):
        print(f"Received signal {signum}, shutting down...")
        send_telegram_message("🛑 Minecraft server notification system has been stopped.")
        exit(0)
    
    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)
    
    try:
        main()
    except Exception as e:
        error_message = f"CRITICAL ERROR: {str(e)}"
        print(error_message)
        send_telegram_message(f"⚠️ {error_message}")
        # Wait a moment to ensure message is sent
        time.sleep(2)
        sys.exit(1)