"""
Talk2YourServer - Configuration Management

Loads settings from environment variables.
All sensitive data should be in .env file (not committed to git).
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
# First try project directory, then home directory
env_paths = [
    Path(__file__).parent.parent / ".env",  # Project root
    Path.home() / ".env",                    # Home directory
]

for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        break


@dataclass
class BotConfig:
    """Bot configuration loaded from environment variables"""

    # Telegram Settings
    telegram_token: str = ""
    allowed_users: list[int] = field(default_factory=list)
    admin_users: list[int] = field(default_factory=list)

    # API Keys for LLM Providers
    groq_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""  # For direct Anthropic API (optional)

    # Database Configuration
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "talk2server"
    db_user: str = ""
    db_password: str = ""

    # Service URLs
    ollama_url: str = "http://localhost:11434"
    prometheus_url: str = "http://localhost:9090"

    # Rate Limiting
    rate_limit: int = 60  # requests per window
    rate_window: int = 60  # seconds

    # LLM Settings
    default_ollama_model: str = "llama3.2:3b"
    default_claude_model: str = "opus"  # sonnet, opus, haiku
    groq_models: list[str] = field(default_factory=lambda: [
        # Production Models
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        # Preview Models
        "llama-3.2-90b-text-preview",
        "mixtral-8x7b-32768",
    ])
    openai_model: str = "gpt-4o-mini"

    # Message Settings
    max_message_length: int = 4096

    # Paths (relative to home directory by default)
    working_dir: str = ""  # Set in from_env()
    log_dir: str = ""      # Set in from_env()
    workspace_dir: str = ""  # Claude Code workspace

    # Alert Thresholds
    alert_gpu_temp: int = 80          # Celsius
    alert_gpu_memory_percent: int = 95  # %
    alert_disk_percent: int = 90      # %
    alert_memory_percent: int = 90    # %
    alert_cpu_percent: int = 95       # %

    # Alert Settings
    alert_check_interval: int = 60    # seconds between checks
    alert_cooldown: int = 300         # seconds before re-alerting same issue
    alert_enabled: bool = True        # master switch for alerts

    # Health Check Settings
    health_check_port: int = 8765     # HTTP health check port

    # Critical Services to Monitor
    critical_services: list[str] = field(default_factory=lambda: [
        "postgresql"
    ])

    # Email Settings (optional)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notification_email: str = ""

    @classmethod
    def from_env(cls) -> "BotConfig":
        """Load configuration from environment variables"""

        # Parse allowed users (comma-separated list of IDs)
        allowed_users_str = os.getenv("TELEGRAM_ALLOWED_USERS", "")
        allowed_users = [
            int(uid.strip())
            for uid in allowed_users_str.split(",")
            if uid.strip().isdigit()
        ]

        # Parse admin users
        admin_users_str = os.getenv("TELEGRAM_ADMIN_USERS", "")
        admin_users = [
            int(uid.strip())
            for uid in admin_users_str.split(",")
            if uid.strip().isdigit()
        ]

        # Parse critical services
        critical_services_str = os.getenv("CRITICAL_SERVICES", "postgresql")
        critical_services = [
            s.strip()
            for s in critical_services_str.split(",")
            if s.strip()
        ]

        # Set up paths
        home = Path.home()
        project_dir = Path(__file__).parent.parent

        return cls(
            # Telegram
            telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            allowed_users=allowed_users,
            admin_users=admin_users,

            # API Keys
            groq_api_key=os.getenv("GROQ_API_KEY", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),

            # Database
            db_host=os.getenv("POSTGRES_HOST", "localhost"),
            db_port=int(os.getenv("POSTGRES_PORT", "5432")),
            db_name=os.getenv("POSTGRES_DB", "talk2server"),
            db_user=os.getenv("POSTGRES_USER", ""),
            db_password=os.getenv("POSTGRES_PASSWORD", ""),

            # Service URLs
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
            prometheus_url=os.getenv("PROMETHEUS_URL", "http://localhost:9090"),

            # Rate Limiting
            rate_limit=int(os.getenv("RATE_LIMIT", "60")),
            rate_window=int(os.getenv("RATE_WINDOW", "60")),

            # LLM Settings
            default_ollama_model=os.getenv("DEFAULT_OLLAMA_MODEL", "llama3.2:3b"),
            default_claude_model=os.getenv("DEFAULT_CLAUDE_MODEL", "opus"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),

            # Paths
            working_dir=os.getenv("WORKING_DIR", str(home)),
            log_dir=os.getenv("LOG_DIR", str(project_dir / "logs")),
            workspace_dir=os.getenv("WORKSPACE_DIR", str(home / "claude_workspace")),

            # Alerts
            alert_gpu_temp=int(os.getenv("ALERT_GPU_TEMP", "80")),
            alert_gpu_memory_percent=int(os.getenv("ALERT_GPU_MEMORY", "95")),
            alert_disk_percent=int(os.getenv("ALERT_DISK", "90")),
            alert_memory_percent=int(os.getenv("ALERT_MEMORY", "90")),
            alert_cpu_percent=int(os.getenv("ALERT_CPU", "95")),
            alert_check_interval=int(os.getenv("ALERT_CHECK_INTERVAL", "60")),
            alert_cooldown=int(os.getenv("ALERT_COOLDOWN", "300")),
            alert_enabled=os.getenv("ALERT_ENABLED", "true").lower() == "true",

            # Health Check
            health_check_port=int(os.getenv("HEALTH_CHECK_PORT", "8765")),

            # Critical Services
            critical_services=critical_services,

            # Email
            smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            notification_email=os.getenv("NOTIFICATION_EMAIL", ""),
        )

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors"""
        errors = []

        if not self.telegram_token:
            errors.append("TELEGRAM_BOT_TOKEN is not set")

        if not self.allowed_users:
            errors.append("TELEGRAM_ALLOWED_USERS is not set (no users will have access)")

        # API keys are optional - we use fallback chain
        # But warn if none are set
        if not any([self.groq_api_key, self.openai_api_key]):
            errors.append("WARNING: No cloud LLM API keys set. Only local Ollama will be available.")

        return errors

    def get_llm_status(self) -> dict:
        """Get status of configured LLM providers"""
        return {
            "ollama": bool(self.ollama_url),
            "groq": bool(self.groq_api_key),
            "openai": bool(self.openai_api_key),
            "anthropic": bool(self.anthropic_api_key),
        }


# Global config instance
config = BotConfig.from_env()


# Service definitions for management
MANAGED_SERVICES = {
    # Systemd services
    "ollama": {"type": "systemd", "name": "ollama"},
    "postgresql": {"type": "systemd", "name": "postgresql"},
    "docker": {"type": "systemd", "name": "docker"},

    # Docker containers (add your own)
    # "my-app": {"type": "docker", "name": "my-app-container"},
}

# Dangerous commands that require confirmation
DANGEROUS_COMMANDS = {
    "reboot": "System will be rebooted",
    "shutdown": "System will be shut down",
    "kill": "Process will be terminated",
    "rm": "File will be deleted",
}

# LLM Provider priority for fallback
LLM_FALLBACK_ORDER = ["ollama", "groq", "openai"]
