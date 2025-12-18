"""
Email Handler

Multi-step conversation handler for sending emails via Telegram bot.
Uses the mailer service for sending emails.
"""

import sys
import re
from pathlib import Path

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from security import require_auth
from db import db

# Add mailer to path - user should configure their own mailer service
# sys.path.insert(0, str(Path.home() / "helper_services"))
# from mailer import ExperimentMailer

# Conversation states
RECIPIENT, SUBJECT, MESSAGE, CONFIRM = range(4)

# Email validation regex
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def validate_email(email: str) -> bool:
    """Validate email address format"""
    return bool(EMAIL_REGEX.match(email.strip()))


@require_auth
async def email_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start email conversation - ask for recipient"""
    # Clear any previous data
    context.user_data.clear()

    await update.message.reply_text(
        "📧 Email Sending\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Enter recipient email address:\n\n"
        "(/cancel to abort)"
    )
    return RECIPIENT


async def email_recipient(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive recipient email and ask for subject"""
    email = update.message.text.strip()

    if not validate_email(email):
        await update.message.reply_text(
            "❌ Invalid email address!\n\n"
            "Please enter a valid email address:\n"
            "(e.g., example@gmail.com)"
        )
        return RECIPIENT

    context.user_data['recipient'] = email

    await update.message.reply_text(
        f"✅ Recipient: {email}\n\n"
        "What should the subject be?\n"
        "(Write - to leave blank)"
    )
    return SUBJECT


async def email_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive subject and ask for message"""
    subject = update.message.text.strip()

    if subject == "-" or subject == "":
        subject = "Telegram Bot Message"

    context.user_data['subject'] = subject

    await update.message.reply_text(
        f"✅ Subject: {subject}\n\n"
        "Now write your message:"
    )
    return MESSAGE


async def email_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive message and ask for confirmation"""
    message = update.message.text.strip()

    if len(message) < 2:
        await update.message.reply_text(
            "❌ Message too short!\n\n"
            "Please write a longer message:"
        )
        return MESSAGE

    context.user_data['message'] = message

    # Show preview
    recipient = context.user_data['recipient']
    subject = context.user_data['subject']

    # Truncate message preview if too long
    preview = message[:200] + "..." if len(message) > 200 else message

    await update.message.reply_text(
        "📋 Email Summary\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📬 Recipient: {recipient}\n"
        f"📝 Subject: {subject}\n"
        f"💬 Message:\n{preview}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Write 'yes' to send.\n"
        "Write anything else to cancel."
    )
    return CONFIRM


async def email_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle confirmation and send email"""
    response = update.message.text.strip().lower()
    user = update.effective_user

    # Check for confirmation
    confirm_words = ['yes', 'y', 'confirm', 'send', 'ok']

    if response in confirm_words:
        recipient = context.user_data.get('recipient')
        subject = context.user_data.get('subject')
        message = context.user_data.get('message')

        try:
            # NOTE: User needs to implement their own mailer service
            # Example implementation:
            # from mailer import ExperimentMailer
            # mailer = ExperimentMailer(recipient=recipient)
            # full_message = f"{message}\n\n---\nSent via Telegram Bot."
            # success = mailer.send(subject, full_message)

            # For now, just log the attempt
            await update.message.reply_text(
                "⚠️ Email sending not configured.\n\n"
                "Please implement your own mailer service.\n"
                "See email.py for details."
            )

            # Log to database
            await db.log_message(
                user_id=user.id,
                username=user.username,
                message_type="email",
                user_message=f"/email → {recipient}",
                bot_response=f"Email attempt: {subject}",
                provider="mailer"
            )

        except Exception as e:
            await update.message.reply_text(
                f"❌ Error occurred: {str(e)}"
            )
    else:
        await update.message.reply_text(
            "❌ Cancelled.\n\n"
            "Email not sent."
        )

    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END


async def email_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation"""
    context.user_data.clear()

    await update.message.reply_text(
        "❌ Email sending cancelled."
    )
    return ConversationHandler.END


# Create the conversation handler
email_conversation_handler = ConversationHandler(
    entry_points=[CommandHandler("email", email_start)],
    states={
        RECIPIENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, email_recipient)],
        SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, email_subject)],
        MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, email_message)],
        CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, email_confirm)],
    },
    fallbacks=[
        CommandHandler("cancel", email_cancel),
    ],
    name="email_conversation",
    persistent=False,
)
