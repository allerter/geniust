from unittest.mock import patch, MagicMock

import pytest

from geniust import constants
from geniust.functions import account


@pytest.mark.parametrize("genius_token", [None, "some_token"])
@pytest.mark.parametrize("spotify_token", [None, "some_token"])
def test_login_choices(update_message, context, genius_token, spotify_token):
    update = update_message
    context.user_data["genius_token"] = genius_token
    context.user_data["spotify_token"] = spotify_token

    res = account.login_choices(update, context)

    keyboard = update.message.reply_text.call_args[1]["reply_markup"][
        "inline_keyboard"
    ]
    if genius_token and spotify_token:
        assert len(keyboard) == 0
    elif genius_token or spotify_token:
        assert len(keyboard) == 1
    else:
        assert len(keyboard) == 2


@pytest.mark.parametrize("platform", ["genius", "spotify"])
def test_login(update_callback_query, context, platform):
    update = update_callback_query
    update.callback_query.data = f"account_login_{platform}"

    res = account.login(update, context)

    keyboard = context.bot.send_message.call_args[1]["reply_markup"][
        "inline_keyboard"
    ]
    update.callback_query.answer.assert_called_once()
    assert platform in keyboard[0][0]["url"]
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
