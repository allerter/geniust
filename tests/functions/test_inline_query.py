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
    assert articles


@pytest.mark.parametrize("query", [".album   ", ".album test"])
def test_search_albums_inline(update, context, query, search_albums_dict):
    update.inline_query.query = query
    genius = context.bot_data["genius"]
    genius.search_albums.return_value = search_albums_dict

    inline_query.search_albums(update, context)

    if query == ".album   ":
        update.inline_query.answer.assert_not_called()
    else:
        articles = update.inline_query.answer.call_args[0][0]
        assert len(articles) == 10


@pytest.mark.parametrize("query", [".artist   ", ".artist test"])
def test_search_artists_inline(update, context, query, search_artists_dict):
    update.inline_query.query = query
    genius = context.bot_data["genius"]
    genius.search_artists.return_value = search_artists_dict

    inline_query.search_artists(update, context)

    if query == ".artist   ":
        update.inline_query.answer.assert_not_called()
    else:
        articles = update.inline_query.answer.call_args[0][0]
        assert len(articles) == 10


@pytest.mark.parametrize("query", [".lyrics   ", ".lyrics test"])
def test_search_lyrics_inline(update, context, query, search_lyrics_dict):
    update.inline_query.query = query
    genius = context.bot_data["genius"]
    genius.search_lyrics.return_value = search_lyrics_dict

    inline_query.search_lyrics(update, context)

    if query == ".lyrics   ":
        update.inline_query.answer.assert_not_called()
    else:
        articles = update.inline_query.answer.call_args[0][0]
        assert len(articles) == 10


@pytest.mark.parametrize("query", [".user   ", ".user test"])
def test_search_users_inline(update, context, query, search_users_dict):
    update.inline_query.query = query
    genius = context.bot_data["genius"]
    genius.search_users.return_value = search_users_dict

    inline_query.search_users(update, context)

    if query == ".user   ":
        update.inline_query.answer.assert_not_called()
    else:
        articles = update.inline_query.answer.call_args[0][0]
        assert len(articles) == 10
