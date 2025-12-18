"""
Server Activity Logger

Logs all server activities for context-aware AI responses.
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of server events"""
    SERVICE_EVENT = "service_event"     # Service start/stop/restart
    GPU_ACTIVITY = "gpu_activity"       # GPU usage, training, inference
    USER_ACTIVITY = "user_activity"     # User commands, messages
    SYSTEM_METRIC = "system_metric"     # CPU, memory, disk alerts
    AI_TASK = "ai_task"                 # LLM requests, Claude sessions
    SCHEDULED_TASK = "scheduled_task"   # Cron jobs, scheduled reports
    FILE_OPERATION = "file_operation"   # File uploads, downloads
    ALERT = "alert"                     # System alerts


class Importance(Enum):
    """Event importance levels"""
    DEBUG = "debug"
    INFO = "info"
    NOTABLE = "notable"
    IMPORTANT = "important"
    CRITICAL = "critical"


@dataclass
class ServerEvent:
    """Represents a server event"""
    id: int = 0
    timestamp: datetime = None
    event_type: str = ""
    event_subtype: str = ""
    description: str = ""
    details: dict = None
    importance: str = "info"
    source: str = "system"
    related_service: str = None
    duration_seconds: int = None


class ServerLogger:
    """Logs and queries server activity"""

    def __init__(self):
        self.pool = None
        self._initialized = False
        self._event_buffer: list[dict] = []
        self._buffer_flush_task: Optional[asyncio.Task] = None

    async def initialize(self, pool) -> bool:
        """Initialize with database pool"""
        self.pool = pool
        if not self.pool:
            logger.warning("No database pool provided to ServerLogger")
            return False

        try:
            await self._create_tables()
            self._initialized = True
            # Start buffer flush task
            self._buffer_flush_task = asyncio.create_task(self._flush_loop())
            logger.info("ServerLogger initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize ServerLogger: {e}")
            return False

    async def _create_tables(self):
        """Create server log tables"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS server_logs (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    event_type VARCHAR(50) NOT NULL,
                    event_subtype VARCHAR(100),
                    description TEXT,
                    details JSONB DEFAULT '{}',
                    importance VARCHAR(20) DEFAULT 'info',
                    source VARCHAR(50) DEFAULT 'system',
                    related_service VARCHAR(100),
                    duration_seconds INTEGER,
                    is_processed BOOLEAN DEFAULT FALSE
                );

                CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON server_logs(timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_logs_event_type ON server_logs(event_type);
                CREATE INDEX IF NOT EXISTS idx_logs_importance ON server_logs(importance);
            """)

    async def _flush_loop(self):
        """Background task to flush event buffer"""
        while True:
            try:
                await asyncio.sleep(10)  # Flush every 10 seconds
                await self._flush_buffer()
            except asyncio.CancelledError:
                await self._flush_buffer()  # Final flush
                break
            except Exception as e:
                logger.error(f"Error in flush loop: {e}")

    async def _flush_buffer(self):
        """Flush buffered events to database"""
        if not self._event_buffer or not self.pool:
            return

        events = self._event_buffer.copy()
        self._event_buffer.clear()

        try:
            async with self.pool.acquire() as conn:
                for event in events:
                    await conn.execute("""
                        INSERT INTO server_logs
                        (event_type, event_subtype, description, details,
                         importance, source, related_service, duration_seconds)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, event['event_type'], event.get('event_subtype'),
                        event.get('description'), json.dumps(event.get('details', {})),
                        event.get('importance', 'info'), event.get('source', 'system'),
                        event.get('related_service'), event.get('duration_seconds'))
        except Exception as e:
            logger.error(f"Error flushing event buffer: {e}")
            # Put events back
            self._event_buffer.extend(events)

    def log(
        self,
        event_type: str,
        description: str,
        event_subtype: str = None,
        details: dict = None,
        importance: str = "info",
        source: str = "system",
        related_service: str = None,
        duration_seconds: int = None
    ):
        """Log a server event (buffered)"""
        event = {
            'event_type': event_type,
            'event_subtype': event_subtype,
            'description': description,
            'details': details or {},
            'importance': importance,
            'source': source,
            'related_service': related_service,
            'duration_seconds': duration_seconds
        }
        self._event_buffer.append(event)

        # Log to Python logger too for debugging
        log_level = logging.DEBUG if importance == 'debug' else logging.INFO
        logger.log(log_level, f"[{event_type}] {description}")

    async def log_immediate(
        self,
        event_type: str,
        description: str,
        **kwargs
    ) -> int:
        """Log an event immediately (not buffered)"""
        if not self.pool:
            return -1

        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("""
                    INSERT INTO server_logs
                    (event_type, event_subtype, description, details,
                     importance, source, related_service, duration_seconds)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING id
                """, event_type, kwargs.get('event_subtype'),
                    description, json.dumps(kwargs.get('details', {})),
                    kwargs.get('importance', 'info'), kwargs.get('source', 'system'),
                    kwargs.get('related_service'), kwargs.get('duration_seconds'))
                return result
        except Exception as e:
            logger.error(f"Error logging event: {e}")
            return -1

    async def get_recent(
        self,
        hours: int = 24,
        event_type: str = None,
        min_importance: str = None,
        limit: int = 50
    ) -> list[ServerEvent]:
        """Get recent server events"""
        if not self.pool:
            return []

        try:
            async with self.pool.acquire() as conn:
                # Build query with proper parameter indexing
                params = []
                param_idx = 1

                # Base query with interval
                query = f"""
                    SELECT * FROM server_logs
                    WHERE timestamp > NOW() - INTERVAL '{int(hours)} hours'
                """

                if event_type:
                    query += f" AND event_type = ${param_idx}"
                    params.append(event_type)
                    param_idx += 1

                if min_importance:
                    importance_order = ['debug', 'info', 'notable', 'important', 'critical']
                    min_idx = importance_order.index(min_importance) if min_importance in importance_order else 0
                    valid_importances = importance_order[min_idx:]
                    query += f" AND importance = ANY(${param_idx}::text[])"
                    params.append(valid_importances)
                    param_idx += 1

                query += f" ORDER BY timestamp DESC LIMIT ${param_idx}"
                params.append(limit)

                rows = await conn.fetch(query, *params)

                return [ServerEvent(
                    id=row['id'],
                    timestamp=row['timestamp'],
                    event_type=row['event_type'],
                    event_subtype=row['event_subtype'],
                    description=row['description'],
                    details=row['details'] or {},
                    importance=row['importance'],
                    source=row['source'],
                    related_service=row['related_service'],
                    duration_seconds=row['duration_seconds']
                ) for row in rows]
        except Exception as e:
            logger.error(f"Error getting recent events: {e}")
            return []

    async def get_notable_events(self, hours: int = 24, limit: int = 10) -> list[ServerEvent]:
        """Get notable and important events"""
        return await self.get_recent(
            hours=hours,
            min_importance='notable',
            limit=limit
        )

    async def get_daily_summary(self, date: datetime = None) -> dict:
        """Get summary of a day's events"""
        if not self.pool:
            return {}

        if date is None:
            date = datetime.now()

        try:
            async with self.pool.acquire() as conn:
                # Get event counts by type
                type_counts = await conn.fetch("""
                    SELECT event_type, COUNT(*) as count
                    FROM server_logs
                    WHERE DATE(timestamp) = $1
                    GROUP BY event_type
                """, date.date())

                # Get important events
                important = await conn.fetch("""
                    SELECT description, event_type, importance, timestamp
                    FROM server_logs
                    WHERE DATE(timestamp) = $1
                      AND importance IN ('notable', 'important', 'critical')
                    ORDER BY timestamp DESC
                    LIMIT 10
                """, date.date())

                # Get service activity
                services = await conn.fetch("""
                    SELECT related_service, COUNT(*) as count
                    FROM server_logs
                    WHERE DATE(timestamp) = $1
                      AND related_service IS NOT NULL
                    GROUP BY related_service
                """, date.date())

                return {
                    "date": date.date().isoformat(),
                    "event_counts": {r['event_type']: r['count'] for r in type_counts},
                    "total_events": sum(r['count'] for r in type_counts),
                    "important_events": [dict(r) for r in important],
                    "service_activity": {r['related_service']: r['count'] for r in services}
                }
        except Exception as e:
            logger.error(f"Error getting daily summary: {e}")
            return {}

    async def get_context_for_llm(self, hours: int = 6, max_events: int = 15) -> str:
        """Get formatted server context for LLM prompts"""
        events = await self.get_recent(hours=hours, min_importance='info', limit=max_events)

        if not events:
            return "No notable activity on the server in the last few hours."

        lines = [f"## Server Activity (Last {hours} Hours)", ""]

        for event in events[:max_events]:
            time_str = event.timestamp.strftime("%H:%M") if event.timestamp else ""
            importance_emoji = {
                'debug': '🔍',
                'info': 'ℹ️',
                'notable': '📌',
                'important': '⚠️',
                'critical': '🚨'
            }.get(event.importance, 'ℹ️')

            line = f"- [{time_str}] {importance_emoji} {event.description}"
            if event.related_service:
                line += f" (service: {event.related_service})"
            lines.append(line)

        return "\n".join(lines)

    async def cleanup_old_logs(self, days: int = 30) -> int:
        """Delete logs older than specified days"""
        if not self.pool:
            return 0

        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute("""
                    DELETE FROM server_logs
                    WHERE timestamp < NOW() - INTERVAL '%s days'
                      AND importance NOT IN ('important', 'critical')
                """, days)
                deleted = int(result.split()[-1])
                logger.info(f"Cleaned up {deleted} old log entries")
                return deleted
        except Exception as e:
            logger.error(f"Error cleaning up logs: {e}")
            return 0

    async def stop(self):
        """Stop the logger and flush remaining events"""
        if self._buffer_flush_task:
            self._buffer_flush_task.cancel()
            try:
                await self._buffer_flush_task
            except asyncio.CancelledError:
                pass
        await self._flush_buffer()


# Global instance
server_logger = ServerLogger()
