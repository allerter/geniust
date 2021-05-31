from collections import namedtuple
from unittest.mock import MagicMock, patch

import pytest

from geniust import api, constants
from geniust.constants import Preferences
from geniust.functions import recommender as rcr


@pytest.mark.parametrize("genius_token", ["test_token", None])
@pytest.mark.parametrize("spotify_token", ["test_token", None])
def test_welcome_to_shuffle(update_message, context, genius_token, spotify_token):
    update = update_message
    context.user_data["genius_token"] = genius_token
    context.user_data["spotify_token"] = spotify_token

    res = rcr.welcome_to_shuffle(update, context)

    assert res == constants.SELECT_ACTION


def test_input_preferences(update_callback_query, context):
    update = update_callback_query

    res = rcr.input_preferences(update, context)

    assert res == constants.SELECT_GENRES


@pytest.mark.parametrize(
    "update",
    [
        pytest.lazy_fixture("update_message"),
        pytest.lazy_fixture("update_callback_query"),
    ],
)
@pytest.mark.parametrize("age", ["_invalid", "20"])
def test_input_age(
    update,
    context,
    requests_mock,
    age,
    recommender_genres_age_20,
):
    if update.message:
        update.message.text = age
    if age == "20":
        api_root = api.Recommender.API_ROOT
        requests_mock.get(api_root + "genres?age=20", json=recommender_genres_age_20)

    res = rcr.input_age(update, context)

    if update.callback_query or age != "20":
        assert res == constants.SELECT_GENRES
    else:
        assert res == constants.SELECT_ARTISTS


@pytest.mark.parametrize("genres", [[], ["pop"]])
@pytest.mark.parametrize("query_data", ["genre", "done", "select_4"])
def test_select_genres(update_callback_query, context, query_data, genres):
    update = update_callback_query
    update.callback_query.data = query_data
    context.user_data["genres"] = genres

    rcr.select_genres(update, context)

    if context.user_data["bot_lang"] == "fa" and query_data == "genres":
        assert "persian" in context.user_data["genres"]


@pytest.mark.parametrize(
    "update",
    [
        pytest.lazy_fixture("update_message"),
        pytest.lazy_fixture("update_callback_query"),
    ],
)
def test_begin_artist(update, context):
    res = rcr.begin_artist(update, context)

    assert res == constants.SELECT_ARTISTS


def test_input_artist(update_callback_query, context):
    update = update_callback_query

    res = rcr.input_artist(update, context)

    assert res == constants.SELECT_ARTISTS


@pytest.mark.parametrize(
    "update",
    [
        pytest.lazy_fixture("update_message"),
        pytest.lazy_fixture("update_callback_query"),
    ],
)
@pytest.mark.parametrize("query", ["select_none", "select_1", "done"])
@pytest.mark.parametrize("text", ["Eminem", "no_matches"])
def test_select_artists(
    update,
    context,
    query,
    text,
    requests_mock,
    recommender_search_artists,
    recommender_artist,
):
    context.user_data["artists"] = []
    api_root = api.Recommender.API_ROOT
    if update.message:
        update.message.text = text
    else:
        update.callback_query.data = query
        requests_mock.get(api_root + "artists/1", json=recommender_artist)
        if query == "done":
            context.user_data["genres"] = ["pop"]
            context.user_data["artists"] = []
    if text == "Eminem":
        requests_mock.get(
            api_root + f"search/artists?q={text}", json=recommender_search_artists
        )
    else:
        requests_mock.get(api_root + "search/artists?q=no_matches", json={"hits": []})

    rcr.select_artists(update, context)

    if update.callback_query and query == "done":
        context.bot_data["db"].update_preferences.assert_called_once()


@pytest.mark.parametrize("platform", ["genius", "spotify"])
@pytest.mark.parametrize(
    "result",
    [
        {"preferences": {"genres": [], "artists": []}},
        pytest.lazy_fixture("recommender_preferences"),
    ],
)
def test_process_preferences(
    update_callback_query,
    song_dict,
    context,
    platform,
    result,
    requests_mock,
):
    update = update_callback_query
    update.callback_query.data = f"process_{platform}"
    context.user_data["genius_token"] = "test_token"
    context.user_data["spotify_token"] = "test_token"
    api_root = api.Recommender.API_ROOT
    endpoint = f"preferences?token=test_token&platform={platform}"
    requests_mock.get(api_root + endpoint, json=result)

    client = MagicMock()
    client.RefreshingCredentials().refresh_user_token.return_value = "test_token"
    current_module = "geniust.functions.recommender"
    with patch(current_module + ".tk", client):
        rcr.process_preferences(update, context)


def test_reset_shuffle(update_callback_query, context):
    update = update_callback_query

    res = rcr.reset_shuffle(update, context)

    assert res == constants.END
    context.bot_data["db"].delete_preferences.assert_called_once()


@pytest.mark.parametrize(
    "update",
    [
        pytest.lazy_fixture("update_message"),
        pytest.lazy_fixture("update_callback_query"),
        pytest.lazy_fixture("update_callback_query"),
    ],
)
def test_display_recommendations(
    update, context, requests_mock, recommender_recommendations
):
    # modify songs to cover all possible cases
    songs = recommender_recommendations.copy()["recommendations"]
    for key in ("id_spotify", "preview_url", "download_url"):
        songs[0][key] = None
    songs[1]["download_url"] = "some_url"
    context.user_data["preferences"] = Preferences(genres=["pop"], artists=[])
    api_root = api.Recommender.API_ROOT
    requests_mock.get(
        api_root + "recommendations?genres=pop", json=recommender_recommendations
    )

    res = rcr.display_recommendations(update, context)

    assert res == constants.END
