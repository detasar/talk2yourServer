"""
Memory Management Commands

Telegram commands for viewing and managing user memory.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from security import require_auth, require_admin
from memory import memory_manager, server_logger, proactive_agent, conversation_analyzer

logger = logging.getLogger(__name__)


@require_admin
async def cmd_memory_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /memory - View memory contents

    Usage:
        /memory              - Show memory summary
        /memory <category>   - Show memories in category
        /memory search <query>  - Search memories
    """
    args = context.args

    if not args:
        # Show summary
        stats = await memory_manager.get_summary_stats()

        lines = [
            "🧠 **User Memory - Summary**\n",
            f"📊 Total: {stats.get('total', 0)} memory entries\n",
            "📁 **Categories:**"
        ]

        by_category = stats.get('by_category', {})
        for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
            lines.append(f"  • {cat}: {count}")

        lines.extend([
            "\n🔍 **Commands:**",
            "  `/memory personal` - Personal info",
            "  `/memory professional` - Work info",
            "  `/memory interests` - Interests",
            "  `/memory goals` - Goals",
            "  `/memory search <keyword>` - Search"
        ])

        await update.message.reply_text("\n".join(lines), parse_mode='Markdown')
        return

    # Search
    if args[0] == "search" and len(args) > 1:
        query = " ".join(args[1:])
        memories = await memory_manager.search(query, limit=10)

        if not memories:
            await update.message.reply_text(f"❌ No results for '{query}'")
            return

        lines = [f"🔍 **Search: '{query}'**\n"]
        for m in memories:
            importance_stars = "⭐" * min(m.importance // 2, 5)
            lines.append(f"**{m.category}:{m.key}** {importance_stars}")
            lines.append(f"  {m.value[:100]}{'...' if len(m.value) > 100 else ''}\n")

        await update.message.reply_text("\n".join(lines), parse_mode='Markdown')
        return

    # View category
    category = args[0].lower()
    memories = await memory_manager.get_by_category(category, limit=20)

    if not memories:
        await update.message.reply_text(f"❌ No memories found in '{category}' category")
        return

    lines = [f"🧠 **{category.title()} Memory**\n"]
    for m in memories:
        importance_stars = "⭐" * min(m.importance // 2, 5)
        lines.append(f"**{m.key}** {importance_stars}")
        lines.append(f"  {m.value[:150]}{'...' if len(m.value) > 150 else ''}")
        if m.source != 'seed':
            lines.append(f"  _Source: {m.source}_")
        lines.append("")

    # Truncate if too long
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3900] + "\n\n...(truncated)"

    await update.message.reply_text(text, parse_mode='Markdown')


@require_admin
async def cmd_memory_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /memory_add <category> <key> <value>

    Add or update a memory manually.
    """
    args = context.args

    if len(args) < 3:
        await update.message.reply_text(
            "Usage: `/memory_add <category> <key> <value>`\n\n"
            "Example: `/memory_add interests new_hobby Learning chess`",
            parse_mode='Markdown'
        )
        return

    category = args[0].lower()
    key = args[1].lower().replace(" ", "_")
    value = " ".join(args[2:])

    result = await memory_manager.add(
        category=category,
        key=key,
        value=value,
        source="manual",
        confidence=1.0,
        importance=6
    )

    if result:
        await update.message.reply_text(
            f"✅ Memory added:\n"
            f"**{category}:{key}**\n"
            f"{value}",
            parse_mode='Markdown'
        )

        # Log the event
        server_logger.log(
            event_type='ai_task',
            event_subtype='memory_add',
            description=f'Manual memory added: {category}:{key}',
            importance='info',
            source='telegram_bot'
        )
    else:
        await update.message.reply_text("❌ Failed to add memory")


@require_admin
async def cmd_memory_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /memory_delete <category> <key>

    Delete a memory.
    """
    args = context.args

    if len(args) < 2:
        await update.message.reply_text(
            "Usage: `/memory_delete <category> <key>`\n\n"
            "Example: `/memory_delete interests old_hobby`",
            parse_mode='Markdown'
        )
        return

    category = args[0].lower()
    key = args[1].lower()

    # Check if exists
    existing = await memory_manager.get(category, key)
    if not existing:
        await update.message.reply_text(f"❌ Memory not found: {category}:{key}")
        return

    result = await memory_manager.delete(category, key)

    if result:
        await update.message.reply_text(
            f"✅ Memory deleted: **{category}:{key}**",
            parse_mode='Markdown'
        )

        # Log the event
        server_logger.log(
            event_type='ai_task',
            event_subtype='memory_delete',
            description=f'Memory deleted: {category}:{key}',
            importance='info',
            source='telegram_bot'
        )
    else:
        await update.message.reply_text("❌ Failed to delete memory")


@require_admin
async def cmd_server_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /server_log - View server activity logs

    Usage:
        /server_log              - Last 10 logs
        /server_log <hours>      - Logs from last N hours
        /server_log summary      - Daily summary
    """
    args = context.args

    if args and args[0] == "summary":
        # Daily summary
        summary = await server_logger.get_daily_summary()

        lines = [
            f"📊 **Daily Server Summary - {summary.get('date', 'Today')}**\n",
            f"📈 Total events: {summary.get('total_events', 0)}\n",
            "**Event Types:**"
        ]

        for event_type, count in summary.get('event_counts', {}).items():
            lines.append(f"  • {event_type}: {count}")

        if summary.get('important_events'):
            lines.append("\n**Important Events:**")
            for event in summary['important_events'][:5]:
                lines.append(f"  • {event.get('description', '')[:50]}")

        await update.message.reply_text("\n".join(lines), parse_mode='Markdown')
        return

    # Get recent logs
    hours = 24
    if args:
        try:
            hours = int(args[0])
        except ValueError:
            pass

    events = await server_logger.get_recent(hours=hours, limit=15)

    if not events:
        await update.message.reply_text("📋 No recent logs")
        return

    lines = [f"📋 **Server Log (Last {hours} hours)**\n"]

    importance_emoji = {
        'debug': '🔍',
        'info': 'ℹ️',
        'notable': '📌',
        'important': '⚠️',
        'critical': '🚨'
    }

    for event in events:
        emoji = importance_emoji.get(event.importance, 'ℹ️')
        time_str = event.timestamp.strftime("%H:%M") if event.timestamp else ""
        lines.append(f"[{time_str}] {emoji} {event.description[:60]}")
        if event.related_service:
            lines.append(f"     _{event.related_service}_")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3900] + "\n\n...(truncated)"

    await update.message.reply_text(text, parse_mode='Markdown')


@require_admin
async def cmd_proactive_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /proactive - View and control proactive agent

    Usage:
        /proactive           - Show status
        /proactive on        - Enable
        /proactive off       - Disable
        /proactive test      - Send test message
    """
    args = context.args

    if args:
        action = args[0].lower()

        if action in ["on", "enable"]:
            proactive_agent.config.enabled = True
            await update.message.reply_text("✅ Proactive agent enabled")
            return

        if action in ["off", "disable"]:
            proactive_agent.config.enabled = False
            await update.message.reply_text("⏸️ Proactive agent disabled")
            return

        if action == "test":
            # Trigger a test message
            success = await proactive_agent.trigger_now("check_in")
            if success:
                await update.message.reply_text("✅ Test message sent")
            else:
                await update.message.reply_text("❌ Failed to send test message")
            return

    # Show status
    status = proactive_agent.get_status()

    lines = [
        "🤖 **Proactive Agent Status**\n",
        f"▸ Running: {'✅ Yes' if status['running'] else '❌ No'}",
        f"▸ Active: {'✅ Yes' if status['enabled'] else '⏸️ Disabled'}",
        f"▸ Messages today: {status['messages_today']}/{status['daily_limit']}",
        f"▸ Morning greeting: {'✅' if status['morning_sent'] else '⏳'}",
        f"▸ Evening summary: {'✅' if status['evening_sent'] else '⏳'}",
    ]

    if status['last_message']:
        lines.append(f"▸ Last message: {status['last_message']}")

    lines.extend([
        "\n**Commands:**",
        "  `/proactive on` - Enable",
        "  `/proactive off` - Disable",
        "  `/proactive test` - Send test message"
    ])

    await update.message.reply_text("\n".join(lines), parse_mode='Markdown')


@require_admin
async def cmd_insights(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /insights - View recent conversation insights

    Usage:
        /insights           - Last 10 insights
        /insights stats     - Insight statistics
    """
    args = context.args

    if args and args[0] == "stats":
        stats = await conversation_analyzer.get_insight_stats()

        lines = ["📊 **Insight Statistics (Last 30 days)**\n"]

        if stats.get('by_type'):
            lines.append("**By Type:**")
            for t, count in stats['by_type'].items():
                lines.append(f"  • {t}: {count}")

        if stats.get('by_category'):
            lines.append("\n**By Category:**")
            for c, count in stats['by_category'].items():
                lines.append(f"  • {c}: {count}")

        await update.message.reply_text("\n".join(lines), parse_mode='Markdown')
        return

    # Get recent insights
    insights = await conversation_analyzer.get_recent_insights(days=7, limit=10)

    if not insights:
        await update.message.reply_text("📋 No recent insights extracted")
        return

    lines = ["💡 **Recent Insights**\n"]

    for insight in insights:
        insight_type = insight.get('insight_type', '')
        category = insight.get('category', '')
        content = insight.get('content', '')[:80]
        confidence = insight.get('confidence', 0)

        type_emoji = {
            'preference': '❤️',
            'interest': '🎯',
            'goal': '🎯',
            'fact': '📌',
            'task': '📝'
        }.get(insight_type, '💡')

        lines.append(f"{type_emoji} **{insight_type}** ({category})")
        lines.append(f"   {content}")
        lines.append(f"   _Confidence: {confidence:.0%}_\n")

    await update.message.reply_text("\n".join(lines), parse_mode='Markdown')


# Command aliases - for compatibility with different naming conventions
cmd_hafiza = cmd_memory_view
cmd_hafiza_ekle = cmd_memory_add
cmd_hafiza_sil = cmd_memory_delete
cmd_sunucu_log = cmd_server_logs
cmd_proaktif = cmd_proactive_status
