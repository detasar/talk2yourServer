"""
Inline Keyboard Handlers

Provides interactive buttons for common actions.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from security import require_auth
from tools.services import (
    get_all_services_status, start_service, stop_service, restart_service
)
from tools.system import get_gpu_info, get_disk_usage, get_memory_usage
from tools.docker import list_containers
from config import MANAGED_SERVICES

logger = logging.getLogger(__name__)


# Callback data prefixes
CB_SERVICE = "srv"
CB_QUICK = "quick"
CB_CONFIRM = "cfm"
CB_CANCEL = "cancel"


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Get the main menu inline keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("📊 System", callback_data=f"{CB_QUICK}:status"),
            InlineKeyboardButton("🎮 GPU", callback_data=f"{CB_QUICK}:gpu"),
        ],
        [
            InlineKeyboardButton("💾 Disk", callback_data=f"{CB_QUICK}:disk"),
            InlineKeyboardButton("🧠 Memory", callback_data=f"{CB_QUICK}:memory"),
        ],
        [
            InlineKeyboardButton("⚙️ Services", callback_data=f"{CB_QUICK}:services"),
            InlineKeyboardButton("🐳 Docker", callback_data=f"{CB_QUICK}:docker"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_services_keyboard() -> InlineKeyboardMarkup:
    """Get the services management keyboard"""
    keyboard = []

    # Group services into rows of 2
    services = list(MANAGED_SERVICES.keys())
    for i in range(0, len(services), 2):
        row = []
        for service in services[i:i+2]:
            row.append(InlineKeyboardButton(
                f"⚙️ {service}",
                callback_data=f"{CB_SERVICE}:show:{service}"
            ))
        keyboard.append(row)

    # Back button
    keyboard.append([
        InlineKeyboardButton("⬅️ Back", callback_data=f"{CB_QUICK}:menu")
    ])

    return InlineKeyboardMarkup(keyboard)


def get_service_actions_keyboard(service_name: str) -> InlineKeyboardMarkup:
    """Get action buttons for a specific service"""
    keyboard = [
        [
            InlineKeyboardButton("▶️ Start", callback_data=f"{CB_SERVICE}:start:{service_name}"),
            InlineKeyboardButton("⏹️ Stop", callback_data=f"{CB_SERVICE}:stop:{service_name}"),
            InlineKeyboardButton("🔄 Restart", callback_data=f"{CB_SERVICE}:restart:{service_name}"),
        ],
        [
            InlineKeyboardButton("📋 Logs", callback_data=f"{CB_SERVICE}:logs:{service_name}"),
            InlineKeyboardButton("⬅️ Back", callback_data=f"{CB_QUICK}:services"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_confirm_keyboard(action: str, data: str) -> InlineKeyboardMarkup:
    """Get confirmation buttons"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm", callback_data=f"{CB_CONFIRM}:yes:{action}:{data}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"{CB_CANCEL}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


@require_auth
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button presses"""
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    data = query.data
    parts = data.split(":")

    if len(parts) < 2:
        return

    category = parts[0]
    action = parts[1]

    try:
        if category == CB_QUICK:
            await handle_quick_action(query, action)

        elif category == CB_SERVICE:
            service = parts[2] if len(parts) > 2 else None
            await handle_service_action(query, action, service)

        elif category == CB_CONFIRM:
            if action == "yes" and len(parts) >= 4:
                confirmed_action = parts[2]
                confirmed_data = parts[3]
                await handle_confirmed_action(query, confirmed_action, confirmed_data)

        elif category == CB_CANCEL:
            await query.edit_message_text("❌ Operation cancelled.")

    except Exception as e:
        logger.error(f"Callback query error: {e}")
        await query.edit_message_text(f"Error: {str(e)}")


async def handle_quick_action(query, action: str) -> None:
    """Handle quick action buttons"""
    if action == "menu":
        await query.edit_message_text(
            "🤖 AI Server Bot - Quick Access",
            reply_markup=get_main_menu_keyboard()
        )

    elif action == "status":
        from tools.system import get_full_status
        status = await get_full_status()
        await query.edit_message_text(
            status,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Refresh", callback_data=f"{CB_QUICK}:status"),
                InlineKeyboardButton("⬅️ Back", callback_data=f"{CB_QUICK}:menu"),
            ]])
        )

    elif action == "gpu":
        info = await get_gpu_info("summary")
        await query.edit_message_text(
            info,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📊 Full", callback_data=f"{CB_QUICK}:gpu_full"),
                    InlineKeyboardButton("📈 Procs", callback_data=f"{CB_QUICK}:gpu_procs"),
                ],
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data=f"{CB_QUICK}:gpu"),
                    InlineKeyboardButton("⬅️ Back", callback_data=f"{CB_QUICK}:menu"),
                ],
            ])
        )

    elif action == "gpu_full":
        info = await get_gpu_info("full")
        # Truncate if too long
        if len(info) > 4000:
            info = info[:3900] + "\n...(truncated)"
        await query.edit_message_text(
            f"```\n{info}\n```",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data=f"{CB_QUICK}:gpu"),
            ]])
        )

    elif action == "gpu_procs":
        info = await get_gpu_info("processes")
        await query.edit_message_text(
            info,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data=f"{CB_QUICK}:gpu"),
            ]])
        )

    elif action == "disk":
        info = await get_disk_usage("summary")
        await query.edit_message_text(
            info,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📁 Full", callback_data=f"{CB_QUICK}:disk_full"),
                    InlineKeyboardButton("📊 Large", callback_data=f"{CB_QUICK}:disk_large"),
                ],
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data=f"{CB_QUICK}:disk"),
                    InlineKeyboardButton("⬅️ Back", callback_data=f"{CB_QUICK}:menu"),
                ],
            ])
        )

    elif action == "disk_full":
        info = await get_disk_usage("full")
        await query.edit_message_text(
            f"```\n{info}\n```",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data=f"{CB_QUICK}:disk"),
            ]])
        )

    elif action == "disk_large":
        info = await get_disk_usage("large")
        if len(info) > 4000:
            info = info[:3900] + "\n...(truncated)"
        await query.edit_message_text(
            info,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data=f"{CB_QUICK}:disk"),
            ]])
        )

    elif action == "memory":
        info = await get_memory_usage()
        await query.edit_message_text(
            f"```\n{info}\n```",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Refresh", callback_data=f"{CB_QUICK}:memory"),
                InlineKeyboardButton("⬅️ Back", callback_data=f"{CB_QUICK}:menu"),
            ]])
        )

    elif action == "services":
        status = await get_all_services_status()
        await query.edit_message_text(
            status,
            reply_markup=get_services_keyboard()
        )

    elif action == "docker":
        info = await list_containers()
        await query.edit_message_text(
            info,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📦 All", callback_data=f"{CB_QUICK}:docker_all"),
                    InlineKeyboardButton("📊 Stats", callback_data=f"{CB_QUICK}:docker_stats"),
                ],
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data=f"{CB_QUICK}:docker"),
                    InlineKeyboardButton("⬅️ Back", callback_data=f"{CB_QUICK}:menu"),
                ],
            ])
        )

    elif action == "docker_all":
        info = await list_containers(all_containers=True)
        await query.edit_message_text(
            info,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data=f"{CB_QUICK}:docker"),
            ]])
        )

    elif action == "docker_stats":
        from tools.docker import get_container_stats
        info = await get_container_stats()
        if len(info) > 4000:
            info = info[:3900] + "\n...(truncated)"
        await query.edit_message_text(
            f"```\n{info}\n```",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data=f"{CB_QUICK}:docker"),
            ]])
        )


async def handle_service_action(query, action: str, service: str) -> None:
    """Handle service management actions"""
    if action == "show":
        # Show service details with action buttons
        from tools.services import get_service_status
        status, is_running = await get_service_status(service)
        status_emoji = "🟢" if is_running else "🔴"

        await query.edit_message_text(
            f"{status_emoji} **{service}**\n\n{status}",
            parse_mode="Markdown",
            reply_markup=get_service_actions_keyboard(service)
        )

    elif action == "start":
        success, msg = await start_service(service)
        status_emoji = "✅" if success else "❌"
        await query.edit_message_text(
            f"{status_emoji} {msg}",
            reply_markup=get_service_actions_keyboard(service)
        )

    elif action == "stop":
        # Request confirmation for stop
        await query.edit_message_text(
            f"⚠️ **{service}** - Are you sure you want to stop this service?",
            parse_mode="Markdown",
            reply_markup=get_confirm_keyboard("stop_service", service)
        )

    elif action == "restart":
        success, msg = await restart_service(service)
        status_emoji = "✅" if success else "❌"
        await query.edit_message_text(
            f"{status_emoji} {msg}",
            reply_markup=get_service_actions_keyboard(service)
        )

    elif action == "logs":
        from tools.docker import get_container_logs
        logs = await get_container_logs(service, lines=30)
        if len(logs) > 4000:
            logs = logs[-3900:]
            logs = "...(truncated)\n" + logs
        await query.edit_message_text(
            f"📋 **{service}** Logs:\n```\n{logs}\n```",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data=f"{CB_SERVICE}:show:{service}"),
            ]])
        )


async def handle_confirmed_action(query, action: str, data: str) -> None:
    """Handle confirmed dangerous actions"""
    if action == "stop_service":
        success, msg = await stop_service(data)
        status_emoji = "✅" if success else "❌"
        await query.edit_message_text(
            f"{status_emoji} {msg}",
            reply_markup=get_service_actions_keyboard(data)
        )


@require_auth
async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the main menu with inline keyboard"""
    await update.message.reply_text(
        "🤖 AI Server Bot - Quick Access\n\nSelect a category:",
        reply_markup=get_main_menu_keyboard()
    )


# Callback query handler for bot registration
callback_handler = CallbackQueryHandler(handle_callback_query)
