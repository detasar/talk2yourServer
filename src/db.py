"""
Talk2YourServer - Database Module

Stores chat history, Claude sessions, and usage statistics.
Uses PostgreSQL with asyncpg for async operations.
"""

import asyncio
import functools
from datetime import datetime
from typing import Optional, Callable, TypeVar, ParamSpec

import asyncpg

from config import config


# Type hints for decorator
P = ParamSpec('P')
T = TypeVar('T')


def with_retry(max_retries: int = 3, base_delay: float = 0.5):
    """
    Decorator for retrying database operations with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries (doubles each attempt)
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except (asyncpg.PostgresConnectionError,
                        asyncpg.InterfaceError,
                        ConnectionRefusedError,
                        OSError) as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        print(f"DB retry {attempt + 1}/{max_retries} after {delay}s: {e}")
                        await asyncio.sleep(delay)
                    continue
                except Exception:
                    raise

            print(f"DB operation failed after {max_retries} retries: {last_exception}")
            raise last_exception
        return wrapper
    return decorator


class Database:
    """Async PostgreSQL database handler with connection pooling"""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.dsn = f"postgresql://{config.db_user}:{config.db_password}@{config.db_host}:{config.db_port}/{config.db_name}"

    async def connect(self) -> bool:
        """Initialize connection pool and create tables"""
        if self.pool is None:
            try:
                self.pool = await asyncpg.create_pool(
                    self.dsn,
                    min_size=1,
                    max_size=5
                )
                await self._create_tables()
                return True
            except Exception as e:
                print(f"Database connection failed: {e}")
                return False
        return True

    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def _create_tables(self):
        """Create tables if they don't exist"""
        async with self.pool.acquire() as conn:
            # Chat messages table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS telegram_messages (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username VARCHAR(255),
                    message_type VARCHAR(50) NOT NULL,
                    user_message TEXT NOT NULL,
                    bot_response TEXT,
                    provider VARCHAR(50),
                    model VARCHAR(100),
                    tokens_used INTEGER,
                    response_time_ms INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_telegram_messages_user_id
                ON telegram_messages(user_id);

                CREATE INDEX IF NOT EXISTS idx_telegram_messages_created_at
                ON telegram_messages(created_at);
            """)

            # Claude Code sessions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS claude_sessions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    session_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    session_end TIMESTAMP,
                    message_count INTEGER DEFAULT 0,
                    total_cost_usd DECIMAL(10, 4) DEFAULT 0,
                    working_directory TEXT,
                    is_active BOOLEAN DEFAULT TRUE
                );

                CREATE INDEX IF NOT EXISTS idx_claude_sessions_user_id
                ON claude_sessions(user_id);
            """)

            # Claude session messages
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS claude_session_messages (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER REFERENCES claude_sessions(id),
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    cost_usd DECIMAL(10, 4),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_claude_session_messages_session_id
                ON claude_session_messages(session_id);
            """)

            # Usage statistics (daily aggregates)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_stats (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    user_id BIGINT NOT NULL,
                    provider VARCHAR(50) NOT NULL,
                    request_count INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    estimated_cost_usd DECIMAL(10, 4) DEFAULT 0,
                    UNIQUE(date, user_id, provider)
                );

                CREATE INDEX IF NOT EXISTS idx_usage_stats_date
                ON usage_stats(date);
            """)

            # User memory/preferences table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_memory (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    memory_type VARCHAR(50) NOT NULL,
                    key VARCHAR(255) NOT NULL,
                    value TEXT,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, memory_type, key)
                );

                CREATE INDEX IF NOT EXISTS idx_user_memory_user_id
                ON user_memory(user_id);
            """)

            # Server events log
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS server_events (
                    id SERIAL PRIMARY KEY,
                    event_type VARCHAR(50) NOT NULL,
                    severity VARCHAR(20) NOT NULL,
                    message TEXT NOT NULL,
                    details JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_server_events_created_at
                ON server_events(created_at);

                CREATE INDEX IF NOT EXISTS idx_server_events_type
                ON server_events(event_type);
            """)

    @with_retry(max_retries=3)
    async def log_message(
        self,
        user_id: int,
        username: str,
        message_type: str,
        user_message: str,
        bot_response: str = None,
        provider: str = None,
        model: str = None,
        tokens_used: int = None,
        response_time_ms: int = None
    ) -> int:
        """Log a chat message to the database"""
        if not self.pool:
            return -1

        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("""
                    INSERT INTO telegram_messages
                    (user_id, username, message_type, user_message, bot_response,
                     provider, model, tokens_used, response_time_ms)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    RETURNING id
                """, user_id, username, message_type, user_message, bot_response,
                    provider, model, tokens_used, response_time_ms)
                return result
        except Exception as e:
            print(f"Error logging message: {e}")
            return -1

    @with_retry(max_retries=3)
    async def log_server_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        details: dict = None
    ):
        """Log a server event"""
        if not self.pool:
            return

        try:
            async with self.pool.acquire() as conn:
                import json
                await conn.execute("""
                    INSERT INTO server_events (event_type, severity, message, details)
                    VALUES ($1, $2, $3, $4)
                """, event_type, severity, message,
                    json.dumps(details) if details else None)
        except Exception as e:
            print(f"Error logging server event: {e}")

    @with_retry(max_retries=3)
    async def start_claude_session(self, user_id: int, working_dir: str = None) -> int:
        """Start a new Claude Code session"""
        if not self.pool:
            return -1

        try:
            async with self.pool.acquire() as conn:
                # End any active sessions for this user
                await conn.execute("""
                    UPDATE claude_sessions
                    SET is_active = FALSE, session_end = CURRENT_TIMESTAMP
                    WHERE user_id = $1 AND is_active = TRUE
                """, user_id)

                # Start new session
                result = await conn.fetchval("""
                    INSERT INTO claude_sessions (user_id, working_directory)
                    VALUES ($1, $2)
                    RETURNING id
                """, user_id, working_dir)
                return result
        except Exception as e:
            print(f"Error starting Claude session: {e}")
            return -1

    async def get_active_claude_session(self, user_id: int) -> Optional[int]:
        """Get active Claude session ID for user"""
        if not self.pool:
            return None

        try:
            async with self.pool.acquire() as conn:
                return await conn.fetchval("""
                    SELECT id FROM claude_sessions
                    WHERE user_id = $1 AND is_active = TRUE
                    ORDER BY session_start DESC
                    LIMIT 1
                """, user_id)
        except:
            return None

    @with_retry(max_retries=3)
    async def add_claude_message(
        self,
        session_id: int,
        role: str,
        content: str,
        cost_usd: float = None
    ):
        """Add message to Claude session"""
        if not self.pool or session_id < 0:
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO claude_session_messages (session_id, role, content, cost_usd)
                    VALUES ($1, $2, $3, $4)
                """, session_id, role, content, cost_usd)

                # Update session stats
                await conn.execute("""
                    UPDATE claude_sessions
                    SET message_count = message_count + 1,
                        total_cost_usd = total_cost_usd + COALESCE($2, 0)
                    WHERE id = $1
                """, session_id, cost_usd)
        except Exception as e:
            print(f"Error adding Claude message: {e}")

    async def end_claude_session(self, session_id: int):
        """End a Claude session"""
        if not self.pool or session_id < 0:
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE claude_sessions
                    SET is_active = FALSE, session_end = CURRENT_TIMESTAMP
                    WHERE id = $1
                """, session_id)
        except Exception as e:
            print(f"Error ending Claude session: {e}")

    @with_retry(max_retries=3)
    async def update_usage_stats(
        self,
        user_id: int,
        provider: str,
        tokens: int = 0,
        cost_usd: float = 0
    ):
        """Update daily usage statistics"""
        if not self.pool:
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO usage_stats (date, user_id, provider, request_count, total_tokens, estimated_cost_usd)
                    VALUES (CURRENT_DATE, $1, $2, 1, $3, $4)
                    ON CONFLICT (date, user_id, provider)
                    DO UPDATE SET
                        request_count = usage_stats.request_count + 1,
                        total_tokens = usage_stats.total_tokens + $3,
                        estimated_cost_usd = usage_stats.estimated_cost_usd + $4
                """, user_id, provider, tokens, cost_usd)
        except Exception as e:
            print(f"Error updating usage stats: {e}")

    async def get_user_stats(self, user_id: int, days: int = 7) -> dict:
        """Get usage statistics for a user"""
        if not self.pool:
            return {}

        try:
            async with self.pool.acquire() as conn:
                # Message counts
                messages = await conn.fetch("""
                    SELECT message_type, COUNT(*) as count
                    FROM telegram_messages
                    WHERE user_id = $1 AND created_at > CURRENT_DATE - $2
                    GROUP BY message_type
                """, user_id, days)

                # Provider usage
                providers = await conn.fetch("""
                    SELECT provider, SUM(request_count) as requests,
                           SUM(total_tokens) as tokens,
                           SUM(estimated_cost_usd) as cost
                    FROM usage_stats
                    WHERE user_id = $1 AND date > CURRENT_DATE - $2
                    GROUP BY provider
                """, user_id, days)

                # Claude sessions
                claude = await conn.fetchrow("""
                    SELECT COUNT(*) as sessions,
                           SUM(message_count) as messages,
                           SUM(total_cost_usd) as cost
                    FROM claude_sessions
                    WHERE user_id = $1 AND session_start > CURRENT_DATE - $2
                """, user_id, days)

                return {
                    "messages": {r["message_type"]: r["count"] for r in messages},
                    "providers": {r["provider"]: {
                        "requests": r["requests"],
                        "tokens": r["tokens"],
                        "cost": float(r["cost"] or 0)
                    } for r in providers},
                    "claude": {
                        "sessions": claude["sessions"] if claude else 0,
                        "messages": claude["messages"] if claude else 0,
                        "cost": float(claude["cost"] or 0) if claude else 0
                    }
                }
        except Exception as e:
            print(f"Error getting user stats: {e}")
            return {}

    async def get_recent_messages(self, user_id: int, limit: int = 20) -> list:
        """Get recent messages for a user"""
        if not self.pool:
            return []

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT message_type, user_message, bot_response, provider, created_at
                    FROM telegram_messages
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                """, user_id, limit)
                return [dict(r) for r in rows]
        except:
            return []

    async def get_chat_history(self, user_id: int, limit: int = 10) -> list:
        """Get formatted chat history for display"""
        if not self.pool:
            return []

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, message_type, user_message, bot_response,
                           provider, response_time_ms, created_at
                    FROM telegram_messages
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                """, user_id, limit)
                return [dict(r) for r in rows]
        except Exception as e:
            print(f"Error getting chat history: {e}")
            return []

    async def get_message_count(self, user_id: int) -> int:
        """Get total message count for user"""
        if not self.pool:
            return 0

        try:
            async with self.pool.acquire() as conn:
                return await conn.fetchval("""
                    SELECT COUNT(*) FROM telegram_messages
                    WHERE user_id = $1
                """, user_id)
        except:
            return 0

    @with_retry(max_retries=3)
    async def get_claude_session_state(self, user_id: int) -> bool:
        """Check if user has an active Claude session"""
        if not self.pool:
            return False

        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("""
                    SELECT is_active FROM claude_sessions
                    WHERE user_id = $1 AND is_active = TRUE
                    ORDER BY session_start DESC
                    LIMIT 1
                """, user_id)
                return bool(result)
        except Exception as e:
            print(f"Error getting claude session state: {e}")
            return False

    @with_retry(max_retries=3)
    async def set_claude_session_active(self, user_id: int, active: bool) -> bool:
        """Set Claude session state for a user"""
        if not self.pool:
            return False

        try:
            async with self.pool.acquire() as conn:
                if active:
                    existing = await conn.fetchval("""
                        SELECT id FROM claude_sessions
                        WHERE user_id = $1 AND is_active = TRUE
                    """, user_id)

                    if not existing:
                        await conn.execute("""
                            INSERT INTO claude_sessions (user_id, is_active)
                            VALUES ($1, TRUE)
                        """, user_id)
                else:
                    await conn.execute("""
                        UPDATE claude_sessions
                        SET is_active = FALSE, session_end = CURRENT_TIMESTAMP
                        WHERE user_id = $1 AND is_active = TRUE
                    """, user_id)
                return True
        except Exception as e:
            print(f"Error setting claude session state: {e}")
            return False

    # User Memory Methods
    @with_retry(max_retries=3)
    async def set_user_memory(
        self,
        user_id: int,
        memory_type: str,
        key: str,
        value: str,
        metadata: dict = None
    ):
        """Store a user memory/preference"""
        if not self.pool:
            return

        try:
            async with self.pool.acquire() as conn:
                import json
                await conn.execute("""
                    INSERT INTO user_memory (user_id, memory_type, key, value, metadata)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (user_id, memory_type, key)
                    DO UPDATE SET
                        value = $4,
                        metadata = $5,
                        updated_at = CURRENT_TIMESTAMP
                """, user_id, memory_type, key, value,
                    json.dumps(metadata) if metadata else None)
        except Exception as e:
            print(f"Error setting user memory: {e}")

    async def get_user_memory(
        self,
        user_id: int,
        memory_type: str = None,
        key: str = None
    ) -> list:
        """Get user memories, optionally filtered"""
        if not self.pool:
            return []

        try:
            async with self.pool.acquire() as conn:
                if memory_type and key:
                    rows = await conn.fetch("""
                        SELECT * FROM user_memory
                        WHERE user_id = $1 AND memory_type = $2 AND key = $3
                    """, user_id, memory_type, key)
                elif memory_type:
                    rows = await conn.fetch("""
                        SELECT * FROM user_memory
                        WHERE user_id = $1 AND memory_type = $2
                    """, user_id, memory_type)
                else:
                    rows = await conn.fetch("""
                        SELECT * FROM user_memory
                        WHERE user_id = $1
                    """, user_id)
                return [dict(r) for r in rows]
        except Exception as e:
            print(f"Error getting user memory: {e}")
            return []

    async def get_recent_server_events(self, limit: int = 50, event_type: str = None) -> list:
        """Get recent server events"""
        if not self.pool:
            return []

        try:
            async with self.pool.acquire() as conn:
                if event_type:
                    rows = await conn.fetch("""
                        SELECT * FROM server_events
                        WHERE event_type = $1
                        ORDER BY created_at DESC
                        LIMIT $2
                    """, event_type, limit)
                else:
                    rows = await conn.fetch("""
                        SELECT * FROM server_events
                        ORDER BY created_at DESC
                        LIMIT $1
                    """, limit)
                return [dict(r) for r in rows]
        except Exception as e:
            print(f"Error getting server events: {e}")
            return []


# Global database instance
db = Database()
