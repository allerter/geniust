"""Some constants e.g. the bot token"""
import os

from typing import List, Optional

from telegram.ext import ConversationHandler

BOT_TOKEN: str = os.environ['BOT_TOKEN']
DATABASE_URL: str = os.environ['DATABASE_URL']
TELEGRAPH_TOKEN: str = os.environ['TELEGRAPH_TOKEN']
GENIUS_TOKEN: str = os.environ['GENIUS_TOKEN']
GENIUS_CLIENT_ID: str = os.environ['GENIUS_CLIENT_ID']
GENIUS_CLIENT_SECRET: str = os.environ['GENIUS_CLIENT_SECRET']
GENIUS_REDIRECT_URI: str = os.environ['GENIUS_REDIRECT_URI']
ANNOTATIONS_CHANNEL_HANDLE: str = os.environ['ANNOTATIONS_CHANNEL_HANDLE']
DEVELOPERS: List[int] = ([int(x) for x in os.environ['DEVELOPERS'].split(',')]
                         if os.environ.get('DEVELOPERS')
                         else [])
SERVER_PORT: Optional[int] = int(os.environ['PORT']) if os.environ.get('PORT') else None
SERVER_ADDRESS: Optional[str] = os.environ.get('SERVER_ADDRESS')
TELETHON_API_ID: str = os.environ['TELETHON_API_ID']
TELETHON_API_HASH: str = os.environ['TELETHON_API_HASH']
TELETHON_SESSION_STRING: str = os.environ['TELETHON_SESSION_STRING']

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

    def assign(self, length: int) -> range:
        start = self.current
        end = start + length
        self.current = end
        return range(start, end)


num = AutoRange()

# Menu Levels
MAIN_MENU, CUSTOMIZE_MENU, ACCOUNT_MENU = num.assign(3)

# User Input States
(TYPING_ALBUM, TYPING_ARTIST, TYPING_SONG, TYPING_FEEDBACK,
INCLUDE, LYRICS_LANG, BOT_LANG, SELECT_ACTION) = num.assign(8)

# Input Options
OPTION1, OPTION2, OPTION3 = num.assign(3)

LOGIN, LOGGED_IN, LOGOUT = num.assign(3)

END = ConversationHandler.END
