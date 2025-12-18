"""
Conversation Analyzer

Extracts insights from conversations and updates user's memory.
Uses LLM to understand context and extract meaningful information.
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Insight:
    """Represents an extracted insight"""
    insight_type: str      # preference, interest, goal, task, fact, opinion
    category: str          # maps to memory categories
    key: str               # memory key
    value: str             # memory value
    confidence: float      # 0.0 - 1.0
    importance: int        # 1-10


class ConversationAnalyzer:
    """
    Analyzes conversations to extract insights about the user.

    Runs asynchronously after each conversation to:
    1. Extract new facts/preferences
    2. Update existing memory
    3. Identify goals and interests
    4. Track conversation patterns
    """

    def __init__(self):
        self.memory_manager = None
        self.pool = None
        self._initialized = False
        self._pending_analyses: list[dict] = []
        self._analysis_task: Optional[asyncio.Task] = None

    async def initialize(self, pool, memory_manager) -> bool:
        """Initialize with database pool and memory manager"""
        self.pool = pool
        self.memory_manager = memory_manager

        if not self.pool:
            logger.warning("No database pool provided to ConversationAnalyzer")
            return False

        try:
            await self._create_tables()
            self._initialized = True
            self._analysis_task = asyncio.create_task(self._analysis_loop())
            logger.info("ConversationAnalyzer initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize ConversationAnalyzer: {e}")
            return False

    async def _create_tables(self):
        """Create insight tables"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_insights (
                    id SERIAL PRIMARY KEY,
                    message_id INTEGER,
                    conversation_date DATE DEFAULT CURRENT_DATE,
                    insight_type VARCHAR(50) NOT NULL,
                    category VARCHAR(50),
                    content TEXT NOT NULL,
                    extracted_entities JSONB DEFAULT '[]',
                    sentiment VARCHAR(20),
                    confidence FLOAT DEFAULT 0.8,
                    extracted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    processed BOOLEAN DEFAULT FALSE,
                    applied_to_memory BOOLEAN DEFAULT FALSE,
                    memory_id INTEGER
                );

                CREATE INDEX IF NOT EXISTS idx_insights_date
                ON conversation_insights(conversation_date DESC);
                CREATE INDEX IF NOT EXISTS idx_insights_processed
                ON conversation_insights(processed);
            """)

    async def _analysis_loop(self):
        """Background loop for processing pending analyses"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                if self._pending_analyses:
                    analyses = self._pending_analyses.copy()
                    self._pending_analyses.clear()

                    for analysis in analyses:
                        await self._process_analysis(analysis)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in analysis loop: {e}")

    async def analyze_conversation(
        self,
        user_message: str,
        bot_response: str,
        message_id: int = None
    ):
        """
        Queue a conversation for analysis.
        Analysis happens asynchronously to not block the main flow.
        """
        self._pending_analyses.append({
            'user_message': user_message,
            'bot_response': bot_response,
            'message_id': message_id,
            'timestamp': datetime.now()
        })

    async def _process_analysis(self, analysis: dict):
        """Process a single conversation analysis"""
        try:
            # Extract insights using LLM
            insights = await self._extract_insights(
                analysis['user_message'],
                analysis['bot_response']
            )

            if not insights:
                return

            # Save insights to database
            for insight in insights:
                await self._save_insight(insight, analysis.get('message_id'))

                # Apply to memory if confidence is high enough
                if insight.confidence >= 0.7:
                    await self._apply_to_memory(insight)

        except Exception as e:
            logger.error(f"Error processing analysis: {e}")

    async def _extract_insights(
        self,
        user_message: str,
        bot_response: str
    ) -> list[Insight]:
        """Extract insights from conversation using LLM"""

        # Skip very short messages
        if len(user_message) < 20:
            return []

        prompt = f"""Analyze the following conversation and extract important information.

CONVERSATION:
User: {user_message}
Assistant: {bot_response}

Extract the following information (if present):
1. Preferences - Things the user likes/dislikes
2. Interests - Topics they're interested in
3. Goals - Things they want to do
4. Facts - Information they shared about themselves
5. Tasks - Things they plan to do

Return JSON in this format for each piece of information:
[
  {{
    "type": "preference|interest|goal|fact|task",
    "category": "personal|professional|academic|interests|preferences|goals|health|location|social|skills|projects",
    "key": "short_key",
    "value": "description of the information",
    "confidence": 0.0-1.0,
    "importance": 1-10
  }}
]

Do NOT add insignificant or unclear information. Only extract clear and meaningful facts.
If nothing is found, return empty array: []
"""

        try:
            from llm.router import llm_router

            response, _ = await llm_router.chat(
                prompt=prompt,
                system="You are a conversation analysis assistant. You extract meaningful information from conversations. Only return JSON, no other explanation."
            )

            # Parse JSON from response
            insights = self._parse_insights_response(response)
            return insights

        except Exception as e:
            logger.error(f"Error extracting insights: {e}")
            return []

    def _parse_insights_response(self, response: str) -> list[Insight]:
        """Parse LLM response into Insight objects"""
        insights = []

        try:
            # Find JSON array in response
            start = response.find('[')
            end = response.rfind(']') + 1

            if start == -1 or end == 0:
                return []

            json_str = response[start:end]
            data = json.loads(json_str)

            for item in data:
                if not all(k in item for k in ['type', 'category', 'key', 'value']):
                    continue

                insights.append(Insight(
                    insight_type=item['type'],
                    category=item['category'],
                    key=item['key'],
                    value=item['value'],
                    confidence=item.get('confidence', 0.8),
                    importance=item.get('importance', 5)
                ))

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse insights JSON: {e}")
        except Exception as e:
            logger.error(f"Error parsing insights: {e}")

        return insights

    async def _save_insight(self, insight: Insight, message_id: int = None):
        """Save insight to database"""
        if not self.pool:
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO conversation_insights
                    (message_id, insight_type, category, content, confidence)
                    VALUES ($1, $2, $3, $4, $5)
                """, message_id, insight.insight_type, insight.category,
                    f"{insight.key}: {insight.value}", insight.confidence)
        except Exception as e:
            logger.error(f"Error saving insight: {e}")

    async def _apply_to_memory(self, insight: Insight):
        """Apply insight to memory"""
        if not self.memory_manager:
            return

        try:
            await self.memory_manager.add(
                category=insight.category,
                key=insight.key,
                value=insight.value,
                source='conversation',
                confidence=insight.confidence,
                importance=insight.importance
            )
            logger.debug(f"Applied insight to memory: {insight.category}:{insight.key}")
        except Exception as e:
            logger.error(f"Error applying insight to memory: {e}")

    async def get_recent_insights(self, days: int = 7, limit: int = 20) -> list[dict]:
        """Get recent insights"""
        if not self.pool:
            return []

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM conversation_insights
                    WHERE conversation_date > CURRENT_DATE - $1
                    ORDER BY extracted_at DESC
                    LIMIT $2
                """, days, limit)
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Error getting recent insights: {e}")
            return []

    async def get_insight_stats(self) -> dict:
        """Get insight statistics"""
        if not self.pool:
            return {}

        try:
            async with self.pool.acquire() as conn:
                # Count by type
                type_counts = await conn.fetch("""
                    SELECT insight_type, COUNT(*) as count
                    FROM conversation_insights
                    WHERE conversation_date > CURRENT_DATE - 30
                    GROUP BY insight_type
                """)

                # Count by category
                category_counts = await conn.fetch("""
                    SELECT category, COUNT(*) as count
                    FROM conversation_insights
                    WHERE conversation_date > CURRENT_DATE - 30
                    GROUP BY category
                """)

                return {
                    "by_type": {r['insight_type']: r['count'] for r in type_counts},
                    "by_category": {r['category']: r['count'] for r in category_counts}
                }
        except Exception as e:
            logger.error(f"Error getting insight stats: {e}")
            return {}

    async def stop(self):
        """Stop the analyzer"""
        if self._analysis_task:
            self._analysis_task.cancel()
            try:
                await self._analysis_task
            except asyncio.CancelledError:
                pass


# Global instance
conversation_analyzer = ConversationAnalyzer()
