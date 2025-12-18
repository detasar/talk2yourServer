"""
Proactive Alerting System

Monitors system metrics and sends alerts to Telegram when thresholds are exceeded.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable, Any

from telegram import Bot

from config import config, MANAGED_SERVICES
from tools.gpu import get_gpu_temperature, get_gpu_utilization, get_gpu_memory_free
from tools.system import get_disk_percent, get_memory_percent, get_cpu_percent
from tools.services import get_service_status

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Represents an alert"""
    key: str  # Unique identifier (e.g., "gpu_temp", "disk_root")
    level: AlertLevel
    title: str
    message: str
    value: Any
    threshold: Any
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def format_message(self) -> str:
        """Format alert for Telegram"""
        level_emoji = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.CRITICAL: "🚨"
        }
        emoji = level_emoji.get(self.level, "❓")
        return f"{emoji} **{self.title}**\n\n{self.message}\n\nValue: {self.value}\nThreshold: {self.threshold}"


class AlertManager:
    """Manages proactive alerts"""

    def __init__(self):
        self.bot: Optional[Bot] = None
        self.running = False
        self.task: Optional[asyncio.Task] = None

        # Cooldown tracking: key -> last_alert_time
        self._cooldowns: dict[str, float] = {}

        # Alert state tracking: key -> is_active
        self._active_alerts: dict[str, bool] = {}

    def set_bot(self, bot: Bot) -> None:
        """Set the Telegram bot instance"""
        self.bot = bot

    def _is_on_cooldown(self, alert_key: str) -> bool:
        """Check if alert is on cooldown"""
        if alert_key not in self._cooldowns:
            return False

        elapsed = time.time() - self._cooldowns[alert_key]
        return elapsed < config.alert_cooldown

    def _set_cooldown(self, alert_key: str) -> None:
        """Set cooldown for an alert"""
        self._cooldowns[alert_key] = time.time()

    async def send_alert(self, alert: Alert) -> bool:
        """Send alert to all admin users"""
        if not self.bot:
            logger.warning("Bot not set, cannot send alert")
            return False

        if not config.admin_users:
            logger.warning("No admin users configured for alerts")
            return False

        # Check cooldown (only for repeated alerts of same type)
        if self._active_alerts.get(alert.key) and self._is_on_cooldown(alert.key):
            logger.debug(f"Alert {alert.key} is on cooldown, skipping")
            return False

        message = alert.format_message()

        sent = False
        for user_id in config.admin_users:
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode="Markdown"
                )
                sent = True
                logger.info(f"Alert sent to {user_id}: {alert.key}")
            except Exception as e:
                logger.error(f"Failed to send alert to {user_id}: {e}")

        if sent:
            self._set_cooldown(alert.key)
            self._active_alerts[alert.key] = True

        return sent

    async def send_recovery(self, alert_key: str, title: str, message: str) -> bool:
        """Send recovery notification when issue is resolved"""
        if not self.bot or not config.admin_users:
            return False

        # Only send if there was an active alert
        if not self._active_alerts.get(alert_key):
            return False

        self._active_alerts[alert_key] = False

        recovery_msg = f"✅ **{title} - Resolved**\n\n{message}"

        for user_id in config.admin_users:
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=recovery_msg,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to send recovery to {user_id}: {e}")

        return True

    async def check_gpu_temperature(self) -> Optional[Alert]:
        """Check GPU temperature"""
        try:
            temp = await get_gpu_temperature()
            if temp <= 0:
                return None

            if temp >= config.alert_gpu_temp:
                return Alert(
                    key="gpu_temp",
                    level=AlertLevel.CRITICAL if temp >= 90 else AlertLevel.WARNING,
                    title="High GPU Temperature",
                    message=f"GPU temperature is {temp}°C - check cooling!",
                    value=f"{temp}°C",
                    threshold=f"{config.alert_gpu_temp}°C"
                )
            else:
                # Check for recovery
                await self.send_recovery(
                    "gpu_temp",
                    "GPU Temperature",
                    f"GPU temperature returned to normal: {temp}°C"
                )
        except Exception as e:
            logger.error(f"Error checking GPU temp: {e}")

        return None

    async def check_disk_usage(self) -> Optional[Alert]:
        """Check disk usage"""
        try:
            percent = await get_disk_percent()
            if percent < 0:
                return None

            if percent >= config.alert_disk_percent:
                return Alert(
                    key="disk_root",
                    level=AlertLevel.CRITICAL if percent >= 95 else AlertLevel.WARNING,
                    title="Disk Space Running Low",
                    message=f"Root disk is {percent}% full - free up space!",
                    value=f"{percent}%",
                    threshold=f"{config.alert_disk_percent}%"
                )
            else:
                await self.send_recovery(
                    "disk_root",
                    "Disk Space",
                    f"Disk usage returned to normal: {percent}%"
                )
        except Exception as e:
            logger.error(f"Error checking disk: {e}")

        return None

    async def check_memory_usage(self) -> Optional[Alert]:
        """Check RAM usage"""
        try:
            percent = await get_memory_percent()
            if percent < 0:
                return None

            if percent >= config.alert_memory_percent:
                return Alert(
                    key="memory",
                    level=AlertLevel.CRITICAL if percent >= 95 else AlertLevel.WARNING,
                    title="High RAM Usage",
                    message=f"RAM usage is {percent}% - check processes!",
                    value=f"{percent}%",
                    threshold=f"{config.alert_memory_percent}%"
                )
            else:
                await self.send_recovery(
                    "memory",
                    "RAM Usage",
                    f"RAM usage returned to normal: {percent}%"
                )
        except Exception as e:
            logger.error(f"Error checking memory: {e}")

        return None

    async def check_services(self) -> list[Alert]:
        """Check critical services"""
        alerts = []

        for service_name in config.critical_services:
            if service_name not in MANAGED_SERVICES:
                continue

            try:
                status_msg, is_running = await get_service_status(service_name)

                alert_key = f"service_{service_name}"

                if not is_running:
                    alerts.append(Alert(
                        key=alert_key,
                        level=AlertLevel.CRITICAL,
                        title=f"Service Down: {service_name}",
                        message=f"{service_name} service is not running!\nStatus: {status_msg}",
                        value="DOWN",
                        threshold="RUNNING"
                    ))
                else:
                    await self.send_recovery(
                        alert_key,
                        f"Service: {service_name}",
                        f"{service_name} service is running again."
                    )
            except Exception as e:
                logger.error(f"Error checking service {service_name}: {e}")

        return alerts

    async def run_checks(self) -> list[Alert]:
        """Run all alert checks"""
        alerts = []

        # GPU temperature
        alert = await self.check_gpu_temperature()
        if alert:
            alerts.append(alert)

        # Disk usage
        alert = await self.check_disk_usage()
        if alert:
            alerts.append(alert)

        # Memory usage
        alert = await self.check_memory_usage()
        if alert:
            alerts.append(alert)

        # Services
        service_alerts = await self.check_services()
        alerts.extend(service_alerts)

        return alerts

    async def monitoring_loop(self) -> None:
        """Main monitoring loop"""
        logger.info("Proactive alerting started")

        while self.running:
            try:
                if config.alert_enabled:
                    alerts = await self.run_checks()

                    for alert in alerts:
                        await self.send_alert(alert)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

            await asyncio.sleep(config.alert_check_interval)

        logger.info("Proactive alerting stopped")

    def start(self) -> None:
        """Start the monitoring loop"""
        if self.running:
            return

        self.running = True
        self.task = asyncio.create_task(self.monitoring_loop())

    def stop(self) -> None:
        """Stop the monitoring loop"""
        self.running = False
        if self.task:
            self.task.cancel()


# Global alert manager instance
alert_manager = AlertManager()
