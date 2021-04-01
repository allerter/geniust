import pytest
import re
import json
from unittest.mock import AsyncMock, MagicMock, patch, create_autospec
from os.path import join

from bs4 import BeautifulSoup
from telethon import TelegramClient

from geniust import api
from geniust.constants import Preferences


@pytest.fixture(scope="function")
def lyrics(page):
    html = BeautifulSoup(page.replace("<br/>", "\n"), "html.parser")
    lyrics = html.find_all("div", class_=re.compile("^lyrics$|Lyrics__Container"))
    if lyrics[0].get("class")[0] == "lyrics":
        lyrics = lyrics[0]
        lyrics = lyrics.find("p") if lyrics.find("p") else lyrics
    else:
        br = html.new_tag("br")
        try:
            for div in lyrics[1:]:
                lyrics[0].append(div).append(br)
        except Exception as e:
            msg = f"{str(e)} with {div.attrs}"
            print(msg)
        lyrics = lyrics[0]

    return lyrics


@pytest.fixture(scope="module")
def posted_annotations(annotations):
    posted = []
    for id_, _ in annotations.items():
        posted.append((id_, f"link_{id_}"))

    return posted


@pytest.fixture
def referents(data_path):
    with open(join(data_path, "referents.json"), "r") as f:
        return json.load(f)


@pytest.mark.parametrize("text_format", ["html", "html,plain"])
def test_song_annotations(referents, text_format):
    client = MagicMock()
    client.referents.return_value = referents

    if text_format == "html,plain":
        with pytest.raises(AssertionError):
            api.GeniusT.song_annotations(client, 1, text_format)
        return
    else:
        res = api.GeniusT.song_annotations(client, 1, text_format)

    assert client.referents.call_args[1]["song_id"] == 1
    assert client.referents.call_args[1]["text_format"] == text_format

    assert isinstance(res, dict)

    for key, value in res.items():
        assert isinstance(key, int)
        assert isinstance(value, str)

    for referent in referents["referents"]:
        assert referent["id"] in res.keys()


@pytest.mark.parametrize("include_annotations", [True, False])
@pytest.mark.parametrize("lyrics_state", ["complete", "instrumental", "unreleased"])
def test_fetch(song_dict, lyrics_state, include_annotations):
    client = MagicMock()
    if include_annotations and lyrics_state == "complete":
        annotations = {"annotations": []}
    else:
        annotations = {}
    client.lyrics.return_value = "lyrics", annotations
    client.song.return_value = {"song": {}}
    song = song_dict["song"]
    song["instrumental"] = True if lyrics_state == "instrumental" else False
    song["lyrics_state"] = lyrics_state

    res = api.GeniusT.fetch(client, song_dict, include_annotations)

    assert res is None
    assert client.song.called_once_with(song["id"])
    assert client.lyrics.called_once_with(
        song["id"], song["url"], include_annotations=include_annotations
    )

    if lyrics_state == "instrumental":
        lyrics = "[Instrumental]"
    elif lyrics_state == "unreleased":
        lyrics = ""
    else:
        lyrics = "lyrics"

    assert song["lyrics"] == lyrics
    assert song["annotations"] == annotations


def test_get_channel():
    client = create_autospec(TelegramClient)

    with patch("telethon.TelegramClient", client):
        res = api.get_channel()

    assert res is not None


@pytest.fixture
def album_tracks(data_path):
    with open(join(data_path, "album_tracks.json"), "r") as f:
        return json.load(f)


@pytest.mark.asyncio
async def test_search_album(album_dict, album_tracks):
    client = MagicMock()
    client.album.return_value = album_dict
    client.album_tracks.return_value = album_tracks
    queue = MagicMock()
    album = album_dict["album"]

    res = await api.GeniusT.search_album(
        client, album["id"], include_annotations=True, queue=queue
    )

    assert res is None
    assert queue.put.call_args[0][0] == album
    assert client.album.call_args[0][0] == album["id"]
    assert client.album_tracks.call_args[0][0] == album["id"]
    assert client.fetch.call_count == len(album_tracks["tracks"])


def test_async_album_search(album_dict):

    client = MagicMock()
    album = album_dict["album"]
    client.search_album.return_value = AsyncMock()()
    queue = MagicMock()
    queue().get.return_value = album

    with patch("queue.Queue", queue):
        res = api.GeniusT.async_album_search(
            client, album["id"], include_annotations=True
        )

    assert res == album
    queue = queue()
    queue.get.assert_called_once()
    client.search_album.assert_called_once_with(album["id"], True, queue)


def test_telegram_annotation(annotation):
    annotation = annotation["annotation"]["body"]["html"]
    returned_annotation, preview = api.telegram_annotation(annotation)

    assert preview is True, "Annotation preview wasn't true"
    assert "&#8204;" in returned_annotation, "No non-width space char in annotation"


def test_replace_hrefs(lyrics, posted_annotations):
    api.replace_hrefs(lyrics)

    ids = [x[0] for x in posted_annotations]

    for a in lyrics.find_all("a"):
        if (id_ := a.get("href")) != "0":
            assert id_ in ids, "annotation ID wasn't in lyrics"


def test_replace_hrefs_telegram_song(lyrics, posted_annotations):

    api.replace_hrefs(lyrics, posted_annotations, telegram_song=True)

    msg = "Annotation link wasn't found in the tags"
    for text in [x[1] for x in posted_annotations]:
        assert lyrics.find("a", attrs={"href": text}) is not None, msg


@pytest.fixture
def genius():
    return api.GeniusT()


@pytest.mark.parametrize("html", [pytest.lazy_fixture("page"), "None"])
def test_lyrics_no_annotations(genius, song_id, song_url, html, requests_mock):
    requests_mock.get(song_url, text=html)

    lyrics, annotations = genius.lyrics(
        song_id=song_id,
        song_url=song_url,
        include_annotations=False,
        telegram_song=False,
    )
    assert isinstance(lyrics, str), "Lyrics wasn't a string"
    assert annotations == {}, "Annotations weren't empty"
    if html == "None":
        assert lyrics == "None"


def test_lyrics_telegram_song(genius, song_id, song_url, page, annotations):
    page = MagicMock(return_value=page)
    client = MagicMock()
    annotations = MagicMock(return_value=annotations)

    current_module = "geniust.api"
    with patch(current_module + ".GeniusT._make_request", page), patch(
        current_module + ".GeniusT.song_annotations", annotations
    ), patch("telethon.TelegramClient", client), patch(
        current_module + ".get_channel", MagicMock()
    ):
        lyrics = genius.lyrics(
            song_id=song_id,
            song_url=song_url,
            include_annotations=True,
            telegram_song=True,
        )
    assert type(lyrics) is not str, "Lyrics was a string"


class TestRecommender:
    def test_init(self, requests_mock, recommender_num_songs, recommender_genres):
        api_root = api.Recommender.API_ROOT
        requests_mock.get(api_root + "genres", json=recommender_genres)
        requests_mock.get(api_root + "songs/len", json=recommender_num_songs)

        rcr = api.Recommender()

        assert rcr.num_songs == recommender_num_songs["len"]
        assert rcr.genres == recommender_genres["genres"]

    def test_artist(self, requests_mock, recommender, recommender_artist):
        api_root = api.Recommender.API_ROOT
        requests_mock.get(api_root + "artists/1", json=recommender_artist)

        artist = recommender.artist(1)

        assert artist.id == recommender_artist["artist"]["id"]

    def test_genres_age_20(
        self,
        requests_mock,
        recommender,
        recommender_genres_age_20,
    ):
        api_root = api.Recommender.API_ROOT
        requests_mock.get(api_root + "genres?age=20", json=recommender_genres_age_20)

        genres = recommender.genres_by_age(age=20)

        assert genres == recommender_genres_age_20["genres"]

    def test_preferences(
        self,
        requests_mock,
        recommender,
        recommender_preferences,
    ):
        api_root = api.Recommender.API_ROOT
        requests_mock.get(
            api_root + "preferences?token=test_token&platform=genius",
            json=recommender_preferences,
        )

        pref = recommender.preferences_from_platform(
            token="test_token", platform="genius"
        )

        rcr_pref = recommender_preferences["preferences"]
        assert pref.genres == rcr_pref["genres"]
        assert pref.artists == rcr_pref["artists"]

    def test_search_artist(
        self,
        requests_mock,
        recommender,
        recommender_search_artists,
    ):
        api_root = api.Recommender.API_ROOT
        requests_mock.get(
            api_root + "search/artists?q=Eminem", json=recommender_search_artists
        )

        hits = recommender.search_artist("Eminem")

        assert hits[0].name == recommender_search_artists["hits"][0]["name"]
        assert hits[-1].name == recommender_search_artists["hits"][-1]["name"]

    def test_shuffle(
        self,
        requests_mock,
        recommender,
        recommender_recommendations,
    ):
        api_root = api.Recommender.API_ROOT
        requests_mock.get(
            api_root + "recommendations?genres=pop&artists=Eminem",
            json=recommender_recommendations,
        )
        pref = Preferences(genres=["pop"], artists=["Eminem"])

        songs = recommender.shuffle(pref)

        rcr_songs = recommender_recommendations["recommendations"]
        assert songs[0].id == rcr_songs[0]["id"]
        assert songs[-1].id == rcr_songs[-1]["id"]

    def test_song(
        self,
        requests_mock,
        recommender,
        recommender_song,
    ):
        api_root = api.Recommender.API_ROOT
        requests_mock.get(api_root + "songs/1", json=recommender_song)

        song = recommender.song(1)

        assert song.id == 1
