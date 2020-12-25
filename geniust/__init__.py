import functools
import pathlib
from os import listdir
from os.path import isfile, join
from typing import TypeVar, Callable

# from telegram import Bot
import tekore as tk
from lyricsgenius import OAuth2
import yaml

from geniust.db import Database
from geniust.constants import (
    GENIUS_CLIENT_ID,
    GENIUS_REDIRECT_URI,
    GENIUS_CLIENT_SECRET,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
)

username: str = "genius_the_bot"  # Bot(BOT_TOKEN).get_me().username

database = Database("user_data", "user_preferences")

RT = TypeVar("RT")


def get_user(func: Callable[..., RT]) -> Callable[..., RT]:
    """Gets user data for the function

    Checks for user data in CallbackContext and gets
    user data from the database if the CallbackContext doesn't
    have user's data.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> RT:
        chat_id = args[0].effective_chat.id
        context = args[1]
        if "bot_lang" not in context.user_data:
            database.user(chat_id, context.user_data)
        result = func(*args, **kwargs)
        return result

    return wrapper


data_path = pathlib.Path(__file__).parent.resolve() / "data"
files = [f
         for f in listdir(data_path)
         if isfile(join(data_path, f)) and f.endswith(".yaml")]
texts = {}
for file in files:
    with open(join(data_path, file), "r", encoding="utf8") as f:
        language = file[:2]
        texts[language] = yaml.full_load(f)

genius_auth = OAuth2.full_code_exchange(
    GENIUS_CLIENT_ID, GENIUS_REDIRECT_URI, GENIUS_CLIENT_SECRET, scope=("me", "vote")
)
spotify_auth = tk.UserAuth(
    tk.Credentials(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI),
    scope=tk.scope.user_top_read)
auths = {'genius': genius_auth, 'spotify': spotify_auth}
