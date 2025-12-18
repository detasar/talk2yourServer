"""
Command Handlers

Implements all regex-based commands (no LLM needed).
"""

import time
from functools import wraps
from typing import Any, Callable, Coroutine

from telegram import Update
from telegram.ext import ContextTypes

from security import require_auth, require_admin, request_dangerous_confirmation, handle_confirm
from db import db

# Type alias for command handler functions
CommandHandler = Callable[
    [Update, ContextTypes.DEFAULT_TYPE],
    Coroutine[Any, Any, None]
]


def log_command(func: CommandHandler) -> CommandHandler:
    """Decorator to log command execution to database"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        start_time = time.time()
        user = update.effective_user

        # Get command text
        command_text = update.message.text if update.message else ""

        # Execute the command
        result = await func(update, context)

        response_time_ms = int((time.time() - start_time) * 1000)

        # Get the response (last message sent)
        # We'll capture a summary of what was done
        response_summary = f"Command executed: {func.__name__}"

        # Log to database
        await db.log_message(
            user_id=user.id,
            username=user.username,
            message_type="command",
            user_message=command_text,
            bot_response=response_summary,
            provider="system",
            response_time_ms=response_time_ms
        )

        return result
    return wrapper


from tools.system import (
    get_gpu_info, get_disk_usage, get_memory_usage, get_cpu_usage,
    get_uptime, get_network_info, get_processes, get_full_status,
    get_conda_envs, get_ollama_models, run_command,
    get_disk_percent, get_memory_percent, get_cpu_percent
)
from tools.gpu import get_gpu_temperature
from monitoring.alerting import alert_manager, Alert, AlertLevel
from monitoring.smart_alerter import smart_alerter, AlertContext, AlertType
from utils.message_coordinator import message_coordinator
from config import config
from tools.services import (
    get_all_services_status, get_service_status, start_service,
    stop_service, restart_service, get_service_logs,
    get_monitoring_status, start_monitoring, stop_monitoring
)
from tools.docker import (
    list_containers, get_container_stats, get_container_logs,
    list_images
)
from tools.screenshot import (
    capture_screenshot, generate_gpu_chart,
    generate_system_chart, generate_disk_chart
)
from llm.router import llm_router
from monitoring.scheduler import scheduler


HELP_TEXT_1 = """
🤖 *AI Server Bot - Command List (1/2)*

🎛️ *INTERACTIVE MENU*
/menu - Quick access with clickable buttons

📊 *SYSTEM INFO*
/status - Full system status
/gpu - GPU summary (usage, memory, temp)
/gpu full|processes|memory|temp
/disk - Root partition usage
/disk full|large - All disks / Top 15 dirs
/memory - RAM usage
/cpu - CPU usage and load
/uptime - System uptime
/processes - Top 10 CPU processes
/processes memory - Top 10 RAM processes
/ip - Tailscale and local IPs

🐳 *DOCKER*
/docker - Running containers
/docker all|stats|images
/logs <container> [lines]

⚙️ *SERVICE MANAGEMENT*
/services - All services status
/start|stop|restart <service>

📈 *MONITORING*
/monitoring [start|stop]
/llm status - LLM provider status

🚨 *ALERTS*
/alert - Status and thresholds
/alert on|off|test|check

🧠 *CLAUDE CODE*
/claude <msg> - Send to Claude
/claude new <msg> - New session
/claude status|cancel|reset
"""

HELP_TEXT_2 = """
🤖 *AI Server Bot - Command List (2/2)*

📸 *VISUAL METRICS*
/screenshot - Desktop screenshot
/chart gpu|system|disk

📁 *FILE OPERATIONS*
/ls [dir] - List directory
/cat <file> [lines] - View file
/download <file> - Download (max 50MB)
Send file - Upload to server

⏰ *SCHEDULED TASKS*
/schedule [enable|disable|run] <task>

🛠️ *UTILITY*
/conda - Conda environments
/ollama [pull <model>] - Models
/stats [days] - Usage statistics
/history [count] - Chat history

📧 *EMAIL*
/email - Start email wizard
/cancel - Cancel operation

⚠️ *DANGEROUS* (requires /confirm)
/reboot - Reboot system
/shutdown - Shutdown system
/kill <pid> - Kill process

🧠 *MEMORY*
/memory [category|search <keyword>]
/memory_add <cat> <key> <value>
/memory_delete <cat> <key>

📋 *SERVER LOG*
/server_log [hours|summary]

🤖 *PROACTIVE AGENT*
/proactive [on|off|test]

💡 *INSIGHTS*
/insights [stats]

💬 *NATURAL LANGUAGE*
Non-command messages go to LLM.
Fallback: Ollama → Groq → OpenAI
Add ---groq or ---openai to force provider.
"""


@require_auth
@log_command
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help message (split into 2 messages to avoid Telegram limit)"""
    await update.message.reply_text(HELP_TEXT_1, parse_mode="Markdown")
    await update.message.reply_text(HELP_TEXT_2, parse_mode="Markdown")


@require_auth
@log_command
async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ping command to check if bot is alive"""
    await update.message.reply_text("Pong! Bot is running.")


@require_auth
@log_command
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show full system status"""
    status = await get_full_status()
    await update.message.reply_text(status)


@require_auth
@log_command
async def cmd_gpu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """GPU information"""
    args = context.args
    detail = args[0] if args else "summary"

    if detail not in ["summary", "full", "processes", "memory", "temp"]:
        detail = "summary"

    info = await get_gpu_info(detail)
    await update.message.reply_text(info)


@require_auth
@log_command
async def cmd_disk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Disk usage"""
    args = context.args
    detail = args[0] if args else "summary"

    if detail not in ["summary", "full", "large"]:
        detail = "summary"

    info = await get_disk_usage(detail)
    await update.message.reply_text(info)


@require_auth
@log_command
async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Memory usage"""
    info = await get_memory_usage()
    await update.message.reply_text(info)


@require_auth
@log_command
async def cmd_cpu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """CPU usage"""
    info = await get_cpu_usage()
    await update.message.reply_text(info)


@require_auth
@log_command
async def cmd_uptime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """System uptime"""
    info = await get_uptime()
    await update.message.reply_text(info)


@require_auth
@log_command
async def cmd_processes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Top processes"""
    args = context.args
    sort_by = args[0] if args else "cpu"

    if sort_by not in ["cpu", "memory"]:
        sort_by = "cpu"

    info = await get_processes(sort_by)
    await update.message.reply_text(info)


@require_auth
@log_command
async def cmd_ip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Network information"""
    info = await get_network_info()
    await update.message.reply_text(info)


@require_auth
@log_command
async def cmd_services(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all services status"""
    status = await get_all_services_status()
    await update.message.reply_text(status)


@require_auth
@log_command
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start a service"""
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /start <service_name>")
        return

    service_name = args[0]
    success, msg = await start_service(service_name)
    await update.message.reply_text(msg)


@require_auth
@log_command
async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stop a service"""
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /stop <service_name>")
        return

    service_name = args[0]

    # Check if dangerous
    if await request_dangerous_confirmation(update, "stop", [service_name]):
        return

    success, msg = await stop_service(service_name)
    await update.message.reply_text(msg)


@require_auth
@log_command
async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Restart a service"""
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /restart <service_name>")
        return

    service_name = args[0]
    success, msg = await restart_service(service_name)
    await update.message.reply_text(msg)


@require_auth
@log_command
async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get service/container logs"""
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /logs <container> [line_count]")
        return

    container = args[0]
    lines = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50

    logs = await get_container_logs(container, lines)

    # Truncate if too long
    if len(logs) > 4000:
        logs = logs[-4000:]
        logs = "...(truncated)\n" + logs

    await update.message.reply_text(logs)


@require_auth
@log_command
async def cmd_docker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Docker commands"""
    args = context.args
    subcommand = args[0] if args else ""

    if subcommand == "all":
        info = await list_containers(all_containers=True)
    elif subcommand == "stats":
        info = await get_container_stats()
    elif subcommand == "images":
        info = await list_images()
    else:
        info = await list_containers()

    await update.message.reply_text(info)


@require_auth
@log_command
async def cmd_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Monitoring stack commands"""
    args = context.args
    subcommand = args[0] if args else ""

    if subcommand == "start":
        msg = await start_monitoring()
    elif subcommand == "stop":
        msg = await stop_monitoring()
    else:
        msg = await get_monitoring_status()

    await update.message.reply_text(msg)


@require_admin
@log_command
async def cmd_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Smart alerting control (LLM-powered)"""
    args = context.args
    subcommand = args[0] if args else "status"

    if subcommand == "on":
        config.alert_enabled = True
        if not smart_alerter.running and config.admin_users:
            from memory import memory_manager, server_logger
            smart_alerter.set_dependencies(context.bot, memory_manager, server_logger)
            smart_alerter.start()
        await update.message.reply_text("✅ Smart Alerter enabled (LLM-powered).")

    elif subcommand == "off":
        config.alert_enabled = False
        smart_alerter.stop()
        await update.message.reply_text("⛔ Smart Alerter disabled.")

    elif subcommand == "test":
        # Send a test smart alert
        await update.message.reply_text("🧪 Sending LLM-powered test alert...")
        if smart_alerter.bot:
            # Test with server_idle type to show personalized message
            success = await smart_alerter.send_smart_alert(AlertContext(
                alert_type=AlertType.SERVER_IDLE
            ))
            if success:
                await update.message.reply_text("✅ Test message sent!")
            else:
                await update.message.reply_text("❌ Failed to send test message.")
        else:
            await update.message.reply_text("⚠️ Smart Alerter has no bot connection.")

    elif subcommand == "check":
        # Run immediate check
        await update.message.reply_text("🔍 Running smart checks...")

        # Get current values
        gpu_temp = await get_gpu_temperature()
        disk_pct = await get_disk_percent()
        mem_pct = await get_memory_percent()
        cpu_pct = await get_cpu_percent()

        lines = [
            "📊 CURRENT SYSTEM STATUS",
            "=" * 30,
            "",
            f"🌡️ GPU Temp: {gpu_temp}°C (threshold: {config.alert_gpu_temp}°C) " +
                ("⚠️" if gpu_temp >= config.alert_gpu_temp else "✅"),
            f"💾 Disk: {disk_pct}% (threshold: {config.alert_disk_percent}%) " +
                ("⚠️" if disk_pct >= config.alert_disk_percent else "✅"),
            f"🧠 Memory: {mem_pct}% (threshold: {config.alert_memory_percent}%) " +
                ("⚠️" if mem_pct >= config.alert_memory_percent else "✅"),
            f"⚙️ CPU: {cpu_pct}% (threshold: {config.alert_cpu_percent}%) " +
                ("⚠️" if cpu_pct >= config.alert_cpu_percent else "✅"),
        ]

        # Run smart checks
        if config.alert_enabled and smart_alerter.running:
            await smart_alerter.check_and_alert()
            lines.append("")
            lines.append("🤖 Smart Alerter checks completed.")

        await update.message.reply_text("\n".join(lines))

    else:  # status
        status_emoji = "🟢" if smart_alerter.running else "🔴"
        enabled_emoji = "✅" if config.alert_enabled else "⛔"

        lines = [
            "🤖 SMART ALERTER (LLM-Powered)",
            "=" * 30,
            "",
            f"Status: {status_emoji} {'Running' if smart_alerter.running else 'Stopped'}",
            f"Active: {enabled_emoji} {'Yes' if config.alert_enabled else 'No'}",
            "",
            "✨ FEATURES",
            "  • LLM-powered personalized messages",
            "  • Uses user memory",
            "  • Context-aware suggestions",
            "",
            "📏 THRESHOLD VALUES",
            f"  GPU Temperature: {config.alert_gpu_temp}°C",
            f"  Disk Usage: {config.alert_disk_percent}%",
            f"  Memory Usage: {config.alert_memory_percent}%",
            "",
            "⏱️ TIMINGS",
            f"  Check Interval: {smart_alerter.check_interval}s",
            f"  Cooldown: {smart_alerter.cooldown_minutes}min",
            "",
            "🔍 MONITORED SERVICES",
            f"  {', '.join(config.critical_services) if config.critical_services else 'None'}",
            "",
            "📊 ACTIVE ISSUES",
        ]

        if smart_alerter._active_issues:
            for key, is_active in smart_alerter._active_issues.items():
                if is_active:
                    lines.append(f"  ⚠️ {key}")
        else:
            lines.append("  None - Everything OK!")

        # Add coordinator status
        coord_status = message_coordinator.get_status()
        lines.extend([
            "",
            "📬 MESSAGE COORDINATOR",
            f"  Today's messages: {coord_status['daily_count']}/{coord_status['daily_limit']}",
            f"  Last hour: {coord_status['messages_last_hour']} messages",
            f"  Quiet hours: {'🌙 Active' if coord_status['quiet_hours'] else '☀️ Inactive'} ({coord_status['quiet_hours_window']})",
        ])

        if coord_status['recent_messages']:
            lines.append("  Recent messages:")
            for msg in coord_status['recent_messages'][:3]:
                lines.append(f"    • {msg['source']}/{msg['type']} ({msg['minutes_ago']}min ago)")

        await update.message.reply_text("\n".join(lines))


@require_auth
@log_command
async def cmd_conda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List conda environments"""
    info = await get_conda_envs()
    await update.message.reply_text(info)


@require_auth
@log_command
async def cmd_ollama(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ollama commands"""
    args = context.args
    subcommand = args[0] if args else "models"

    if subcommand == "models" or subcommand == "list":
        info = await get_ollama_models()
    elif subcommand == "pull" and len(args) > 1:
        model = args[1]
        output, _ = await run_command(f"ollama pull {model}")
        info = f"Downloading model: {model}\n{output}"
    else:
        info = await get_ollama_models()

    await update.message.reply_text(info)


@require_auth
@log_command
async def cmd_llm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """LLM status command"""
    args = context.args
    subcommand = args[0] if args else "status"

    if subcommand == "status":
        status = await llm_router.get_provider_status()
        await update.message.reply_text(status)
    else:
        await update.message.reply_text("Usage: /llm status")


@require_auth
@log_command
async def cmd_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Confirm dangerous command"""
    result = await handle_confirm(update, context)
    if result:
        command, args = result
        # Execute the confirmed command
        if command == "reboot":
            await update.message.reply_text("Rebooting system...")
            await run_command("sudo reboot")
        elif command == "shutdown":
            await update.message.reply_text("Shutting down system...")
            await run_command("sudo shutdown now")
        elif command == "kill":
            if args:
                pid = args[0]
                output, code = await run_command(f"kill {pid}")
                await update.message.reply_text(f"Process {pid} terminated" if code == 0 else f"Error: {output}")
        elif command == "stop":
            if args:
                service = args[0]
                success, msg = await stop_service(service)
                await update.message.reply_text(msg)


@require_admin
@log_command
async def cmd_reboot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reboot system (requires confirmation)"""
    if await request_dangerous_confirmation(update, "reboot", []):
        return


@require_admin
@log_command
async def cmd_shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shutdown system (requires confirmation)"""
    if await request_dangerous_confirmation(update, "shutdown", []):
        return


@require_admin
@log_command
async def cmd_kill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kill process (requires confirmation)"""
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /kill <pid>")
        return

    pid = args[0]
    if await request_dangerous_confirmation(update, "kill", [pid]):
        return


@require_auth
@log_command
async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recent chat history"""
    args = context.args
    limit = 10  # Default

    if args and args[0].isdigit():
        limit = min(int(args[0]), 50)  # Max 50

    user_id = update.effective_user.id
    messages = await db.get_chat_history(user_id, limit)
    total_count = await db.get_message_count(user_id)

    if not messages:
        await update.message.reply_text("No chat history yet.")
        return

    lines = [
        f"📜 CHAT HISTORY (Last {len(messages)}/{total_count})",
        "=" * 35,
        ""
    ]

    # Reverse to show oldest first
    for msg in reversed(messages):
        timestamp = msg.get('created_at')
        time_str = timestamp.strftime("%d/%m %H:%M") if timestamp else ""
        msg_type = msg.get('message_type', '')
        provider = msg.get('provider', '')
        response_ms = msg.get('response_time_ms')

        # Type icon
        if msg_type == 'command':
            icon = "⚡"
        elif msg_type == 'claude':
            icon = "🧠"
        else:
            icon = "💬"

        # User message (truncate)
        user_msg = msg.get('user_message', '')[:80]
        if len(msg.get('user_message', '')) > 80:
            user_msg += "..."

        lines.append(f"{icon} [{time_str}] {user_msg}")

        # Bot response preview
        bot_resp = msg.get('bot_response', '')
        if bot_resp and not bot_resp.startswith("ERROR"):
            preview = bot_resp[:60].replace('\n', ' ')
            if len(bot_resp) > 60:
                preview += "..."
            provider_info = f" [{provider}]" if provider else ""
            time_info = f" {response_ms}ms" if response_ms else ""
            lines.append(f"   → {preview}{provider_info}{time_info}")

        lines.append("")

    # Truncate if too long
    result = "\n".join(lines)
    if len(result) > 4000:
        result = result[:3900] + "\n\n...(truncated)"

    await update.message.reply_text(result)


@require_auth
@log_command
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show usage statistics"""
    args = context.args
    days = 7  # Default

    if args and args[0].isdigit():
        days = int(args[0])

    user_id = update.effective_user.id
    stats = await db.get_user_stats(user_id, days)

    if not stats:
        await update.message.reply_text("Unable to retrieve statistics. Database connection may be down.")
        return

    lines = [
        f"📊 USAGE STATISTICS (Last {days} days)",
        "=" * 35,
        ""
    ]

    # Message counts
    if stats.get("messages"):
        lines.append("📨 Message Counts:")
        for msg_type, count in stats["messages"].items():
            lines.append(f"  {msg_type}: {count}")
        lines.append("")

    # Provider usage
    if stats.get("providers"):
        lines.append("🤖 LLM Usage:")
        for provider, data in stats["providers"].items():
            lines.append(f"  {provider}:")
            lines.append(f"    Requests: {data['requests']}")
            if data['tokens']:
                lines.append(f"    Tokens: {data['tokens']}")
            if data['cost'] > 0:
                lines.append(f"    Cost: ${data['cost']:.4f}")
        lines.append("")

    # Claude stats
    if stats.get("claude") and stats["claude"]["sessions"]:
        lines.append("🧠 Claude Code:")
        lines.append(f"  Sessions: {stats['claude']['sessions']}")
        lines.append(f"  Messages: {stats['claude']['messages']}")
        if stats['claude']['cost'] > 0:
            lines.append(f"  Cost: ${stats['claude']['cost']:.4f}")

    await update.message.reply_text("\n".join(lines))


@require_auth
@log_command
async def cmd_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Capture and send desktop screenshot"""
    await update.message.reply_text("📸 Capturing screenshot...")

    image_data = await capture_screenshot()

    if image_data:
        await update.message.reply_photo(
            photo=image_data,
            caption="🖥️ Desktop Screenshot"
        )
    else:
        await update.message.reply_text(
            "❌ Failed to capture screenshot.\n"
            "Display not found or scrot/imagemagick not installed."
        )


@require_auth
@log_command
async def cmd_chart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate and send metric charts"""
    args = context.args
    chart_type = args[0] if args else "system"

    await update.message.reply_text(f"📊 Generating {chart_type.upper()} chart...")

    image_data = None

    if chart_type == "gpu":
        image_data = await generate_gpu_chart()
        caption = "🎮 GPU Metrics"
    elif chart_type == "system":
        image_data = await generate_system_chart()
        caption = "🖥️ System Overview"
    elif chart_type == "disk":
        image_data = await generate_disk_chart()
        caption = "💾 Disk Usage"
    else:
        await update.message.reply_text(
            "Usage: /chart <gpu|system|disk>\n"
            "Example: /chart gpu"
        )
        return

    if image_data:
        await update.message.reply_photo(
            photo=image_data,
            caption=caption
        )
    else:
        await update.message.reply_text(
            "❌ Failed to generate chart.\n"
            "matplotlib may not be installed or an error occurred."
        )


@require_admin
@log_command
async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manage scheduled tasks"""
    args = context.args
    subcommand = args[0] if args else "list"

    if subcommand == "list" or not args:
        status = scheduler.get_tasks_status()
        await update.message.reply_text(status, parse_mode="Markdown")

    elif subcommand == "enable" and len(args) > 1:
        task_name = args[1]
        if scheduler.enable_task(task_name):
            await update.message.reply_text(f"✅ Task enabled: {task_name}")
        else:
            await update.message.reply_text(f"❌ Task not found: {task_name}")

    elif subcommand == "disable" and len(args) > 1:
        task_name = args[1]
        if scheduler.disable_task(task_name):
            await update.message.reply_text(f"⛔ Task disabled: {task_name}")
        else:
            await update.message.reply_text(f"❌ Task not found: {task_name}")

    elif subcommand == "run" and len(args) > 1:
        task_name = args[1]
        await update.message.reply_text(f"🔄 Running task: {task_name}")
        if await scheduler.run_task(task_name):
            await update.message.reply_text(f"✅ Task completed: {task_name}")
        else:
            await update.message.reply_text(f"❌ Failed to run task: {task_name}")

    else:
        await update.message.reply_text(
            "Usage:\n"
            "/schedule - List tasks\n"
            "/schedule enable <task> - Enable\n"
            "/schedule disable <task> - Disable\n"
            "/schedule run <task> - Run now"
        )
