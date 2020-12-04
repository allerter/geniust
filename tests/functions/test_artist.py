import json
from os.path import join

import pytest

from geniust import constants
from geniust.functions import artist


@pytest.mark.parametrize('update', [pytest.lazy_fixture('update_callback_query'),
                                    pytest.lazy_fixture('update_message'),
                                    ])
def test_type_artist(update, context):

    res = artist.type_artist(update, context)

    if getattr(update, 'callback_query', None):
        update.callback_query.answer.assert_called_once()
    else:
        update.message.reply_text.assert_called_once()

    assert res == constants.TYPING_ARTIST


@pytest.mark.parametrize('search_dict',
                         [pytest.lazy_fixture('search_artists_dict'),
                          {'sections': [{'hits': []}]}
                          ])
def test_search_artists(update_message, context, search_dict):
    update = update_message
    genius = context.bot_data['genius']
    genius.search_artists.return_value = search_dict

    if search_dict['sections'][0]['hits']:
        update.message.text = 'test'

    res = artist.search_artists(update, context)

    if search_dict['sections'][0]['hits']:
        keyboard = (update.message.reply_text
                    .call_args[1]['reply_markup']['inline_keyboard'])
        assert len(keyboard) == 10

    assert res == constants.END


@pytest.mark.parametrize('update', [pytest.lazy_fixture('update_callback_query'),
                                    pytest.lazy_fixture('update_message'),
                                    ])
def test_display_artist(update, context, artist_dict):
    if update.callback_query:
        update.callback_query.data = 'artist_1'
    else:
        context.args[0] = 'artist_1'

    genius = context.bot_data['genius']
    genius.artist.return_value = artist_dict

    res = artist.display_artist(update, context)

    keyboard = (context.bot.send_photo
                .call_args[1]['reply_markup']['inline_keyboard'])

    assert len(keyboard) == 4
    assert len(keyboard[0]) == 2

    # artist ID = 1
    genius.artist.assert_called_once_with(1)

    if update.callback_query:
        update.callback_query.answer.assert_called_once()

    assert res == constants.END


@pytest.fixture(scope='module')
def albums_dict(data_path):
    with open(join(data_path, 'artist_albums.json'), 'r') as f:
        return json.load(f)


@pytest.mark.parametrize('update, artist_albums_dict',
                         [
                             (pytest.lazy_fixture('update_callback_query'),
                              pytest.lazy_fixture('albums_dict')),

                             (pytest.lazy_fixture('update_message'),
                              {'albums': []}),
                         ])
def test_display_artist_albums(update, context, artist_dict, artist_albums_dict):
    if update.callback_query:
        update.callback_query.data = 'artist_1_albums'
    else:
        context.args[0] = 'artist_1_albums'

    genius = context.bot_data['genius']
    genius.artist.return_value = artist_dict
    genius.artist_albums.return_value = artist_albums_dict

    res = artist.display_artist_albums(update, context)

    # artist ID = 1
    assert genius.artist_albums.call_args[0][0] == 1

    if update.callback_query:
        update.callback_query.answer.assert_called_once()

    if artist_albums_dict['albums']:
        text = context.bot.send_message.call_args[0][1]
        assert len(text.split('\n')) >= len(artist_albums_dict['albums'])
    else:
        genius.artist.assert_called_once_with(1)

    assert res == constants.END


@pytest.fixture(scope='module')
def songs_dict(data_path):
    with open(join(data_path, 'artist_songs.json'), 'r') as f:
        return json.load(f)


@pytest.mark.parametrize('update, artist_songs_dict',
                         [
                             (pytest.lazy_fixture('update_callback_query'),
                              pytest.lazy_fixture('songs_dict')),

                             (pytest.lazy_fixture('update_message'),
                              {'songs': [], 'next_page': None}),
                         ])
def test_display_artist_songs(update, context, artist_dict, artist_songs_dict):
    if update.callback_query:
        update.callback_query.data = 'artist_1_songs_ppt_1'
    else:
        context.args[0] = 'artist_1_songs_ptt_1'

    genius = context.bot_data['genius']
    genius.artist.return_value = artist_dict
    genius.artist_songs.return_value = artist_songs_dict
    if update.callback_query:
        update.callback_query.message.configure_mock(photo='Photo object')

    res = artist.display_artist_songs(update, context)

    # artist ID = 1
    assert genius.artist_songs.call_args[0][0] == 1

    if update.callback_query:
        update.callback_query.answer.assert_called_once()

    if artist_songs_dict['songs']:
        reply = context.bot.send_message.call_args[0][1]
        keyboard = (context.bot.send_message.call_args[1]
                    ['reply_markup']['inline_keyboard'])
        assert len(reply.split('\n')) >= len(artist_songs_dict['songs'])
        assert len(keyboard[0]) == 3
        assert keyboard[0][0].text == '⬛️'
        assert keyboard[0][1].text == '1'
        assert keyboard[0][2].callback_data == 'artist_1_songs_ppt_2'
    else:
        genius.artist.assert_called_once_with(1)

    assert res == constants.END
