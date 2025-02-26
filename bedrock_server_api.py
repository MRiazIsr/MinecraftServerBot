#!/usr/bin/env python3
import os
import subprocess
import re
import time
import socket
import threading
import json
import logging
from datetime import datetime
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("minecraft_bot.log")
    ]
)

logger = logging.getLogger("BedrockServerAPI")

class BedrockServerAPI:
    """A class to interact with a Minecraft Bedrock server running on the same machine."""
    
    def __init__(self, server_path="/home/ubuntu/minecraft-bedrock", 
                 log_path="/home/ubuntu/minecraft-bedrock/logs.txt",
                 server_port=19132):
        """Initialize the API.
        
        Args:
            server_path: Path to the Bedrock server directory
            log_path: Path to the server log file
            server_port: The port the server is running on
        """
        self.server_path = server_path
        self.log_path = log_path
        self.server_port = server_port
        self.server_process = None
        self.input_pipe = None
        self.event_callbacks = {
            'player_join': [],
            'player_leave': [],
            'chat_message': [],
            'server_start': [],
            'server_stop': []
        }
        
        # Make paths absolute
        self.server_path = os.path.abspath(self.server_path)
        self.log_path = os.path.abspath(self.log_path)
        
        logger.info(f"Initialized API with server path: {self.server_path}")
        logger.info(f"Log path: {self.log_path}")
        
        # Create the log file directory if it doesn't exist
        log_dir = os.path.dirname(self.log_path)
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create log directory: {e}")
        
        # Create the log file if it doesn't exist
        self._ensure_log_file_exists()
        
    def _ensure_log_file_exists(self):
        """Create the log file if it doesn't exist, with robust error handling."""
        try:
            if not os.path.exists(self.log_path):
                logger.info(f"Log file doesn't exist, creating: {self.log_path}")
                # Create an empty file
                with open(self.log_path, 'w') as f:
                    pass
                
                # Set appropriate permissions
                try:
                    os.chmod(self.log_path, 0o644)  # Owner read/write, group/others read
                except Exception as perm_error:
                    logger.warning(f"Could not set permissions on log file: {perm_error}")
                
                return True
        except Exception as e:
            logger.error(f"Error creating log file: {e}")
            return False
        
        return True
        
    def is_server_running(self):
        """Check if the Bedrock server process is running with multiple fallback methods."""
        try:
            # Method 1: Check using pgrep
            try:
                subprocess.check_output(["pgrep", "-f", "bedrock_server"], universal_newlines=True)
                logger.debug("Server detected as running via pgrep")
                return True
            except subprocess.CalledProcessError:
                # pgrep didn't find the process, but let's try other methods
                pass
            
            # Method 2: Check for running screens with the minecraft server
            try:
                screen_output = subprocess.check_output(["screen", "-ls"], universal_newlines=True)
                if "minecraft" in screen_output:
                    logger.debug("Server detected as running via screen session")
                    return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                # screen command failed or isn't installed
                pass
            
            # Method 3: Check if port is in use
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.bind(('0.0.0.0', self.server_port))
                sock.close()
                # If we can bind to the port, the server is not running
                return False
            except socket.error:
                # Port is in use, likely by the server
                logger.debug("Server detected as running via port check")
                return True
            
            # If all methods fail, assume server is not running
            return False
            
        except Exception as e:
            logger.error(f"Error checking server status: {e}")
            # Default to assuming the server is running to prevent accidental restarts
            return True
        
    def start_server(self):
        """Start the Bedrock server if it's not already running with multiple methods."""
        if self.is_server_running():
            logger.info("Server is already running")
            return True
            
        logger.info("Attempting to start server...")
        
        # Track if any method succeeded
        success = False
        
        try:
            # Change to server directory
            original_dir = os.getcwd()
            os.chdir(self.server_path)
            
            # Try multiple methods to start the server
            
            # Method 1: Using screen
            try:
                logger.info("Attempting to start server with screen...")
                screen_cmd = ["screen", "-dmS", "minecraft", "./bedrock_server"]
                subprocess.run(screen_cmd, check=True)
                success = True
                logger.info("Server started with screen")
            except Exception as e:
                logger.warning(f"Failed to start server with screen: {e}")
            
            # Method 2: Using tmux if screen failed
            if not success:
                try:
                    logger.info("Attempting to start server with tmux...")
                    tmux_cmd = ["tmux", "new-session", "-d", "-s", "minecraft", "./bedrock_server"]
                    subprocess.run(tmux_cmd, check=True)
                    success = True
                    logger.info("Server started with tmux")
                except Exception as e:
                    logger.warning(f"Failed to start server with tmux: {e}")
            
            # Method 3: Direct process (last resort, may not be ideal for production)
            if not success:
                try:
                    logger.info("Attempting to start server directly...")
                    # Start as background process
                    subprocess.Popen(
                        ["./bedrock_server"], 
                        stdout=open("server_output.log", "a"),
                        stderr=subprocess.STDOUT,
                        start_new_session=True
                    )
                    success = True
                    logger.info("Server started directly")
                except Exception as e:
                    logger.error(f"Failed to start server directly: {e}")
            
            # Change back to original directory
            os.chdir(original_dir)
            
            # Wait for the server to finish starting
            if success:
                time.sleep(5)  # Give the server a moment to initialize
                
                # Verify server is actually running
                if not self.is_server_running():
                    logger.error("Server failed to start despite successful command execution")
                    success = False
                else:
                    # Trigger server start event
                    self._trigger_event('server_start', {})
            
            return success
        except Exception as e:
            logger.error(f"Error starting server: {e}")
            return False
            
    def stop_server(self):
        """Stop the Bedrock server gracefully with multiple methods."""
        if not self.is_server_running():
            logger.info("Server is not running")
            return True
            
        try:
            # Method 1: Try running the stop command
            logger.info("Attempting to stop server gracefully...")
            self.run_command("stop")
            
            # Give the server a moment to shut down
            for i in range(10):  # Wait up to 10 seconds
                time.sleep(1)
                if not self.is_server_running():
                    logger.info("Server stopped gracefully")
                    self._trigger_event('server_stop', {})
                    return True
            
            logger.warning("Server didn't stop with command after 10 seconds")
            
            # Method 2: Try killing the process with SIGTERM
            logger.info("Attempting to stop server with SIGTERM...")
            try:
                subprocess.run(["pkill", "-TERM", "-f", "bedrock_server"], check=True)
                time.sleep(3)
                if not self.is_server_running():
                    logger.info("Server stopped with SIGTERM")
                    self._trigger_event('server_stop', {})
                    return True
            except Exception as e:
                logger.warning(f"Error stopping server with SIGTERM: {e}")
            
            # Method 3: Force kill as last resort
            logger.warning("Server didn't stop gracefully, forcing stop...")
            try:
                subprocess.run(["pkill", "-KILL", "-f", "bedrock_server"], check=True)
                time.sleep(1)
                if not self.is_server_running():
                    logger.info("Server stopped forcefully")
                    self._trigger_event('server_stop', {})
                    return True
                else:
                    logger.error("Failed to stop server even with SIGKILL")
                    return False
            except Exception as e:
                logger.error(f"Error force stopping server: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error stopping server: {e}")
            return False
    
    def run_command(self, command):
        """Run a command on the Bedrock server with multiple methods.
        
        Args:
            command: The command to run (without leading slash)
        
        Returns:
            bool: Whether the command was sent successfully
        """
        if not self.is_server_running():
            logger.warning("Cannot run command: Server is not running")
            return False
            
        logger.info(f"Running command: {command}")
        
        try:
            # Try multiple methods to send the command
            
            # Method 1: Using screen
            try:
                screen_cmd = f"screen -S minecraft -X stuff '{command}\n'"
                subprocess.run(screen_cmd, shell=True, check=True)
                logger.info(f"Command sent via screen: {command}")
                return True
            except subprocess.CalledProcessError:
                logger.debug("Failed to send command via screen")
            
            # Method 2: Using tmux
            try:
                tmux_cmd = f"tmux send-keys -t minecraft '{command}' Enter"
                subprocess.run(tmux_cmd, shell=True, check=True)
                logger.info(f"Command sent via tmux: {command}")
                return True
            except subprocess.CalledProcessError:
                logger.debug("Failed to send command via tmux")
            
            # Method 3: Find and attach to the process's stdin (advanced)
            try:
                # This approach is more complex and would require additional logic
                # to find and connect to the server process's stdin
                logger.debug("Direct stdin connection not implemented")
            except Exception:
                pass
            
            logger.warning(f"Could not find a method to send command: {command}")
            return False
        except Exception as e:
            logger.error(f"Error running command: {e}")
            return False
    
    def get_online_players(self):
        """Get a list of online players using multiple methods."""
        online_players = []
        
        try:
            # Method 1: Parse the log file (from your existing code)
            log_players = self._get_players_from_log()
            if log_players:
                online_players.extend(log_players)
                logger.debug(f"Found {len(log_players)} players from log file")
            
            # Method 2: Try running the 'list' command and capturing output
            # This would require more advanced handling to capture command output
            
            # Deduplicate the list
            online_players = list(set(online_players))
            
            return online_players
        except Exception as e:
            logger.error(f"Error getting player list: {e}")
            return []
    
    def _get_players_from_log(self):
        """Get player list by parsing the log file with robust error handling."""
        try:
            # Make sure log file exists
            if not os.path.exists(self.log_path):
                logger.warning(f"Log file doesn't exist: {self.log_path}")
                self._ensure_log_file_exists()
                return []
                
            # Check if log file is readable
            if not os.access(self.log_path, os.R_OK):
                logger.warning(f"Log file is not readable: {self.log_path}")
                return []
                
            # Check if log file is empty
            if os.path.getsize(self.log_path) == 0:
                logger.debug("Log file is empty")
                return []
            
            # This uses a simple approach by checking recent log entries
            # Read the last 1000 lines of the log file
            try:
                output = subprocess.check_output(["tail", "-n", "1000", self.log_path], universal_newlines=True)
            except subprocess.CalledProcessError:
                logger.warning("Failed to read log file with tail command")
                # Fallback: read directly
                try:
                    with open(self.log_path, 'r', errors='replace') as f:
                        lines = f.readlines()
                        output = ''.join(lines[-1000:] if len(lines) > 1000 else lines)
                except Exception as read_error:
                    logger.error(f"Failed to read log file directly: {read_error}")
                    return []
            
            # Find all player connections and disconnections
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
                        player_name = match.group(1).strip()
                        if player_name and player_name not in connected_players:
                            connected_players.append(player_name)
                
                # Check for player disconnections
                for pattern in player_leave_patterns:
                    match = pattern.search(line)
                    if match:
                        player_name = match.group(1).strip()
                        if player_name:
                            disconnected_players.append(player_name)
            
            # Filter out disconnected players
            current_players = [p for p in connected_players if p not in disconnected_players]
            
            return current_players
            
        except Exception as e:
            logger.error(f"Error parsing log file for players: {e}")
            return []
    
    def on(self, event_type, callback):
        """Register a callback for a specific event.
        
        Args:
            event_type: The type of event ('player_join', 'player_leave', etc.)
            callback: The function to call when the event occurs
        """
        if event_type in self.event_callbacks:
            self.event_callbacks[event_type].append(callback)
            logger.debug(f"Registered callback for event: {event_type}")
            return True
        logger.warning(f"Attempted to register callback for unknown event: {event_type}")
        return False
    
    def _trigger_event(self, event_type, data):
        """Trigger callbacks for an event.
        
        Args:
            event_type: The type of event
            data: Data to pass to the callbacks
        """
        if event_type in self.event_callbacks:
            for callback in self.event_callbacks[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Error in {event_type} callback: {e}")
    
    def start_log_monitor(self):
        """Start monitoring the log file for events."""
        # Create a dedicated thread for log monitoring
        self.log_monitor_thread = threading.Thread(
            target=self._monitor_log_file,
            daemon=True,
            name="LogMonitorThread"
        )
        self.log_monitor_thread.start()
        logger.info("Log monitor thread started")
            
    def _monitor_log_file(self):
        """Monitor the log file for events with robust error handling."""
        logger.info(f"Starting to monitor log file: {self.log_path}")
        
        # Create the log file if it doesn't exist
        if not self._ensure_log_file_exists():
            logger.error("Failed to create or access log file, monitoring may not work")
        
        # Get current file size or create file if it doesn't exist
        try:
            file_size = os.path.getsize(self.log_path)
        except Exception as e:
            logger.error(f"Error getting initial file size: {e}")
            file_size = 0
        
        # Precompile regular expressions for better performance
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
        
        chat_patterns = [
            re.compile(r"\[CHAT\] (.*?): (.*)"),
            re.compile(r"\[INFO\] (.*?) says: (.*)"),
            re.compile(r"<(.*?)> (.*)")
        ]
        
        logger.info(f"Starting monitoring from position {file_size} in log file")
        
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while True:
            try:
                # Check if log file exists
                if not os.path.exists(self.log_path):
                    logger.warning("Log file disappeared, attempting to recreate")
                    self._ensure_log_file_exists()
                    file_size = 0
                    time.sleep(5)
                    continue
                
                # Check if file size has changed
                try:
                    current_size = os.path.getsize(self.log_path)
                except Exception as e:
                    logger.error(f"Error getting current file size: {e}")
                    time.sleep(5)
                    continue
                
                # Check if file was truncated (e.g., log rotation)
                if current_size < file_size:
                    logger.info("Log file was truncated, resetting position")
                    file_size = 0
                
                if current_size > file_size:
                    try:
                        with open(self.log_path, 'r', errors='replace') as f:
                            # Move to the position we last read
                            f.seek(file_size)
                            
                            # Read new content
                            new_content = f.read()
                            
                            # Process each line separately
                            for line in new_content.splitlines():
                                line = line.strip()
                                if not line:
                                    continue
                                    
                                # Check for player joins
                                for pattern in player_join_patterns:
                                    match = pattern.search(line)
                                    if match:
                                        player_name = match.group(1).strip()
                                        if player_name:
                                            logger.info(f"Detected player join: {player_name}")
                                            self._trigger_event('player_join', {'player': player_name})
                                            break
                                
                                # Check for player leaves
                                for pattern in player_leave_patterns:
                                    match = pattern.search(line)
                                    if match:
                                        player_name = match.group(1).strip()
                                        if player_name:
                                            logger.info(f"Detected player leave: {player_name}")
                                            self._trigger_event('player_leave', {'player': player_name})
                                            break
                                        
                                # Check for chat messages
                                for pattern in chat_patterns:
                                    match = pattern.search(line)
                                    if match:
                                        player_name = match.group(1).strip()
                                        message = match.group(2).strip()
                                        if player_name and message:
                                            logger.info(f"Detected chat message: {player_name}: {message}")
                                            self._trigger_event('chat_message', {
                                                'player': player_name,
                                                'message': message
                                            })
                                            break
                                            
                        # Reset consecutive errors counter
                        consecutive_errors = 0
                    except Exception as e:
                        logger.error(f"Error reading log file content: {e}")
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            logger.critical(f"Too many consecutive errors ({consecutive_errors}), resetting file position")
                            file_size = 0
                            consecutive_errors = 0
                        time.sleep(5)
                        continue
                    
                    # Update the file position
                    file_size = current_size
            
            except Exception as e:
                logger.error(f"Unexpected error in log monitor: {e}")
                time.sleep(5)
                continue
            
            # Wait before checking again
            time.sleep(1)