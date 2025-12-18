"""
Talk2YourServer - Security Module

Handles:
- User authentication (whitelist-based)
- Rate limiting (sliding window)
- Dangerous command confirmation
"""

import time
from collections import defaultdict
from functools import wraps
from typing import Callable, Any

from telegram import Update
from telegram.ext import ContextTypes

from config import config, DANGEROUS_COMMANDS


class RateLimiter:
    """Rate limiter using sliding window algorithm"""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests: dict[int, list[float]] = defaultdict(list)

    def is_allowed(self, user_id: int) -> bool:
        """Check if user is within rate limit"""
        now = time.time()

        # Clean old requests outside the window
        self.requests[user_id] = [
            t for t in self.requests[user_id]
            if now - t < self.window
        ]

        if len(self.requests[user_id]) >= self.max_requests:
            return False

        self.requests[user_id].append(now)
        return True

    def get_remaining(self, user_id: int) -> int:
        """Get remaining requests for user in current window"""
        now = time.time()
        self.requests[user_id] = [
            t for t in self.requests[user_id]
            if now - t < self.window
        ]
        return max(0, self.max_requests - len(self.requests[user_id]))


# Global rate limiter instance
rate_limiter = RateLimiter(
    max_requests=config.rate_limit,
    window_seconds=config.rate_window
)


class ConfirmationManager:
    """Manages dangerous command confirmations with timeout"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        # user_id -> (command, args, timestamp)
        self.pending: dict[int, tuple[str, list[str], float]] = {}

    def request_confirmation(self, user_id: int, command: str, args: list[str]):
        """Store a pending confirmation request"""
        self.pending[user_id] = (command, args, time.time())

    def check_confirmation(self, user_id: int) -> tuple[str, list[str]] | None:
        """Check if user has a valid pending confirmation"""
        if user_id not in self.pending:
            return None

        command, args, timestamp = self.pending[user_id]

        if time.time() - timestamp > self.timeout:
            del self.pending[user_id]
            return None

        return (command, args)

    def clear(self, user_id: int):
        """Clear pending confirmation for user"""
        if user_id in self.pending:
            del self.pending[user_id]

    def get_warning(self, command: str) -> str | None:
        """Get warning message for dangerous command"""
        cmd_base = command.split()[0] if command else ""
        return DANGEROUS_COMMANDS.get(cmd_base)


# Global confirmation manager
confirmation_manager = ConfirmationManager()


def is_user_allowed(user_id: int) -> bool:
    """Check if user is in the allowed list"""
    # Security default: if no users configured, deny all
    if not config.allowed_users:
        return False
    return user_id in config.allowed_users


def is_user_admin(user_id: int) -> bool:
    """Check if user has admin privileges"""
    return user_id in config.admin_users


def require_auth(func: Callable) -> Callable:
    """
    Decorator to require user authentication.
    Checks whitelist and rate limit.
    """

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return

        user_id = user.id

        # Check if user is in whitelist
        if not is_user_allowed(user_id):
            await update.message.reply_text(
                "Access denied. This bot is private and requires authorization."
            )
            return

        # Check rate limit
        if not rate_limiter.is_allowed(user_id):
            remaining = rate_limiter.get_remaining(user_id)
            await update.message.reply_text(
                f"Rate limit exceeded. Please wait a moment.\n"
                f"Remaining: {remaining}/{config.rate_limit}"
            )
            return

        return await func(update, context, *args, **kwargs)

    return wrapper


def require_admin(func: Callable) -> Callable:
    """
    Decorator to require admin privileges.
    Must be used after @require_auth.
    """

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return

        if not is_user_admin(user.id):
            await update.message.reply_text(
                "This command requires admin privileges."
            )
            return

        return await func(update, context, *args, **kwargs)

    return wrapper


async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[str, list[str]] | None:
    """
    Handle /confirm command for dangerous operations.
    Returns (command, args) tuple if confirmation is valid, None otherwise.
    """
    user_id = update.effective_user.id

    pending = confirmation_manager.check_confirmation(user_id)
    if not pending:
        await update.message.reply_text(
            "No pending confirmation or timeout expired."
        )
        return None

    confirmation_manager.clear(user_id)
    return pending


async def request_dangerous_confirmation(
    update: Update,
    command: str,
    args: list[str]
) -> bool:
    """
    Request confirmation for a dangerous command.
    Returns True if confirmation is needed, False if command is safe.
    """
    warning = confirmation_manager.get_warning(command)
    if not warning:
        return False

    user_id = update.effective_user.id
    confirmation_manager.request_confirmation(user_id, command, args)

    args_str = " ".join(args) if args else ""
    await update.message.reply_text(
        f"⚠️ Dangerous Command\n\n"
        f"Command: /{command} {args_str}\n"
        f"Warning: {warning}\n\n"
        f"Send /confirm within 30 seconds to proceed."
    )
    return True
