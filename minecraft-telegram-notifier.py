#!/usr/bin/env python3
import os
import sys
import requests

# Get token and chat ID from environment variables or command line
if len(sys.argv) >= 3:
    # Command line arguments
    TELEGRAM_BOT_TOKEN = sys.argv[1]
    TELEGRAM_CHAT_ID = sys.argv[2]
else:
    # Environment variables
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
    
# Check if credentials are available
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("Error: Telegram credentials not found.")
    print("You can provide them in two ways:")
    print("1. As environment variables TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
    print("2. As command line arguments: ./telegram-test.py BOT_TOKEN CHAT_ID")
    sys.exit(1)

# Send a test message
def send_test_message():
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": "🧪 Test message from Minecraft notification bot!",
        "parse_mode": "HTML"
    }
    
    print(f"Sending test message to chat ID: {TELEGRAM_CHAT_ID}")
    
    try:
        response = requests.post(api_url, data=data)
        if response.status_code == 200:
            print("✅ Message sent successfully!")
            return True
        else:
            print(f"❌ Error sending message. Status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

# Get bot information to verify token
def check_bot_info():
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
    
    print(f"Checking bot token validity...")
    
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            bot_info = response.json().get("result", {})
            bot_name = bot_info.get("first_name", "Unknown")
            bot_username = bot_info.get("username", "Unknown")
            print(f"✅ Bot token is valid!")
            print(f"Bot name: {bot_name}")
            print(f"Bot username: @{bot_username}")
            return True
        else:
            print(f"❌ Invalid bot token! Status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception when checking bot token: {e}")
        return False

if __name__ == "__main__":
    print("Telegram Bot Test Utility")
    print("------------------------")
    
    # Check bot token validity
    if check_bot_info():
        # If token is valid, send a test message
        send_test_message()
    else:
        print("Failed to validate bot token. Please check your credentials.")