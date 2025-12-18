"""
Handlers Module

Exports all handler functions for the Telegram bot.
"""

from .commands import (
    cmd_help, cmd_ping, cmd_status, cmd_gpu, cmd_disk, cmd_memory,
    cmd_cpu, cmd_uptime, cmd_processes, cmd_ip, cmd_services,
    cmd_start, cmd_stop, cmd_restart, cmd_logs, cmd_docker,
    cmd_monitoring, cmd_alert, cmd_conda, cmd_ollama, cmd_llm,
    cmd_confirm, cmd_reboot, cmd_shutdown, cmd_kill,
    cmd_history, cmd_stats, cmd_screenshot, cmd_chart, cmd_schedule
)

from .llm import handle_message

from .claude import handle_claude_command

from .email import email_conversation_handler

from .files import (
    cmd_download, cmd_ls, cmd_cat,
    file_upload_handler
)

from .keyboard import cmd_menu, callback_handler

from .memory_cmd import (
    cmd_memory_view, cmd_memory_add, cmd_memory_delete,
    cmd_server_logs, cmd_proactive_status, cmd_insights,
    cmd_hafiza, cmd_hafiza_ekle, cmd_hafiza_sil,
    cmd_sunucu_log, cmd_proaktif
)

__all__ = [
    # Command handlers
    'cmd_help', 'cmd_ping', 'cmd_status', 'cmd_gpu', 'cmd_disk', 'cmd_memory',
    'cmd_cpu', 'cmd_uptime', 'cmd_processes', 'cmd_ip', 'cmd_services',
    'cmd_start', 'cmd_stop', 'cmd_restart', 'cmd_logs', 'cmd_docker',
    'cmd_monitoring', 'cmd_alert', 'cmd_conda', 'cmd_ollama', 'cmd_llm',
    'cmd_confirm', 'cmd_reboot', 'cmd_shutdown', 'cmd_kill',
    'cmd_history', 'cmd_stats', 'cmd_screenshot', 'cmd_chart', 'cmd_schedule',

    # LLM handler
    'handle_message',

    # Claude handler
    'handle_claude_command',

    # Email handler
    'email_conversation_handler',

    # File handlers
    'cmd_download', 'cmd_ls', 'cmd_cat', 'file_upload_handler',

    # Keyboard handlers
    'cmd_menu', 'callback_handler',

    # Memory handlers
    'cmd_memory_view', 'cmd_memory_add', 'cmd_memory_delete',
    'cmd_server_logs', 'cmd_proactive_status', 'cmd_insights',
    'cmd_hafiza', 'cmd_hafiza_ekle', 'cmd_hafiza_sil',
    'cmd_sunucu_log', 'cmd_proaktif'
]
