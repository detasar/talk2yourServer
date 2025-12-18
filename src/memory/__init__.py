"""
Memory System for Personal AI Assistant

Provides:
- Persistent memory about user (preferences, interests, goals)
- Server activity logging
- Conversation insight extraction
- Proactive AI agent for personalized messages
"""

from .manager import MemoryManager, memory_manager
from .server_logger import ServerLogger, server_logger
from .proactive_agent import ProactiveAgent, proactive_agent
from .analyzer import ConversationAnalyzer, conversation_analyzer

__all__ = [
    "MemoryManager", "memory_manager",
    "ServerLogger", "server_logger",
    "ProactiveAgent", "proactive_agent",
    "ConversationAnalyzer", "conversation_analyzer"
]
