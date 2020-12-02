import pathlib
import json
from os import listdir
from os.path import isfile, join
from unittest.mock import create_autospec, MagicMock
from random import randint

import pytest
import yaml
from telegram import Update, CallbackQuery, Bot
from telegram.ext import CallbackContext

from geniust import api
from geniust import db
from geniust import text


@pytest.fixture(scope='session')
def song_id():
    return 4589365


@pytest.fixture(scope='session')
def song_url():
    return 'https://genius.com/Machine-gun-kelly-glass-house-lyrics'


@pytest.fixture(scope='session')
def data_path():
    return pathlib.Path('data').resolve()


@pytest.fixture(scope='session')
def album(data_path):
    with open(data_path / 'album.json', 'r') as f:
        return json.load(f)


@pytest.fixture(scope='session')
def artist(data_path):
    with open(data_path / 'artist.json', 'r') as f:
        return json.load(f)


@pytest.fixture(scope='session')
def song(data_path):
    with open(data_path / 'song.json', 'r') as f:
        return json.load(f)


@pytest.fixture(scope='session')
def annotation(data_path):
    with open(data_path / 'annotation.json', 'r') as f:
        return json.load(f)


@pytest.fixture(scope='session')
def annotations(data_path):
    with open(data_path / 'annotations.json', 'r') as f:
        return json.load(f)


@pytest.fixture(scope='session')
def page(data_path):
    with open(data_path / 'song_page.html', 'r', encoding='utf8') as f:
        return f.read()


@pytest.fixture(scope='session')
def genius():
    return api.GeniusT()


@pytest.fixture(scope='function')
def update_callback_query():
    update = create_autospec(Update)
    update.message = None
    update.callback_query = create_autospec(CallbackQuery, spec_set=True)
    return update


@pytest.fixture(scope='function')
def update_message():
    update = create_autospec(Update)
    update.callback_query = None
    update.message = MagicMock()
    return update


path = pathlib.Path(text.__file__).parent.resolve()
files = [f for f in listdir(path) if isfile(join(path, f)) and f.endswith('.yaml')]
languages = []
texts = {}
for file in files:
    with open(join(path, file), 'r', encoding='utf8') as f:
        language = file[:2]
        languages.append(language)
        texts[language] = yaml.full_load(f)

users = []
for language in languages:
    users.append({'chat_id': randint(1, 10),
                  'include_annotations': True,
                  'lyrics_lang': 'English + Non-English',
                  'bot_lang': language,
                  'token': 'a'})
    users.append({'chat_id': randint(10, 20),
                  'include_annotations': False,
                  'lyrics_lang': 'English + Non-English',
                  'bot_lang': language,
                  'token': 'a'})
    users.append({'chat_id': randint(20, 30),
                  'include_annotations': True,
                  'lyrics_lang': 'English + Non-English',
                  'bot_lang': language,
                  'token': None})
    users.append({'chat_id': randint(30, 40),
                  'include_annotations': False,
                  'lyrics_lang': 'English + Non-English',
                  'bot_lang': language,
                  'token': None})


@pytest.fixture(scope='function', params=users)
def context(request):
    context = create_autospec(CallbackContext, spec_set=True)
    context.bot = create_autospec(Bot, spec_set=True)
    context.bot_data = {}
    context.bot_data['db'] = create_autospec(db.Database, spec_set=True)
    context.bot_data['texts'] = texts
    context.user_data = request.param
    return context
