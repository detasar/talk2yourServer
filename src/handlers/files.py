"""
File Upload/Download Handlers

Allows users to transfer files to/from the server via Telegram.
"""

import os
import logging
from pathlib import Path
from typing import Optional

from telegram import Update, Document
from telegram.ext import ContextTypes, MessageHandler, filters

from security import require_auth, require_admin

logger = logging.getLogger(__name__)

# Maximum file size for download (50 MB - Telegram limit)
MAX_DOWNLOAD_SIZE = 50 * 1024 * 1024

# Default upload directory - user should configure this
DEFAULT_UPLOAD_DIR = Path.home() / "telegram_uploads"

# Allowed download paths (security - prevent access to sensitive files)
# User should configure these based on their system
ALLOWED_PATHS = [
    Path.home(),
    Path("/tmp"),
]

# Blocked patterns (never allow download of these)
BLOCKED_PATTERNS = [
    ".env",
    ".ssh",
    ".gnupg",
    "id_rsa",
    "id_ed25519",
    "credentials",
    "secrets",
    ".git/config",
]


def is_path_allowed(path: Path) -> bool:
    """Check if path is allowed for download"""
    resolved = path.resolve()

    # Check if under allowed paths
    allowed = False
    for allowed_path in ALLOWED_PATHS:
        try:
            resolved.relative_to(allowed_path.resolve())
            allowed = True
            break
        except ValueError:
            continue

    if not allowed:
        return False

    # Check blocked patterns
    path_str = str(resolved).lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern.lower() in path_str:
            return False

    return True


def get_file_info(path: Path) -> str:
    """Get file information"""
    if not path.exists():
        return "File not found"

    stat = path.stat()
    size = stat.st_size

    if size < 1024:
        size_str = f"{size} B"
    elif size < 1024 * 1024:
        size_str = f"{size / 1024:.1f} KB"
    else:
        size_str = f"{size / (1024 * 1024):.1f} MB"

    return f"📄 {path.name}\n📦 Size: {size_str}"


@require_auth
async def cmd_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Download a file from the server.
    Usage: /download <file_path>
    """
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: /download <file_path>\n"
            "Example: /download ~/test.txt\n"
            "Example: /download /tmp/output.log"
        )
        return

    # Expand path
    file_path = Path(" ".join(args)).expanduser()

    # Security check
    if not is_path_allowed(file_path):
        await update.message.reply_text(
            "⛔ Access denied to this file.\n"
            "Some files cannot be downloaded for security reasons."
        )
        return

    # Check if exists
    if not file_path.exists():
        await update.message.reply_text(f"❌ File not found: {file_path}")
        return

    # Check if directory
    if file_path.is_dir():
        await update.message.reply_text(
            "❌ This is a directory. Specify a single file.\n"
            "For directory contents: /ls <directory>"
        )
        return

    # Check size
    file_size = file_path.stat().st_size
    if file_size > MAX_DOWNLOAD_SIZE:
        size_mb = file_size / (1024 * 1024)
        await update.message.reply_text(
            f"❌ File too large: {size_mb:.1f} MB\n"
            f"Telegram limit: {MAX_DOWNLOAD_SIZE / (1024 * 1024):.0f} MB"
        )
        return

    # Send file
    try:
        await update.message.reply_text(f"📤 Sending file: {file_path.name}")

        with open(file_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=file_path.name,
                caption=get_file_info(file_path)
            )

        logger.info(f"File downloaded: {file_path} by user {update.effective_user.id}")

    except Exception as e:
        logger.error(f"Download error: {e}")
        await update.message.reply_text(f"❌ Download error: {str(e)}")


@require_auth
async def cmd_ls(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    List directory contents.
    Usage: /ls [directory]
    """
    args = context.args
    dir_path = Path(" ".join(args)).expanduser() if args else Path.home()

    # Security check
    if not is_path_allowed(dir_path):
        await update.message.reply_text("⛔ Access denied to this directory.")
        return

    if not dir_path.exists():
        await update.message.reply_text(f"❌ Directory not found: {dir_path}")
        return

    if not dir_path.is_dir():
        await update.message.reply_text(f"❌ Not a directory: {dir_path}")
        return

    try:
        items = list(dir_path.iterdir())
        items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

        lines = [
            f"📁 {dir_path}",
            "=" * 30,
            ""
        ]

        for item in items[:50]:  # Limit to 50 items
            if item.is_dir():
                lines.append(f"📁 {item.name}/")
            else:
                size = item.stat().st_size
                if size < 1024:
                    size_str = f"{size}B"
                elif size < 1024 * 1024:
                    size_str = f"{size // 1024}K"
                else:
                    size_str = f"{size // (1024 * 1024)}M"
                lines.append(f"📄 {item.name} ({size_str})")

        if len(items) > 50:
            lines.append(f"\n...and {len(items) - 50} more")

        result = "\n".join(lines)
        if len(result) > 4000:
            result = result[:3900] + "\n...(truncated)"

        await update.message.reply_text(result)

    except PermissionError:
        await update.message.reply_text("⛔ Permission denied to read directory.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


@require_auth
async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle file uploads from user.
    Files are saved to ~/telegram_uploads/
    """
    document = update.message.document

    if not document:
        return

    # Create upload directory if needed
    upload_dir = DEFAULT_UPLOAD_DIR
    upload_dir.mkdir(exist_ok=True)

    # Get file name
    file_name = document.file_name or f"upload_{document.file_id}"

    # Sanitize filename
    file_name = "".join(c for c in file_name if c.isalnum() or c in "._-")
    if not file_name:
        file_name = f"upload_{document.file_id}"

    # Check size
    if document.file_size > MAX_DOWNLOAD_SIZE:
        size_mb = document.file_size / (1024 * 1024)
        await update.message.reply_text(
            f"❌ File too large: {size_mb:.1f} MB\n"
            f"Limit: {MAX_DOWNLOAD_SIZE / (1024 * 1024):.0f} MB"
        )
        return

    # Download file
    try:
        await update.message.reply_text(f"📥 Downloading file: {file_name}")

        file = await document.get_file()
        save_path = upload_dir / file_name

        # Add suffix if exists
        counter = 1
        original_path = save_path
        while save_path.exists():
            stem = original_path.stem
            suffix = original_path.suffix
            save_path = upload_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        await file.download_to_drive(save_path)

        await update.message.reply_text(
            f"✅ File saved!\n\n"
            f"📁 Location: {save_path}\n"
            f"📦 Size: {document.file_size / 1024:.1f} KB"
        )

        logger.info(f"File uploaded: {save_path} by user {update.effective_user.id}")

    except Exception as e:
        logger.error(f"Upload error: {e}")
        await update.message.reply_text(f"❌ Upload error: {str(e)}")


@require_auth
async def cmd_cat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Display file contents.
    Usage: /cat <file_path> [lines]
    """
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: /cat <file_path> [lines]\n"
            "Example: /cat ~/test.txt\n"
            "Example: /cat ~/log.txt 50"
        )
        return

    file_path = Path(args[0]).expanduser()
    lines_limit = int(args[1]) if len(args) > 1 and args[1].isdigit() else 100

    # Security check
    if not is_path_allowed(file_path):
        await update.message.reply_text("⛔ Access denied to this file.")
        return

    if not file_path.exists():
        await update.message.reply_text(f"❌ File not found: {file_path}")
        return

    if file_path.is_dir():
        await update.message.reply_text("❌ This is a directory. Use /ls.")
        return

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total_lines = len(lines)
        lines = lines[-lines_limit:]  # Last N lines

        content = "".join(lines)
        if len(content) > 3900:
            content = content[-3900:]
            content = "...(truncated)\n" + content

        header = f"📄 {file_path.name} (last {len(lines)}/{total_lines} lines)\n"
        header += "=" * 30 + "\n\n"

        await update.message.reply_text(header + content)

    except UnicodeDecodeError:
        await update.message.reply_text(
            "❌ This file is not text (binary).\n"
            "You can download it with /download."
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


# Document handler for file uploads
file_upload_handler = MessageHandler(
    filters.Document.ALL & ~filters.COMMAND,
    handle_file_upload
)
