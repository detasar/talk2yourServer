# Talk2YourServer 🤖💬

<div align="center">

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Telegram Bot](https://img.shields.io/badge/Telegram-Bot-blue?logo=telegram)](https://telegram.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?logo=postgresql&logoColor=white)](https://www.postgresql.org/)

**Manage your Linux server from anywhere using a powerful Telegram bot with multi-LLM intelligence**

[Features](#-features) • [Quick Start](#-quick-start) • [Documentation](#-documentation) • [Architecture](#-architecture) • [Contributing](#-contributing)

</div>

---

## 🌟 Overview

Talk2YourServer is an intelligent Telegram bot that transforms your server management experience. Chat with your server as if it were a knowledgeable assistant, get real-time monitoring alerts, and execute complex tasks using natural language powered by multiple AI models.

**Why Talk2YourServer?**
- 🧠 **Multi-LLM Intelligence**: Automatic fallback between Ollama (local), Groq, and OpenAI
- 🔧 **Claude Code Integration**: Execute complex multi-step tasks with Anthropic's Claude
- 📊 **Smart Monitoring**: GPU, CPU, RAM, disk metrics with intelligent alert system
- 🐳 **Service Management**: Control Docker containers and systemd services via chat
- 💾 **Persistent Memory**: PostgreSQL-backed conversation history and user sessions
- 🔐 **Secure by Design**: User authentication, rate limiting, and dangerous command protection
- 🌅 **Proactive Assistant**: Morning greetings, daily summaries, and automatic health checks

---

## ✨ Features

### 🤖 Multi-LLM Chat Interface
- **Automatic Provider Fallback**: Ollama → Groq → OpenAI
- **Context-Aware Conversations**: Remembers your preferences and history
- **Streaming Responses**: Real-time message updates for long responses
- **Model Switching**: Choose your preferred AI model on the fly

### 🔧 Advanced Task Execution
- **Claude Code Integration**: Complex multi-step operations with code execution
- **Natural Language Commands**: "Check disk space" or "Restart the database"
- **File Operations**: Read logs, search files, edit configurations
- **Git Integration**: Commit changes, create pull requests, manage repositories

### 📊 Intelligent Monitoring
- **Real-Time Metrics**: GPU temperature, VRAM usage, CPU load, memory, disk space
- **Smart Alerts**: LLM-powered analysis of system issues
- **Threshold-Based Notifications**: Customizable alert triggers
- **Service Health Checks**: Monitor critical systemd services and Docker containers

### 🐳 Service Management
- **Docker Control**: Start, stop, restart, and inspect containers
- **Systemd Integration**: Manage system services (ollama, postgresql, nginx, etc.)
- **Status Overview**: Get comprehensive system and service status reports
- **Log Viewing**: Tail and search service logs directly from Telegram

### 💬 Proactive Communication
- **Morning Greetings**: Daily system status on your schedule
- **Event Summaries**: Recap of system events while you were away
- **Scheduled Reports**: Weekly/monthly usage statistics
- **Emergency Alerts**: Critical issues sent immediately

### 🔐 Security & Reliability
- **User Authentication**: Whitelist-based access control
- **Admin Roles**: Separate permissions for dangerous operations
- **Rate Limiting**: Prevent abuse and API quota exhaustion
- **Audit Trail**: Full history of commands and changes in PostgreSQL
- **Confirmation Prompts**: Safety checks for destructive operations

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11 or higher
- PostgreSQL 14+ with `asyncpg`
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- At least one LLM provider:
  - [Ollama](https://ollama.ai/) (local, free) or
  - [Groq API](https://console.groq.com) (cloud, free tier) or
  - [OpenAI API](https://platform.openai.com) (cloud, paid)

### Installation (5 Minutes)

```bash
# 1. Clone the repository
git clone https://github.com/detasar/talk2yourServer.git
cd talk2yourServer

# 2. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up database
sudo -u postgres createdb talk2server
sudo -u postgres createuser your_username

# 5. Configure environment
cp .env.example .env
nano .env  # Fill in your credentials

# 6. Initialize database
python src/db.py --init

# 7. Start the bot
python src/bot.py
```

**That's it!** Open Telegram and message your bot: `/start`

For detailed installation instructions, see [docs/INSTALLATION.md](docs/INSTALLATION.md).

---

## 📸 Screenshots

<div align="center">

### System Monitoring
![System Status](docs/images/screenshot-status.png)

### Chat with AI
![AI Chat](docs/images/screenshot-chat.png)

### Claude Code Execution
![Claude Code](docs/images/screenshot-claude.png)

### Smart Alerts
![Alerts](docs/images/screenshot-alerts.png)

</div>

> **Note**: Screenshots coming soon! Check back after the first stable release.

---

## 🎮 Usage Examples

### Basic Commands

```
/start          - Initialize bot and show welcome
/help           - Show all available commands
/status         - System overview (CPU, RAM, disk, GPU)
/gpu            - Detailed GPU metrics
/services       - List all managed services
/docker         - List running containers
/logs <service> - View recent logs
/alert toggle   - Enable/disable smart alerts
```

### Natural Language Queries

Just chat naturally! The bot understands:

```
"What's the GPU temperature?"
"Show me disk space on /home"
"Restart the ollama service"
"Is PostgreSQL running?"
"Show me the last 20 lines of nginx error log"
"What happened while I was away?"
```

### Claude Code Tasks

Prefix your message with `/claude` for complex operations:

```
/claude Find all Python files using deprecated imports and create a report

/claude Check if there are any security updates available and create a summary

/claude Analyze disk usage and suggest cleanup targets

/claude Create a backup script for the database and schedule it in cron
```

### Monitoring & Alerts

Set up proactive monitoring:

```
/alert set gpu_temp 85        - Alert when GPU exceeds 85°C
/alert set disk 90            - Alert when disk usage > 90%
/alert set memory 85          - Alert when RAM usage > 85%
/alert schedule morning 09:00 - Daily status at 9 AM
/alert history                - View recent alerts
```

---

## 🏗 Architecture

### System Design

```
┌─────────────────────────────────────────────────────────────┐
│                      Telegram Bot                           │
│                    (python-telegram-bot)                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
       ▼               ▼               ▼
┌────────────┐  ┌────────────┐  ┌────────────┐
│   LLM      │  │ Monitoring │  │  Service   │
│  Manager   │  │   System   │  │  Manager   │
└─────┬──────┘  └──────┬─────┘  └──────┬─────┘
      │                │                │
      ▼                ▼                ▼
┌─────────────────────────────────────────┐
│              PostgreSQL                 │
│  • Chat History    • Sessions           │
│  • User Memory     • Events             │
│  • Usage Stats     • Alerts             │
└─────────────────────────────────────────┘
      ▲                ▲                ▲
      │                │                │
┌─────┴────┐    ┌──────┴─────┐   ┌─────┴──────┐
│  Ollama  │    │   Docker   │   │  systemd   │
│  (Local) │    │ Containers │   │  Services  │
└──────────┘    └────────────┘   └────────────┘
      │                                  │
      ▼                                  ▼
┌──────────┐                      ┌────────────┐
│   Groq   │                      │   Claude   │
│  (Cloud) │                      │    Code    │
└──────────┘                      └────────────┘
      │
      ▼
┌──────────┐
│  OpenAI  │
│  (Cloud) │
└──────────┘
```

### Key Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Bot Handler** | Message routing, command processing | python-telegram-bot |
| **LLM Manager** | Multi-provider chat with automatic fallback | ollama, groq, openai |
| **Claude Integration** | Complex task execution and code generation | Claude Code CLI |
| **Monitoring System** | Resource tracking and alert generation | psutil, nvidia-smi |
| **Service Manager** | Docker and systemd control | docker-py, subprocess |
| **Database Layer** | Persistent storage with connection pooling | asyncpg, PostgreSQL |
| **Memory System** | User preferences and conversation context | PostgreSQL + embeddings |

### Data Flow

1. **User sends message** → Telegram → Bot Handler
2. **Authentication & Rate Limiting** → Allowed?
3. **Command or Chat?**
   - **Command**: Direct execution → Response
   - **Chat**: LLM Manager → Provider selection
4. **LLM Processing**:
   - Try Ollama (local) → Fast, free, private
   - Fallback to Groq (cloud) → Fast, generous free tier
   - Fallback to OpenAI (cloud) → Most capable, paid
5. **Response Generation** → Streaming updates → User
6. **Logging** → PostgreSQL for history and analytics

---

## 📚 Documentation

### User Guides
- [Installation Guide](docs/INSTALLATION.md) - Step-by-step setup
- [Configuration Reference](docs/CONFIGURATION.md) - All environment variables
- [Command Reference](docs/COMMANDS.md) - Complete command list
- [Claude Code Guide](docs/CLAUDE_CODE.md) - Advanced task automation

### Developer Docs
- [Architecture Overview](docs/ARCHITECTURE.md) - System design deep-dive
- [API Reference](docs/API.md) - Internal API documentation
- [Database Schema](docs/DATABASE.md) - PostgreSQL table structures
- [Plugin Development](docs/PLUGINS.md) - Extending functionality

### Operations
- [Deployment Guide](docs/DEPLOYMENT.md) - Production setup
- [Monitoring Setup](docs/MONITORING.md) - Prometheus, Grafana integration
- [Security Best Practices](docs/SECURITY.md) - Hardening your installation
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions

---

## 🛠 Technology Stack

### Core
- **Python 3.11+** - Modern async/await syntax
- **python-telegram-bot** - Telegram Bot API wrapper
- **asyncpg** - High-performance PostgreSQL driver
- **PostgreSQL 14+** - Persistent storage

### LLM Providers
- **Ollama** - Local LLM inference (llama3.2, qwen, mistral)
- **Groq** - Fast cloud inference (llama-3.3-70b, mixtral)
- **OpenAI** - GPT-4, GPT-3.5-turbo
- **Claude Code** - Anthropic's Claude with tool use

### Monitoring
- **psutil** - System metrics (CPU, memory, disk)
- **nvidia-smi** - GPU monitoring
- **docker-py** - Docker container management
- **systemd (via subprocess)** - Service management

### Development
- **black** - Code formatting
- **ruff** - Fast Python linter
- **pytest** - Testing framework
- **mypy** - Static type checking

---

## 🤝 Contributing

We welcome contributions! Whether it's bug reports, feature requests, documentation improvements, or code contributions.

### How to Contribute

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes** and add tests
4. **Format code**: `black . && ruff check .`
5. **Commit**: `git commit -m 'Add amazing feature'`
6. **Push**: `git push origin feature/amazing-feature`
7. **Open a Pull Request**

### Development Setup

```bash
# Clone your fork
git clone https://github.com/detasar/talk2yourServer.git
cd talk2yourServer

# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Format code
black .
ruff check . --fix

# Type checking
mypy src/
```

### Contribution Ideas

- 🌐 **Internationalization**: Add support for more languages
- 📊 **Grafana Dashboards**: Pre-built monitoring dashboards
- 🔌 **Plugin System**: Make the bot more extensible
- 📱 **Web Dashboard**: Companion web interface
- 🧪 **More Tests**: Improve test coverage
- 📖 **Documentation**: Improve docs and add examples
- 🎨 **UI/UX**: Better message formatting and menus

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## 📋 Roadmap

### Version 1.0 (Current)
- [x] Multi-LLM chat with fallback
- [x] Claude Code integration
- [x] System monitoring and alerts
- [x] Docker and systemd management
- [x] PostgreSQL storage
- [x] Rate limiting and security

### Version 1.1 (Next)
- [ ] Web dashboard for configuration
- [ ] Prometheus metrics export
- [ ] Plugin system for extensibility
- [ ] Multi-language support
- [ ] Voice message support
- [ ] Scheduled task execution

### Version 2.0 (Future)
- [ ] Multi-server management (one bot, many servers)
- [ ] Mobile app companion
- [ ] Machine learning for predictive alerts
- [ ] Integration with cloud providers (AWS, Azure, GCP)
- [ ] Collaborative features (team access)
- [ ] Advanced automation workflows

Vote for features or suggest new ones in [GitHub Discussions](https://github.com/detasar/talk2yourServer/discussions)!

---

## ❓ FAQ

<details>
<summary><b>Do I need all three LLM providers?</b></summary>

No! You only need **one**. The bot will automatically use whichever providers you've configured. For best experience:
- **Local only**: Install Ollama (free, private, offline)
- **Best balance**: Ollama + Groq (free tier generous)
- **Maximum capability**: All three providers

</details>

<details>
<summary><b>How much does it cost to run?</b></summary>

**Infrastructure**: Free (runs on your own server)
**LLM costs**:
- Ollama: $0 (local inference)
- Groq: ~$0 (generous free tier: 14,400 requests/day)
- OpenAI: ~$0.50-2.00/day for moderate usage (GPT-4o-mini)

Most users spend **$0/month** using Ollama + Groq!

</details>

<details>
<summary><b>Is it secure?</b></summary>

Yes! Security features:
- ✅ Whitelist-based user authentication
- ✅ Rate limiting to prevent abuse
- ✅ Confirmation prompts for dangerous commands
- ✅ Full audit trail in PostgreSQL
- ✅ No credential storage in messages
- ✅ Local LLM option for privacy

Always keep your `.env` file secure and never commit it!

</details>

<details>
<summary><b>Can I run this on a VPS without GPU?</b></summary>

Absolutely! GPU monitoring is optional. The bot works perfectly on:
- Basic VPS (2GB RAM minimum)
- Raspberry Pi 4 (with lightweight Ollama models)
- Any Linux server

Just skip GPU-related commands and alerts.

</details>

<details>
<summary><b>Does it work with Windows/macOS?</b></summary>

The bot itself is cross-platform, but some features are Linux-specific:
- systemd service management (Linux only)
- GPU monitoring via nvidia-smi (NVIDIA GPUs)
- Some system metrics

For Windows, consider running in WSL2 or Docker.

</details>

<details>
<summary><b>How do I add more users?</b></summary>

Edit your `.env` file:
```bash
TELEGRAM_ALLOWED_USERS=123456789,987654321,111222333
```
Then restart the bot. Get user IDs from [@userinfobot](https://t.me/userinfobot).

</details>

---

## 📝 License

This project is licensed under the **Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0)**.

You are free to:
- **Share** — copy and redistribute the material in any medium or format
- **Adapt** — remix, transform, and build upon the material

Under the following terms:
- **Attribution** — You must give appropriate credit and indicate if changes were made
- **NonCommercial** — You may not use the material for commercial purposes

See the [LICENSE](LICENSE) file for full details or visit [creativecommons.org/licenses/by-nc/4.0](https://creativecommons.org/licenses/by-nc/4.0/)

```
Copyright (c) 2025 Emre Tasar
```

---

## 🙏 Acknowledgments

Built with these amazing open-source projects:
- [python-telegram-bot](https://python-telegram-bot.org/) - Telegram Bot API wrapper
- [Ollama](https://ollama.ai/) - Local LLM inference
- [Groq](https://groq.com/) - Fast LLM inference
- [OpenAI](https://openai.com/) - GPT models
- [Anthropic Claude](https://www.anthropic.com/) - Claude models
- [PostgreSQL](https://www.postgresql.org/) - Database
- [asyncpg](https://github.com/MagicStack/asyncpg) - Async PostgreSQL driver

Special thanks to all contributors and the open-source community!

---

## 🔗 Links

- **Documentation**: [docs/](docs/)
- **Issue Tracker**: [GitHub Issues](https://github.com/detasar/talk2yourServer/issues)
- **Discussions**: [GitHub Discussions](https://github.com/detasar/talk2yourServer/discussions)
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)

---

## 📧 Contact & Support

- **Issues**: Open an issue on GitHub
- **Discussions**: Join our community discussions
- **Author**: [Emre Tasar](https://github.com/detasar)

---

<div align="center">

**Made with ❤️ by developers, for developers**

⭐ **Star this repo** if you find it useful!

[Report Bug](https://github.com/detasar/talk2yourServer/issues) • [Request Feature](https://github.com/detasar/talk2yourServer/issues) • [Documentation](docs/)

</div>
