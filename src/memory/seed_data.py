"""
Seed Data for User Memory

Initial knowledge base template to bootstrap the memory system.
This file should be customized with actual user information before use.
"""

import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Template memories - customize these with actual user information
SEED_MEMORIES = [
    # ========== PERSONAL ==========
    {
        "category": "personal",
        "key": "full_name",
        "value": "User Full Name",
        "importance": 10,
        "confidence": 1.0
    },
    {
        "category": "personal",
        "key": "birthday",
        "value": "January 1, 1990",
        "importance": 9,
        "confidence": 1.0
    },
    {
        "category": "personal",
        "key": "languages",
        "value": "English (native), Spanish (fluent)",
        "importance": 8,
        "confidence": 1.0
    },

    # ========== LOCATION ==========
    {
        "category": "location",
        "key": "current_city",
        "value": "City, Country",
        "importance": 9,
        "confidence": 1.0
    },

    # ========== PROFESSIONAL ==========
    {
        "category": "professional",
        "key": "current_job",
        "value": "Job Title at Company",
        "importance": 10,
        "confidence": 1.0
    },
    {
        "category": "professional",
        "key": "work_focus",
        "value": "AI/ML, Software Development",
        "importance": 9,
        "confidence": 1.0
    },

    # ========== INTERESTS ==========
    {
        "category": "interests",
        "key": "primary_interest",
        "value": "Artificial Intelligence and Machine Learning",
        "importance": 10,
        "confidence": 1.0
    },
    {
        "category": "interests",
        "key": "technology",
        "value": "Open source software, cloud computing, automation",
        "importance": 9,
        "confidence": 1.0
    },

    # ========== GOALS ==========
    {
        "category": "goals",
        "key": "career_goal",
        "value": "Lead technical teams and drive AI innovation",
        "importance": 10,
        "confidence": 1.0
    },

    # ========== SKILLS ==========
    {
        "category": "skills",
        "key": "programming_languages",
        "value": "Python (expert), JavaScript, SQL",
        "importance": 9,
        "confidence": 1.0
    },
    {
        "category": "skills",
        "key": "ml_frameworks",
        "value": "PyTorch, TensorFlow, scikit-learn",
        "importance": 9,
        "confidence": 1.0
    },

    # ========== PROJECTS ==========
    {
        "category": "projects",
        "key": "ai_server",
        "value": "Personal AI server with GPU for ML experiments",
        "importance": 9,
        "confidence": 1.0
    },

    # ========== PREFERENCES ==========
    {
        "category": "preferences",
        "key": "communication_style",
        "value": "Direct and technical, avoid unnecessary formality",
        "importance": 8,
        "confidence": 1.0
    },
]


async def load_seed_data(memory_manager) -> int:
    """
    Load all seed data into memory.
    Returns number of memories loaded.
    """
    loaded = 0

    for memory in SEED_MEMORIES:
        try:
            result = await memory_manager.add(
                category=memory["category"],
                key=memory["key"],
                value=memory["value"],
                source="seed",
                confidence=memory.get("confidence", 1.0),
                importance=memory.get("importance", 5)
            )

            if result:
                loaded += 1
                logger.debug(f"Loaded: {memory['category']}:{memory['key']}")

        except Exception as e:
            logger.error(f"Failed to load {memory['category']}:{memory['key']}: {e}")

    logger.info(f"Seed data loaded: {loaded}/{len(SEED_MEMORIES)} memories")
    return loaded


async def check_and_load_seed_data(memory_manager) -> bool:
    """
    Check if seed data is already loaded, if not load it.
    Returns True if data was loaded, False if already exists.
    """
    # Check if we have any seed data
    existing = await memory_manager.get("personal", "full_name")

    if existing:
        logger.info("Seed data already exists, skipping load")
        return False

    logger.info("No seed data found, loading initial memories...")
    await load_seed_data(memory_manager)
    return True
