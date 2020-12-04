import json
from os.path import join
from unittest.mock import patch, MagicMock

import pytest

from geniust import constants
from geniust.functions import album


@pytest.mark.parametrize('update', [pytest.lazy_fixture('update_callback_query'),
                                    pytest.lazy_fixture('update_message'),
                                    ])
def test_type_album(update, context):

    res = album.type_album(update, context)

    if getattr(update, 'callback_query', None):
        update.callback_query.answer.assert_called_once()
    else:
        update.message.reply_text.assert_called_once()

    assert res == constants.TYPING_ALBUM


@pytest.mark.parametrize('search_dict',
                         [pytest.lazy_fixture('search_albums_dict'),
                          {'sections': [{'hits': []}]}
                          ])
def test_search_albums(update_message, context, search_dict):
    update = update_message
    genius = context.bot_data['genius']
    genius.search_albums.return_value = search_dict

    if search_dict['sections'][0]['hits']:
        update.message.text = 'test'

    res = album.search_albums(update, context)

    if search_dict['sections'][0]['hits']:
        keyboard = (update.message.reply_text
                    .call_args[1]['reply_markup']['inline_keyboard'])
        assert len(keyboard) == 10

    assert res == constants.END


@pytest.mark.parametrize('update', [pytest.lazy_fixture('update_callback_query'),
                                    pytest.lazy_fixture('update_message'),
                                    ])
def test_display_album(update, context, album_dict):
    if update.callback_query:
        update.callback_query.data = 'album_1'
    else:
        context.args[0] = 'album_1'

    genius = context.bot_data['genius']
    genius.album.return_value = album_dict

    res = album.display_album(update, context)

    keyboard = (context.bot.send_photo
                .call_args[1]['reply_markup']['inline_keyboard'])

    # Covers - Tracks - Lyrics - Description
    assert len(keyboard) == 3
    assert len(keyboard[0]) == 2

    # album ID = 1
    genius.album.assert_called_once_with(1)

    if update.callback_query:
        update.callback_query.answer.assert_called_once()

    assert res == constants.END


@pytest.fixture(scope='module')
def covers_dict(data_path):
    with open(join(data_path, 'album_cover_arts.json'), 'r') as f:
        return json.load(f)


@pytest.mark.parametrize('update, album_covers_dict',
                         [
                             (pytest.lazy_fixture('update_callback_query'),
                              pytest.lazy_fixture('covers_dict')),

                             (pytest.lazy_fixture('update_message'),
                              {'cover_arts': [{'image_url': 'test_url'}]}),
                         ])
def test_display_album_covers(update, context, album_dict, album_covers_dict):
    if update.callback_query:
        update.callback_query.data = 'album_1_covers'
    else:
        context.args[0] = 'album_1_covers'

    genius = context.bot_data['genius']
    genius.album.return_value = album_dict
    genius.album_cover_arts.return_value = album_covers_dict

    res = album.display_album_covers(update, context)

    # album ID = 1
    genius.album.assert_called_once_with(1)
    genius.album_cover_arts.assert_called_once_with(1)

    if update.callback_query:
        update.callback_query.answer.assert_called_once()

    if len(album_covers_dict['cover_arts']) > 1:
        pics = context.bot.send_media_group.call_args[0][1]
        assert len(pics) == 5
        context.bot.send_media_group.assert_called_once()
    else:
        context.bot.send_photo.assert_called_once()

    assert res == constants.END


@pytest.fixture(scope='module')
def tracks_dict(data_path):
    with open(join(data_path, 'album_tracks.json'), 'r') as f:
        return json.load(f)


@pytest.mark.parametrize('update, album_tracks_dict',
                         [
                             (pytest.lazy_fixture('update_callback_query'),
                              pytest.lazy_fixture('tracks_dict')),

                             (pytest.lazy_fixture('update_message'),
                              {'tracks': []}),
                         ])
def test_display_album_tracks(update, context, album_dict, album_tracks_dict):
    if update.callback_query:
        update.callback_query.data = 'album_1_tracks'
    else:
        context.args[0] = 'album_1_tracks'

    genius = context.bot_data['genius']
    genius.album.return_value = album_dict
    genius.album_tracks.return_value = album_tracks_dict

    res = album.display_album_tracks(update, context)

    # album ID = 1
    genius.album.assert_called_once_with(1)
    assert genius.album_tracks.call_args[0][0] == 1

    if update.callback_query:
        update.callback_query.answer.assert_called_once()

    if album_tracks_dict['tracks']:
        reply = context.bot.send_message.call_args[0][1]
        assert len(reply.split('\n')) >= len(album_tracks_dict['tracks'])

    assert res == constants.END


@pytest.mark.parametrize('update',
                         [
                             pytest.lazy_fixture('update_callback_query'),
                             pytest.lazy_fixture('update_message'),
                         ])
def test_display_album_formats(update, context):
    if update.callback_query:
        update.callback_query.data = 'album_1_lyrics'
    else:
        context.args[0] = 'album_1_lyrics'

    res = album.display_album_formats(update, context)

    if update.callback_query:
        update.callback_query.answer.assert_called_once()
        keyboard = (update.callback_query.edit_message_reply_markup
                    .call_args[0][0]['inline_keyboard'])
    else:
        keyboard = (context.bot.send_message
                    .call_args[1]['reply_markup']['inline_keyboard'])

    assert len(keyboard) == 3

    assert res == constants.END


@pytest.mark.parametrize('album_format', ['pdf', 'tgf', 'zip'])
def test_thread_get_album(update_callback_query, context, album_format):
    update = update_callback_query
    update.callback_query.data = 'album_1_lyrics_' + album_format

    thread = MagicMock()
    with patch('threading.Thread', thread):
        res = album.thread_get_album(update, context)

    target_function = thread.call_args[1]['target']
    args = thread.call_args[1]['args']

    assert target_function == album.get_album

    album_id = 1
    assert args[:4] == (update, context, album_id, album_format)

    thread().start.assert_called_once()
    thread().join.assert_called_once()

    assert res == constants.END


@pytest.mark.parametrize('album_format', ['pdf', 'tgf', 'zip'])
def test_get_album(update_callback_query, context, album_format, full_album):
    update = update_callback_query
    language = context.user_data['bot_lang']
    text = context.bot_data['texts'][language]['get_album']
    album_id = 1

    client = MagicMock()
    client().async_album_search.return_value = full_album
    convert = MagicMock()

    current_module = 'geniust.functions.album'
    with patch('geniust.api.GeniusT', client), \
            patch(current_module + '.create_pdf', convert), \
            patch(current_module + '.create_pages', convert), \
            patch(current_module + '.create_zip', convert):
        album.get_album(update, context, album_id, album_format, text)

    convert.assert_called_once_with(full_album, context.user_data)

    if album_format == 'tgf':
        context.bot.send_message.call_args[1]['text'] == convert
    else:
        context.bot.send_document.assert_called_once()
