from unittest.mock import create_autospec

import pytest
from telegram import InlineQuery, Update

from geniust.functions import inline_query


@pytest.fixture
def update():
    update = create_autospec(Update)
    update.effective_chat.id = 123
    update.inline_query = create_autospec(InlineQuery)

    return update


def test_inline_menu(update, context):

    inline_query.inline_menu(update, context)

    articles = update.inline_query.answer.call_args[0][0]

    assert len(articles) == 3


@pytest.mark.parametrize('query', ['.album   ', '.album test'])
def test_search_albums_inline(update, context, query, search_albums_dict):
    update.inline_query.query = query
    genius = context.bot_data['genius']
    genius.search_albums.return_value = search_albums_dict

    inline_query.search_albums(update, context)

    if query == '.album   ':
        update.inline_query.answer.assert_not_called()
    else:
        articles = update.inline_query.answer.call_args[0][0]
        assert len(articles) == 10


@pytest.mark.parametrize('query', ['.artist   ', '.artist test'])
def test_search_artists_inline(update, context, query, search_artists_dict):
    update.inline_query.query = query
    genius = context.bot_data['genius']
    genius.search_artists.return_value = search_artists_dict

    inline_query.search_artists(update, context)

    if query == '.artist   ':
        update.inline_query.answer.assert_not_called()
    else:
        articles = update.inline_query.answer.call_args[0][0]
        assert len(articles) == 10


@pytest.mark.parametrize('query', ['.song   ', '.song test'])
def test_search_songs_inline(update, context, query, search_songs_dict):
    update.inline_query.query = query
    genius = context.bot_data['genius']
    genius.search_songs.return_value = search_songs_dict

    inline_query.search_songs(update, context)

    if query == '.song   ':
        update.inline_query.answer.assert_not_called()
    else:
        articles = update.inline_query.answer.call_args[0][0]
        assert len(articles) == 10
