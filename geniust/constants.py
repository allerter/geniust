"""Some constants e.g. the bot token"""
import os

from telegram.ext import ConversationHandler

BOT_TOKEN = os.environ['BOT_TOKEN']
DATABASE_URL = os.environ['DATABASE_URL']
TELEGRAPH_TOKEN = os.environ['TELEGRAPH_TOKEN']
GENIUS_TOKEN = os.environ['GENIUS_TOKEN']
ANNOTATIONS_CHANNEL_HANDLE = os.environ['ANNOTATIONS_CHANNEL_HANDLE']
DEVELOPERS = ([int(x) for x in os.environ['DEVELOPERS'].split(',')]
              if os.environ.get('DEVELOPERS')
              else [])
SERVER_PORT = int(os.environ['PORT']) if os.environ.get('PORT') else None
SERVER_ADDRESS = os.environ.get('SERVER_ADDRESS')
TELETHON_API_ID = os.environ['TELETHON_API_ID']
TELETHON_API_HASH = os.environ['TELETHON_API_HASH']
TELETHON_SESSION_STRING = os.environ['TELETHON_SESSION_STRING']

TELEGRAM_HTML_TAGS = [
    'b', 'strong',
    'i', 'em',
    'u', 'ins',
    's', 'strike', 'del',
    'a',
    'code', 'pre'
]

# State definitions for conversation
class AutoRange:
    def __init__(self):
        self.current = 0

    def assign(self, length):
        start = self.current
        end = start + length
        self.current = end
        return range(start, end)


num = AutoRange()

# Menu Levels
MAIN_MENU, CUSTOMIZE_MENU = num.assign(2)

# User Input States
(TYPING_ALBUM, TYPING_ARTIST, TYPING_SONG, TYPING_FEEDBACK,
INCLUDE, LYRICS_LANG, BOT_LANG, SELECT_ACTION) = num.assign(8)

# Input Options
OPTION1, OPTION2, OPTION3 = num.assign(3)

END = ConversationHandler.END
