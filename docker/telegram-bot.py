"""Telegram Bot for Beaver.

Receives messages and files from Telegram users, forwards them to the Beaver API.
- Text messages → /v1/chat/completions (RAG-powered replies)
- Files (pdf, docx, etc.) → /v1/knowledge/documents (auto-indexed)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import tempfile
from pathlib import Path

import httpx
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("beaver-telegram-bot")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
BEAVER_API_URL = os.environ.get("BEAVER_API_URL", "http://api:8741")
BEAVER_API_KEY = os.environ.get("BEAVER_API_KEY", "")

# Per-user chat history (in-memory, keyed by telegram user id)
chat_histories: dict[int, list[dict]] = {}
MAX_HISTORY = 20


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {BEAVER_API_KEY}",
        "Content-Type": "application/json",
    }


async def start_command(update: Update, context) -> None:
    await update.message.reply_text(
        "Hi! I'm Beaver 🦫\n\n"
        "Send me a message and I'll answer using my knowledge base.\n"
        "Send me a file (PDF, DOCX, TXT, etc.) and I'll index it for future questions.\n\n"
        "Commands:\n"
        "/clear - Clear chat history\n"
        "/status - Check service status"
    )


async def clear_command(update: Update, context) -> None:
    user_id = update.effective_user.id
    chat_histories.pop(user_id, None)
    await update.message.reply_text("Chat history cleared.")


async def status_command(update: Update, context) -> None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{BEAVER_API_URL}/health")
            if resp.status_code == 200:
                await update.message.reply_text("Beaver API is running.")
            else:
                await update.message.reply_text(f"Beaver API returned status {resp.status_code}")
    except Exception as e:
        await update.message.reply_text(f"Cannot reach Beaver API: {e}")


async def handle_message(update: Update, context) -> None:
    """Forward text messages to Beaver chat API."""
    user_id = update.effective_user.id
    text = update.message.text

    if not text:
        return

    # Build message history
    if user_id not in chat_histories:
        chat_histories[user_id] = []

    chat_histories[user_id].append({"role": "user", "content": text})

    # Trim history
    if len(chat_histories[user_id]) > MAX_HISTORY:
        chat_histories[user_id] = chat_histories[user_id][-MAX_HISTORY:]

    # Send typing indicator
    await update.message.chat.send_action("typing")

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{BEAVER_API_URL}/v1/chat/completions",
                headers=get_headers(),
                json={
                    "model": "beaver-default",
                    "messages": chat_histories[user_id],
                    "stream": False,
                    "use_knowledge": True,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            reply = data["choices"][0]["message"]["content"]
            chat_histories[user_id].append({"role": "assistant", "content": reply})

            # Telegram has a 4096 char limit per message
            if len(reply) <= 4096:
                await update.message.reply_text(reply)
            else:
                for i in range(0, len(reply), 4096):
                    await update.message.reply_text(reply[i : i + 4096])

    except httpx.HTTPStatusError as e:
        log.error(f"Beaver API error: {e.response.status_code} {e.response.text}")
        await update.message.reply_text("Sorry, I encountered an error processing your message.")
    except Exception as e:
        log.error(f"Error: {e}")
        await update.message.reply_text("Sorry, something went wrong. Please try again.")


async def handle_document(update: Update, context) -> None:
    """Download files and upload them to Beaver knowledge base."""
    document = update.message.document
    if not document:
        return

    filename = document.file_name or "unknown"
    file_size_mb = (document.file_size or 0) / (1024 * 1024)

    await update.message.reply_text(f"Receiving file: {filename} ({file_size_mb:.1f} MB)...")

    try:
        # Download file from Telegram
        tg_file = await document.get_file()

        with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix, delete=False) as tmp:
            tmp_path = tmp.name
            await tg_file.download_to_drive(tmp_path)

        # Upload to Beaver API
        async with httpx.AsyncClient(timeout=300) as client:
            with open(tmp_path, "rb") as f:
                resp = await client.post(
                    f"{BEAVER_API_URL}/v1/knowledge/documents",
                    headers={"Authorization": f"Bearer {BEAVER_API_KEY}"},
                    files={"file": (filename, f)},
                )
            resp.raise_for_status()
            data = resp.json()

        os.unlink(tmp_path)

        doc_id = data.get("id", "unknown")
        await update.message.reply_text(
            f"File uploaded and queued for indexing.\n"
            f"Document ID: {doc_id}\n"
            f"You can ask questions about it once indexing completes."
        )

    except httpx.HTTPStatusError as e:
        log.error(f"Upload error: {e.response.status_code} {e.response.text}")
        await update.message.reply_text(f"Failed to upload file: {e.response.text[:200]}")
    except Exception as e:
        log.error(f"Error handling document: {e}")
        await update.message.reply_text("Failed to process file. Please try again.")


async def handle_photo(update: Update, context) -> None:
    """Handle photos sent to the bot."""
    await update.message.reply_text(
        "Please send files as documents (not compressed photos) for better quality.\n"
        "Use the paperclip icon → File."
    )


def main():
    if not BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    if not BEAVER_API_KEY:
        log.error("BEAVER_API_KEY not set")
        sys.exit(1)

    log.info(f"Starting Beaver Telegram Bot")
    log.info(f"Beaver API: {BEAVER_API_URL}")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
