import json
from os.path import join
from unittest.mock import MagicMock

import pytest

from geniust import constants
from geniust.functions import artist


@pytest.mark.parametrize(
    "update",
    [
        pytest.lazy_fixture("update_callback_query"),
        pytest.lazy_fixture("update_message"),
        pytest.lazy_fixture("update_parametrized_command"),
    ],
)
def test_type_artist(update, context):
    if update.message and update.message.text == "/":
        context.args = ["some", "query"]
        parametrized_command = True
    else:
        parametrized_command = False

    res = artist.type_artist(update, context)

    if getattr(update, "callback_query", None):
        update.callback_query.answer.assert_called_once()
    else:
        update.message.reply_text.assert_called_once()

    if parametrized_command:
        assert res == constants.END
    else:
        assert res == constants.TYPING_ARTIST


@pytest.mark.parametrize(
    "search_dict",
    [pytest.lazy_fixture("search_artists_dict"), {"sections": [{"hits": []}]}],
)
def test_search_artists(update_message, context, search_dict):
    update = update_message
    genius = context.bot_data["genius"]
    genius.search_artists.return_value = search_dict

    if search_dict["sections"][0]["hits"]:
        update.message.text = "test"

    res = artist.search_artists(update, context)

    if search_dict["sections"][0]["hits"]:
        keyboard = update.message.reply_text.call_args[1]["reply_markup"][
            "inline_keyboard"
        ]
        assert len(keyboard) == 10

    assert res == constants.END


@pytest.fixture
def artist_dict_no_description(artist_dict):
    artist_dict["artist"]["description_annotation"]["annotations"][0]["body"][
        "plain"
    ] = ""
    return artist_dict


@pytest.mark.parametrize(
    "artist_data",
    [
        pytest.lazy_fixture("artist_dict"),
        pytest.lazy_fixture("artist_dict_no_description"),
    ],
)
@pytest.mark.parametrize(
    "update",
    [
        pytest.lazy_fixture("update_callback_query"),
        pytest.lazy_fixture("update_message"),
    ],
)
@pytest.mark.parametrize("platform", ["genius", "spotify"])
def test_display_artist(update, context, artist_data, platform):
    if update.callback_query:
        update.callback_query.data = f"artist_1_{platform}"
    else:
        context.args = [f"artist_1_{platform}"]

    genius = context.bot_data["genius"]
    genius.artist.return_value = artist_data
    genius.search_artists.return_value = MagicMock()

    res = artist.display_artist(update, context)

    if platform == "genius":
        genius.artist.assert_called_once_with(1)
        keyboard = context.bot.send_photo.call_args[1]["reply_markup"][
            "inline_keyboard"
        ]
        assert len(keyboard) == 4
        if artist_data["artist"]["description_annotation"]["annotations"][0]["body"][
            "plain"
        ]:
            assert len(keyboard[0]) == 2
        else:
            assert len(keyboard[0]) == 1

    if update.callback_query:
        update.callback_query.answer.assert_called_once()

    assert res == constants.END


@pytest.fixture(scope="module")
def albums_dict(data_path):
    with open(join(data_path, "artist_albums.json"), "r") as f:
        return json.load(f)


@pytest.mark.parametrize(
    "update, artist_albums_dict",
    [
        (
            pytest.lazy_fixture("update_callback_query"),
            pytest.lazy_fixture("albums_dict"),
        ),
        (pytest.lazy_fixture("update_message"), {"albums": []}),
    ],
)
def test_display_artist_albums(update, context, artist_dict, artist_albums_dict):
    if update.callback_query:
        update.callback_query.data = "artist_1_albums"
    else:
        context.args = ["artist_1_albums"]

    genius = context.bot_data["genius"]
    genius.artist.return_value = artist_dict
    genius.artist_albums.return_value = artist_albums_dict

    res = artist.display_artist_albums(update, context)

    # artist ID = 1
    assert genius.artist_albums.call_args[0][0] == 1

    if update.callback_query:
        update.callback_query.answer.assert_called_once()

    if artist_albums_dict["albums"]:
        text = context.bot.send_message.call_args[0][1]
        assert len(text.split("\n")) >= len(artist_albums_dict["albums"])
    else:
        genius.artist.assert_called_once_with(1)

    assert res == constants.END


@pytest.fixture(scope="function")
def songs_dict(data_path):
    with open(join(data_path, "artist_songs.json"), "r") as f:
        return json.load(f)


@pytest.mark.parametrize("page", [1, 3, 10])
@pytest.mark.parametrize(
    "update, artist_songs_dict, sort",
    [
        (
            pytest.lazy_fixture("update_callback_query"),
            pytest.lazy_fixture("songs_dict"),
            "ppt",
        ),
        (
            pytest.lazy_fixture("update_callback_query"),
            pytest.lazy_fixture("songs_dict"),
            "rdt",
        ),
        (
            pytest.lazy_fixture("update_callback_query"),
            pytest.lazy_fixture("songs_dict"),
            "rdt",
        ),
        (pytest.lazy_fixture("update_message"), {"songs": [], "next_page": None}, None),
    ],
)
def test_display_artist_songs(
    update, context, artist_dict, artist_songs_dict, sort, page
):
    if update.callback_query:
        update.callback_query.data = f"artist_1_songs_{sort}_{page}"
    else:
        context.args = [f"artist_1_songs_{sort}_{page}"]
    if page == 10:
        next_page = None
    else:
        next_page = page + 1

    artist_songs_dict["next_page"] = next_page

    genius = context.bot_data["genius"]
    genius.artist.return_value = artist_dict
    genius.artist_songs.return_value = artist_songs_dict
    if update.callback_query and sort != "ttl":
        update.callback_query.message.configure_mock(photo="Photo object")
    elif update.callback_query:
        update.callback_query.message.configure_mock(photo=None)

    res = artist.display_artist_songs(update, context)

    # artist ID = 1
    assert genius.artist_songs.call_args[0][0] == 1

    if update.callback_query:
        update.callback_query.answer.assert_called_once()

    if artist_songs_dict["songs"]:
        reply = context.bot.send_message.call_args[0][1]
        keyboard = context.bot.send_message.call_args[1]["reply_markup"][
            "inline_keyboard"
        ]
        assert len(reply.split("\n")) >= len(artist_songs_dict["songs"])
        assert len(keyboard[0]) == 3
        if page == 1:
            assert keyboard[0][0].text == "⬛️"
            assert keyboard[0][1].text == "1"
            assert keyboard[0][2].callback_data == f"artist_1_songs_{sort}_2"
        elif page == 3:
            assert keyboard[0][0].callback_data == f"artist_1_songs_{sort}_2"
            assert keyboard[0][1].text == "3"
            assert keyboard[0][2].callback_data == f"artist_1_songs_{sort}_4"
        else:
            assert keyboard[0][0].callback_data == f"artist_1_songs_{sort}_9"
            assert keyboard[0][1].text == "10"
            assert keyboard[0][2].text == "⬛️"
    else:
        genius.artist.assert_called_once_with(1)

    assert res == constants.END
