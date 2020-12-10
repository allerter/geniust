from unittest.mock import patch, MagicMock

import pytest

from geniust import constants
from geniust.functions import account


def test_login(update_callback_query, context):
    update = update_callback_query

    res = account.login(update, context)

    keyboard = update.callback_query.edit_message_text.call_args[1]["reply_markup"][
        "inline_keyboard"
    ]

    assert keyboard[0][0]["url"].startswith("https://api.genius.com/oauth/authorize")

    update.callback_query.answer.assert_called_once()

    assert res == constants.END


def test_logged_in(update_callback_query, context):
    update = update_callback_query
    user = context.user_data
    user["token"] = "test_token"

    res = account.logged_in(update, context)

    keyboard = update.callback_query.edit_message_text.call_args[1]["reply_markup"][
        "inline_keyboard"
    ]

    assert len(keyboard) == 3

    update.callback_query.answer.assert_called_once()

    assert res == constants.SELECT_ACTION


def test_logout(update_callback_query, context):
    update = update_callback_query
    user = context.user_data
    user["token"] = "test_token"

    res = account.logout(update, context)

    context.bot_data["db"].delete_token.assert_called_once()

    update.callback_query.answer.assert_called_once()

    assert res == constants.END


@pytest.mark.parametrize("artist_data", [pytest.lazy_fixture("song_dict"), None])
def test_display_account(update_callback_query, context, account_dict, artist_data):
    update = update_callback_query
    user = context.user_data
    user["token"] = "test_token"

    genius = MagicMock()
    if artist_data is None:
        account_dict["user"]["artist"] = None
    else:
        song = artist_data
        account_dict["user"]["artist"] = song["song"]["primary_artist"]

    genius().account.return_value = account_dict

    with patch("geniust.api.GeniusT", genius):
        res = account.display_account(update, context)

    update.callback_query.message.delete.assert_called_once()

    assert res == constants.END
