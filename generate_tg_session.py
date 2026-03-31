"""Generate Telegram session string for telegram-mcp.

Run this script interactively:
    python3 generate_tg_session.py

It will:
1. Ask for your API ID and API Hash (from https://my.telegram.org/apps)
2. Ask for your phone number (e.g. +1234567890)
3. Telegram will send a code to your Telegram app
4. Enter the code here
5. The session string gets printed — copy it
"""

from telethon.sync import TelegramClient
from telethon.sessions import StringSession

print("=" * 50)
print("Telegram Session String Generator")
print("=" * 50)
print()
print("Get your API ID and Hash from: https://my.telegram.org/apps")
print()

api_id = int(input("API ID: ").strip())
api_hash = input("API Hash: ").strip()

with TelegramClient(StringSession(), api_id, api_hash) as client:
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
