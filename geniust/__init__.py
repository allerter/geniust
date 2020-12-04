"""Some constants e.g. the bot token"""
import functools
import pathlib
from os import listdir
from os.path import isfile, join

from telegram import Bot
from lyricsgenius import OAuth2
import yaml

from geniust.db import Database
from geniust.api import GeniusT
from geniust.constants import (BOT_TOKEN,
    GENIUS_CLIENT_ID, GENIUS_REDIRECT_URI, GENIUS_CLIENT_SECRET)

username = 'genius_the_bot'  # Bot(BOT_TOKEN).get_me().username

database = Database(table='user_data')

genius = GeniusT()


def get_user(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        chat_id = args[0].effective_chat.id
        context = args[1]
        if 'bot_lang' not in context.user_data:
            database.user(chat_id, context.user_data)
        result = func(*args, **kwargs)
        return result
    return wrapper


here = pathlib.Path(__file__).parent.resolve()
path = here / 'text'
files = [f for f in listdir(path) if isfile(join(path, f)) and f.endswith('.yaml')]
texts = {}
for file in files:
    with open(join(path, file), 'r', encoding='utf8') as f:
        language = file[:2]
        texts[language] = yaml.full_load(f)

auth = OAuth2.full_code_exchange(
    GENIUS_CLIENT_ID,
    GENIUS_REDIRECT_URI,
    GENIUS_CLIENT_SECRET,
    scope=('me', 'vote')
)
