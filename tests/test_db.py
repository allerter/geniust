from unittest.mock import patch, MagicMock, create_autospec

import pytest

from geniust import db, constants, get_user
from geniust.constants import Preferences


@pytest.fixture(scope="module")
def database():
    return db.Database("test_table", "pref_table")


@patch("psycopg2.connect")
def test_get_cursor(connection):
    func = MagicMock()

    res = db.get_cursor(func)
    res(1, 2, a=1)

    connection.assert_called_once_with(constants.DATABASE_URL, sslmode="require")
    cursor = connection().__enter__().cursor().__enter__()
    func.assert_called_once_with(1, 2, a=1, cursor=cursor)


@pytest.mark.parametrize("user_data", [{"bot_lang": "en"}, {}])
def test_get_user(update_message, context, user_data):
    update = update_message
    context.user_data = user_data
    func = MagicMock()
    user = create_autospec(db.Database.user)

    with patch("geniust.db.Database.user", user):
        res = get_user(func)
        res(update, context)

    func.assert_called_once_with(update, context)

    if user_data == {}:
        assert user.call_args[0][1] == update.effective_chat.id
        assert user.call_args[0][2] == context.user_data
    else:
        user.assert_not_called()


def test_user_in_db(database):
    user_data = {}
    chat_id = 1
    values = {1: 1, 2: 2}

    select = MagicMock()

    def select_value(*args, **kwargs):
        if kwargs.get("table") == "pref_table":
            return {"genres": ["pop"], "artists": []}
        else:
            return values

    select.side_effect = select_value
    with patch("geniust.db.Database.select", select):
        database.user(chat_id, user_data)

    assert user_data["preferences"].genres == ["pop"]
    for key, value in values.items():
        assert key in user_data
        assert value in user_data.values()


def test_user_not_in_db(database):
    user_data = {}
    chat_id = 1

    select = MagicMock(return_value=None)
    insert = MagicMock()
    with patch("geniust.db.Database.select", select), patch(
        "geniust.db.Database.insert", insert
    ):
        database.user(chat_id, user_data)

    for key in ("include_annotations", "lyrics_lang", "bot_lang"):
        assert key in user_data
    insert.assert_called_once_with(chat_id, True, "English + Non-English", "en")


@patch("psycopg2.connect")
@pytest.mark.parametrize("table", ["test_table", "pref_table"])
def test_insert(connection, database, table):
    chat_id = 1
    values = True, "English", "en"
    database.insert(chat_id, *values, table=table)

    args = connection().__enter__().cursor().__enter__().execute.call_args

    assert args[0][1] == (chat_id, *values)


@patch("psycopg2.connect")
@pytest.mark.parametrize("table", ["test_table", "pref_table"])
def test_upsert(connection, database, table):
    chat_id = 1
    values = 1, "some_data"

    database.upsert(chat_id, *values, table=table)

    args = connection().__enter__().cursor().__enter__().execute.call_args

    assert args[0][1] == (chat_id, *values)


@patch("psycopg2.connect")
@pytest.mark.parametrize("value", ["en", None])
def test_select(connection, database, value):
    chat_id = 1
    key = "bot_lang"
    if value is not None:
        value = (value,)

    connection().__enter__().cursor().__enter__().fetchone.return_value = value

    res = database.select(chat_id, column=key)

    if value is not None:
        assert res == {key: value[0]}
    else:
        assert res is None


@patch("psycopg2.connect")
def test_select_all(connection, database):
    chat_id = 1
    values = (1, True, "English", "en", None, "test_token")
    connection().__enter__().cursor().__enter__().fetchone.return_value = values

    res = database.select(chat_id)

    assert res["chat_id"] == values[0]
    assert res["include_annotations"] == values[1]
    assert res["lyrics_lang"] == values[2]
    assert res["bot_lang"] == values[3]
    assert res["genius_token"] == values[4]
    assert res["spotify_token"] == values[5]


@patch("psycopg2.connect")
def test_update(connection, database):
    chat_id = 1
    value = "en"
    database.update(chat_id, value, "bot_lang")

    args = connection().__enter__().cursor().__enter__().execute.call_args

    assert args[0][1] == (value,)


def test_update_include_annotations(database):
    chat_id = 1
    data = False

    update = MagicMock()
    with patch("geniust.db.Database.update", update):
        database.update_include_annotations(chat_id, data)

    update.assert_called_once_with(chat_id, data, "include_annotations")


def test_update_lyrics_language(database):
    chat_id = 1
    data = "Non-English"

    update = MagicMock()
    with patch("geniust.db.Database.update", update):
        database.update_lyrics_language(chat_id, data)

    update.assert_called_once_with(chat_id, data, "lyrics_lang")


def test_update_bot_language(database):
    chat_id = 1
    data = "fa"

    update = MagicMock()
    with patch("geniust.db.Database.update", update):
        database.update_bot_language(chat_id, data)

    update.assert_called_once_with(chat_id, data, "bot_lang")


@pytest.mark.parametrize("platform", ["genius", "spotify"])
def test_update_tokens(database, platform):
    chat_id = 1
    data = "a"

    update = MagicMock()
    with patch("geniust.db.Database.update", update):
        database.update_token(chat_id, data, platform)

    update.assert_called_once_with(chat_id, data, f"{platform}_token")


@pytest.mark.parametrize("platform", ["genius", "spotify"])
def test_delete_token(database, platform):
    chat_id = 1
    data = None

    update = MagicMock()
    with patch("geniust.db.Database.update", update):
        database.delete_token(chat_id, platform)

    update.assert_called_once_with(chat_id, data, f"{platform}_token")


@pytest.mark.parametrize("platform", ["genius", "spotify"])
def test_get_token(database, platform):
    chat_id = 1
    data = "a"

    select = MagicMock()
    select.return_value = {f"{platform}_token": data}
    with patch("geniust.db.Database.select", select):
        res = database.get_token(chat_id, platform)

    select.assert_called_once_with(chat_id, column=f"{platform}_token")
    assert res == data


def test_get_tokens(database):
    chat_id = 1
    values = {"geniu_token": "test_token", "spotify_token": None}

    select = MagicMock()
    select.return_value = values
    with patch("geniust.db.Database.select", select):
        res = database.get_tokens(chat_id)

    assert res == values


def test_get_language(database):
    chat_id = 1
    data = "en"

    select = MagicMock()
    select.return_value = {"bot_lang": data}
    with patch("geniust.db.Database.select", select):
        res = database.get_language(chat_id)

    select.assert_called_once_with(chat_id, column="bot_lang")
    assert res == data


@pytest.mark.parametrize("preferences", [None, {"genres": ["pop"], "artists": []}])
def test_get_preferences(database, preferences):
    chat_id = 1

    select = MagicMock()
    select.return_value = preferences
    with patch("geniust.db.Database.select", select):
        res = database.get_preferences(chat_id)

    if preferences is None:
        assert res is None
    else:
        assert res.genres == preferences["genres"]
        assert res.artists == preferences["artists"]


def test_update_preferences(database):
    chat_id = 1
    preferences = Preferences(genres=["pop"], artists=[])

    upsert = MagicMock()
    with patch("geniust.db.Database.upsert", upsert):
        database.update_preferences(chat_id, preferences)

    upsert.assert_called_once()


def test_delete_preferences(database):
    chat_id = 1

    update = MagicMock()
    with patch("geniust.db.Database.update", update):
        database.delete_preferences(chat_id)

    assert update.call_args[0][0] == chat_id
