#!/usr/bin/env python3
"""
Talk2YourServer - Telegram Bot

A comprehensive Telegram bot for managing your Linux server.
Features:
- System monitoring (GPU, disk, memory, CPU)
- Service management (Docker, systemd)
- LLM integration with fallback chain (Ollama -> Groq -> OpenAI)
- Claude Code integration
- Natural language queries
- Smart alerts and proactive messaging

Usage:
    python bot.py
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

# Add the src directory to path for absolute imports
sys.path.insert(0, str(Path(__file__).parent))

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from logging.handlers import RotatingFileHandler

from config import config
from db import db
from monitoring.alerting import alert_manager
from monitoring.smart_alerter import smart_alerter
from monitoring.health import health_checker
from memory import (
    memory_manager, server_logger, proactive_agent, conversation_analyzer
)
from memory.seed_data import check_and_load_seed_data
from handlers.commands import (
    cmd_help, cmd_ping, cmd_status, cmd_gpu, cmd_disk,
    cmd_memory, cmd_cpu, cmd_uptime, cmd_processes, cmd_ip,
    cmd_services, cmd_start_service, cmd_stop_service, cmd_restart_service, cmd_logs,
    cmd_docker, cmd_monitoring, cmd_conda, cmd_ollama, cmd_llm,
    cmd_confirm, cmd_reboot, cmd_shutdown, cmd_kill, cmd_stats,
    cmd_history, cmd_alert, cmd_screenshot, cmd_chart, cmd_schedule
)
from handlers.memory_cmd import (
    cmd_memory_view, cmd_memory_add, cmd_memory_del,
    cmd_server_log, cmd_proactive, cmd_insights
)
from monitoring.scheduler import scheduler
from handlers.claude import handle_claude_command
from handlers.llm import handle_message
from handlers.email import email_conversation_handler
from handlers.keyboard import callback_handler, cmd_menu
from handlers.files import cmd_download, cmd_ls, cmd_cat, file_upload_handler
from utils.watchdog import watchdog

# Configure logging with rotation
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / 'bot.log'
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per file
LOG_BACKUP_COUNT = 3  # Keep 3 backup files

# Set up root logger
logging.basicConfig(
    format=LOG_FORMAT,
    level=logging.INFO
)

# Add rotating file handler
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=LOG_MAX_BYTES,
    backupCount=LOG_BACKUP_COUNT,
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
logging.getLogger().addHandler(file_handler)

logger = logging.getLogger(__name__)


def setup_handlers(app: Application) -> None:
    """Register all command and message handlers"""

    # Help and status
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))  # Telegram start
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("status", cmd_status))

    # System info
    app.add_handler(CommandHandler("gpu", cmd_gpu))
    app.add_handler(CommandHandler("disk", cmd_disk))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("ram", cmd_memory))  # Alias
    app.add_handler(CommandHandler("cpu", cmd_cpu))
    app.add_handler(CommandHandler("uptime", cmd_uptime))
    app.add_handler(CommandHandler("processes", cmd_processes))
    app.add_handler(CommandHandler("ps", cmd_processes))  # Alias
    app.add_handler(CommandHandler("ip", cmd_ip))

    # Services
    app.add_handler(CommandHandler("services", cmd_services))
    app.add_handler(CommandHandler("startservice", cmd_start_service))
    app.add_handler(CommandHandler("stopservice", cmd_stop_service))
    app.add_handler(CommandHandler("restart", cmd_restart_service))
    app.add_handler(CommandHandler("logs", cmd_logs))

    # Docker
    app.add_handler(CommandHandler("docker", cmd_docker))

    # Monitoring
    app.add_handler(CommandHandler("monitoring", cmd_monitoring))
    app.add_handler(CommandHandler("llm", cmd_llm))

    # Alerting
    app.add_handler(CommandHandler("alert", cmd_alert))
    app.add_handler(CommandHandler("alerts", cmd_alert))  # Alias

    # Interactive menu
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(callback_handler)

    # Visual / Charts
    app.add_handler(CommandHandler("screenshot", cmd_screenshot))
    app.add_handler(CommandHandler("chart", cmd_chart))

    # File operations
    app.add_handler(CommandHandler("download", cmd_download))
    app.add_handler(CommandHandler("ls", cmd_ls))
    app.add_handler(CommandHandler("cat", cmd_cat))

    # Scheduling
    app.add_handler(CommandHandler("schedule", cmd_schedule))

    # Memory System
    app.add_handler(CommandHandler("memory_view", cmd_memory_view))
    app.add_handler(CommandHandler("memory_add", cmd_memory_add))
    app.add_handler(CommandHandler("memory_del", cmd_memory_del))
    app.add_handler(CommandHandler("server_log", cmd_server_log))
    app.add_handler(CommandHandler("proactive", cmd_proactive))
    app.add_handler(CommandHandler("insights", cmd_insights))

    # Utility
    app.add_handler(CommandHandler("conda", cmd_conda))
    app.add_handler(CommandHandler("ollama", cmd_ollama))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("history", cmd_history))

    # Claude Code
    app.add_handler(CommandHandler("claude", handle_claude_command))
    app.add_handler(CommandHandler("c", handle_claude_command))  # Short alias

    # Dangerous commands (require confirmation)
    app.add_handler(CommandHandler("confirm", cmd_confirm))
    app.add_handler(CommandHandler("reboot", cmd_reboot))
    app.add_handler(CommandHandler("shutdown", cmd_shutdown))
    app.add_handler(CommandHandler("kill", cmd_kill))

    # Email conversation handler (must be before catch-all)
    app.add_handler(email_conversation_handler)

    # File uploads (before catch-all)
    app.add_handler(file_upload_handler)

    # Natural language messages (catch-all)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))


async def error_handler(update: Update, context) -> None:
    """Handle errors gracefully"""
    logger.error(f"Exception while handling an update: {context.error}")

    if update and update.effective_message:
        await update.effective_message.reply_text(
            f"An error occurred: {str(context.error)}"
        )


async def post_init(app: Application) -> None:
    """Post-initialization hook - setup all components"""
    logger.info("Bot initialized successfully")

    # Connect to database
    if await db.connect():
        logger.info("Database connected successfully")

        # Initialize Memory System (requires database)
        try:
            # Initialize Memory Manager
            if await memory_manager.initialize(db.pool):
                logger.info("Memory Manager initialized")

                # Load seed data if needed
                seed_loaded = await check_and_load_seed_data(memory_manager)
                if seed_loaded:
                    logger.info("Seed data loaded into memory")

            # Initialize Server Logger
            if await server_logger.initialize(db.pool):
                logger.info("Server Logger initialized")
                server_logger.log(
                    event_type='service_event',
                    event_subtype='bot_start',
                    description='Telegram bot started',
                    importance='notable',
                    source='telegram_bot'
                )

            # Initialize Conversation Analyzer
            if await conversation_analyzer.initialize(db.pool, memory_manager):
                logger.info("Conversation Analyzer initialized")

            # Initialize Proactive Agent
            if await proactive_agent.initialize(app.bot, memory_manager, server_logger):
                proactive_agent.start()
                logger.info("Proactive Agent started")

        except Exception as e:
            logger.error(f"Error initializing memory system: {e}")
    else:
        logger.warning("Database connection failed - memory system disabled")

    # Validate config
    errors = config.validate()
    if errors:
        for error in errors:
            logger.warning(f"Config warning: {error}")

    # Setup Smart Alerter (LLM-powered alerts)
    if config.alert_enabled and config.admin_users:
        smart_alerter.set_dependencies(app.bot, memory_manager, server_logger)
        smart_alerter.start()
        logger.info(f"Smart Alerter started (check interval: {smart_alerter.check_interval}s)")
    else:
        logger.info("Smart Alerter disabled (no admin users or alerts disabled)")

    # Start systemd watchdog (if running as service)
    if watchdog.start():
        watchdog.notify_ready()
        watchdog.notify_status("Bot running, accepting messages")

    # Start health check HTTP server
    await health_checker.start()

    # Start task scheduler
    if config.admin_users:
        scheduler.set_bot(app.bot)
        scheduler.start()
        logger.info("Task scheduler started")


async def post_shutdown(app: Application) -> None:
    """Graceful shutdown hook - cleanup all resources"""
    logger.info("Shutting down bot...")

    # Notify systemd we're stopping
    watchdog.notify_stopping()
    watchdog.stop()

    # Log shutdown event
    try:
        server_logger.log(
            event_type='service_event',
            event_subtype='bot_stop',
            description='Telegram bot shutting down',
            importance='notable',
            source='telegram_bot'
        )
    except:
        pass

    # Stop Proactive Agent
    try:
        proactive_agent.stop()
        logger.info("Proactive Agent stopped")
    except Exception as e:
        logger.warning(f"Error stopping proactive agent: {e}")

    # Stop Conversation Analyzer
    try:
        await conversation_analyzer.stop()
        logger.info("Conversation Analyzer stopped")
    except Exception as e:
        logger.warning(f"Error stopping conversation analyzer: {e}")

    # Stop Server Logger (flushes remaining events)
    try:
        await server_logger.stop()
        logger.info("Server Logger stopped")
    except Exception as e:
        logger.warning(f"Error stopping server logger: {e}")

    # Stop Smart Alerter
    try:
        smart_alerter.stop()
        logger.info("Smart Alerter stopped")
    except Exception as e:
        logger.warning(f"Error stopping smart alerter: {e}")

    # Stop health check server
    try:
        await health_checker.stop()
    except Exception as e:
        logger.warning(f"Error stopping health checker: {e}")

    # Stop task scheduler
    try:
        scheduler.stop()
    except Exception as e:
        logger.warning(f"Error stopping scheduler: {e}")

    # Cancel any running Claude processes
    try:
        from handlers.claude import claude_runner
        if claude_runner.is_running:
            await claude_runner.cancel()
            logger.info("Claude process cancelled")
    except Exception as e:
        logger.warning(f"Error cancelling Claude process: {e}")

    # Close database connection
    try:
        await db.close()
        logger.info("Database connection closed")
    except Exception as e:
        logger.warning(f"Error closing database: {e}")

    logger.info("Bot shutdown complete")


def main():
    """Main entry point"""

    # Check token
    if not config.telegram_token:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set!")
        print("Please add TELEGRAM_BOT_TOKEN to your .env file.")
        sys.exit(1)

    # Check allowed users
    if not config.allowed_users:
        print("WARNING: No allowed users configured. Bot will deny all requests.")
        print("Add TELEGRAM_ALLOWED_USERS to your .env file.")

    # Create application
    app = (
        Application.builder()
        .token(config.telegram_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Setup handlers
    setup_handlers(app)

    # Add error handler
    app.add_error_handler(error_handler)

    # Start bot
    logger.info("Starting Talk2YourServer Telegram Bot...")
    logger.info(f"Allowed users: {config.allowed_users}")
    logger.info(f"Admin users: {config.admin_users}")

    # Run with polling
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
