import functools
import pathlib
from os import listdir
from os.path import isfile, join
from typing import Callable, TypeVar

# from telegram import Bot
import tekore as tk
import yaml
from lyricsgenius import OAuth2

from geniust.constants import (
    GENIUS_CLIENT_ID,
    GENIUS_CLIENT_SECRET,
    GENIUS_REDIRECT_URI,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
)

username: str = "genius_the_bot"  # Bot(BOT_TOKEN).get_me().username

RT = TypeVar("RT")


def get_user(func: Callable[..., RT]) -> Callable[..., RT]:
    """Gets user data for the function

    Checks for user data in CallbackContext and gets
    user data from the database if the CallbackContext doesn't
    have user's data.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> RT:
        update = args[0]
        context = args[1]
        if update.effective_chat:
            chat_id = update.effective_chat.id
        else:
            chat_id = update.inline_query.from_user.id
        if "bot_lang" not in context.user_data:
            context.bot_data["db"].user(chat_id, context.user_data)
        result = func(*args, **kwargs)
        return result

    return wrapper


data_path = pathlib.Path(__file__).parent.resolve() / "data"
files = [
    f for f in listdir(data_path) if isfile(join(data_path, f)) and f.endswith(".yaml")
]
texts = {}
for file in files:
    with open(join(data_path, file), "r", encoding="utf8") as f:
        language = file[:2]
        texts[language] = yaml.full_load(f)

genius_auth = OAuth2.full_code_exchange(
    GENIUS_CLIENT_ID, GENIUS_REDIRECT_URI, GENIUS_CLIENT_SECRET, scope=("me", "vote")
)
spotify_auth = tk.UserAuth(
    tk.RefreshingCredentials(
        SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
    ),
    scope=tk.scope.user_top_read,
)
auths = {"genius": genius_auth, "spotify": spotify_auth}
