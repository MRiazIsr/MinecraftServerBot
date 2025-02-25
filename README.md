# Minecraft Bedrock Server Telegram Notifier

A complete solution for sending Telegram notifications from your Minecraft Bedrock server. This project includes automatic deployment via GitHub Actions, player join/leave notifications, and secure credential handling.

## Features

- 🎮 Player join/leave notifications
- 🔄 Automatic deployment from GitHub
- 🔒 Secure handling of Telegram credentials
- 🌐 Works with Minecraft Bedrock Server
- 💻 Compatible with WSL development workflow

## Repository Structure

```
├── .github/
│   ├── workflows/
│   │   └── deploy.yml         # GitHub Actions workflow
│   └── scripts/
│       └── deploy.sh          # Deployment script
├── minecraft-telegram-notifier.py   # Main notification script
└── README.md                  # This documentation
```

## Setup Instructions

### 1. Telegram Bot Setup

1. Create a Telegram bot through [@BotFather](https://t.me/BotFather)
2. Get your bot token
3. Add your bot to a group or channel
4. Get the chat ID (use @getidsbot or @userinfobot)

### 2. GitHub Repository Setup

1. Create a new GitHub repository
2. Add the files from this project

### 3. Configure GitHub Secrets

Add these secrets to your repository (Settings > Secrets and variables > Actions):

- `SSH_PRIVATE_KEY`: Your private SSH key for server access
- `SSH_KNOWN_HOSTS`: Your server's SSH fingerprint
- `SSH_USER`: Username for SSH login (e.g., ubuntu)
- `SSH_HOST`: Your server's hostname or IP address
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `TELEGRAM_CHAT_ID`: Your Telegram chat ID

### 4. Server Setup

```bash
# On your Minecraft Bedrock server
cd ~/minecraft-bedrock

# Initialize git repository
git init
git remote add origin https://github.com/yourusername/your-repo.git
git fetch
git checkout -b main origin/main

# Make sure scripts are executable
chmod +x .github/scripts/deploy.sh
chmod +x minecraft-telegram-notifier.py
```

### 5. Development Workflow

```bash
# In WSL or your development environment
git clone https://github.com/yourusername/your-repo.git
cd your-repo

# Make changes
# ...

# Commit and push to deploy
git add .
git commit -m "Update server configuration"
git push
```

## Usage

### Running the Notification Script Directly

```bash
# With environment variables
export TELEGRAM_BOT_TOKEN="your_token_here"
export TELEGRAM_CHAT_ID="your_chat_id_here"
./minecraft-telegram-notifier.py
```

### Options

The notification script offers two modes:

1. **Integrated mode**: Starts and monitors the Minecraft server
2. **Standalone mode**: Only monitors an existing server instance

## Automatic Deployment

When you push changes to your GitHub repository:

1. GitHub Actions workflow triggers
2. Connects to your server via SSH
3. Runs the deployment script
4. Backs up world data
5. Pulls latest changes
6. Restarts the server if necessary
7. Sends notifications to Telegram

## Troubleshooting

- **No notifications**: Verify your bot token and chat ID
- **Deployment failures**: Check GitHub Actions logs
- **Permission denied**: Check SSH key and script permissions
- **Bot not responding**: Ensure the bot is in your group and has necessary permissions

## Security Notes

- Never commit tokens or API keys directly to your repository
- Always use GitHub secrets for sensitive information
- Consider rotating your tokens periodically for enhanced security

## License

This project is available under the MIT License.

## Acknowledgements

- Minecraft is a registered trademark of Mojang Studios
- Telegram is a registered trademark of Telegram FZ LLC