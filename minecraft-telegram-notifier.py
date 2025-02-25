#!/usr/bin/env python3
import os
import time
import re
import requests
import subprocess
import threading
from datetime import datetime

class MinecraftBedrockMonitor:
    def __init__(self):
        # Get credentials from environment variables
        self.telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        
        # Check if we have valid credentials
        self.notifications_enabled = (
            self.telegram_bot_token is not None and 
            self.telegram_chat_id is not None and
            self.telegram_bot_token != "" and
            self.telegram_chat_id != ""
        )
        
        if not self.notifications_enabled:
            print("Warning: Telegram credentials not found in environment variables.")
            print("Notifications will be disabled.")
        
        self.server_process = None
        self.log_thread = None
        self.running = False
        
        # Configure paths
        self.minecraft_bedrock_server_path = "/home/ubuntu/minecraft-bedrock"
        self.bedrock_server_executable = "./bedrock_server"
        self.log_file_path = os.path.join(self.minecraft_bedrock_server_path, "server.log")

    def start_server_with_logging(self):
        """Start the Minecraft Bedrock server with output redirection to a log file."""
        try:
            # Change to the server directory
            os.chdir(self.minecraft_bedrock_server_path)
            
            # Create or truncate the log file
            with open(self.log_file_path, 'w') as log_file:
                pass
                
            # Start the server process with output redirection
            self.server_process = subprocess.Popen(
                self.bedrock_server_executable,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            print(f"Started Minecraft Bedrock server with PID: {self.server_process.pid}")
            self.running = True
            
            # Start a thread to monitor the server output
            self.log_thread = threading.Thread(target=self.monitor_server_output)
            self.log_thread.daemon = True
            self.log_thread.start()
            
            return True
        except Exception as e:
            print(f"Error starting Minecraft server: {e}")
            return False
    
    def monitor_server_output(self):
        """Monitor the server's output for player connections."""
        try:
            # Patterns for Bedrock server player connections and disconnections
            player_join_pattern = r"Player connected: (.*?),"
            player_leave_pattern = r"Player disconnected: (.*?),"
            
            with open(self.log_file_path, 'a') as log_file:
                for line in iter(self.server_process.stdout.readline, ''):
                    # Write to the log file
                    timestamp = datetime.now().strftime('[%Y-%m-%d %H:%M:%S]')
                    log_file.write(f"{timestamp} {line}")
                    log_file.flush()
                    
                    # Check for player connections
                    join_match = re.search(player_join_pattern, line)
                    if join_match:
                        player_name = join_match.group(1)
                        self.send_telegram_message(f"🎮 Player {player_name} has joined the Minecraft server!")
                    
                    # Check for player disconnections
                    leave_match = re.search(player_leave_pattern, line)
                    if leave_match:
                        player_name = leave_match.group(1)
                        self.send_telegram_message(f"👋 Player {player_name} has left the Minecraft server")
                    
                    # Print to console for debugging
                    print(line.strip())
                    
            print("Server process has ended")
            self.running = False
        
        except Exception as e:
            print(f"Error in output monitoring: {e}")
            self.running = False
    
    def send_telegram_message(self, message):
        """Send message to Telegram chat using environment variables."""
        if not self.notifications_enabled:
            print(f"Message not sent (notifications disabled): {message}")
            return
            
        api_url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        data = {
            "chat_id": self.telegram_chat_id,
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
    
    def stop_server(self):
        """Stop the Minecraft server gracefully."""
        if self.server_process:
            print("Stopping Minecraft server...")
            self.server_process.terminate()
            self.server_process.wait(timeout=30)
            self.running = False
            print("Minecraft server stopped")

class StandaloneMonitor:
    """A standalone monitor that doesn't start/stop the server but only watches the log file."""
    
    def __init__(self):
        # Get credentials from environment variables
        self.telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        
        # Check if we have valid credentials
        self.notifications_enabled = (
            self.telegram_bot_token is not None and 
            self.telegram_chat_id is not None and
            self.telegram_bot_token != "" and
            self.telegram_chat_id != ""
        )
        
        if not self.notifications_enabled:
            print("Warning: Telegram credentials not found in environment variables.")
            print("Notifications will be disabled.")
        
        self.running = False
        self.last_position = 0
        
        # Configure paths
        self.log_file_path = "/home/ubuntu/minecraft-bedrock/server.log"
    
    def start_monitoring(self):
        """Start monitoring an existing log file."""
        self.running = True
        
        # Check if the log file exists
        if not os.path.exists(self.log_file_path):
            print(f"Log file not found at: {self.log_file_path}")
            print("Creating an empty log file. Make sure your server writes to this location.")
            with open(self.log_file_path, 'w') as f:
                pass
        
        # Get the current file size
        self.last_position = os.path.getsize(self.log_file_path)
        
        print(f"Starting to monitor log file: {self.log_file_path}")
        print(f"Starting from position: {self.last_position}")
        
        try:
            while self.running:
                if os.path.exists(self.log_file_path):
                    current_size = os.path.getsize(self.log_file_path)
                    
                    if current_size > self.last_position:
                        with open(self.log_file_path, 'r') as file:
                            file.seek(self.last_position)
                            new_content = file.read()
                            self.last_position = file.tell()
                            
                            # Check for player connections
                            player_join_pattern = r"Player connected: (.*?),"
                            join_matches = re.finditer(player_join_pattern, new_content)
                            
                            for match in join_matches:
                                player_name = match.group(1)
                                self.send_telegram_message(f"🎮 Player {player_name} has joined the Minecraft server!")
                            
                            # Check for player disconnections
                            player_leave_pattern = r"Player disconnected: (.*?),"
                            leave_matches = re.finditer(player_leave_pattern, new_content)
                            
                            for match in leave_matches:
                                player_name = match.group(1)
                                self.send_telegram_message(f"👋 Player {player_name} has left the Minecraft server")
                
                time.sleep(1)
        
        except KeyboardInterrupt:
            print("Monitoring stopped by user")
        except Exception as e:
            print(f"Error monitoring log file: {e}")
        finally:
            self.running = False
    
    def send_telegram_message(self, message):
        """Send message to Telegram chat using environment variables."""
        if not self.notifications_enabled:
            print(f"Message not sent (notifications disabled): {message}")
            return
            
        api_url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        data = {
            "chat_id": self.telegram_chat_id,
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
    
    def stop_monitoring(self):
        """Stop the monitoring process."""
        self.running = False
        print("Monitoring stopped")

def main():
    print("Minecraft Bedrock Server Telegram Notifier")
    print("------------------------------------------")
    print("1. Start server with monitoring (will restart your server)")
    print("2. Monitor existing server (use if server is already running)")
    choice = input("Choose an option (1 or 2): ")
    
    try:
        if choice == "1":
            # Integrated mode
            monitor = MinecraftBedrockMonitor()
            if monitor.start_server_with_logging():
                print("Server started with monitoring. Press Ctrl+C to stop.")
                
                try:
                    # Keep the main thread alive
                    while monitor.running:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("Stopping...")
                finally:
                    monitor.stop_server()
            
        elif choice == "2":
            # Standalone monitoring mode
            monitor = StandaloneMonitor()
            print("Starting monitoring. Press Ctrl+C to stop.")
            monitor.start_monitoring()
            
        else:
            print("Invalid choice. Please run the script again.")
    
    except KeyboardInterrupt:
        print("Program terminated by user")

if __name__ == "__main__":
    main()