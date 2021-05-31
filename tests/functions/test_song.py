from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from geniust import constants
from geniust.functions import song


@pytest.mark.parametrize(
    "update",
    [
        pytest.lazy_fixture("update_callback_query"),
        pytest.lazy_fixture("update_message"),
        pytest.lazy_fixture("update_parametrized_command"),
    ],
)
def test_type_song(update, context):
    if update.message and update.message.text == "/":
        context.args = ["some", "query"]
        parametrized_command = True
    else:
        parametrized_command = False

    res = song.type_song(update, context)

    if getattr(update, "callback_query", None):
        update.callback_query.answer.assert_called_once()
    else:
        update.message.reply_text.assert_called_once()

    if parametrized_command:
        assert res == constants.END
    else:
        assert res == constants.TYPING_SONG


@pytest.mark.parametrize(
    "update",
    [
        pytest.lazy_fixture("update_callback_query"),
        pytest.lazy_fixture("update_message"),
        pytest.lazy_fixture("update_parametrized_command"),
    ],
)
def test_type_lyrics(update, context):
    if update.message and update.message.text == "/":
        context.args = ["some", "query"]
        parametrized_command = True
    else:
        parametrized_command = False

    res = song.type_lyrics(update, context)

    if getattr(update, "callback_query", None):
        update.callback_query.answer.assert_called_once()
    else:
        update.message.reply_text.assert_called_once()

    if parametrized_command:
        assert res == constants.END
    else:
        assert res == constants.TYPING_LYRICS


@pytest.mark.parametrize(
    "search_dict",
    [pytest.lazy_fixture("search_lyrics_dict"), {"sections": [{"hits": []}]}],
)
def test_search_lyrics(update_message, context, search_dict):
    update = update_message
    genius = context.bot_data["genius"]
    genius.search_lyrics.return_value = search_dict

    if search_dict["sections"][0]["hits"]:
        update.message.text = "test"

    res = song.search_lyrics(update, context)

    if update.message.text:
        text = update.message.reply_text.call_args[0][0]
        for hit in search_dict["sections"][0]["hits"]:
            assert hit["result"]["title"] in text

    assert res == constants.END


@pytest.mark.parametrize(
    "search_dict",
    [pytest.lazy_fixture("search_songs_dict"), {"sections": [{"hits": []}]}],
)
def test_search_songs(update_message, context, search_dict):
    update = update_message
    genius = context.bot_data["genius"]
    genius.search_songs.return_value = search_dict

    if search_dict["sections"][0]["hits"]:
        update.message.text = "test"

    res = song.search_songs(update, context)

    if search_dict["sections"][0]["hits"]:
        keyboard = update.message.reply_text.call_args[1]["reply_markup"][
            "inline_keyboard"
        ]
        assert len(keyboard) == 10

    assert res == constants.END


@pytest.fixture
def song_dict_no_description(song_dict):
    song_dict["song"]["description_annotation"]["annotations"][0]["body"]["plain"] = ""
    return song_dict


@pytest.mark.parametrize(
    "song_data",
    [pytest.lazy_fixture("song_dict"), pytest.lazy_fixture("song_dict_no_description")],
)
@pytest.mark.parametrize(
    "update",
    [
        pytest.lazy_fixture("update_callback_query"),
        pytest.lazy_fixture("update_message"),
    ],
)
@pytest.mark.parametrize("platform", ["genius", "spotify"])
@pytest.mark.parametrize("search_result", [{"match": None}, {"match": {"id": 1}}])
def test_display_song(update, context, song_data, platform, search_result):
    context.bot_data["recommender"] = MagicMock()
    if update.callback_query:
        update.callback_query.data = f"song_1_{platform}"
    else:
        context.args = [f"song_1_{platform}"]

    genius = context.bot_data["genius"]
    genius.song.return_value = song_data
    genius.search_songs.return_value = search_result

    res = song.display_song(update, context)

    if platform == "genius":
        genius.song.assert_called_once_with(1)

    if update.callback_query:
        update.callback_query.answer.assert_called_once()

    assert res == constants.END


@pytest.mark.parametrize(
    "update",
    [
        pytest.lazy_fixture("update_callback_query"),
        pytest.lazy_fixture("update_message"),
    ],
)
@pytest.mark.parametrize("platform", ["recommender", "spotify"])
def test_download_song(update, context, platform):
    if update.callback_query:
        update.callback_query.data = f"song_1_{platform}_preview"
    else:
        context.args = [f"song_1_{platform}_preview"]

    res = song.download_song(update, context)

    if update.callback_query:
        update.callback_query.answer.assert_called_once()

    assert res == constants.END


@pytest.mark.parametrize("developer", [True, False])
@pytest.mark.parametrize("error", [True, False])
def test_display_lyrics(
    update_callback_query, context, song_id, full_album, developer, error
):
    update = update_callback_query
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["display_lyrics"]
    context.user_data["include_annotations"] = True

    if developer:
        update.effective_user.id = constants.DEVELOPERS[0]
    else:
        update.effective_user.id = 1

    genius_t = context.bot_data["genius"]
    genius = context.bot_data["lyricsgenius"]
    genius_t.song.return_value = full_album["tracks"][3]
    if error:
        genius_t.lyrics.side_effect = Exception("some error")
        genius.lyrics.return_value = BeautifulSoup(
            full_album["tracks"][3]["song"]["lyrics"],
            "html.parser",
        ).get_text()
    else:
        genius_t.lyrics.return_value = BeautifulSoup(
            full_album["tracks"][3]["song"]["lyrics"],
            "html.parser",
        )

    song.display_lyrics(update, context, song_id, text)

    genius_t.lyrics.assert_called_once()
    args = genius_t.lyrics.call_args[1]
    assert args["song_id"] == song_id
    assert args["song_url"] == full_album["tracks"][3]["song"]["url"]
    if developer:
        assert args["include_annotations"] is True
    else:
        assert args["include_annotations"] is False
    assert args["telegram_song"] is True


@pytest.mark.parametrize(
    "update",
    [
        pytest.lazy_fixture("update_callback_query"),
        pytest.lazy_fixture("update_message"),
    ],
)
def test_thread_display_lyrics(update, context):
    if update.callback_query:
        update.callback_query.data = "song_1_lyrics"
    else:
        context.args = ["song_1_lyrics"]

    thread = MagicMock()
    with patch("threading.Thread", thread):
        res = song.thread_display_lyrics(update, context)

    target_function = thread.call_args[1]["target"]
    args = thread.call_args[1]["args"]

    assert target_function == song.display_lyrics

    song_id = 1
    assert args[:3] == (update, context, song_id)

    thread().start.assert_called_once()
    thread().join.assert_called_once()

    assert res == constants.END
