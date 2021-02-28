import pathlib
import json
import os
from os import listdir
from os.path import isfile, join
from unittest.mock import create_autospec, MagicMock

import pytest
import yaml
import tekore as tk
from lyricsgenius import OAuth2
from telegram import Update, CallbackQuery, Bot, Message
from telegram.ext import CallbackContext

from geniust import api
from geniust import db
from geniust import data
from geniust.functions.recommender import Recommender
from geniust.constants import Preferences


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
def search_lyrics_dict(data_path):
    with open(join(data_path, "search_lyrics.json"), "r", encoding="utf-8-sig") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def search_songs_dict(data_path):
    with open(join(data_path, "search_songs.json"), "r", encoding="utf-8-sig") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def search_users_dict(data_path):
    with open(join(data_path, "search_users.json"), "r", encoding="utf-8-sig") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def album_dict(data_path):
    with open(join(data_path, "album.json"), "r") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def artist_dict(data_path):
    with open(join(data_path, "artist.json"), "r") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def annotation(data_path):
    with open(join(data_path, "annotation.json"), "r") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def song_dict(data_path):
    with open(join(data_path, "song.json"), "r") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def user_dict(data_path):
    with open(join(data_path, "user.json"), "r") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def user_pyongs_dict(data_path):
    with open(join(data_path, "user_pyongs.json"), "r", encoding="utf8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def lastfm_track_toptags(data_path):
    with open(join(data_path, "lastfm_track_toptags.json"), "r") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def annotations(data_path):
    with open(join(data_path, "annotations.json"), "r") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def page(data_path):
    with open(join(data_path, "song_page.html"), "r", encoding="utf8") as f:
        return f.read()


@pytest.fixture(scope="session")
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


@pytest.fixture(scope="session")
def auths_class():
    auths = dict(genius=create_autospec(OAuth2), spotify=create_autospec(tk.UserAuth))
    auths["spotify"]._cred = MagicMock()
    return auths


@pytest.fixture(scope="function")
def auths(auths_class):
    auths_class["genius"].reset_mock()
    auths_class["spotify"].reset_mock()
    auths_class["spotify"]._cred.reset_mock()
    return auths_class


# ----------------- Context Fixture -----------------

path = pathlib.Path(data.__file__).parent.resolve()
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
            "genius_token": "test_token",
            "spotify_token": "test_token",
            "preferences": Preferences(genres=["pop"]),
        }
    )


@pytest.fixture(scope="session")
def recommender():
    return Recommender()


@pytest.fixture(scope="session")
def context_class(recommender):
    context = create_autospec(CallbackContext)
    context.args = [[]]
    context.bot = create_autospec(Bot, spec_set=True)
    context.bot_data = {}
    context.bot_data["auths"] = dict(
        genius=create_autospec(OAuth2), spotify=create_autospec(tk.UserAuth)
    )
    context.bot_data["auths"]["spotify"]._cred = MagicMock()
    context.bot_data["db"] = create_autospec(db.Database, spec_set=True)
    context.bot_data["genius"] = create_autospec(api.GeniusT, spec_set=True)
    context.bot_data["spotify"] = create_autospec(tk.Spotify, spec_set=True)
    context.bot_data["texts"] = texts
    context.bot_data["recommender"] = recommender
    return context


@pytest.fixture(scope="function", params=users)
def context(context_class, request):
    context_class.bot.reset_mock()
    for spec in ("db", "genius", "spotify", "auths"):
        spec_class = context_class.bot_data[spec]
        if spec == "auths":
            spec_class["genius"].reset_mock()
            spec_class["spotify"].reset_mock()
            spec_class["spotify"]._cred = MagicMock()
        else:
            spec_class.reset_mock()
    context_class.user_data = request.param
    return context_class
