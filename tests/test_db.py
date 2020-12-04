from unittest.mock import patch, MagicMock

import pytest

from geniust import db, constants


@pytest.fixture(scope='module')
def database():
    return db.Database('test_table')


@patch('psycopg2.connect')
def test_get_cursor(connection):
    func = MagicMock()
    res = db.get_cursor(func)
    res(1, 2, a=1)

    connection.assert_called_once_with(constants.DATABASE_URL,
                                       sslmode='require')


def test_user_in_db(database):
    user_data = {}
    chat_id = 1
    values = {1: 1, 2: 2}

    select = MagicMock(return_value=values)
    with patch('geniust.db.Database.select', select):
        database.user(chat_id, user_data)

    assert user_data == values


def test_user_not_in_db(database):
    user_data = {}
    chat_id = 1

    select = MagicMock(return_value=None)
    insert = MagicMock()
    with patch('geniust.db.Database.select', select), \
            patch('geniust.db.Database.insert', insert):
        database.user(chat_id, user_data)

    assert user_data == {'include_annotations': True,
                         'lyrics_lang': 'English + Non-English',
                         'bot_lang': 'en',
                         'token': None
                         }
    insert.assert_called_once_with(chat_id,
                                   True,
                                   'English + Non-English',
                                   'en')


@patch('psycopg2.connect')
def test_insert(connection, database):
    chat_id = 1
    values = True, 'English', 'en'
    database.insert(chat_id, *values)

    args = connection().__enter__().cursor().__enter__().execute.call_args

    assert args[0][0] == 'INSERT INTO test_table VALUES (%s, %s, %s, %s);'
    assert args[0][1] == (chat_id, *values)


@patch('psycopg2.connect')
def test_select(connection, database):
    chat_id = 1
    key = 'bot_lang'
    value = 'en'

    connection().__enter__().cursor().__enter__().fetchone.return_value = (value,)

    res = database.select(chat_id, column=key)

    assert res == {key: value}


@patch('psycopg2.connect')
def test_select_all(connection, database):
    chat_id = 1
    values = (1, True, 'English', 'en', None)
    connection().__enter__().cursor().__enter__().fetchone.return_value = values

    res = database.select(chat_id)

    assert res['chat_id'] == values[0]
    assert res['include_annotations'] == values[1]
    assert res['lyrics_lang'] == values[2]
    assert res['bot_lang'] == values[3]
    assert res['token'] == values[4]


@patch('psycopg2.connect')
def test_update(connection, database):
    chat_id = 1
    value = 'en'
    database.update(chat_id, value, 'bot_lang')

    args = connection().__enter__().cursor().__enter__().execute.call_args

    assert args[0][0] == 'UPDATE test_table SET bot_lang = %s WHERE chat_id = 1;'
    assert args[0][1] == (value,)


def test_update_include_annotations(database):
    chat_id = 1
    data = False

    update = MagicMock()
    with patch('geniust.db.Database.update', update):
        database.update_include_annotations(chat_id, data)

    update.assert_called_once_with(chat_id, data, 'include_annotations')


def test_update_lyrics_language(database):
    chat_id = 1
    data = 'Non-English'

    update = MagicMock()
    with patch('geniust.db.Database.update', update):
        database.update_lyrics_language(chat_id, data)

    update.assert_called_once_with(chat_id, data, 'lyrics_lang')


def test_update_bot_language(database):
    chat_id = 1
    data = 'fa'

    update = MagicMock()
    with patch('geniust.db.Database.update', update):
        database.update_bot_language(chat_id, data)

    update.assert_called_once_with(chat_id, data, 'bot_lang')


def test_update_token(database):
    chat_id = 1
    data = 'a'

    update = MagicMock()
    with patch('geniust.db.Database.update', update):
        database.update_token(chat_id, data)

    update.assert_called_once_with(chat_id, data, 'token')


def test_delete_token(database):
    chat_id = 1
    data = None

    update = MagicMock()
    with patch('geniust.db.Database.update', update):
        database.delete_token(chat_id)

    update.assert_called_once_with(chat_id, data, 'token')


def test_get_token(database):
    chat_id = 1
    data = 'a'

    select = MagicMock()
    select.return_value = {'token': data}
    with patch('geniust.db.Database.select', select):
        res = database.get_token(chat_id)

    select.assert_called_once_with(chat_id, column='token')
    assert res == data


def test_get_language(database):
    chat_id = 1
    data = 'en'

    select = MagicMock()
    select.return_value = {'bot_lang': data}
    with patch('geniust.db.Database.select', select):
        res = database.get_language(chat_id)

    select.assert_called_once_with(chat_id, column='bot_lang')
    assert res == data
