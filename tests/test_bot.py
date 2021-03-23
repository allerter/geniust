import warnings
from unittest.mock import patch, MagicMock

import pytest
from telegram.ext import Updater

from geniust import constants, bot
from geniust.db import Database
from geniust.constants import Preferences


@pytest.mark.parametrize("token", ["test_token", None])
@pytest.mark.parametrize("preferences", [Preferences(genres=["pop"]), None])
def test_main_menu(update_callback_query, context, token, preferences):

    update = update_callback_query
    user = context.user_data
    user["genius_token"] = token
    user["preferences"] = preferences

    res = bot.main_menu(update, context)

    # Check if bot answered the callback query
    update.callback_query.answer.assert_called_once()

    # Check if bot returned the correct state to maintain the conversation
    assert res == constants.SELECT_ACTION


def test_stop(update_message, context):
    update = update_message

    res = bot.stop(update, context)
    update.message.reply_text.assert_called_once()
    assert res == constants.END


def test_send_feedback(update_message, context):
    update = update_message

    chat_id = update.effective_chat.id
    update.message.chat.id = chat_id

    username = "test_username"
    update.effective_chat.username = username

    text = "test_text"
    update.message.text = text

    res = bot.send_feedback(update, context)

    assert context.bot.send_message.call_count == len(constants.DEVELOPERS) + 1
    assert context.bot.send_message.call_args[1]["chat_id"] == chat_id

    assert res == constants.END


@pytest.mark.parametrize(
    "update",
    [
        pytest.lazy_fixture("update_message"),
        pytest.lazy_fixture("update_callback_query"),
    ],
)
@pytest.mark.parametrize(
    "level",
    [
        constants.MAIN_MENU,
        constants.ACCOUNT_MENU,
        constants.CUSTOMIZE_MENU,
    ],
)
def test_end_describing(update, context, level):
    context.user_data["level"] = level

    main_menu = MagicMock()
    customize_menu = MagicMock()

    with patch("geniust.bot.main_menu", main_menu), patch(
        "geniust.functions.customize.customize_menu", customize_menu
    ):
        res = bot.end_describing(update, context)

    if update.callback_query:
        if level == constants.MAIN_MENU:
            main_menu.assert_not_called()
            customize_menu.assert_not_called()
        elif level == constants.ACCOUNT_MENU or level == constants.CUSTOMIZE_MENU:
            main_menu.assert_called_once()

        assert res == constants.SELECT_ACTION
    else:
        assert res == constants.END


def test_help_message(update_message, context):
    update = update_message

    res = bot.help_message(update, context)

    update.message.reply_text.assert_called_once()
    assert res == constants.END


def test_contact_us(update_message, context):
    update = update_message

    res = bot.contact_us(update, context)

    update.message.reply_text.assert_called_once()
    assert res == constants.TYPING_FEEDBACK


def test_main():
    webhoook = MagicMock()
    updater = MagicMock(spec=Updater)
    database = MagicMock(spec=Database)

    current_module = "geniust.bot"
    with patch(current_module + ".SERVER_PORT", 5000), patch(
        current_module + ".WebhookThread", webhoook
    ), patch(current_module + ".Updater", updater), warnings.catch_warnings(), patch(
        current_module + ".tk.RefreshingCredentials", MagicMock()
    ), patch(
        current_module + ".Database", database
    ):
        warnings.filterwarnings("ignore", category=UserWarning)
        bot.main()

    updater = updater()
    webhoook = webhoook()
    webhoook.start.assert_called_once()
    updater.start_polling.assert_called_once()
    updater.idle.assert_called_once()
