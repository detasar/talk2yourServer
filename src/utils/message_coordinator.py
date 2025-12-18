"""
Message Coordinator

Coordinates all outgoing proactive messages to prevent spam
and ensure proper timing between SmartAlerter, ProactiveAgent, etc.
"""

import logging
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class MessagePriority(Enum):
    """Priority levels for messages"""
    CRITICAL = 1    # Service down, GPU overheating - always send
    ALERT = 2       # Warnings, disk full - send with short cooldown
    PROACTIVE = 3   # Scheduled messages, suggestions - respect long cooldown
    INFO = 4        # FYI messages - only if nothing else sent recently


@dataclass
class MessageRecord:
    """Record of a sent message"""
    timestamp: float
    source: str  # 'smart_alerter', 'proactive_agent', etc.
    priority: MessagePriority
    message_type: str  # 'service_down', 'morning_greeting', etc.
    key: str  # Unique key for deduplication


class MessageCoordinator:
    """
    Coordinates all proactive messaging to prevent spam.

    Features:
    - Global rate limiting across all message sources
    - Priority-based message delivery
    - Deduplication within time window
    - Quiet hours support
    """

    def __init__(self):
        self._message_history: list[MessageRecord] = []
        self._daily_count: int = 0
        self._last_date: Optional[datetime] = None

        # Configuration
        self.max_messages_per_day: int = 15  # Absolute daily limit
        self.min_interval_minutes: dict[MessagePriority, int] = {
            MessagePriority.CRITICAL: 5,     # Critical alerts: 5 min cooldown
            MessagePriority.ALERT: 30,       # Regular alerts: 30 min cooldown
            MessagePriority.PROACTIVE: 120,  # Proactive: 2 hour cooldown
            MessagePriority.INFO: 240,       # Info: 4 hour cooldown
        }

        # Quiet hours (no proactive messages, only critical)
        self.quiet_hours_start: int = 23  # 11 PM
        self.quiet_hours_end: int = 8     # 8 AM

        # Global minimum between ANY messages (prevents rapid fire)
        self.global_min_interval_minutes: int = 2

    def _is_quiet_hours(self) -> bool:
        """Check if we're in quiet hours"""
        hour = datetime.now().hour
        if self.quiet_hours_start > self.quiet_hours_end:
            return hour >= self.quiet_hours_start or hour < self.quiet_hours_end
        else:
            return self.quiet_hours_start <= hour < self.quiet_hours_end

    def _reset_daily_if_needed(self) -> None:
        """Reset daily counter if it's a new day"""
        today = datetime.now().date()
        if self._last_date != today:
            self._daily_count = 0
            self._last_date = today
            cutoff = time.time() - 86400
            self._message_history = [
                m for m in self._message_history if m.timestamp > cutoff
            ]

    def can_send(
        self,
        source: str,
        priority: MessagePriority,
        message_type: str,
        key: Optional[str] = None
    ) -> tuple[bool, str]:
        """Check if a message can be sent."""
        self._reset_daily_if_needed()
        now = time.time()
        unique_key = key or f"{source}_{message_type}"

        if priority != MessagePriority.CRITICAL:
            if self._daily_count >= self.max_messages_per_day:
                return False, f"Daily limit reached ({self.max_messages_per_day})"

        if self._is_quiet_hours() and priority != MessagePriority.CRITICAL:
            return False, "Quiet hours - only critical alerts allowed"

        if self._message_history:
            last_any = max(m.timestamp for m in self._message_history)
            minutes_since = (now - last_any) / 60
            if minutes_since < self.global_min_interval_minutes:
                return False, f"Global cooldown ({self.global_min_interval_minutes - minutes_since:.1f} min left)"

        min_interval = self.min_interval_minutes.get(priority, 60)
        same_priority_msgs = [m for m in self._message_history if m.priority == priority]
        if same_priority_msgs:
            last_same = max(m.timestamp for m in same_priority_msgs)
            minutes_since = (now - last_same) / 60
            if minutes_since < min_interval:
                return False, f"Priority cooldown ({min_interval - minutes_since:.1f} min left)"

        same_key_msgs = [m for m in self._message_history if m.key == unique_key and (now - m.timestamp) < 1800]
        if same_key_msgs and priority != MessagePriority.CRITICAL:
            return False, f"Duplicate message blocked (key: {unique_key})"

        return True, "OK"

    def record_sent(
        self,
        source: str,
        priority: MessagePriority,
        message_type: str,
        key: Optional[str] = None
    ) -> None:
        """Record that a message was sent"""
        self._reset_daily_if_needed()
        unique_key = key or f"{source}_{message_type}"

        record = MessageRecord(
            timestamp=time.time(),
            source=source,
            priority=priority,
            message_type=message_type,
            key=unique_key
        )

        self._message_history.append(record)
        self._daily_count += 1

        logger.info(
            f"Message recorded: {source}/{message_type} (priority={priority.name}, "
            f"daily_count={self._daily_count})"
        )

    def get_status(self) -> dict:
        """Get coordinator status"""
        self._reset_daily_if_needed()
        now = time.time()
        recent = [m for m in self._message_history if now - m.timestamp < 3600]

        return {
            "daily_count": self._daily_count,
            "daily_limit": self.max_messages_per_day,
            "messages_last_hour": len(recent),
            "quiet_hours": self._is_quiet_hours(),
            "quiet_hours_window": f"{self.quiet_hours_start}:00-{self.quiet_hours_end}:00",
            "recent_messages": [
                {
                    "source": m.source,
                    "type": m.message_type,
                    "priority": m.priority.name,
                    "minutes_ago": round((now - m.timestamp) / 60, 1)
                }
                for m in sorted(recent, key=lambda x: x.timestamp, reverse=True)[:5]
            ]
        }

    def time_until_can_send(self, priority: MessagePriority) -> int:
        """Get minutes until a message of given priority can be sent"""
        can, reason = self.can_send("check", priority, "check")
        if can:
            return 0
        if "min left" in reason:
            try:
                return int(float(reason.split("(")[1].split(" min")[0]))
            except:
                pass
        return self.min_interval_minutes.get(priority, 60)


# Global singleton
message_coordinator = MessageCoordinator()
