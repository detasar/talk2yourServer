# Talk2YourServer - Installation Guide

A complete step-by-step guide to install and configure the Talk2YourServer Telegram bot for remote server management and AI assistance.

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Prerequisites Installation](#prerequisites-installation)
3. [PostgreSQL Setup](#postgresql-setup)
4. [Python Environment Setup](#python-environment-setup)
5. [Telegram Bot Setup](#telegram-bot-setup)
6. [API Keys Setup](#api-keys-setup)
7. [Local LLM Setup (Ollama)](#local-llm-setup-ollama)
8. [Claude Code Setup](#claude-code-setup)
9. [Configuration](#configuration)
10. [Running the Bot](#running-the-bot)
11. [Systemd Service Setup](#systemd-service-setup)
12. [Verification](#verification)
13. [Troubleshooting](#troubleshooting)

---

## System Requirements

### Minimum Requirements
- **OS:** Ubuntu 20.04+ or Debian 11+ (x86_64)
- **Python:** 3.11 or higher
- **PostgreSQL:** 14 or higher
- **RAM:** 2GB minimum (4GB recommended)
- **Disk Space:** 5GB free space (10GB+ if using local LLMs)
- **Network:** Internet connection for cloud LLM APIs

### Optional Requirements
- **GPU:** NVIDIA GPU with CUDA for local LLM acceleration
- **Docker:** For containerized services
- **Tailscale:** For secure VPN access (highly recommended)

---

## Prerequisites Installation

### Step 1: Update System Packages

```bash
sudo apt update
sudo apt upgrade -y
```

### Step 2: Install Python 3.11+

**Ubuntu 22.04+ (Python 3.11 included):**
```bash
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
```

**Ubuntu 20.04 (add repository):**
```bash
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
```

**Verify installation:**
```bash
python3.11 --version
# Should output: Python 3.11.x
```

### Step 3: Install PostgreSQL

```bash
# Install PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Check status
sudo systemctl status postgresql

# If not running, start it
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### Step 4: Install System Dependencies

```bash
# Essential build tools
sudo apt install -y build-essential git curl wget

# Optional: For system monitoring features
sudo apt install -y htop iotop sysstat
```

---

## PostgreSQL Setup

### Step 1: Create Database and User

Switch to PostgreSQL user and create the database:

```bash
# Switch to postgres user
sudo -i -u postgres

# Create database user (replace 'yourpassword' with a strong password)
createuser --interactive --pwprompt talk2server_user
# Enter password when prompted
# Answer 'n' to superuser, 'n' to create databases, 'n' to create roles

# Create database
createdb -O talk2server_user talk2server

# Exit postgres user
exit
```

**Alternative method using psql:**

```bash
sudo -u postgres psql

-- Inside PostgreSQL prompt:
CREATE USER talk2server_user WITH PASSWORD 'yourpassword';
CREATE DATABASE talk2server OWNER talk2server_user;
GRANT ALL PRIVILEGES ON DATABASE talk2server TO talk2server_user;

-- Exit
\q
```

### Step 2: Configure PostgreSQL Access (if needed)

If you plan to connect from another machine, edit the configuration:

```bash
# Edit pg_hba.conf
sudo nano /etc/postgresql/14/main/pg_hba.conf

# Add this line (for local network access):
# host    talk2server    talk2server_user    192.168.1.0/24    md5

# Edit postgresql.conf for network listening
sudo nano /etc/postgresql/14/main/postgresql.conf

# Change:
# listen_addresses = 'localhost'
# To:
# listen_addresses = '*'

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### Step 3: Test Database Connection

```bash
# Test connection (enter password when prompted)
psql -h localhost -U talk2server_user -d talk2server

# If successful, you'll see:
# talk2server=>

# Exit with:
\q
```

---

## Python Environment Setup

### Option 1: Using venv (Recommended for most users)

```bash
# Clone or navigate to project directory
cd /home/$USER
git clone https://github.com/detasar/talk2yourServer.git
cd talk2yourServer

# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### Option 2: Using Conda (If you have Miniconda/Anaconda)

```bash
# Navigate to project directory
cd /home/$USER/talk2yourServer

# Create conda environment
conda create -n talk2server python=3.11 -y

# Activate environment
conda activate talk2server

# Install dependencies
pip install -r requirements.txt
```

### Verify Installation

```bash
# Check installed packages
pip list | grep -E "telegram|asyncpg|groq|openai"

# Should see:
# python-telegram-bot    20.x
# asyncpg               0.29.x
# groq                  0.4.x
# openai                1.x.x
```

---

## Telegram Bot Setup

### Step 1: Create Bot with BotFather

1. Open Telegram and search for `@BotFather`
2. Start a conversation and send `/newbot`
3. Follow the prompts:
   - **Bot name:** Talk2YourServer (or your preferred name)
   - **Bot username:** Must end in 'bot', e.g., `YourServerManagerBot`
4. Save the **bot token** provided (looks like `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Configure Bot Settings (Optional)

```
# In BotFather chat:
/setdescription - Set bot description
/setabouttext - Set about text
/setuserpic - Upload bot profile picture
/setcommands - Set command list (see below)
```

**Suggested command list for BotFather:**
```
start - Start the bot and see welcome message
help - Show available commands
status - Show system status
stats - Show usage statistics
ask - Ask AI a question
shell - Execute shell command (admin only)
claude - Start Claude Code session
claude_end - End Claude Code session
history - Show chat history
services - Manage systemd services
```

### Step 3: Get Your Telegram User ID

1. Open Telegram and search for `@userinfobot`
2. Start a conversation
3. Your user ID will be displayed (a number like `123456789`)
4. Save this number - you'll need it for configuration

---

## API Keys Setup

The bot supports multiple LLM providers with automatic fallback. All API keys are **optional**, but you need at least one provider (cloud API or local Ollama).

### Groq API (Recommended - Fast & Free Tier)

1. Visit [https://console.groq.com](https://console.groq.com)
2. Sign up or log in
3. Navigate to **API Keys** section
4. Click **Create API Key**
5. Copy the key (starts with `gsk_`)

**Free Tier:** 30 requests/minute, 14,400 requests/day

### OpenAI API (Optional)

1. Visit [https://platform.openai.com](https://platform.openai.com)
2. Sign up or log in
3. Go to **API keys** → **Create new secret key**
4. Copy the key (starts with `sk-`)

**Pricing:** Pay-as-you-go (GPT-4o-mini: ~$0.15/1M input tokens)

### Anthropic API (Optional)

1. Visit [https://console.anthropic.com](https://console.anthropic.com)
2. Sign up or log in
3. Navigate to **API Keys**
4. Click **Create Key**
5. Copy the key (starts with `sk-ant-`)

**Pricing:** Pay-as-you-go (Claude 3.5 Sonnet: ~$3/1M input tokens)

---

## Local LLM Setup (Ollama)

Ollama provides free, local LLM inference without API keys.

### Step 1: Install Ollama

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Verify installation
ollama --version
```

### Step 2: Start Ollama Service

```bash
# Enable and start service
sudo systemctl enable ollama
sudo systemctl start ollama

# Check status
sudo systemctl status ollama
```

### Step 3: Pull Models

```bash
# Small, fast model (recommended for testing)
ollama pull llama3.2:3b

# Larger, more capable models
ollama pull llama3.3:70b      # Requires 40GB+ RAM
ollama pull qwen2.5-coder:7b   # Good for coding

# List installed models
ollama list
```

### Step 4: Test Ollama

```bash
# Interactive test
ollama run llama3.2:3b
# Type a message and press Enter
# Type /bye to exit

# API test
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.2:3b",
  "prompt": "Hello, world!",
  "stream": false
}'
```

### GPU Acceleration (Optional)

If you have an NVIDIA GPU:

```bash
# Check GPU is detected
nvidia-smi

# Ollama automatically uses GPU if available
# Check GPU usage while running a model:
watch -n 1 nvidia-smi
```

---

## Claude Code Setup

Claude Code provides advanced AI assistance with direct file system access.

### Step 1: Install Claude CLI

```bash
# Install via npm (requires Node.js)
npm install -g @anthropic-ai/claude-cli

# Or use the standalone installer:
curl -fsSL https://raw.githubusercontent.com/anthropics/claude-cli/main/install.sh | sh
```

**If Node.js is not installed:**
```bash
# Install Node.js 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Verify
node --version
npm --version
```

### Step 2: Authenticate Claude CLI

```bash
# Start authentication
claude auth

# Follow the prompts:
# 1. Your browser will open
# 2. Log in to Claude account
# 3. Authorize the CLI
# 4. Return to terminal
```

### Step 3: Test Claude Code

```bash
# Test in current directory
claude "What files are in this directory?"

# Should get a response listing files
```

### Step 4: Create Workspace Directory

```bash
# Create dedicated workspace for Claude
mkdir -p ~/claude_workspace

# Test Claude in workspace
cd ~/claude_workspace
claude "Create a test file called hello.txt with the text 'Hello from Claude Code'"

# Verify
ls -la
cat hello.txt
```

---

## Configuration

### Step 1: Create Environment File

```bash
# Navigate to project directory
cd ~/talk2yourServer

# Copy example environment file (if exists) or create new
cp .env.example .env 2>/dev/null || touch .env

# Edit environment file
nano .env
```

### Step 2: Fill in Configuration

Copy and paste the following into `.env`, replacing values with your actual credentials:

```bash
# =============================================================================
# Talk2YourServer Configuration
# =============================================================================

# -----------------------------------------------------------------------------
# Telegram Bot Settings (REQUIRED)
# -----------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_ALLOWED_USERS=123456789,987654321
TELEGRAM_ADMIN_USERS=123456789

# -----------------------------------------------------------------------------
# Database Configuration (REQUIRED)
# -----------------------------------------------------------------------------
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=talk2server
POSTGRES_USER=talk2server_user
POSTGRES_PASSWORD=yourpassword

# -----------------------------------------------------------------------------
# LLM API Keys (At least ONE recommended)
# -----------------------------------------------------------------------------
# Groq (recommended - fast & free tier)
GROQ_API_KEY=gsk_your_groq_api_key_here

# OpenAI (optional)
OPENAI_API_KEY=sk-your_openai_api_key_here

# Anthropic (optional)
ANTHROPIC_API_KEY=sk-ant-your_anthropic_api_key_here

# -----------------------------------------------------------------------------
# Service URLs
# -----------------------------------------------------------------------------
OLLAMA_URL=http://localhost:11434
PROMETHEUS_URL=http://localhost:9090

# -----------------------------------------------------------------------------
# LLM Model Selection
# -----------------------------------------------------------------------------
DEFAULT_OLLAMA_MODEL=llama3.2:3b
DEFAULT_CLAUDE_MODEL=opus
OPENAI_MODEL=gpt-4o-mini

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
WORKING_DIR=/home/detasar
WORKSPACE_DIR=/home/detasar/claude_workspace
LOG_DIR=/home/detasar/talk2yourServer/logs

# -----------------------------------------------------------------------------
# Rate Limiting
# -----------------------------------------------------------------------------
RATE_LIMIT=60
RATE_WINDOW=60

# -----------------------------------------------------------------------------
# Alert Thresholds
# -----------------------------------------------------------------------------
ALERT_ENABLED=true
ALERT_GPU_TEMP=80
ALERT_GPU_MEMORY=95
ALERT_DISK=90
ALERT_MEMORY=90
ALERT_CPU=95
ALERT_CHECK_INTERVAL=60
ALERT_COOLDOWN=300

# -----------------------------------------------------------------------------
# Health Check
# -----------------------------------------------------------------------------
HEALTH_CHECK_PORT=8765

# -----------------------------------------------------------------------------
# Critical Services to Monitor
# -----------------------------------------------------------------------------
CRITICAL_SERVICES=postgresql,ollama

# -----------------------------------------------------------------------------
# Email Notifications (Optional)
# -----------------------------------------------------------------------------
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
NOTIFICATION_EMAIL=your-email@gmail.com
```

### Step 3: Secure Environment File

```bash
# Set restrictive permissions
chmod 600 .env

# Verify
ls -la .env
# Should show: -rw------- (only owner can read/write)
```

### Step 4: Create Log Directory

```bash
# Create logs directory
mkdir -p ~/talk2yourServer/logs

# Set permissions
chmod 755 ~/talk2yourServer/logs
```

### Step 5: Validate Configuration

```bash
# Activate virtual environment (if using venv)
source venv/bin/activate

# Run validation (if available in project)
python3 -c "from src.config import config; errors = config.validate(); print('\n'.join(errors) if errors else 'Configuration valid!')"
```

---

## Running the Bot

### Manual Start (for testing)

```bash
# Navigate to project directory
cd ~/talk2yourServer

# Activate virtual environment
source venv/bin/activate  # or: conda activate talk2server

# Run the bot
python3 src/bot.py
```

**Expected output:**
```
2025-12-18 12:00:00 - INFO - Starting Talk2YourServer bot...
2025-12-18 12:00:00 - INFO - Connected to PostgreSQL database
2025-12-18 12:00:00 - INFO - LLM providers available: ollama, groq
2025-12-18 12:00:00 - INFO - Bot started successfully!
```

### Test Basic Functionality

1. Open Telegram
2. Search for your bot by username
3. Send `/start`
4. You should receive a welcome message

### Stop the Bot

Press `Ctrl + C` in the terminal running the bot.

---

## Systemd Service Setup

For production use, run the bot as a systemd service that starts automatically on boot.

### Step 1: Create Service File

```bash
# Create service file
sudo nano /etc/systemd/system/talk2yourserver.service
```

### Step 2: Add Service Configuration

**If using venv:**

```ini
[Unit]
Description=Talk2YourServer Telegram Bot
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=detasar
Group=detasar
WorkingDirectory=/home/detasar/talk2yourServer
Environment="PATH=/home/detasar/talk2yourServer/venv/bin"
ExecStart=/home/detasar/talk2yourServer/venv/bin/python3 src/bot.py
Restart=always
RestartSec=10
StandardOutput=append:/home/detasar/talk2yourServer/logs/bot.log
StandardError=append:/home/detasar/talk2yourServer/logs/bot.error.log

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/detasar/talk2yourServer/logs

[Install]
WantedBy=multi-user.target
```

**If using conda:**

```ini
[Unit]
Description=Talk2YourServer Telegram Bot
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=detasar
Group=detasar
WorkingDirectory=/home/detasar/talk2yourServer
Environment="PATH=/home/detasar/miniconda3/envs/talk2server/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/detasar/miniconda3/envs/talk2server/bin/python src/bot.py
Restart=always
RestartSec=10
StandardOutput=append:/home/detasar/talk2yourServer/logs/bot.log
StandardError=append:/home/detasar/talk2yourServer/logs/bot.error.log

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/detasar/talk2yourServer/logs

[Install]
WantedBy=multi-user.target
```

**Important:** Replace `detasar` with your actual Linux username in all paths.

### Step 3: Enable and Start Service

```bash
# Reload systemd to recognize new service
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable talk2yourserver.service

# Start service
sudo systemctl start talk2yourserver.service

# Check status
sudo systemctl status talk2yourserver.service
```

### Step 4: Manage Service

```bash
# Stop service
sudo systemctl stop talk2yourserver.service

# Restart service
sudo systemctl restart talk2yourserver.service

# View logs (live)
sudo journalctl -u talk2yourserver.service -f

# View recent logs
sudo journalctl -u talk2yourserver.service -n 100

# View logs from today
sudo journalctl -u talk2yourserver.service --since today
```

---

## Verification

### Step 1: Check Service Status

```bash
# Check bot service
sudo systemctl status talk2yourserver.service

# Should show: Active: active (running)
```

### Step 2: Test Telegram Bot

Open Telegram and test these commands:

1. **Start bot:**
   ```
   /start
   ```
   Expected: Welcome message with bot description

2. **Check status:**
   ```
   /status
   ```
   Expected: System information (CPU, memory, disk usage)

3. **Test LLM:**
   ```
   /ask What is 2+2?
   ```
   Expected: AI response (e.g., "4" or detailed explanation)

4. **View history:**
   ```
   /history
   ```
   Expected: Recent chat messages

5. **Check statistics:**
   ```
   /stats
   ```
   Expected: Usage statistics

### Step 3: Verify Database

```bash
# Connect to database
psql -h localhost -U talk2server_user -d talk2server

# Check tables
\dt

# Should see:
# telegram_messages
# claude_sessions
# claude_session_messages
# usage_stats
# user_memory
# server_events

# Check message count
SELECT COUNT(*) FROM telegram_messages;

# Exit
\q
```

### Step 4: Check Logs

```bash
# View bot logs
tail -f ~/talk2yourServer/logs/bot.log

# View error logs
tail -f ~/talk2yourServer/logs/bot.error.log

# Check systemd logs
sudo journalctl -u talk2yourserver.service -n 50
```

### Step 5: Test LLM Providers

Send this command in Telegram:
```
/ask test
```

Check the response to see which provider was used. The bot will try providers in this order:
1. Ollama (local)
2. Groq (if API key configured)
3. OpenAI (if API key configured)

---

## Troubleshooting

### Bot Not Responding

**Symptom:** No response from bot in Telegram

**Solutions:**

1. **Check bot is running:**
   ```bash
   sudo systemctl status talk2yourserver.service
   ```

2. **Check logs for errors:**
   ```bash
   sudo journalctl -u talk2yourserver.service -n 100
   ```

3. **Verify network connectivity:**
   ```bash
   ping telegram.org
   ```

4. **Restart bot:**
   ```bash
   sudo systemctl restart talk2yourserver.service
   ```

### Database Connection Failed

**Symptom:** Error: "Database connection failed"

**Solutions:**

1. **Check PostgreSQL is running:**
   ```bash
   sudo systemctl status postgresql
   sudo systemctl start postgresql
   ```

2. **Test database connection:**
   ```bash
   psql -h localhost -U talk2server_user -d talk2server
   ```

3. **Check credentials in .env:**
   ```bash
   cat ~/.env | grep POSTGRES
   ```

4. **Check PostgreSQL logs:**
   ```bash
   sudo tail -f /var/log/postgresql/postgresql-14-main.log
   ```

### Permission Denied Errors

**Symptom:** Permission errors in logs

**Solutions:**

1. **Check .env file permissions:**
   ```bash
   ls -la ~/talk2yourServer/.env
   chmod 600 ~/talk2yourServer/.env
   ```

2. **Check log directory permissions:**
   ```bash
   ls -ld ~/talk2yourServer/logs
   chmod 755 ~/talk2yourServer/logs
   ```

3. **Check service user:**
   ```bash
   sudo systemctl cat talk2yourserver.service | grep User=
   # Should match your username
   ```

### Ollama Not Working

**Symptom:** "Ollama provider unavailable"

**Solutions:**

1. **Check Ollama service:**
   ```bash
   sudo systemctl status ollama
   sudo systemctl start ollama
   ```

2. **Test Ollama API:**
   ```bash
   curl http://localhost:11434/api/tags
   ```

3. **Check models are installed:**
   ```bash
   ollama list
   ```

4. **Pull default model:**
   ```bash
   ollama pull llama3.2:3b
   ```

### LLM API Key Errors

**Symptom:** "API key invalid" or "Authentication failed"

**Solutions:**

1. **Verify API key format:**
   - Groq: starts with `gsk_`
   - OpenAI: starts with `sk-`
   - Anthropic: starts with `sk-ant-`

2. **Check API key in .env:**
   ```bash
   cat ~/.env | grep API_KEY
   ```

3. **Test API key manually:**

   **Groq:**
   ```bash
   curl https://api.groq.com/openai/v1/models \
     -H "Authorization: Bearer $GROQ_API_KEY"
   ```

   **OpenAI:**
   ```bash
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer $OPENAI_API_KEY"
   ```

4. **Regenerate API key** on provider's website

### Bot Crashes or Restarts Frequently

**Symptom:** Bot repeatedly restarts

**Solutions:**

1. **Check error logs:**
   ```bash
   sudo journalctl -u talk2yourserver.service -p err
   ```

2. **Check system resources:**
   ```bash
   free -h
   df -h
   top
   ```

3. **Increase restart delay in systemd:**
   ```bash
   sudo systemctl edit talk2yourserver.service

   # Add:
   [Service]
   RestartSec=30
   ```

4. **Check Python dependencies:**
   ```bash
   source venv/bin/activate
   pip list | grep -E "telegram|asyncpg"
   pip install --upgrade -r requirements.txt
   ```

### Claude Code Not Working

**Symptom:** Claude Code commands fail

**Solutions:**

1. **Check Claude CLI is installed:**
   ```bash
   which claude
   claude --version
   ```

2. **Re-authenticate:**
   ```bash
   claude auth
   ```

3. **Test Claude manually:**
   ```bash
   cd ~/claude_workspace
   claude "Hello, can you read this directory?"
   ```

4. **Check workspace directory exists:**
   ```bash
   ls -ld ~/claude_workspace
   mkdir -p ~/claude_workspace
   ```

### Unauthorized Access

**Symptom:** "You are not authorized to use this bot"

**Solutions:**

1. **Verify your user ID:**
   - Search `@userinfobot` in Telegram
   - Compare with TELEGRAM_ALLOWED_USERS in .env

2. **Update allowed users:**
   ```bash
   nano ~/talk2yourServer/.env
   # Update: TELEGRAM_ALLOWED_USERS=your_user_id
   ```

3. **Restart bot:**
   ```bash
   sudo systemctl restart talk2yourserver.service
   ```

---

## Next Steps

After successful installation:

1. **Read the User Guide** - Learn all available commands
2. **Set up monitoring** - Configure alerts for system events
3. **Backup configuration** - Save `.env` file securely
4. **Configure firewall** - Ensure only necessary ports are open
5. **Set up Tailscale** - For secure remote access

---

## Getting Help

If you encounter issues not covered here:

1. **Check logs:**
   ```bash
   sudo journalctl -u talk2yourserver.service -f
   ```

2. **Search GitHub issues** - Someone may have solved your problem

3. **Create an issue** - Provide:
   - Error messages from logs
   - Output of `/status` command
   - System information (`uname -a`)
   - Python version (`python3 --version`)

---

## Security Notes

### Important Security Practices

1. **Protect your .env file:**
   ```bash
   chmod 600 ~/.env
   ```

2. **Restrict Telegram access:**
   - Only add trusted users to TELEGRAM_ALLOWED_USERS
   - Use TELEGRAM_ADMIN_USERS for elevated permissions

3. **Use Tailscale or VPN:**
   - Don't expose bot to public internet
   - Use VPN for remote access

4. **Regular updates:**
   ```bash
   cd ~/talk2yourServer
   git pull
   pip install --upgrade -r requirements.txt
   sudo systemctl restart talk2yourserver.service
   ```

5. **Monitor logs regularly:**
   ```bash
   sudo journalctl -u talk2yourserver.service --since today
   ```

6. **Database backups:**
   ```bash
   pg_dump -U talk2server_user talk2server > backup_$(date +%Y%m%d).sql
   ```

---

## Additional Resources

- **Telegram Bot API:** https://core.telegram.org/bots/api
- **Ollama Documentation:** https://ollama.com/docs
- **Claude Code:** https://github.com/anthropics/claude-cli
- **Groq API:** https://console.groq.com/docs
- **PostgreSQL:** https://www.postgresql.org/docs/

---

**Installation Complete!** Your Talk2YourServer bot should now be running and accessible via Telegram.
