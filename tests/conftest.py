import pathlib
import json
import os
from os import listdir
from os.path import isfile, join
from unittest.mock import create_autospec, MagicMock

import pytest
import yaml
from telegram import Update, CallbackQuery, Bot, Message
from telegram.ext import CallbackContext

from geniust import api
from geniust import db
from geniust import text


@pytest.fixture(scope="session")
def song_id():
    return 4589365


@pytest.fixture(scope="session")
def song_url():
    return "https://genius.com/Machine-gun-kelly-glass-house-lyrics"


# ----------------- Data Files Fixtures -----------------


@pytest.fixture(scope="session")
def data_path():
    return join(os.path.dirname(os.path.abspath(__file__)), "data")


@pytest.fixture(scope="session")
def full_album(data_path):
    with open(join(data_path, "full_album.json"), "r") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def search_albums_dict(data_path):
    with open(join(data_path, "search_albums.json"), "r") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def search_artists_dict(data_path):
    with open(join(data_path, "search_artists.json"), "r") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def search_songs_dict(data_path):
    with open(join(data_path, "search_songs.json"), "r", encoding="utf-8-sig") as f:
        return json.load(f)


@pytest.fixture(scope="function")
def album_dict(data_path):
    with open(join(data_path, "album.json"), "r") as f:
        return json.load(f)


@pytest.fixture(scope="function")
def artist_dict(data_path):
    with open(join(data_path, "artist.json"), "r") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def annotation(data_path):
    with open(join(data_path, "annotation.json"), "r") as f:
        return json.load(f)


@pytest.fixture(scope="function")
def song_dict(data_path):
    with open(join(data_path, "song.json"), "r") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def annotations(data_path):
    with open(join(data_path, "annotations.json"), "r") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def page(data_path):
    with open(join(data_path, "song_page.html"), "r", encoding="utf8") as f:
        return f.read()


@pytest.fixture(scope="module")
def account_dict(data_path):
    with open(join(data_path, "account.json"), "r") as f:
        return json.load(f)


# ----------------- Update Fixtures -----------------


@pytest.fixture(scope="session")
def update_callback_query_class():
    update = create_autospec(Update)
    update.effective_chat.id = 123
    update.message = None
    update.callback_query = create_autospec(CallbackQuery)
    update.callback_query.message = create_autospec(Message)
    return update


@pytest.fixture(scope="function")
def update_callback_query(update_callback_query_class):
    update = update_callback_query_class
    update.callback_query.reset_mock()
    update.callback_query.message.reset_mock()
    return update


@pytest.fixture(scope="session")
def update_message_class():
    update = create_autospec(Update)
    update.effective_chat.id = 123
    update.callback_query = None
    update.message = MagicMock()
    return update


@pytest.fixture(scope="function")
def update_message(update_message_class):
    update = update_message_class
    update.message.reset_mock()
    return update


# ----------------- Context Fixture -----------------


path = pathlib.Path(text.__file__).parent.resolve()
files = [f for f in listdir(path) if isfile(join(path, f)) and f.endswith(".yaml")]
languages = []
texts = {}
for file in files:
    with open(join(path, file), "r", encoding="utf8") as f:
        language = file[:2]
        languages.append(language)
        texts[language] = yaml.full_load(f)

users = []
for language in languages:
    users.append(
        {
            "include_annotations": True,
            "lyrics_lang": "English + Non-English",
            "bot_lang": language,
            "token": None,
        }
    )


# for language in languages:
#    users.append({'chat_id': randint(1, 10),
#                  'include_annotations': True,
#                  'lyrics_lang': 'English + Non-English',
#                  'bot_lang': language,
#                  'token': 'a'})
#    users.append({'chat_id': randint(10, 20),
#                  'include_annotations': False,
#                  'lyrics_lang': 'English + Non-English',
#                  'bot_lang': language,
#                  'token': 'a'})
#    users.append({'chat_id': randint(20, 30),
#                  'include_annotations': True,
#                  'lyrics_lang': 'English + Non-English',
#                  'bot_lang': language,
#                  'token': None})
#    users.append({'chat_id': randint(30, 40),
#                  'include_annotations': False,
#                  'lyrics_lang': 'English + Non-English',
#                  'bot_lang': language,
#                  'token': None})


@pytest.fixture(scope="session")
def context_class():
    context = create_autospec(CallbackContext)
    context.args = [[]]
    context.bot = create_autospec(Bot, spec_set=True)
    context.bot_data = {}
    context.bot_data["db"] = create_autospec(db.Database, spec_set=True)
    context.bot_data["texts"] = texts
    context.bot_data["genius"] = create_autospec(api.GeniusT, spec_set=True)
    return context


@pytest.fixture(scope="function", params=users)
def context(context_class, request):
    context_class.bot.reset_mock()
    context_class.bot_data["db"].reset_mock()
    context_class.bot_data["genius"].reset_mock()
    context_class.user_data = request.param
    return context_class
