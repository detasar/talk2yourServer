"""
LLM Handler

Handles natural language messages and routes them to appropriate LLM provider.
Includes smart command suggestion, context-aware responses, and conversation history.
Includes memory integration for personalized responses.
"""

import asyncio
import time
from telegram import Update
from telegram.ext import ContextTypes

from security import require_auth
from llm.router import llm_router
from config import config
from db import db
from monitoring.health import health_checker
from memory import memory_manager, server_logger, conversation_analyzer


# High-quality system prompt with conversation history support
SYSTEM_PROMPT = """You are a personal AI assistant managing an AI/ML server via a Telegram bot.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🖥️ SERVER SPECIFICATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• GPU: NVIDIA RTX 3060 (12GB VRAM) - For deep learning and LLM inference
• CPU: Intel i5-10400F (6 core / 12 thread)
• RAM: 32GB DDR4
• OS: Ubuntu 22.04 LTS
• Storage: ~400GB available
• Remote Access: Via Tailscale VPN

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 ACTIVE SERVICES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Ollama (:11434) - Local LLMs: qwen3:8b, qwen2.5-coder:7b, deepseek-r1:8b
• JupyterLab (:8888) - Interactive notebook development
• code-server (:9000) - Browser-based VS Code
• Open WebUI (:8080) - ChatGPT-like chat interface
• PostgreSQL (:5432) - Vector database with pgvector
• Prometheus + Grafana - System metrics and monitoring

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 AVAILABLE BOT COMMANDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
If a question can be answered with these commands, SUGGEST the command:

📊 SYSTEM INFO:
  /status - System overview
  /gpu, /gpu full, /gpu processes, /gpu temp - GPU metrics
  /disk, /disk large - Disk usage
  /memory - RAM status
  /cpu - CPU load
  /uptime - System uptime
  /processes - Top processes
  /ip - Network info

🐳 DOCKER & SERVICES:
  /docker, /docker all, /docker stats - Container management
  /logs <container> - Container logs
  /services - All services status
  /start, /stop, /restart <service> - Service control

🧠 CLAUDE CODE:
  /claude <message> - Code writing/fixing with Claude
  /claude new <message> - Start new session
  /claude status - Session status

📈 OTHER:
  /monitoring - Prometheus/Grafana stack
  /llm status - LLM provider status
  /stats - Usage statistics
  /conda - Python environments
  /ollama - Available models

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 USER MEMORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Between "###user_memory###" and "###end_user_memory###" markers,
you may find information about the user.

• Use this information NATURALLY - don't repeat everything
• Reference when relevant: "Related to your work at..."
• Remember goals: "Regarding your PhD completion goal..."
• Respect preferences: User prefers technical and direct communication
• Note new learnings (you can mention in chat)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💬 CONVERSATION HISTORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Between "###previous conversations###" and "###end of previous conversations###"
markers, you may find previous chat history.

• If current question is RELATED to previous conversations, use that context
• For example, "can you explain that more?" needs previous context
• If question is INDEPENDENT, ignore history and answer directly
• History may be empty - this is normal, could be first message

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 BEHAVIOR PRINCIPLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. COMMAND SUGGESTION: If a question can be answered with a command, SUGGEST it first.
   Example: "How hot is GPU?" → "You can check with /gpu temp command"

2. BREVITY: Give concise and clear answers. Don't over-explain.

3. FRIENDLINESS: Talk to user informally, like a friend.

4. EXPERTISE: Deep knowledge in ML, AI, Python, Docker, Linux, server management.

5. HONESTY: If you don't know something, say so. If guessing, mention it.

6. LANGUAGE: Respond in the same language as the user's question. Technical terms can stay in English (GPU, container, model etc.)

7. CODE: When code examples needed, provide short and working examples.

8. PROBLEM SOLVING: For errors/problems, suggest step-by-step solutions."""


async def get_conversation_history(user_id: int, limit: int = 8) -> str:
    """
    Fetch recent conversation history from database.
    Returns formatted string for prompt injection.
    """
    messages = await db.get_recent_messages(user_id, limit)

    if not messages:
        return ""

    # Reverse to get chronological order (oldest first)
    messages = list(reversed(messages))

    history_lines = []
    for msg in messages:
        # Format timestamp
        timestamp = msg.get('created_at')
        time_str = timestamp.strftime("%H:%M") if timestamp else ""

        # User message
        user_msg = msg.get('user_message', '')
        if user_msg:
            history_lines.append(f"[{time_str}] User: {user_msg[:500]}")

        # Bot response
        bot_resp = msg.get('bot_response', '')
        if bot_resp and not bot_resp.startswith("ERROR"):
            # Truncate long responses
            if len(bot_resp) > 300:
                bot_resp = bot_resp[:300] + "..."
            history_lines.append(f"[{time_str}] Bot: {bot_resp}")

    if not history_lines:
        return ""

    return "\n".join(history_lines)


@require_auth
async def handle_llm_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle natural language messages (non-command).
    Routes to appropriate LLM based on suffix or availability.
    Includes conversation history and memory context for personalized responses.
    Logs all messages to database and queues for conversation analysis.
    """
    text = update.message.text
    user = update.effective_user
    start_time = time.time()

    # Record message for health tracking
    health_checker.record_message()

    # Log user activity to server logger
    server_logger.log(
        event_type='user_activity',
        event_subtype='llm_message',
        description=f'LLM message from {user.username or user.id}',
        details={'message_length': len(text)},
        importance='info',
        source='telegram_bot'
    )

    # Send typing action
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    # Get conversation history for context
    history = await get_conversation_history(user.id, limit=8)

    # Get memory context for personalized response
    memory_context = ""
    try:
        memory_context = await memory_manager.get_context_for_llm(
            categories=['personal', 'professional', 'interests', 'preferences', 'goals'],
            max_tokens=800
        )
    except Exception as e:
        pass  # Memory not available, continue without it

    # Build prompt with history and memory markers
    prompt_parts = []

    if memory_context:
        prompt_parts.append(f"###user_memory###\n{memory_context}\n###end_user_memory###\n")

    if history:
        prompt_parts.append(f"###previous conversations###\n{history}\n###end of previous conversations###\n")

    prompt_parts.append(text)
    prompt_with_context = "\n".join(prompt_parts)

    # Get response from LLM
    try:
        response, provider = await llm_router.chat(
            prompt=prompt_with_context,
            system=SYSTEM_PROMPT
        )

        response_time_ms = int((time.time() - start_time) * 1000)

        # Add provider info to response
        final_response = f"{response}\n\n[{provider}]"

        # Truncate if too long
        if len(final_response) > config.max_message_length:
            final_response = final_response[:config.max_message_length - 100]
            final_response += "\n\n...(truncated)"

        await update.message.reply_text(final_response)

        # Log to database
        message_id = await db.log_message(
            user_id=user.id,
            username=user.username,
            message_type="text",
            user_message=text,
            bot_response=response,
            provider=provider.split()[0] if provider else None,  # "groq (model)" -> "groq"
            response_time_ms=response_time_ms
        )

        # Update usage stats
        provider_name = provider.split()[0] if provider else "unknown"
        await db.update_usage_stats(user.id, provider_name)

        # Log LLM activity to server logger
        server_logger.log(
            event_type='ai_task',
            event_subtype='llm_response',
            description=f'LLM response via {provider_name}',
            details={'response_time_ms': response_time_ms, 'provider': provider_name},
            importance='info',
            source='telegram_bot'
        )

        # Queue conversation for analysis (non-blocking)
        # Only analyze if it's from an admin user
        if user.id in config.admin_users:
            await conversation_analyzer.analyze_conversation(
                user_message=text,
                bot_response=response,
                message_id=message_id
            )

    except Exception as e:
        health_checker.record_error()
        await update.message.reply_text(f"LLM Error: {str(e)}")

        # Log error to server logger
        server_logger.log(
            event_type='alert',
            event_subtype='llm_error',
            description=f'LLM error: {str(e)}',
            importance='notable',
            source='telegram_bot'
        )

        # Log error
        await db.log_message(
            user_id=user.id,
            username=user.username,
            message_type="text",
            user_message=text,
            bot_response=f"ERROR: {str(e)}",
            provider="error"
        )


@require_auth
async def handle_llm_message_streaming(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle natural language messages with streaming response.
    Includes conversation history for context-aware responses.
    """
    text = update.message.text
    user = update.effective_user

    # Send initial message
    progress_msg = await update.message.reply_text("Thinking...")

    # Get conversation history for context
    history = await get_conversation_history(user.id, limit=8)

    # Build prompt with history markers
    if history:
        prompt_with_history = f"""###previous conversations###
{history}
###end of previous conversations###

{text}"""
    else:
        prompt_with_history = text

    full_response = ""
    last_update_len = 0
    provider_used = ""

    try:
        async for chunk, provider in llm_router.chat_stream(
            prompt=prompt_with_history,
            system=SYSTEM_PROMPT
        ):
            full_response += chunk
            provider_used = provider

            # Update message every 500 chars
            if len(full_response) - last_update_len >= 500:
                try:
                    display = full_response[-3500:] if len(full_response) > 3500 else full_response
                    await progress_msg.edit_text(display)
                except:
                    pass
                last_update_len = len(full_response)

        # Final update
        final_text = f"{full_response}\n\n[{provider_used}]"
        if len(final_text) > config.max_message_length:
            final_text = final_text[:config.max_message_length - 100]
            final_text += "\n\n...(truncated)"

        try:
            await progress_msg.edit_text(final_text)
        except:
            await update.message.reply_text(final_text)

    except Exception as e:
        try:
            await progress_msg.edit_text(f"LLM Error: {str(e)}")
        except:
            await update.message.reply_text(f"LLM Error: {str(e)}")


# Use non-streaming by default for simplicity
handle_message = handle_llm_message
