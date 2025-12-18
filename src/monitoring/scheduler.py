"""
Scheduled Tasks Manager

Provides periodic reports and automated tasks via asyncio scheduling.
"""

import asyncio
import logging
from datetime import datetime, time as dt_time
from typing import Callable, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from telegram import Bot

from config import config

logger = logging.getLogger(__name__)


class ScheduleType(Enum):
    """Types of schedules"""
    DAILY = "daily"
    WEEKLY = "weekly"
    HOURLY = "hourly"
    INTERVAL = "interval"  # Every N minutes


@dataclass
class ScheduledTask:
    """Represents a scheduled task"""
    name: str
    schedule_type: ScheduleType
    callback: Callable
    enabled: bool = True

    # For DAILY/WEEKLY - specific time
    run_time: Optional[dt_time] = None

    # For WEEKLY - day of week (0=Monday, 6=Sunday)
    day_of_week: Optional[int] = None

    # For INTERVAL - minutes between runs
    interval_minutes: int = 60

    # Track last run
    last_run: Optional[datetime] = None

    def should_run_now(self) -> bool:
        """Check if task should run now"""
        if not self.enabled:
            return False

        now = datetime.now()

        if self.schedule_type == ScheduleType.INTERVAL:
            if self.last_run is None:
                return True
            elapsed = (now - self.last_run).total_seconds() / 60
            return elapsed >= self.interval_minutes

        elif self.schedule_type == ScheduleType.HOURLY:
            if self.last_run is None:
                return True
            elapsed = (now - self.last_run).total_seconds() / 3600
            return elapsed >= 1

        elif self.schedule_type == ScheduleType.DAILY:
            if self.run_time is None:
                return False
            # Check if it's the right time and hasn't run today
            if now.hour == self.run_time.hour and now.minute == self.run_time.minute:
                if self.last_run is None or self.last_run.date() < now.date():
                    return True
            return False

        elif self.schedule_type == ScheduleType.WEEKLY:
            if self.run_time is None or self.day_of_week is None:
                return False
            # Check if it's the right day and time
            if now.weekday() == self.day_of_week:
                if now.hour == self.run_time.hour and now.minute == self.run_time.minute:
                    if self.last_run is None or (now - self.last_run).days >= 7:
                        return True
            return False

        return False


class TaskScheduler:
    """Manages scheduled tasks"""

    def __init__(self):
        self.bot: Optional[Bot] = None
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.scheduled_tasks: dict[str, ScheduledTask] = {}

        # Register default tasks
        self._register_default_tasks()

    def set_bot(self, bot: Bot) -> None:
        """Set the Telegram bot instance"""
        self.bot = bot

    def _register_default_tasks(self) -> None:
        """Register default scheduled tasks"""

        # Daily morning report at 09:00
        # DISABLED: ProactiveAgent handles morning greetings with LLM personalization
        self.scheduled_tasks["daily_report"] = ScheduledTask(
            name="daily_report",
            schedule_type=ScheduleType.DAILY,
            callback=self._send_daily_report,
            enabled=False,  # Disabled - ProactiveAgent does this better
            run_time=dt_time(9, 0)
        )

        # Weekly summary on Sunday at 20:00
        self.scheduled_tasks["weekly_summary"] = ScheduledTask(
            name="weekly_summary",
            schedule_type=ScheduleType.WEEKLY,
            callback=self._send_weekly_summary,
            enabled=False,  # Disabled by default
            run_time=dt_time(20, 0),
            day_of_week=6  # Sunday
        )

    async def _send_daily_report(self) -> None:
        """Send daily system report to admins"""
        if not self.bot or not config.admin_users:
            return

        from tools.system import get_full_status
        from tools.gpu import get_gpu_temperature

        try:
            status = await get_full_status()
            temp = await get_gpu_temperature()

            message = (
                f"📊 **DAILY REPORT** - {datetime.now().strftime('%d/%m/%Y')}\n"
                f"{'=' * 30}\n\n"
                f"{status}\n\n"
                f"🌡️ GPU Temperature: {temp}°C"
            )

            for user_id in config.admin_users:
                try:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to send daily report to {user_id}: {e}")

            logger.info("Daily report sent successfully")

        except Exception as e:
            logger.error(f"Error generating daily report: {e}")

    async def _send_weekly_summary(self) -> None:
        """Send weekly usage summary to admins"""
        if not self.bot or not config.admin_users:
            return

        from db import db

        try:
            # Get stats for all admin users
            message_lines = [
                f"📈 **WEEKLY SUMMARY** - {datetime.now().strftime('%d/%m/%Y')}",
                "=" * 30,
                ""
            ]

            for user_id in config.admin_users:
                stats = await db.get_user_stats(user_id, days=7)
                if stats:
                    total_messages = sum(stats.get("messages", {}).values())
                    message_lines.append(f"User {user_id}:")
                    message_lines.append(f"  Messages: {total_messages}")

                    if stats.get("providers"):
                        for provider, data in stats["providers"].items():
                            message_lines.append(f"  {provider}: {data['requests']} requests")

                    message_lines.append("")

            message = "\n".join(message_lines)

            for user_id in config.admin_users:
                try:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to send weekly summary to {user_id}: {e}")

            logger.info("Weekly summary sent successfully")

        except Exception as e:
            logger.error(f"Error generating weekly summary: {e}")

    def add_task(self, task: ScheduledTask) -> None:
        """Add a scheduled task"""
        self.scheduled_tasks[task.name] = task
        logger.info(f"Scheduled task added: {task.name}")

    def remove_task(self, name: str) -> bool:
        """Remove a scheduled task"""
        if name in self.scheduled_tasks:
            del self.scheduled_tasks[name]
            logger.info(f"Scheduled task removed: {name}")
            return True
        return False

    def enable_task(self, name: str) -> bool:
        """Enable a scheduled task"""
        if name in self.scheduled_tasks:
            self.scheduled_tasks[name].enabled = True
            logger.info(f"Scheduled task enabled: {name}")
            return True
        return False

    def disable_task(self, name: str) -> bool:
        """Disable a scheduled task"""
        if name in self.scheduled_tasks:
            self.scheduled_tasks[name].enabled = False
            logger.info(f"Scheduled task disabled: {name}")
            return True
        return False

    async def run_task(self, name: str) -> bool:
        """Manually run a task"""
        if name not in self.scheduled_tasks:
            return False

        task = self.scheduled_tasks[name]
        try:
            await task.callback()
            task.last_run = datetime.now()
            return True
        except Exception as e:
            logger.error(f"Error running task {name}: {e}")
            return False

    def get_tasks_status(self) -> str:
        """Get status of all scheduled tasks"""
        lines = [
            "⏰ SCHEDULED TASKS",
            "=" * 30,
            ""
        ]

        for name, task in self.scheduled_tasks.items():
            status = "✅" if task.enabled else "⛔"
            schedule_info = ""

            if task.schedule_type == ScheduleType.DAILY:
                schedule_info = f"Daily at {task.run_time.strftime('%H:%M')}"
            elif task.schedule_type == ScheduleType.WEEKLY:
                days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                day_name = days[task.day_of_week] if task.day_of_week is not None else "?"
                time_str = task.run_time.strftime('%H:%M') if task.run_time else "?"
                schedule_info = f"Every {day_name} at {time_str}"
            elif task.schedule_type == ScheduleType.HOURLY:
                schedule_info = "Hourly"
            elif task.schedule_type == ScheduleType.INTERVAL:
                schedule_info = f"Every {task.interval_minutes} minutes"

            last_run = task.last_run.strftime("%d/%m %H:%M") if task.last_run else "Not run yet"

            lines.append(f"{status} **{name}**")
            lines.append(f"   Schedule: {schedule_info}")
            lines.append(f"   Last run: {last_run}")
            lines.append("")

        return "\n".join(lines)

    async def scheduler_loop(self) -> None:
        """Main scheduler loop - checks every minute"""
        logger.info("Task scheduler started")

        while self.running:
            try:
                for name, task in self.scheduled_tasks.items():
                    if task.should_run_now():
                        logger.info(f"Running scheduled task: {name}")
                        try:
                            await task.callback()
                            task.last_run = datetime.now()
                        except Exception as e:
                            logger.error(f"Scheduled task {name} failed: {e}")

            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")

            # Check every 60 seconds
            await asyncio.sleep(60)

        logger.info("Task scheduler stopped")

    def start(self) -> None:
        """Start the scheduler"""
        if self.running:
            return

        self.running = True
        self.task = asyncio.create_task(self.scheduler_loop())
        logger.info("Task scheduler started")

    def stop(self) -> None:
        """Stop the scheduler"""
        self.running = False
        if self.task:
            self.task.cancel()
            self.task = None
        logger.info("Task scheduler stopped")


# Global scheduler instance
scheduler = TaskScheduler()
