#!/usr/bin/env python3
import os
import time
import requests
import subprocess
import signal
import sys
from datetime import datetime
import json
import threading

# Add a startup delay to prevent rapid restarts
print("Starting bot with 10-second startup delay to prevent restart loops...")
time.sleep(10)

# Create a marker file to track restarts
restart_marker_file = "/tmp/minecraft_bot_restart_count"
MAX_RESTARTS_PER_HOUR = 5

def check_restart_limit():
    """Check if we've restarted too many times recently"""
    try:
        current_time = int(time.time())
        one_hour_ago = current_time - 3600
        
        if os.path.exists(restart_marker_file):
            with open(restart_marker_file, 'r') as f:
                restarts = [int(line.strip()) for line in f if line.strip()]
                # Filter to only include restarts in the last hour
                recent_restarts = [t for t in restarts if t > one_hour_ago]
                if len(recent_restarts) >= MAX_RESTARTS_PER_HOUR:
                    print(f"WARNING: {len(recent_restarts)} restarts in the last hour, exceeding limit of {MAX_RESTARTS_PER_HOUR}")
                    return False
        
        # Add this restart to the log
        with open(restart_marker_file, 'a') as f:
            f.write(f"{current_time}\n")
        
        return True
    except Exception as e:
        print(f"Error checking restart limit: {e}")
        return True  # Default to allowing restart if we can't check

# Add error handling for import
try:
    from bedrock_server_api import BedrockServerAPI
    print("Successfully imported BedrockServerAPI")
except ImportError as e:
    print(f"ERROR: Failed to import BedrockServerAPI: {e}")
    print("Current directory:", os.getcwd())
    print("Files in directory:", os.listdir('.'))
    sys.exit(1)

# Configuration - Read from environment variables with defaults
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SERVER_LOG_PATH = os.environ.get("SERVER_LOG_PATH", os.path.join(os.getcwd(), "logs.txt"))
SERVER_PATH = os.environ.get("SERVER_PATH", os.getcwd())
SERVER_IP = os.environ.get("SERVER_IP", "127.0.0.1")
SERVER_PORT = int(os.environ.get("SERVER_PORT", "19132"))
SERVER_TYPE = os.environ.get("SERVER_TYPE", 'Bedrock')
SERVER_NAME = os.environ.get("SERVER_NAME", 'Super Massive Black Hole')

# Track active players to prevent duplicate notifications
active_players = set()
# Add a lock for thread safety when modifying the active_players set
player_lock = threading.Lock()
# Track last message sent to prevent spam
last_message_time = {}
# Cooldown between identical messages (in seconds)
MESSAGE_COOLDOWN = 300  # 5 minutes

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

# Initialize the server API with proper error handling
try:
    print("Initializing server API...")
    server_api = BedrockServerAPI(
        server_path=SERVER_PATH,
        log_path=SERVER_LOG_PATH,
        server_port=SERVER_PORT
    )
    print("Server API initialized successfully")
except Exception as e:
    print(f"ERROR: Failed to initialize server API: {e}")
    # Don't exit immediately - try to send error notification
    error_msg = f"⚠️ Failed to initialize server API: {str(e)}"
    
    # Try to send error message directly
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(api_url, data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": error_msg,
                "parse_mode": "HTML"
            }, timeout=10)
        except Exception:
            pass
    
    # Exit with error
    sys.exit(1)

def is_message_on_cooldown(message_key, message_type="default"):
    """Check if a message is on cooldown to prevent spam"""
    current_time = time.time()
    full_key = f"{message_type}:{message_key}"
    
    if full_key in last_message_time:
        elapsed_time = current_time - last_message_time[full_key]
        if elapsed_time < MESSAGE_COOLDOWN:
            return True
    
    # Update the last time this message was sent
    last_message_time[full_key] = current_time
    return False

def send_telegram_message(message, chat_id=None, force=False):
    """Send message to Telegram chat using environment variables.
    
    Args:
        message: Message text to send
        chat_id: Optional specific chat ID to send to
        force: If True, bypass cooldown check
    """
    if not NOTIFICATIONS_ENABLED and not chat_id:
        print(f"Message not sent (notifications disabled): {message}")
        return False
    
    # If no specific chat_id is provided, use the default one
    if not chat_id:
        chat_id = TELEGRAM_CHAT_ID
    
    # Skip duplicate messages on cooldown (unless forced)
    if not force and is_message_on_cooldown(message):
        print(f"Message on cooldown, not sending: {message}")
        return False
        
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(api_url, data=data, timeout=10)
        if response.status_code != 200:
            print(f"Failed to send Telegram message: {response.text}")
            return False
        else:
            print(f"Notification sent to {chat_id}: {message}")
            return True
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return False

def handle_player_join(data):
    """Handle player join event with improved tracking"""
    try:
        player_name = data['player']
        
        # Thread-safe update of active players
        with player_lock:
            # Check if this player is already tracked to avoid duplicate notifications
            if player_name not in active_players:
                active_players.add(player_name)
                # Only send a message if this is a new player
                send_telegram_message(f"🎮 Player {player_name} has joined the Minecraft server!")
                print(f"Player joined (new): {player_name}")
            else:
                print(f"Player join event for already tracked player: {player_name}")
    except Exception as e:
        print(f"Error handling player join: {e}")

def handle_player_leave(data):
    """Handle player leave event with improved tracking"""
    try:
        player_name = data['player']
        
        # Thread-safe update of active players
        with player_lock:
            if player_name in active_players:
                active_players.remove(player_name)
                send_telegram_message(f"👋 Player {player_name} has left the Minecraft server")
                print(f"Player left: {player_name}")
            else:
                print(f"Player leave event for untracked player: {player_name}")
    except Exception as e:
        print(f"Error handling player leave: {e}")

def handle_chat_message(data):
    """Handle chat message event"""
    try:
        send_telegram_message(f"💬 <b>{data['player']}</b>: {data['message']}")
    except Exception as e:
        print(f"Error handling chat message: {e}")

def handle_server_start(data):
    """Handle server start event"""
    try:
        send_telegram_message("🟢 Minecraft server has started")
    except Exception as e:
        print(f"Error handling server start: {e}")

def handle_server_stop(data):
    """Handle server stop event"""
    try:
        send_telegram_message("🔴 Minecraft server has stopped")
    except Exception as e:
        print(f"Error handling server stop: {e}")

def setup_server_event_handlers():
    """Set up handlers for server events."""
    try:
        # Player join event
        server_api.on('player_join', handle_player_join)
        
        # Player leave event
        server_api.on('player_leave', handle_player_leave)
        
        # Chat message event
        server_api.on('chat_message', handle_chat_message)
        
        # Server start event
        server_api.on('server_start', handle_server_start)
        
        # Server stop event
        server_api.on('server_stop', handle_server_stop)
        
        print("Server event handlers set up successfully")
    except Exception as e:
        print(f"Error setting up event handlers: {e}")

def sync_player_list():
    """Periodically sync the player list with the server to ensure accuracy"""
    while True:
        try:
            # Skip if server is not running
            if not server_api.is_server_running():
                time.sleep(60)  # Wait a minute before checking again
                continue
                
            # Get current players from server
            server_players = server_api.get_online_players()
            
            with player_lock:
                # Players that are in our tracking but not on server
                for player in list(active_players):
                    if player not in server_players:
                        print(f"Removing player not on server: {player}")
                        active_players.remove(player)
                
                # Players on server but not in our tracking
                for player in server_players:
                    if player not in active_players:
                        print(f"Adding missing player from server: {player}")
                        active_players.add(player)
                        # We don't send a notification here to avoid spam
            
        except Exception as e:
            print(f"Error syncing player list: {e}")
        
        # Sleep for 5 minutes before next sync
        time.sleep(300)

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
            
            # Get active players from our tracking
            with player_lock:
                tracked_players = list(active_players)
            
            # Combine the two sources and remove duplicates
            all_players = list(set(player_list + tracked_players))
            player_count = len(all_players)
            
            # Create response message
            response = f"<b>Server Status:</b> {server_status}\n"
            response += f"<b>Server Type:</b> <code>{SERVER_TYPE}</code>\n"
            response += f"<b>Server Name:</b> <code>{SERVER_NAME}</code>\n"
            response += f"<b>Server IP:</b> <code>{SERVER_IP}:{SERVER_PORT}</code>\n"
            
            if server_status == "Online ✅":
                response += f"<b>Players Online:</b> {player_count}\n"
                if player_count > 0:
                    response += "\n<b>Players:</b>\n"
                    for player in sorted(all_players):
                        response += f"• {player}\n"
            
            # Send the response (force bypass cooldown for commands)
            send_telegram_message(response, chat_id, force=True)
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
            send_telegram_message(help_text, chat_id, force=True)
            print(f"Responded to /help command from chat {chat_id}")
            
        # Handle /start command
        elif text.startswith("/start"):
            if server_api.is_server_running():
                send_telegram_message("⚠️ Minecraft server is already running", chat_id, force=True)
            else:
                send_telegram_message("🔄 Starting Minecraft server...", chat_id, force=True)
                success = server_api.start_server()
                if success:
                    send_telegram_message("✅ Minecraft server started successfully", chat_id, force=True)
                else:
                    send_telegram_message("❌ Failed to start Minecraft server", chat_id, force=True)
        
        # Handle /stop command
        elif text.startswith("/stop"):
            if not server_api.is_server_running():
                send_telegram_message("⚠️ Minecraft server is not running", chat_id, force=True)
            else:
                send_telegram_message("🔄 Stopping Minecraft server...", chat_id, force=True)
                success = server_api.stop_server()
                if success:
                    send_telegram_message("✅ Minecraft server stopped successfully", chat_id, force=True)
                else:
                    send_telegram_message("❌ Failed to stop Minecraft server", chat_id, force=True)
                    
        # Handle /cmd command
        elif text.startswith("/cmd "):
            if not server_api.is_server_running():
                send_telegram_message("⚠️ Cannot run command: Minecraft server is not running", chat_id, force=True)
            else:
                command = text[5:].strip()  # Remove "/cmd " prefix
                if not command:
                    send_telegram_message("⚠️ Please specify a command to run", chat_id, force=True)
                else:
                    send_telegram_message(f"🔄 Running command: <code>{command}</code>", chat_id, force=True)
                    success = server_api.run_command(command)
                    if success:
                        send_telegram_message("✅ Command sent successfully", chat_id, force=True)
                    else:
                        send_telegram_message("❌ Failed to send command", chat_id, force=True)
                        
        # Handle /restart command (restart the bot)
        elif text.startswith("/restart"):
            # Check if we've restarted too many times recently
            if check_restart_limit():
                send_telegram_message("🔄 Restarting the notification bot...", chat_id, force=True)
                print("Restart command received, exiting process...")
                # The systemd service will restart the bot
                sys.exit(0)
            else:
                send_telegram_message("⚠️ Too many restarts in the last hour. Please wait before restarting again.", chat_id, force=True)
            
        # Handle /debug command
        elif text.startswith("/debug"):
            with player_lock:
                tracked_player_count = len(active_players)
                player_list = list(active_players)
            
            # Check if restart marker file exists
            restart_count = 0
            if os.path.exists(restart_marker_file):
                try:
                    with open(restart_marker_file, 'r') as f:
                        restarts = [int(line.strip()) for line in f if line.strip()]
                        one_hour_ago = int(time.time()) - 3600
                        restart_count = len([t for t in restarts if t > one_hour_ago])
                except Exception:
                    pass
            
            debug_info = f"""
<b>Debug Information:</b>
• <b>Bot Version:</b> 1.2
• <b>Server Path:</b> <code>{SERVER_PATH}</code>
• <b>Log Path:</b> <code>{SERVER_LOG_PATH}</code>
• <b>Server IP:</b> <code>{SERVER_IP}</code>
• <b>Server Port:</b> <code>{SERVER_PORT}</code>
• <b>Server Running:</b> {server_api.is_server_running()}
• <b>Log File Exists:</b> {os.path.exists(SERVER_LOG_PATH)}
• <b>Log File Size:</b> {os.path.getsize(SERVER_LOG_PATH) if os.path.exists(SERVER_LOG_PATH) else 0} bytes
• <b>Current Directory:</b> <code>{os.getcwd()}</code>
• <b>Python Version:</b> <code>{sys.version}</code>
• <b>Tracked Player Count:</b> {tracked_player_count}
• <b>Tracked Players:</b> {', '.join(player_list) if player_list else 'None'}
• <b>Active Message Cooldowns:</b> {len(last_message_time)}
• <b>Restarts in Last Hour:</b> {restart_count}
"""
            send_telegram_message(debug_info, chat_id, force=True)
            print(f"Responded to /debug command from chat {chat_id}")
    
    except Exception as e:
        error_message = f"⚠️ Error processing command: {str(e)}"
        print(f"Error handling command: {e}")
        try:
            send_telegram_message(error_message, chat_id, force=True)
        except:
            pass

def start_command_listener():
    """Start a background thread to listen for Telegram commands."""
    # Using long polling to listen for updates
    last_update_id = 0
    
    print("Starting Telegram command listener...")
    
    # Exponential backoff parameters
    max_retry_delay = 300  # Maximum retry delay in seconds (5 minutes)
    retry_delay = 1  # Start with 1 second delay
    
    while True:
        try:
            # Get updates from Telegram
            api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            params = {
                "offset": last_update_id + 1,
                "timeout": 30
            }
            
            response = requests.get(api_url, params=params, timeout=35)
            if response.status_code == 200:
                # Reset retry delay on success
                retry_delay = 1
                
                updates = response.json().get("result", [])
                
                for update in updates:
                    # Process the update
                    update_id = update.get("update_id")
                    last_update_id = max(last_update_id, update_id)
                    
                    # Handle commands
                    handle_telegram_commands(update)
            else:
                print(f"Error from Telegram API: {response.status_code} - {response.text}")
                # Implement exponential backoff
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)
            
            time.sleep(1)  # Small delay to avoid hammering the API
        
        except requests.exceptions.RequestException as e:
            print(f"Network error in command listener: {e}")
            # Implement exponential backoff for network errors
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)
        
        except Exception as e:
            print(f"Error in command listener: {e}")
            time.sleep(5)  # Wait a bit longer on other errors

def main():
    print("Minecraft Bedrock Server Telegram Notifier v1.2")
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
    
    # Initialize the player list with currently online players
    try:
        if server_api.is_server_running():
            online_players = server_api.get_online_players()
            with player_lock:
                active_players.update(online_players)
            print(f"Initialized player list with {len(online_players)} player(s)")
        else:
            print("Server not running, skipping player list initialization")
    except Exception as e:
        print(f"Error initializing player list: {e}")
    
    # Start player list sync thread
    sync_thread = threading.Thread(
        target=sync_player_list,
        daemon=True,
        name="PlayerSyncThread"
    )
    sync_thread.start()
    
    # Send startup notification (with high priority)
    send_telegram_message("🎮 Minecraft server notification system is now active!", force=True)
    
    # Start the command listener if Telegram is configured
    if NOTIFICATIONS_ENABLED:
        # Register signal handlers for graceful shutdown
        def handle_exit(signum, frame):
            print(f"\nReceived signal {signum}, shutting down...")
            try:
                send_telegram_message("🔄 Minecraft notification bot is shutting down", force=True)
            except:
                pass
            sys.exit(0)
            
        signal.signal(signal.SIGINT, handle_exit)
        signal.signal(signal.SIGTERM, handle_exit)
        
        # Start command listener in the main thread
        try:
            start_command_listener()
        except Exception as e:
            print(f"Fatal error in command listener: {e}")
            send_telegram_message(f"⚠️ Fatal error: {str(e)}", force=True)
            sys.exit(1)
    else:
        print("Telegram notifications disabled. Running in monitoring mode only.")
        # Just keep the script alive to monitor events
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print("\nShutting down notification system...")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Last resort error handling
        print(f"FATAL ERROR: {e}")
        
        # Try to send error notification before exiting
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            try:
                api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                requests.post(api_url, data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": f"⚠️ Bot crashed with error: {str(e)}",
                    "parse_mode": "HTML"
                }, timeout=10)
            except:
                pass
            
        sys.exit(1)