"""Generate Telegram session string for telegram-mcp.

Run this script interactively:
    python3 generate_tg_session.py

It will:
1. Ask for your phone number (e.g. +1234567890)
2. Telegram will send a code to your Telegram app
3. Enter the code here
4. The session string gets printed — copy it
"""

from telethon.sync import TelegramClient
from telethon.sessions import StringSession

API_ID = 146991
API_HASH = "5d7440809f6a634b33f5cccf46d638b1"

print("=" * 50)
print("Telegram Session String Generator")
print("=" * 50)
print()

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    session_string = client.session.save()
    print()
    print("=" * 50)
    print("SUCCESS! Your session string:")
    print("=" * 50)
    print()
    print(session_string)
    print()
    print("=" * 50)
    print("Copy the string above and paste it when asked.")
    print("=" * 50)
