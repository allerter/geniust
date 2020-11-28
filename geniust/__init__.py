"""Some constants e.g. the bot token"""
import functools
from os import listdir
from os.path import isfile, join

from telegram import Bot
import yaml

from geniust.db import Database
from geniust.api import GeniusT
from geniust.constants import BOT_TOKEN

username = Bot(BOT_TOKEN).get_me().username

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


path = 'text'
files = [f for f in listdir(path) if isfile(join(path, f)) and f.endswith('.yaml')]
texts = {}
for file in files:
    with open(join(path, file), 'r', encoding='utf8') as f:
        language = file[:2]
        texts[language] = yaml.full_load(f)
