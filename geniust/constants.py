"""Some constants e.g. the bot token"""
import os
from telethon import TelegramClient
from telethon.sessions import StringSession

BOT_TOKEN = os.environ['BOT_TOKEN']
DATABASE_URL = os.environ['DATABASE_URL']
TELEGRAPH_TOKEN = os.environ['TELEGRAPH_TOKEN']
GENIUS_TOKEN = os.environ['GENIUS_TOKEN']
ANNOTATIONS_CHANNEL_HANDLE = os.environ['ANNOTATIONS_TELEGRAM_CHANNEL']
DEVELOPERS = ([int(x) for x in os.environ['DEVELOPERS'].split(',')]
              if os.environ.get('DEVELOPERS')
              else [])
SERVER_PORT = int(os.environ.get('PORT', 5000))
SERVER_ADDRESS = os.environ.get('SERVER_ADDRESS')
TELETHON_API_ID = os.environ['TELETHON_API_ID']
TELETHON_API_HASH = os.environ['TELETHON_API_HASH']
TELETHON_SESSION_STRING = os.environ['TELETHON_SESSION_STRING']

client = TelegramClient(StringSession(TELETHON_SESSION_STRING),
                        TELETHON_API_ID, TELETHON_API_HASH)
client.start()

ANNOTATIONS_CHANNEL = client.loop.run_until_complete(
    client.get_input_entity(ANNOTATIONS_CHANNEL_HANDLE)
)
