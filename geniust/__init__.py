"""Some constants e.g. the bot token"""
from telegram import Bot

from geniust.db import Database
from geniust.api import GeniusT
from geniust.constants import BOT_TOKEN

username = Bot(BOT_TOKEN).get_me().username

database = Database(table='data')

genius = GeniusT()
