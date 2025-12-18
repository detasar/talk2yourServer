"""
Claude Code Integration Handler

Handles /claude commands by running Claude CLI in print mode.
Supports session continuity with -c flag.
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Optional

from telegram import Update
from telegram.ext import ContextTypes

from config import config
from security import require_auth
from db import db


class ClaudeCodeRunner:
    """Runs Claude CLI in non-interactive mode with session support"""

    def __init__(self, working_dir: str = None):
        self.working_dir = working_dir or str(Path.home())
        self.current_process = None
        self.is_running = False
        # Session state is now stored per-user in database
        self._session_cache: dict[int, bool] = {}  # user_id -> has_session (memory cache)

    async def has_session(self, user_id: int) -> bool:
        """Check if user has an active session (from DB or cache)"""
        if user_id in self._session_cache:
            return self._session_cache[user_id]
        # Load from DB
        has_sess = await db.get_claude_session_state(user_id)
        self._session_cache[user_id] = has_sess
        return has_sess

    async def set_session(self, user_id: int, active: bool) -> None:
        """Set session state for user (saves to DB)"""
        self._session_cache[user_id] = active
        await db.set_claude_session_active(user_id, active)

    async def run_prompt(
        self,
        prompt: str,
        user_id: int,
        timeout: int = 300,
        max_budget: float = 5.0,
        allowed_tools: list[str] | None = None,
        bypass_permissions: bool = True,
        continue_session: bool = True,
        force_new: bool = False
    ) -> AsyncIterator[str]:
        """
        Run Claude CLI with prompt and stream response.
        Uses --output-format stream-json for real-time output.

        Args:
            user_id: Telegram user ID for session tracking
            continue_session: If True and has_session, use -c to continue
            force_new: If True, start fresh session (ignore continue)
        """
        cmd = [
            "claude", "-p", prompt,
            "--model", "opus",  # Use Opus by default
            "--output-format", "stream-json",
            "--max-budget-usd", str(max_budget)
        ]

        # Continue previous session if available (unless force_new)
        user_has_session = await self.has_session(user_id)
        if continue_session and user_has_session and not force_new:
            cmd.append("-c")

        if bypass_permissions:
            # Skip all permission checks - required for non-interactive Telegram usage
            cmd.append("--dangerously-skip-permissions")
            cmd.extend(["--permission-mode", "bypassPermissions"])

        if allowed_tools:
            cmd.extend(["--allowedTools", ",".join(allowed_tools)])

        self.current_process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.working_dir
        )
        self.is_running = True

        try:
            buffer = ""
            while True:
                try:
                    line = await asyncio.wait_for(
                        self.current_process.stdout.readline(),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    yield "\n\nTimeout - operation took too long"
                    break

                if not line:
                    break

                line_str = line.decode('utf-8').strip()
                if not line_str:
                    continue

                try:
                    data = json.loads(line_str)
                    msg_type = data.get("type", "")

                    # Handle different message types
                    if msg_type == "assistant":
                        # Assistant text content
                        content = data.get("message", {}).get("content", [])
                        for block in content:
                            if block.get("type") == "text":
                                text = block.get("text", "")
                                buffer += text
                                if len(buffer) >= 500:
                                    yield buffer
                                    buffer = ""

                    elif msg_type == "content_block_delta":
                        # Streaming delta
                        delta = data.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            buffer += text
                            if len(buffer) >= 500:
                                yield buffer
                                buffer = ""

                    elif msg_type == "result":
                        # Final result
                        if buffer:
                            yield buffer
                            buffer = ""

                        # Include cost info if available
                        cost = data.get("cost_usd")
                        if cost:
                            yield f"\n\n[Cost: ${cost:.4f}]"
                        break

                except json.JSONDecodeError:
                    # Plain text output
                    buffer += line_str + "\n"
                    if len(buffer) >= 500:
                        yield buffer
                        buffer = ""

            # Yield remaining buffer
            if buffer:
                yield buffer

            # Mark that we now have a session for future -c usage
            # Note: user_id is available in closure from run_prompt args
            await self.set_session(user_id, True)

        finally:
            self.is_running = False
            if self.current_process:
                try:
                    self.current_process.terminate()
                except:
                    pass

    async def reset_session(self, user_id: int) -> None:
        """Reset session state for user (for /claude new)"""
        self._session_cache[user_id] = False
        await db.set_claude_session_active(user_id, False)

    async def run_simple(self, prompt: str, timeout: int = 120) -> str:
        """Run simple prompt and return full response"""
        cmd = [
            "claude", "-p", prompt,
            "--model", "opus",  # Use Opus by default
            "--output-format", "text",
            "--dangerously-skip-permissions",
            "--permission-mode", "bypassPermissions"
        ]

        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir
            )

            stdout, stderr = await asyncio.wait_for(
                result.communicate(),
                timeout=timeout
            )

            return stdout.decode('utf-8')
        except asyncio.TimeoutError:
            return "Timeout - operation took too long"
        except Exception as e:
            return f"Error: {str(e)}"

    async def cancel(self) -> bool:
        """Cancel current operation"""
        if self.current_process and self.is_running:
            try:
                self.current_process.terminate()
                self.is_running = False
                return True
            except:
                pass
        return False


# Global runner instance - uses workspace from config
claude_runner = ClaudeCodeRunner(working_dir=config.working_dir)


def split_message(text: str, max_length: int = 4000) -> list[str]:
    """Split long text into chunks that fit Telegram's message limit"""
    if len(text) <= max_length:
        return [text]

    chunks = []
    current_chunk = ""

    # Try to split on newlines first
    lines = text.split('\n')

    for line in lines:
        # If single line is too long, split by words
        if len(line) > max_length:
            words = line.split(' ')
            for word in words:
                if len(current_chunk) + len(word) + 1 > max_length:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = word + ' '
                else:
                    current_chunk += word + ' '
        elif len(current_chunk) + len(line) + 1 > max_length:
            chunks.append(current_chunk.strip())
            current_chunk = line + '\n'
        else:
            current_chunk += line + '\n'

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


async def send_long_message(update: Update, progress_msg, response: str):
    """Send response, splitting into multiple messages if needed"""
    MAX_LENGTH = 4000  # Leave some margin

    # Add Claude header
    full_response = f"Claude Code:\n\n{response}"

    if len(full_response) <= MAX_LENGTH:
        try:
            await progress_msg.edit_text(full_response)
        except:
            await update.message.reply_text(full_response)
        return

    # Split into chunks
    chunks = split_message(response, MAX_LENGTH - 50)  # Leave room for headers

    # Edit progress message with first chunk
    try:
        header = f"Claude Code (1/{len(chunks)}):\n\n"
        await progress_msg.edit_text(header + chunks[0])
    except:
        await update.message.reply_text(f"Claude Code (1/{len(chunks)}):\n\n{chunks[0]}")

    # Send remaining chunks as new messages
    for i, chunk in enumerate(chunks[1:], start=2):
        await update.message.reply_text(f"({i}/{len(chunks)}):\n\n{chunk}")

    # If total is very long (>15000), also send as file for easy copying
    if len(response) > 15000:
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.txt',
            delete=False,
            prefix='claude_'
        ) as f:
            f.write(response)
            temp_path = f.name

        filename = f"claude_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        await update.message.reply_document(
            document=open(temp_path, 'rb'),
            filename=filename,
            caption=f"Full output ({len(response)} chars)"
        )

        try:
            os.unlink(temp_path)
        except:
            pass


@require_auth
async def handle_claude_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /claude commands with session continuity

    /claude <message> - Send message (continues previous session if exists)
    /claude new <message> - Start fresh session
    /claude status - Check status and session info
    /claude cancel - Cancel current operation
    /claude reset - Reset session (next message starts fresh)
    """
    args = context.args

    if not args:
        user_id = update.effective_user.id
        user_has_session = await claude_runner.has_session(user_id)
        session_status = "Active (will continue)" if user_has_session else "None (will start new)"
        await update.message.reply_text(
            "🤖 Claude Code (Opus)\n\n"
            "/c <message> - Send message (session continues)\n"
            "/c new <message> - Start new session\n"
            "/c status - Check status\n"
            "/c cancel - Cancel operation\n"
            "/c reset - Reset session\n\n"
            f"Session: {session_status}\n"
            "Model: Claude Opus 4.5\n\n"
            "Example:\n"
            "/c hello, analyze the project\n"
            "/c now fix the errors"
        )
        return

    message = " ".join(args)
    force_new = False

    # Check for "new" prefix
    if message.lower().startswith("new "):
        force_new = True
        message = message[4:].strip()
        if not message:
            await update.message.reply_text("Usage: /c new <message>")
            return

    # Status check
    if message.lower() == "status":
        user_id = update.effective_user.id
        running_status = "Running" if claude_runner.is_running else "Idle"
        user_has_session = await claude_runner.has_session(user_id)
        session_status = "Active (next message continues)" if user_has_session else "None (will start new)"
        await update.message.reply_text(
            f"Claude Code Status:\n\n"
            f"Operation: {running_status}\n"
            f"Session: {session_status}"
        )
        return

    # Cancel
    if message.lower() == "cancel":
        if await claude_runner.cancel():
            await update.message.reply_text("Operation cancelled")
        else:
            await update.message.reply_text("No running operation")
        return

    # Reset session
    if message.lower() == "reset":
        user_id = update.effective_user.id
        await claude_runner.reset_session(user_id)
        await update.message.reply_text("Session reset. Next message will start new session.")
        return

    # Check if already running
    if claude_runner.is_running:
        await update.message.reply_text(
            "Claude is currently working on another operation.\n"
            "You can cancel with /c cancel."
        )
        return

    # Indicate if continuing or starting new
    user_id = update.effective_user.id
    user_has_session = await claude_runner.has_session(user_id)
    session_info = "(continuing)" if (user_has_session and not force_new) else "(new session)"
    progress_msg = await update.message.reply_text(f"Claude working... {session_info}")

    full_response = ""
    last_update_len = 0

    try:
        async for chunk in claude_runner.run_prompt(message, user_id=user_id, force_new=force_new):
            full_response += chunk

            # Update message every 1000 chars
            if len(full_response) - last_update_len >= 1000:
                preview = full_response[-2000:] if len(full_response) > 2000 else full_response
                try:
                    await progress_msg.edit_text(
                        f"Working... {session_info}\n\n{preview}"
                    )
                except:
                    pass
                last_update_len = len(full_response)

        # Send final response
        await send_long_message(update, progress_msg, full_response)

    except Exception as e:
        try:
            await progress_msg.edit_text(f"Error: {str(e)}")
        except:
            await update.message.reply_text(f"Error: {str(e)}")
