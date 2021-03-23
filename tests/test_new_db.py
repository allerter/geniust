import pytest

from geniust import new_db as db
from geniust.new_db import Users, Preferences


@pytest.fixture(scope="function")
def database():
    database = db.Database("sqlite:///:memory:")
    with database.Session() as session:
        user = Users(
            chat_id=1,
            include_annotations=True,
            lyrics_lang="English + Non-English",
            bot_lang="en",
            genius_token="test_token",
            spotify_token=None,
        )
        session.add(user)

        pref = Preferences(chat_id=1, genres=['pop'], artists=[])
        session.add(pref)
        session.commit()
    return database


@pytest.mark.parametrize("chat_id", (1, 2))
def test_user(database, chat_id):
    user_data = {}
    database.user(chat_id, user_data)

    assert user_data["include_annotations"] is True
    assert user_data["spotify_token"] is None
    if chat_id == 1:
        assert user_data["preferences"].genres == ["pop"]
        assert user_data["preferences"].artists == []
        assert user_data["genius_token"] == "test_token"
    else:
        with database.Session() as session:
            user = session.get(Users, 2)
        assert user is not None


@pytest.mark.parametrize("platform", ["genius", "spotify"])
def test_get_token(database, platform):
    res = database.get_token(1, platform)
    if platform == "genius":
        assert res == "test_token"
    else:
        assert res is None


def test_get_tokens(database):
    res = database.get_tokens(1)
    assert res == ("test_token", None)


def test_get_language(database):
    res = database.get_language(1)
    assert res == "en"


def test_get_preferences(database):
    res = database.get_preferences(1)
    assert res.genres == ["pop"]
    assert res.artists == []


def test_update_include_annotations(database):
    database.update_include_annotations(1, False)
    with database.Session() as session:
        user = session.get(Users, 1)

    assert user.include_annotations is False


def test_update_lyrics_language(database):
    new_value = "English"
    database.update_lyrics_language(1, new_value)
    with database.Session() as session:
        user = session.get(Users, 1)

    assert user.lyrics_lang == new_value


def test_update_bot_language(database):
    new_value = "fa"
    database.update_bot_language(1, new_value)
    with database.Session() as session:
        user = session.get(Users, 1)

    assert user.bot_lang == new_value


@pytest.mark.parametrize("platform", ("genius", "spotify"))
def test_update_token(database, platform):
    new_value = "new_token"
    database.update_token(1, new_value, platform)
    with database.Session() as session:
        user = session.get(Users, 1)

    assert getattr(user, f"{platform}_token") == new_value


@pytest.mark.parametrize("platform", ("genius", "spotify"))
def test_delete_token(database, platform):
    database.delete_token(1, platform)
    with database.Session() as session:
        user = session.get(Users, 1)

    assert getattr(user, f"{platform}_token") is None


@pytest.mark.parametrize("chat_id", [1, 2])
def test_update_preferences(database, chat_id):
    new_pref = Preferences(genres=["pop", "rock"], artists=["Eminem", "Blackbear"])
    database.update_preferences(chat_id, new_pref)
    with database.Session() as session:
        pref = session.get(Preferences, chat_id)

    assert pref.artists == new_pref.artists
    assert pref.genres == new_pref.genres


def test_delete_preferences(database):
    database.delete_preferences(1)
    with database.Session() as session:
        pref = session.get(Preferences, 1)

    assert pref is None
