"""
Smart Alerter - LLM-Powered Personalized Alerts

Instead of plain "Service Down: X" messages, generates
personalized, context-aware messages using LLM and user memory.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional, Any
from dataclasses import dataclass
from enum import Enum

from telegram import Bot

from config import config, MANAGED_SERVICES
from tools.gpu import get_gpu_temperature, get_gpu_utilization, get_gpu_memory_free
from tools.system import get_disk_percent, get_memory_percent, get_cpu_percent
from tools.services import get_service_status
from utils.message_coordinator import message_coordinator, MessagePriority

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Types of alerts"""
    SERVICE_DOWN = "service_down"
    SERVICE_UP = "service_up"
    GPU_HOT = "gpu_hot"
    GPU_COOL = "gpu_cool"
    DISK_FULL = "disk_full"
    DISK_OK = "disk_ok"
    MEMORY_HIGH = "memory_high"
    MEMORY_OK = "memory_ok"
    SERVER_IDLE = "server_idle"
    DAILY_SUMMARY = "daily_summary"


@dataclass
class AlertContext:
    """Context for generating personalized alerts"""
    alert_type: AlertType
    service_name: Optional[str] = None
    current_value: Any = None
    threshold: Any = None
    system_metrics: dict = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.system_metrics is None:
            self.system_metrics = {}


class SmartAlerter:
    """
    Intelligent alerting system that uses LLM to generate
    personalized, context-aware messages.
    """

    def __init__(self):
        self.bot: Optional[Bot] = None
        self.memory_manager = None
        self.server_logger = None
        self.running = False
        self.task: Optional[asyncio.Task] = None

        # Cooldown tracking
        self._cooldowns: dict[str, float] = {}
        self._active_issues: dict[str, bool] = {}

        # Config
        self.check_interval = 60  # seconds
        self.cooldown_minutes = 30  # Don't repeat same alert for 30 min

    def set_dependencies(self, bot: Bot, memory_manager, server_logger):
        """Set required dependencies"""
        self.bot = bot
        self.memory_manager = memory_manager
        self.server_logger = server_logger

    def _is_on_cooldown(self, key: str) -> bool:
        """Check if alert is on cooldown"""
        if key not in self._cooldowns:
            return False
        elapsed = (time.time() - self._cooldowns[key]) / 60
        return elapsed < self.cooldown_minutes

    def _set_cooldown(self, key: str):
        """Set cooldown for an alert"""
        self._cooldowns[key] = time.time()

    async def _get_system_snapshot(self) -> dict:
        """Get current system state"""
        snapshot = {
            "timestamp": datetime.now().strftime("%H:%M"),
            "gpu": {},
            "system": {},
            "services": {}
        }

        try:
            snapshot["gpu"]["temp"] = await get_gpu_temperature()
            snapshot["gpu"]["util"] = await get_gpu_utilization()
            snapshot["gpu"]["memory_free"] = await get_gpu_memory_free()
        except:
            pass

        try:
            snapshot["system"]["disk_percent"] = await get_disk_percent()
            snapshot["system"]["memory_percent"] = await get_memory_percent()
            snapshot["system"]["cpu_percent"] = await get_cpu_percent()
        except:
            pass

        # Check key services
        for service in ["ollama", "jupyterlab", "open-webui"]:
            try:
                _, is_running = await get_service_status(service)
                snapshot["services"][service] = "running" if is_running else "stopped"
            except:
                snapshot["services"][service] = "unknown"

        return snapshot

    async def _get_memory_context(self) -> str:
        """Get rich memory context for personalization"""
        if not self.memory_manager:
            return ""

        try:
            context_parts = []

            # Personal info
            name = await self.memory_manager.get("personal", "name")
            if name:
                context_parts.append(f"Name: {name.value}")

            # Current work/profession
            job = await self.memory_manager.get("professional", "current_job")
            if job:
                context_parts.append(f"Job: {job.value}")

            # Active projects
            projects = await self.memory_manager.get_by_category("projects", limit=3)
            if projects:
                context_parts.append("Active projects: " + ", ".join([m.key for m in projects]))

            # Interests
            interests = await self.memory_manager.get_by_category("interests", limit=5)
            if interests:
                context_parts.append("Interests: " + ", ".join([m.key for m in interests]))

            # Goals
            goals = await self.memory_manager.get_by_category("goals", limit=3)
            if goals:
                context_parts.append("Goals: " + ", ".join([f"{m.key}: {m.value[:40]}" for m in goals]))

            # Technical preferences
            prefs = await self.memory_manager.get_by_category("preferences", limit=3)
            if prefs:
                context_parts.append("Preferences: " + ", ".join([f"{m.key}={m.value[:30]}" for m in prefs]))

            # Get recent server activity context
            if self.server_logger:
                activity_context = await self.server_logger.get_context_for_llm(hours=6, max_events=10)
                if activity_context and "notable" not in activity_context.lower():
                    context_parts.append(f"\n{activity_context}")

            return "\n".join(context_parts)

        except Exception as e:
            logger.error(f"Error getting memory context: {e}")
            return ""

    async def _generate_smart_message(self, context: AlertContext) -> str:
        """Generate personalized message using LLM"""

        # Get system snapshot
        system = context.system_metrics or await self._get_system_snapshot()

        # Get memory context
        memory_context = await self._get_memory_context()

        # Build prompt based on alert type
        prompt = self._build_prompt(context, system, memory_context)

        try:
            from llm.router import llm_router

            response, _ = await llm_router.chat(
                prompt=prompt,
                system=self._get_system_prompt()
            )

            return self._format_response(response, context)

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return self._get_fallback_message(context)

    def _get_system_prompt(self) -> str:
        """System prompt for smart alerts"""
        return """You are the user's personal AI assistant. You write informative messages about server status.

RULES:
- Be friendly and conversational, not robotic
- Keep it short and concise (2-3 paragraphs max)
- Address the user directly
- Explain the issue and suggest solutions
- Connect with the user's interests/work when appropriate
- Provide actionable commands (e.g., /start ollama)
- Use emojis but don't overdo it
- Don't be overly dramatic, inform calmly

FORMAT:
- First line: Summarize the situation
- Second paragraph: What can be done
- Optional: Relevant suggestion/context"""

    def _build_prompt(self, context: AlertContext, system: dict, memory: str) -> str:
        """Build LLM prompt for specific alert type"""

        base_info = f"""
CURRENT SYSTEM STATE:
- Time: {system.get('timestamp', 'N/A')}
- GPU Temperature: {system.get('gpu', {}).get('temp', 'N/A')}°C
- GPU Usage: {system.get('gpu', {}).get('util', 'N/A')}%
- GPU Free Memory: {system.get('gpu', {}).get('memory_free', 'N/A')} MB
- Disk Usage: {system.get('system', {}).get('disk_percent', 'N/A')}%
- RAM Usage: {system.get('system', {}).get('memory_percent', 'N/A')}%
- Services: {system.get('services', {})}

USER INFO:
{memory if memory else 'No information available'}
"""

        prompts = {
            AlertType.SERVICE_DOWN: f"""
{base_info}

SITUATION: {context.service_name} service is not running!

Write a short, friendly message to inform the user.
- Remind what the service does (ollama=LLM, jupyterlab=notebook, etc.)
- Provide the start command: /start {context.service_name}
- If GPU/system metrics are good, note that starting is safe
- Connect with the user's interests (e.g., if ollama is down, LLM experiments are affected)
""",

            AlertType.SERVICE_UP: f"""
{base_info}

SITUATION: {context.service_name} service is running again!

Write a short "good news" message.
- Say the service is ready again
- Suggest what they can do
""",

            AlertType.GPU_HOT: f"""
{base_info}

SITUATION: GPU temperature is {context.current_value}°C - high!

Write a warning message:
- Inform about the high temperature
- Possible causes (training, inference, etc.)
- What can be done (fan control, reduce workload)
""",

            AlertType.DISK_FULL: f"""
{base_info}

SITUATION: Disk usage is {context.current_value}% - running low!

Write a disk warning:
- Inform that disk is filling up
- Suggest checking large directories with /disk large
- Suggest Docker image/log cleanup
""",

            AlertType.SERVER_IDLE: f"""
{base_info}

SITUATION: Server is currently idle, resources are available.

Write a suggestion message:
- Say the server is idle and resources are available
- Suggest something related to their interests (AI, research, etc.)
- Don't be pushy, just gently remind
- You can suggest a specific project or experiment
""",

            AlertType.DAILY_SUMMARY: f"""
{base_info}

Write a daily summary message:
- How the server performed today
- Any important events
- Suggestions for tomorrow
"""
        }

        return prompts.get(context.alert_type, f"{base_info}\n\nProvide information about: {context.alert_type.value}")

    def _format_response(self, response: str, context: AlertContext) -> str:
        """Format LLM response"""
        response = response.strip()

        # Add appropriate emoji header if not present
        headers = {
            AlertType.SERVICE_DOWN: "🔴",
            AlertType.SERVICE_UP: "🟢",
            AlertType.GPU_HOT: "🌡️",
            AlertType.GPU_COOL: "❄️",
            AlertType.DISK_FULL: "💾",
            AlertType.MEMORY_HIGH: "🧠",
            AlertType.SERVER_IDLE: "💡",
            AlertType.DAILY_SUMMARY: "📊"
        }

        emoji = headers.get(context.alert_type, "📢")

        if not response.startswith(tuple("🔴🟢🌡️❄️💾🧠💡📊📢⚠️✅")):
            response = f"{emoji} {response}"

        return response

    def _get_fallback_message(self, context: AlertContext) -> str:
        """Fallback message if LLM fails"""
        fallbacks = {
            AlertType.SERVICE_DOWN: f"🔴 **{context.service_name}** service is currently not running.\n\nTo start: `/start {context.service_name}`",
            AlertType.SERVICE_UP: f"🟢 **{context.service_name}** service is running again!",
            AlertType.GPU_HOT: f"🌡️ GPU temperature is high: {context.current_value}°C\n\nCheck workload.",
            AlertType.DISK_FULL: f"💾 Disk filling up: {context.current_value}%\n\nCheck with `/disk large`.",
            AlertType.SERVER_IDLE: "💡 Server is idle, resources available. Good time for an experiment!",
        }
        return fallbacks.get(context.alert_type, f"📢 Notification: {context.alert_type.value}")

    def _get_priority(self, alert_type: AlertType) -> MessagePriority:
        """Map alert type to message priority"""
        critical_alerts = {AlertType.SERVICE_DOWN, AlertType.GPU_HOT}
        recovery_alerts = {AlertType.SERVICE_UP, AlertType.GPU_COOL, AlertType.DISK_OK, AlertType.MEMORY_OK}
        info_alerts = {AlertType.SERVER_IDLE, AlertType.DAILY_SUMMARY}

        if alert_type in critical_alerts:
            return MessagePriority.CRITICAL
        elif alert_type in recovery_alerts:
            return MessagePriority.INFO  # Recovery messages are low priority
        elif alert_type in info_alerts:
            return MessagePriority.PROACTIVE
        else:
            return MessagePriority.ALERT

    async def send_smart_alert(self, context: AlertContext) -> bool:
        """Generate and send a smart alert"""
        if not self.bot or not config.admin_users:
            return False

        alert_key = f"{context.alert_type.value}_{context.service_name or 'system'}"
        priority = self._get_priority(context.alert_type)

        # Check with global coordinator first
        can_send, reason = message_coordinator.can_send(
            source="smart_alerter",
            priority=priority,
            message_type=context.alert_type.value,
            key=alert_key
        )

        if not can_send:
            logger.debug(f"Alert {alert_key} blocked by coordinator: {reason}")
            return False

        # Also check local cooldown (for deduplication within alert types)
        if context.alert_type not in [AlertType.SERVICE_UP, AlertType.GPU_COOL, AlertType.DISK_OK]:
            if self._is_on_cooldown(alert_key):
                logger.debug(f"Alert {alert_key} on local cooldown, skipping")
                return False

        # Generate personalized message
        message = await self._generate_smart_message(context)

        # Send to all admin users
        sent = False
        for user_id in config.admin_users:
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode="Markdown"
                )
                sent = True
                logger.info(f"Smart alert sent: {alert_key}")
            except Exception as e:
                logger.error(f"Failed to send smart alert to {user_id}: {e}")

        if sent:
            # Record with coordinator
            message_coordinator.record_sent(
                source="smart_alerter",
                priority=priority,
                message_type=context.alert_type.value,
                key=alert_key
            )

            self._set_cooldown(alert_key)
            self._active_issues[alert_key] = context.alert_type not in [
                AlertType.SERVICE_UP, AlertType.GPU_COOL, AlertType.DISK_OK
            ]

            # Log to server logger
            if self.server_logger:
                self.server_logger.log(
                    event_type='alert',
                    event_subtype=context.alert_type.value,
                    description=f'Smart alert: {alert_key}',
                    importance='notable',
                    source='smart_alerter',
                    related_service=context.service_name
                )

        return sent

    async def check_and_alert(self):
        """Run all checks and send smart alerts"""
        system = await self._get_system_snapshot()

        # Check services
        for service in config.critical_services:
            if service not in MANAGED_SERVICES:
                continue

            try:
                _, is_running = await get_service_status(service)
                alert_key = f"service_down_{service}"

                if not is_running:
                    if not self._active_issues.get(alert_key):
                        await self.send_smart_alert(AlertContext(
                            alert_type=AlertType.SERVICE_DOWN,
                            service_name=service,
                            system_metrics=system
                        ))
                else:
                    # Service recovered
                    if self._active_issues.get(alert_key):
                        await self.send_smart_alert(AlertContext(
                            alert_type=AlertType.SERVICE_UP,
                            service_name=service,
                            system_metrics=system
                        ))
                        self._active_issues[alert_key] = False

            except Exception as e:
                logger.error(f"Error checking service {service}: {e}")

        # Check GPU temperature
        try:
            gpu_temp = system.get("gpu", {}).get("temp", 0)
            if gpu_temp > 0:
                if gpu_temp >= config.alert_gpu_temp:
                    if not self._active_issues.get("gpu_hot"):
                        await self.send_smart_alert(AlertContext(
                            alert_type=AlertType.GPU_HOT,
                            current_value=gpu_temp,
                            threshold=config.alert_gpu_temp,
                            system_metrics=system
                        ))
                        self._active_issues["gpu_hot"] = True
                elif self._active_issues.get("gpu_hot") and gpu_temp < config.alert_gpu_temp - 10:
                    await self.send_smart_alert(AlertContext(
                        alert_type=AlertType.GPU_COOL,
                        current_value=gpu_temp,
                        system_metrics=system
                    ))
                    self._active_issues["gpu_hot"] = False
        except Exception as e:
            logger.error(f"Error checking GPU: {e}")

        # Check disk
        try:
            disk_percent = system.get("system", {}).get("disk_percent", 0)
            if disk_percent >= config.alert_disk_percent:
                if not self._active_issues.get("disk_full"):
                    await self.send_smart_alert(AlertContext(
                        alert_type=AlertType.DISK_FULL,
                        current_value=disk_percent,
                        threshold=config.alert_disk_percent,
                        system_metrics=system
                    ))
                    self._active_issues["disk_full"] = True
            elif self._active_issues.get("disk_full") and disk_percent < config.alert_disk_percent - 5:
                self._active_issues["disk_full"] = False
        except Exception as e:
            logger.error(f"Error checking disk: {e}")

    async def monitoring_loop(self):
        """Main monitoring loop"""
        logger.info("SmartAlerter started")

        while self.running:
            try:
                if config.alert_enabled:
                    await self.check_and_alert()
            except Exception as e:
                logger.error(f"Error in smart alerter loop: {e}")

            await asyncio.sleep(self.check_interval)

        logger.info("SmartAlerter stopped")

    def start(self):
        """Start the smart alerter"""
        if self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self.monitoring_loop())

    def stop(self):
        """Stop the smart alerter"""
        self.running = False
        if self.task:
            self.task.cancel()


# Global instance
smart_alerter = SmartAlerter()
