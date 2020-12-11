import warnings
from unittest.mock import patch, MagicMock, create_autospec

import pytest
from requests import HTTPError
from telegram.ext import Updater
from lyricsgenius import OAuth2

from geniust import constants, bot
from geniust.bot import CronHandler, TokenHandler
from geniust.db import Database


def test_cron_handler():
    handler = MagicMock()

    CronHandler.get(handler)

    handler.write.assert_called_once()


@pytest.mark.parametrize(
    "state",
    [
        "1_test-state",
        "1_invalid-state",
        "2_test-state",
        "invalid_state",
        "invalid-state",
    ],
)
@pytest.mark.parametrize("code", ["some_code", "invalid_code"])
@pytest.mark.parametrize("user_state", ["test-state", None])
def test_token_handler(context, user_state, code, state):
    handler = MagicMock()
    handler.get_argument.return_value = state
    handler.auth = create_autospec(OAuth2)
    if code == "some_code":
        handler.auth.get_user_token.return_value = "test_token"
    else:
        handler.auth.get_user_token.side_effect = HTTPError()
    handler.database = create_autospec(Database)
    handler.bot = context.bot
    handler.texts = context.bot_data["texts"]
    handler.user_data = {1: {}}
    handler.user_data[1]["bot_lang"] = context.user_data["bot_lang"]
    handler.user_data[1]["state"] = user_state

    handler.request.protocol = "https"
    handler.request.host = "test-app.com"
    handler.request.uri = f"/callback?code={code}&state={state}"

    TokenHandler.get(handler)

    handler.get_argument.assert_called_once_with("state")
    if state == "1_test-state" and user_state == "test-state" and code == "some_code":
        handler.auth.get_user_token.assert_called_once_with(
            "https://test-app.com/callback?code=some_code&state=1_test-state"
        )
        handler.database.update_token.assert_called_once_with(1, "test_token")
        assert handler.bot.send_message.call_args[0][0] == 1
        assert handler.user_data[1]["token"] == "test_token"
        assert "state" not in handler.user_data[1]
        handler.redirect.assert_called_once()
    elif code == "invalid_code":
        handler.database.update_token.assert_not_called()
    else:
        handler.set_status.assert_called_once_with(401)
        handler.finish.assert_called_once()
        handler.auth.get_user_token.assert_not_called()


def test_token_handler_initialize():
    handler = MagicMock()
    auth = "auth"
    bot = "bot"
    database = "database"
    texts = "texts"
    user_data = "user_data"

    res = TokenHandler.initialize(
        handler,
        auth=auth,
        database=database,
        bot=bot,
        texts=texts,
        user_data=user_data,
    )

    assert res is None
    assert handler.auth == auth
    assert handler.database == database
    assert handler.bot == bot
    assert handler.texts == texts
    assert handler.user_data == user_data


@pytest.mark.parametrize("token", ["test_token", None])
def test_main_menu(update_callback_query, context, token):

    update = update_callback_query
    user = context.user_data
    user["token"] = token

    # Return None when bot tries to get the token
    context.bot_data["db"].get_token.return_value = None
    res = bot.main_menu(update, context)

    keyboard = update.callback_query.edit_message_text.call_args[1]["reply_markup"][
        "inline_keyboard"
    ]

    # Check if bot returned correct keyboard for logged-in/out users
    if token is None:
        context.bot_data["db"].get_token.assert_called_once()
        assert keyboard[-1][0]["callback_data"] == str(constants.LOGIN)
    else:
        assert keyboard[-1][0]["callback_data"] == str(constants.LOGGED_IN)

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

    current_module = "geniust.bot"
    with patch(current_module + ".SERVER_PORT", 5000), patch(
        current_module + ".WebhookThread", webhoook
    ), patch(current_module + ".Updater", updater), warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)
        bot.main()

    updater = updater()
    webhoook = webhoook()
    webhoook.start.assert_called_once()
    updater.start_polling.assert_called_once()
    updater.idle.assert_called_once()
