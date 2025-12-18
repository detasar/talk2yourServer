"""
Memory Manager

Manages user's personal knowledge base - facts, preferences, interests, and goals.
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class MemoryCategory(Enum):
    """Categories for organizing memories"""
    PERSONAL = "personal"           # Personal info (birth date, height, weight)
    PROFESSIONAL = "professional"   # Work and career
    ACADEMIC = "academic"           # Academic (PhD, research)
    INTERESTS = "interests"         # Areas of interest
    PREFERENCES = "preferences"     # Preferences
    GOALS = "goals"                 # Goals
    HEALTH = "health"               # Health
    LOCATION = "location"           # Location
    SOCIAL = "social"               # Social relationships
    SKILLS = "skills"               # Skills
    PROJECTS = "projects"           # Projects
    HABITS = "habits"               # Habits


class MemorySource(Enum):
    """Sources of memory information"""
    SEED = "seed"                   # Initial data
    CONVERSATION = "conversation"   # Extracted from conversations
    OBSERVATION = "observation"     # Observed from behavior
    LLM_INFERENCE = "llm_inference" # Inferred by LLM
    MANUAL = "manual"               # Manually added


@dataclass
class Memory:
    """Represents a single memory entry"""
    id: int = 0
    category: str = ""
    subcategory: Optional[str] = None
    key: str = ""
    value: str = ""
    metadata: dict = field(default_factory=dict)
    source: str = "manual"
    confidence: float = 1.0
    importance: int = 5
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    access_count: int = 0
    is_active: bool = True


class MemoryManager:
    """Manages user's memory database"""

    def __init__(self):
        self.pool = None
        self._cache: dict[str, Memory] = {}
        self._initialized = False

    async def initialize(self, pool) -> bool:
        """Initialize with database pool and create tables"""
        self.pool = pool
        if not self.pool:
            logger.warning("No database pool provided to MemoryManager")
            return False

        try:
            await self._create_tables()
            await self._load_cache()
            self._initialized = True
            logger.info(f"MemoryManager initialized with {len(self._cache)} memories")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize MemoryManager: {e}")
            return False

    async def _create_tables(self):
        """Create memory tables if they don't exist"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_memory (
                    id SERIAL PRIMARY KEY,
                    category VARCHAR(50) NOT NULL,
                    subcategory VARCHAR(100),
                    key VARCHAR(255) NOT NULL,
                    value TEXT NOT NULL,
                    metadata JSONB DEFAULT '{}',
                    source VARCHAR(50) NOT NULL DEFAULT 'manual',
                    confidence FLOAT DEFAULT 1.0,
                    importance INTEGER DEFAULT 5,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    last_accessed_at TIMESTAMP WITH TIME ZONE,
                    access_count INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    related_memories INTEGER[],
                    UNIQUE(category, key)
                );

                CREATE INDEX IF NOT EXISTS idx_memory_category ON user_memory(category);
                CREATE INDEX IF NOT EXISTS idx_memory_importance ON user_memory(importance DESC);
                CREATE INDEX IF NOT EXISTS idx_memory_active ON user_memory(is_active);
            """)

    async def _load_cache(self):
        """Load all active memories into cache"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM user_memory WHERE is_active = TRUE
            """)
            for row in rows:
                key = f"{row['category']}:{row['key']}"
                self._cache[key] = Memory(
                    id=row['id'],
                    category=row['category'],
                    subcategory=row['subcategory'],
                    key=row['key'],
                    value=row['value'],
                    metadata=row['metadata'] or {},
                    source=row['source'],
                    confidence=row['confidence'],
                    importance=row['importance'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    access_count=row['access_count'],
                    is_active=row['is_active']
                )

    async def add(
        self,
        category: str,
        key: str,
        value: str,
        subcategory: str = None,
        metadata: dict = None,
        source: str = "manual",
        confidence: float = 1.0,
        importance: int = 5
    ) -> Optional[int]:
        """Add a new memory or update if exists"""
        if not self.pool:
            return None

        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("""
                    INSERT INTO user_memory
                    (category, subcategory, key, value, metadata, source, confidence, importance)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (category, key)
                    DO UPDATE SET
                        value = EXCLUDED.value,
                        metadata = COALESCE(user_memory.metadata, '{}') || EXCLUDED.metadata,
                        source = EXCLUDED.source,
                        confidence = GREATEST(user_memory.confidence, EXCLUDED.confidence),
                        importance = GREATEST(user_memory.importance, EXCLUDED.importance),
                        updated_at = NOW()
                    RETURNING id
                """, category, subcategory, key, value,
                    json.dumps(metadata or {}), source, confidence, importance)

                # Update cache
                cache_key = f"{category}:{key}"
                self._cache[cache_key] = Memory(
                    id=result,
                    category=category,
                    subcategory=subcategory,
                    key=key,
                    value=value,
                    metadata=metadata or {},
                    source=source,
                    confidence=confidence,
                    importance=importance
                )

                logger.debug(f"Memory added/updated: {category}:{key}")
                return result
        except Exception as e:
            logger.error(f"Error adding memory: {e}")
            return None

    async def get(self, category: str, key: str) -> Optional[Memory]:
        """Get a specific memory"""
        cache_key = f"{category}:{key}"

        if cache_key in self._cache:
            memory = self._cache[cache_key]
            # Update access count asynchronously
            asyncio.create_task(self._update_access(memory.id))
            return memory

        if not self.pool:
            return None

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT * FROM user_memory
                    WHERE category = $1 AND key = $2 AND is_active = TRUE
                """, category, key)

                if row:
                    memory = Memory(
                        id=row['id'],
                        category=row['category'],
                        subcategory=row['subcategory'],
                        key=row['key'],
                        value=row['value'],
                        metadata=row['metadata'] or {},
                        source=row['source'],
                        confidence=row['confidence'],
                        importance=row['importance'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at'],
                        access_count=row['access_count'],
                        is_active=row['is_active']
                    )
                    self._cache[cache_key] = memory
                    asyncio.create_task(self._update_access(memory.id))
                    return memory
        except Exception as e:
            logger.error(f"Error getting memory: {e}")

        return None

    async def _update_access(self, memory_id: int):
        """Update access count and timestamp"""
        if not self.pool:
            return
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE user_memory
                    SET access_count = access_count + 1,
                        last_accessed_at = NOW()
                    WHERE id = $1
                """, memory_id)
        except:
            pass

    async def get_by_category(self, category: str, limit: int = 50) -> list[Memory]:
        """Get all memories in a category"""
        result = []

        # First check cache
        for key, memory in self._cache.items():
            if memory.category == category and memory.is_active:
                result.append(memory)

        if len(result) >= limit:
            return sorted(result, key=lambda m: m.importance, reverse=True)[:limit]

        # If not enough in cache, query DB
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    rows = await conn.fetch("""
                        SELECT * FROM user_memory
                        WHERE category = $1 AND is_active = TRUE
                        ORDER BY importance DESC
                        LIMIT $2
                    """, category, limit)

                    for row in rows:
                        cache_key = f"{row['category']}:{row['key']}"
                        if cache_key not in self._cache:
                            memory = Memory(
                                id=row['id'],
                                category=row['category'],
                                subcategory=row['subcategory'],
                                key=row['key'],
                                value=row['value'],
                                metadata=row['metadata'] or {},
                                source=row['source'],
                                confidence=row['confidence'],
                                importance=row['importance'],
                                created_at=row['created_at'],
                                updated_at=row['updated_at'],
                                access_count=row['access_count'],
                                is_active=row['is_active']
                            )
                            self._cache[cache_key] = memory
                            result.append(memory)
            except Exception as e:
                logger.error(f"Error getting memories by category: {e}")

        return sorted(result, key=lambda m: m.importance, reverse=True)[:limit]

    async def get_all(self, limit: int = 100) -> list[Memory]:
        """Get all active memories"""
        return list(self._cache.values())[:limit]

    async def get_important(self, min_importance: int = 7, limit: int = 20) -> list[Memory]:
        """Get high-importance memories"""
        result = [m for m in self._cache.values()
                  if m.importance >= min_importance and m.is_active]
        return sorted(result, key=lambda m: m.importance, reverse=True)[:limit]

    async def search(self, query: str, limit: int = 10) -> list[Memory]:
        """Search memories by value content"""
        query_lower = query.lower()
        result = []

        for memory in self._cache.values():
            if memory.is_active:
                if query_lower in memory.value.lower() or query_lower in memory.key.lower():
                    result.append(memory)

        return sorted(result, key=lambda m: m.importance, reverse=True)[:limit]

    async def update_value(self, category: str, key: str, new_value: str) -> bool:
        """Update memory value"""
        if not self.pool:
            return False

        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE user_memory
                    SET value = $3, updated_at = NOW()
                    WHERE category = $1 AND key = $2
                """, category, key, new_value)

                cache_key = f"{category}:{key}"
                if cache_key in self._cache:
                    self._cache[cache_key].value = new_value

                return True
        except Exception as e:
            logger.error(f"Error updating memory: {e}")
            return False

    async def delete(self, category: str, key: str) -> bool:
        """Soft delete a memory (set inactive)"""
        if not self.pool:
            return False

        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE user_memory
                    SET is_active = FALSE, updated_at = NOW()
                    WHERE category = $1 AND key = $2
                """, category, key)

                cache_key = f"{category}:{key}"
                if cache_key in self._cache:
                    del self._cache[cache_key]

                return True
        except Exception as e:
            logger.error(f"Error deleting memory: {e}")
            return False

    async def get_context_for_llm(self, categories: list[str] = None, max_tokens: int = 2000) -> str:
        """
        Get formatted memory context for LLM prompts.
        Prioritizes by importance and recency.
        """
        if categories:
            memories = []
            for cat in categories:
                memories.extend(await self.get_by_category(cat, limit=20))
        else:
            memories = await self.get_important(min_importance=5, limit=50)

        # Sort by importance
        memories = sorted(memories, key=lambda m: m.importance, reverse=True)

        # Build context string
        lines = ["## User Information", ""]

        current_category = None
        char_count = 0
        max_chars = max_tokens * 4  # Rough estimate

        for memory in memories:
            if char_count > max_chars:
                break

            if memory.category != current_category:
                current_category = memory.category
                lines.append(f"\n### {current_category.title()}")

            line = f"- **{memory.key}**: {memory.value}"
            lines.append(line)
            char_count += len(line)

        return "\n".join(lines)

    async def get_summary_stats(self) -> dict:
        """Get summary statistics about memory"""
        stats = {
            "total": len(self._cache),
            "by_category": {},
            "by_source": {},
            "avg_importance": 0
        }

        if not self._cache:
            return stats

        importance_sum = 0
        for memory in self._cache.values():
            stats["by_category"][memory.category] = stats["by_category"].get(memory.category, 0) + 1
            stats["by_source"][memory.source] = stats["by_source"].get(memory.source, 0) + 1
            importance_sum += memory.importance

        stats["avg_importance"] = importance_sum / len(self._cache)
        return stats


# Global instance
memory_manager = MemoryManager()
