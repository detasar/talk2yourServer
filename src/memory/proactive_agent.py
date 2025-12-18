"""
Proactive AI Agent

An agentic AI that proactively sends personalized messages to the user.
Uses memory, server context, and LLM to generate meaningful interactions.
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta, time as dt_time
from typing import Optional, Any
from dataclasses import dataclass
from enum import Enum

from telegram import Bot

from config import config
from utils.message_coordinator import message_coordinator, MessagePriority

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of proactive messages"""
    MORNING_GREETING = "morning_greeting"       # Morning greeting + day summary
    DAILY_SUMMARY = "daily_summary"             # Daily server summary
    WEEKLY_SUMMARY = "weekly_summary"           # Weekly summary
    SERVER_IDLE = "server_idle"                 # Server idle suggestion
    SERVER_BUSY = "server_busy"                 # High usage info
    INSIGHT = "insight"                         # Observation/insight sharing
    REMINDER = "reminder"                       # Reminder
    SUGGESTION = "suggestion"                   # Suggestion
    CHECK_IN = "check_in"                       # How are you check


@dataclass
class ProactiveConfig:
    """Configuration for proactive messaging"""
    enabled: bool = True

    # Time windows for different message types
    morning_greeting_time: dt_time = dt_time(9, 0)
    evening_summary_time: dt_time = dt_time(21, 0)

    # Cooldowns (minutes)
    min_message_interval: int = 120  # 2 hours minimum between messages
    daily_message_limit: int = 5     # Max messages per day

    # Server idle threshold (minutes of no activity)
    idle_threshold: int = 180  # 3 hours

    # LLM settings
    use_groq: bool = True
    use_openai_fallback: bool = True
    max_tokens: int = 500


class ProactiveAgent:
    """
    Agentic AI that proactively engages with the user.

    Features:
    - Context-aware messaging based on memory and server state
    - Time-appropriate greetings and summaries
    - Personalized suggestions when server is idle
    - Respectful message frequency (cooldowns)
    """

    def __init__(self):
        self.bot: Optional[Bot] = None
        self.memory_manager = None
        self.server_logger = None
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.config = ProactiveConfig()

        # State tracking
        self._last_message_time: Optional[datetime] = None
        self._messages_today: int = 0
        self._last_date: Optional[datetime] = None
        self._morning_sent_today: bool = False
        self._evening_sent_today: bool = False

    async def initialize(self, bot: Bot, memory_manager, server_logger) -> bool:
        """Initialize the agent with dependencies"""
        self.bot = bot
        self.memory_manager = memory_manager
        self.server_logger = server_logger

        logger.info("ProactiveAgent initialized")
        return True

    def start(self) -> None:
        """Start the proactive agent loop"""
        if self.running:
            return

        self.running = True
        self.task = asyncio.create_task(self._agent_loop())
        logger.info("ProactiveAgent started")

    def stop(self) -> None:
        """Stop the agent"""
        self.running = False
        if self.task:
            self.task.cancel()
            self.task = None
        logger.info("ProactiveAgent stopped")

    async def _agent_loop(self) -> None:
        """Main agent loop - runs every 15 minutes"""
        logger.info("ProactiveAgent loop started")

        while self.running:
            try:
                await self._tick()
            except Exception as e:
                logger.error(f"Error in proactive agent loop: {e}")

            # Check every 15 minutes
            await asyncio.sleep(900)

        logger.info("ProactiveAgent loop stopped")

    async def _tick(self) -> None:
        """Single tick of the agent - decide if we should send a message"""
        if not self.config.enabled or not config.admin_users:
            return

        now = datetime.now()

        # Reset daily counters
        if self._last_date is None or self._last_date.date() != now.date():
            self._messages_today = 0
            self._morning_sent_today = False
            self._evening_sent_today = False
            self._last_date = now

        # Check daily limit
        if self._messages_today >= self.config.daily_message_limit:
            return

        # Check cooldown
        if self._last_message_time:
            minutes_since_last = (now - self._last_message_time).total_seconds() / 60
            if minutes_since_last < self.config.min_message_interval:
                return

        # Decide what message to send (if any)
        message_type = await self._decide_message_type(now)

        if message_type:
            await self._send_proactive_message(message_type)

    async def _decide_message_type(self, now: datetime) -> Optional[MessageType]:
        """Decide what type of message to send (if any)"""

        # Morning greeting (9:00-9:30)
        if (now.hour == self.config.morning_greeting_time.hour and
            now.minute < 30 and not self._morning_sent_today):
            return MessageType.MORNING_GREETING

        # Evening summary (21:00-21:30)
        if (now.hour == self.config.evening_summary_time.hour and
            now.minute < 30 and not self._evening_sent_today):
            return MessageType.DAILY_SUMMARY

        # Check for server idle (random chance to avoid predictability)
        if await self._is_server_idle():
            if random.random() < 0.3:  # 30% chance when idle
                return MessageType.SERVER_IDLE

        # Weekly summary on Sunday evening
        if now.weekday() == 6 and now.hour == 20 and now.minute < 15:
            return MessageType.WEEKLY_SUMMARY

        return None

    async def _is_server_idle(self) -> bool:
        """Check if server has been idle"""
        if not self.server_logger:
            return False

        try:
            recent = await self.server_logger.get_recent(
                hours=3,
                event_type='user_activity',
                limit=5
            )
            return len(recent) < 2  # Less than 2 user activities in 3 hours
        except:
            return False

    def _get_priority(self, message_type: MessageType) -> MessagePriority:
        """Map message type to coordinator priority"""
        # Scheduled messages are PROACTIVE priority
        scheduled = {MessageType.MORNING_GREETING, MessageType.DAILY_SUMMARY, MessageType.WEEKLY_SUMMARY}
        if message_type in scheduled:
            return MessagePriority.PROACTIVE

        # Everything else is INFO (lowest priority)
        return MessagePriority.INFO

    async def _send_proactive_message(self, message_type: MessageType) -> bool:
        """Generate and send a proactive message"""
        if not self.bot or not config.admin_users:
            return False

        priority = self._get_priority(message_type)
        msg_key = f"proactive_{message_type.value}"

        # Check with global coordinator first
        can_send, reason = message_coordinator.can_send(
            source="proactive_agent",
            priority=priority,
            message_type=message_type.value,
            key=msg_key
        )

        if not can_send:
            logger.debug(f"Proactive message {message_type.value} blocked by coordinator: {reason}")
            return False

        try:
            # Build context
            context = await self._build_context(message_type)

            # Generate message using LLM
            message = await self._generate_message(message_type, context)

            if not message:
                return False

            # Send to all admin users
            for user_id in config.admin_users:
                try:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to send proactive message to {user_id}: {e}")

            # Record with coordinator
            message_coordinator.record_sent(
                source="proactive_agent",
                priority=priority,
                message_type=message_type.value,
                key=msg_key
            )

            # Update state
            self._last_message_time = datetime.now()
            self._messages_today += 1

            if message_type == MessageType.MORNING_GREETING:
                self._morning_sent_today = True
            elif message_type == MessageType.DAILY_SUMMARY:
                self._evening_sent_today = True

            # Log the event
            if self.server_logger:
                self.server_logger.log(
                    event_type='ai_task',
                    event_subtype='proactive_message',
                    description=f"Sent {message_type.value} message",
                    importance='info',
                    source='proactive_agent'
                )

            logger.info(f"Sent proactive message: {message_type.value}")
            return True

        except Exception as e:
            logger.error(f"Error sending proactive message: {e}")
            return False

    async def _build_context(self, message_type: MessageType) -> dict:
        """Build context for LLM message generation"""
        context = {
            "message_type": message_type.value,
            "current_time": datetime.now().strftime("%H:%M"),
            "current_date": datetime.now().strftime("%B %d %Y, %A"),
            "day_of_week": datetime.now().strftime("%A"),
        }

        # Add memory context
        if self.memory_manager:
            try:
                context["memory"] = await self.memory_manager.get_context_for_llm(
                    categories=['personal', 'professional', 'interests', 'goals'],
                    max_tokens=1000
                )

                # Get some specific important memories
                important = await self.memory_manager.get_important(min_importance=8, limit=5)
                context["key_facts"] = [f"{m.key}: {m.value}" for m in important]
            except Exception as e:
                logger.warning(f"Could not get memory context: {e}")
                context["memory"] = ""
                context["key_facts"] = []

        # Add server context
        if self.server_logger:
            try:
                context["server_activity"] = await self.server_logger.get_context_for_llm(hours=6)
                summary = await self.server_logger.get_daily_summary()
                context["today_summary"] = summary
            except Exception as e:
                logger.warning(f"Could not get server context: {e}")
                context["server_activity"] = ""
                context["today_summary"] = {}

        # Add system metrics
        try:
            from tools.system import get_disk_percent, get_memory_percent, get_cpu_percent
            from tools.gpu import get_gpu_temperature, get_gpu_utilization

            context["system_metrics"] = {
                "cpu_percent": await get_cpu_percent(),
                "memory_percent": await get_memory_percent(),
                "disk_percent": await get_disk_percent(),
                "gpu_temp": await get_gpu_temperature(),
                "gpu_util": await get_gpu_utilization()
            }
        except Exception as e:
            logger.warning(f"Could not get system metrics: {e}")
            context["system_metrics"] = {}

        return context

    async def _generate_message(self, message_type: MessageType, context: dict) -> Optional[str]:
        """Generate personalized message using LLM"""

        # Build the prompt
        prompt = self._build_prompt(message_type, context)

        try:
            from llm.router import llm_router

            response, provider = await llm_router.chat(
                prompt=prompt,
                system=self._get_system_prompt()
            )

            return self._format_response(response, message_type)

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            # Fallback to template-based message
            return self._get_fallback_message(message_type, context)

    def _get_system_prompt(self) -> str:
        """Get system prompt for proactive AI"""
        return """You are the user's personal AI assistant. You send proactive and personalized messages.

Your task:
- Write personalized messages using information about the user
- Summarize server status and activities
- Be appropriate for time and context (morning greeting, evening summary, etc.)
- Reference the user's interests and goals
- Use a friendly but professional tone
- Be brief and concise (2-4 paragraphs max)
- Use emojis but don't overdo it

IMPORTANT:
- Address the user informally
- Provide information and suggestions, not requests or commands
- Don't make it feel like spam, add value
- Avoid unnecessary repetition"""

    def _build_prompt(self, message_type: MessageType, context: dict) -> str:
        """Build prompt for specific message type"""

        base_context = f"""
Current time: {context.get('current_date', '')} {context.get('current_time', '')}

{context.get('memory', '')}

{context.get('server_activity', '')}
"""

        prompts = {
            MessageType.MORNING_GREETING: f"""
{base_context}

Say good morning to the user and write a motivating message for today.
- If it's a weekday, focus on work/research
- If it's a weekend, focus on rest/hobbies
- Briefly summarize server status
- Provide a suggestion for today (based on their interests)
""",

            MessageType.DAILY_SUMMARY: f"""
{base_context}

Today's Summary:
- Event counts: {context.get('today_summary', {}).get('event_counts', {})}
- Service activity: {context.get('today_summary', {}).get('service_activity', {})}

Give the user a brief end-of-day summary:
- What happened on the server today
- How was GPU/system usage
- A suggestion for tomorrow
""",

            MessageType.SERVER_IDLE: f"""
{base_context}

System Metrics:
{context.get('system_metrics', {})}

The server is currently idle and resources are available.
Suggest to the user:
- Something from their interests (AI, ontology, PhD, etc.)
- A specific and actionable suggestion
- But don't be pushy, just a reminder
""",

            MessageType.WEEKLY_SUMMARY: f"""
{base_context}

Give the user a weekly summary:
- What they did this week (if you have info)
- How the server performed
- Motivation for next week
""",

            MessageType.CHECK_IN: f"""
{base_context}

Write a friendly "how are you" message to the user:
- Mention if you haven't talked in a while
- Ask about one of their interests
- Mention that you're there to help
"""
        }

        return prompts.get(message_type, base_context + "\nWrite a brief and friendly message to the user.")

    def _format_response(self, response: str, message_type: MessageType) -> str:
        """Format the LLM response"""
        # Add header based on message type
        headers = {
            MessageType.MORNING_GREETING: "Good Morning!",
            MessageType.DAILY_SUMMARY: "Daily Summary",
            MessageType.SERVER_IDLE: "Suggestion",
            MessageType.WEEKLY_SUMMARY: "Weekly Summary",
            MessageType.CHECK_IN: "Hello!",
            MessageType.INSIGHT: "Observation",
            MessageType.SUGGESTION: "Suggestion",
        }

        header = headers.get(message_type, "AI Assistant")

        # Clean up response
        response = response.strip()

        # Don't add header if response already has one
        if not any(response.startswith(h) for h in headers.values()):
            response = f"**{header}**\n\n{response}"

        return response

    def _get_fallback_message(self, message_type: MessageType, context: dict) -> str:
        """Get a fallback template message if LLM fails"""
        now = datetime.now()

        fallbacks = {
            MessageType.MORNING_GREETING: f"**Good Morning!**\n\nToday is {now.strftime('%B %d %Y, %A')}. Server is running and waiting for you. Have a productive day!",

            MessageType.DAILY_SUMMARY: f"**Daily Summary**\n\nToday is complete. Server ran without issues. See you tomorrow!",

            MessageType.SERVER_IDLE: "**Suggestion**\n\nThe server is currently idle and resources are available. Maybe this is a good time for an experiment or POC?",

            MessageType.WEEKLY_SUMMARY: "**Weekly Summary**\n\nAnother week behind us. Recharge your energy for next week!",
        }

        return fallbacks.get(message_type, "Hello from your AI assistant!")

    async def send_manual_message(self, message: str) -> bool:
        """Send a manual proactive message (admin triggered)"""
        if not self.bot or not config.admin_users:
            return False

        for user_id in config.admin_users:
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to send manual message to {user_id}: {e}")
                return False

        return True

    async def trigger_now(self, message_type: str = "check_in") -> bool:
        """Manually trigger a proactive message"""
        try:
            mt = MessageType(message_type)
            return await self._send_proactive_message(mt)
        except ValueError:
            logger.error(f"Unknown message type: {message_type}")
            return False

    def get_status(self) -> dict:
        """Get agent status"""
        return {
            "running": self.running,
            "enabled": self.config.enabled,
            "messages_today": self._messages_today,
            "daily_limit": self.config.daily_message_limit,
            "last_message": self._last_message_time.isoformat() if self._last_message_time else None,
            "morning_sent": self._morning_sent_today,
            "evening_sent": self._evening_sent_today,
        }


# Global instance
proactive_agent = ProactiveAgent()
