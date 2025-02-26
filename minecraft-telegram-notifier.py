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

# Import the BedrockServerAPI
from bedrock_server_api import BedrockServerAPI

# Configuration - Read from environment variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SERVER_LOG_PATH = "/home/ubuntu/minecraft-bedrock/logs.txt"  # This is the actual log file found on your server
SERVER_PATH = "/home/ubuntu/minecraft-bedrock"  # Path to your Minecraft server directory
SERVER_IP = os.environ.get("SERVER_IP", "18.192.47.133")  # Your server's public IP
SERVER_PORT = int(os.environ.get("SERVER_PORT", "19132"))  # Default Bedrock port

# Check if Telegram configuration is available
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("Warning: Telegram credentials not found in environment variables.")
    print("Notifications will be disabled.")
    NOTIFICATIONS_ENABLED = False
else:
    NOTIFICATIONS_ENABLED = True

# Initialize the server API
server_api = BedrockServerAPI(
    server_path=SERVER_PATH,
    log_path=SERVER_LOG_PATH,
    server_port=SERVER_PORT
)

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
    
    except Exception as e:
        print(f"Error handling command: {e}")
        try:
            send_telegram_message(f"⚠️ Error processing command: {str(e)}", chat_id)
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

def main():
    print("Minecraft Bedrock Server Telegram Notifier")
    print("------------------------------------------")
    
    send_telegram_message("🎮 Minecraft server notification system is now active!")
    
    # Set up server event handlers
    setup_server_event_handlers()
    
    # Start the log monitor
    server_api.start_log_monitor()
    
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
    
    main()