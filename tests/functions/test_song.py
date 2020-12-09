from unittest.mock import patch, MagicMock

import pytest

from geniust import constants
from geniust.functions import song


@pytest.mark.parametrize('update', [pytest.lazy_fixture('update_callback_query'),
                                    pytest.lazy_fixture('update_message'),
                                    ])
def test_type_song(update, context):

    res = song.type_song(update, context)

    if getattr(update, 'callback_query', None):
        update.callback_query.answer.assert_called_once()
    else:
        update.message.reply_text.assert_called_once()

    assert res == constants.TYPING_SONG


@pytest.mark.parametrize('search_dict',
                         [pytest.lazy_fixture('search_songs_dict'),
                          {'sections': [{'hits': []}]}
                          ])
def test_search_songs(update_message, context, search_dict):
    update = update_message
    genius = context.bot_data['genius']
    genius.search_songs.return_value = search_dict

    if search_dict['sections'][0]['hits']:
        update.message.text = 'test'

    res = song.search_songs(update, context)

    if search_dict['sections'][0]['hits']:
        keyboard = (update.message.reply_text
                    .call_args[1]['reply_markup']['inline_keyboard'])
        assert len(keyboard) == 10

    assert res == constants.END


@pytest.fixture
def song_dict_no_description(song_dict):
    song_dict['song']["description_annotation"]["annotations"][0]["body"]["plain"] = ""
    return song_dict


@pytest.mark.parametrize('song_data', [pytest.lazy_fixture('song_dict'),
                                       pytest.lazy_fixture('song_dict_no_description')])
@pytest.mark.parametrize('update', [pytest.lazy_fixture('update_callback_query'),
                                    pytest.lazy_fixture('update_message'),
                                    ])
def test_display_song(update, context, song_data):
    if update.callback_query:
        update.callback_query.data = 'song_1'
    else:
        context.args[0] = 'song_1'

    genius = context.bot_data['genius']
    genius.song.return_value = song_data

    res = song.display_song(update, context)

    keyboard = (context.bot.send_photo
                .call_args[1]['reply_markup']['inline_keyboard'])

    assert len(keyboard) == 1
    if song_data['song']["description_annotation"]["annotations"][0]["body"]["plain"]:
        assert len(keyboard[0]) == 2
    else:
        assert len(keyboard[0]) == 1

    # song ID = 1
    genius.song.assert_called_once_with(1)

    if update.callback_query:
        update.callback_query.answer.assert_called_once()

    assert res == constants.END


@pytest.mark.parametrize('update', [pytest.lazy_fixture('update_callback_query'),
                                    pytest.lazy_fixture('update_message'),
                                    ])
def test_thread_display_lyrics(update, context):
    if update.callback_query:
        update.callback_query.data = 'song_1_lyrics'
    else:
        context.args[0] = 'song_1_lyrics'

    thread = MagicMock()
    with patch('threading.Thread', thread):
        res = song.thread_display_lyrics(update, context)

    target_function = thread.call_args[1]['target']
    args = thread.call_args[1]['args']

    assert target_function == song.display_lyrics

    song_id = 1
    assert args[:3] == (update, context, song_id)

    thread().start.assert_called_once()
    thread().join.assert_called_once()

    assert res == constants.END


def test_display_lyrics(update_callback_query, context, song_id, full_album):
    update = update_callback_query
    language = context.user_data['bot_lang']
    text = context.bot_data['texts'][language]['display_lyrics']
    context.user_data['include_annotations'] = True

    client = MagicMock()
    client().lyrics.return_value = full_album['tracks'][3]['song']['lyrics']
    client().song.return_value = full_album['tracks'][3]

    with patch('geniust.api.GeniusT', client):
        song.display_lyrics(update, context, song_id, text)

    client = client()
    client.lyrics.assert_called_once()
    args = client.lyrics.call_args[1]
    assert args['song_id'] == song_id
    assert args['song_url'] == full_album['tracks'][3]['song']['url']
    assert args['include_annotations'] is True
    assert args['telegram_song'] is True
