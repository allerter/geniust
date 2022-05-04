import warnings
from unittest.mock import MagicMock, patch

import pytest
from telegram.ext import Updater

from geniust import bot, constants, texts
from geniust.api import Recommender
from geniust.constants import Preferences
from geniust.db import Database


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
    assert res == constants.END


def differences_in_nested(a, b, section=None):
    """finds differences in nested dicts

    edited from https://stackoverflow.com/a/48652830
    """
    for [c, d], [_, g] in zip(a.items(), b.items()):
        if isinstance(d, dict) or isinstance(g, dict):
            if diff := set(d.keys()) - set(g.keys()):
                yield diff
            for i in differences_in_nested(d, g, c):
                for b in i:
                    yield b


def test_texts():
    """Tests to make sure all keys of the
    English dict exist in other languages as well"""
    en_dict = texts["en"]
    other_dicts = [lang_dict for lang, lang_dict in texts.items() if lang != "en"]
    for lang_dict in other_dicts:
        assert en_dict.keys() == lang_dict.keys()
        diff = list(differences_in_nested(en_dict, lang_dict))
        assert diff == []


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

    assert context.bot.send_message.call_count >= 2
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
    "query", [str(constants.MAIN_MENU), str(constants.CUSTOMIZE_MENU), "other"]
)
def test_end_describing(update, context, query):
    main_menu = MagicMock()
    customize_menu = MagicMock()

    if update.callback_query:
        update.callback_query.data = query

    with patch("geniust.bot.main_menu", main_menu), patch(
        "geniust.functions.customize.customize_menu", customize_menu
    ):
        bot.end_describing(update, context)

    if update.callback_query:
        if query == str(constants.MAIN_MENU):
            main_menu.assert_called()
            customize_menu.assert_not_called()
        elif query == str(constants.CUSTOMIZE_MENU):
            customize_menu.assert_called_once()


@pytest.mark.parametrize(
    "update",
    [
        pytest.lazy_fixture("update_message"),
        pytest.lazy_fixture("update_callback_query"),
    ],
)
def test_help_message(update, context):

    res = bot.help_message(update, context)

    if update.callback_query:
        update.callback_query.answer.assert_called_once()

    assert res == constants.END


def test_contact_us(update_message, context):
    update = update_message

    res = bot.contact_us(update, context)

    update.message.reply_text.assert_called_once()
    if "group" in update.message.chat.type:
        assert res == constants.END
    else:
        assert res == constants.TYPING_FEEDBACK


@pytest.mark.parametrize(
    "update",
    [
        pytest.lazy_fixture("update_message"),
        pytest.lazy_fixture("update_callback_query"),
    ],
)
def test_donate(update, context):

    res = bot.donate(update, context)

    if update.callback_query:
        update.callback_query.answer.assert_called_once()

    assert res == constants.END


def test_main():
    webhoook = MagicMock()
    updater = MagicMock(spec=Updater)
    database = MagicMock(spec=Database)
    recommender = MagicMock(spec=Recommender)

    current_module = "geniust.bot"
    with patch(current_module + ".SERVER_PORT", 5000), patch(
        current_module + ".WebhookThread", webhoook
    ), patch(current_module + ".Updater", updater), warnings.catch_warnings(), patch(
        current_module + ".tk.RefreshingCredentials", MagicMock()
    ), patch(
        current_module + ".Database", database
    ), patch(
        current_module + ".Recommender", recommender
    ):
        warnings.filterwarnings("ignore", category=UserWarning)
        bot.main()

    updater = updater()
    webhoook = webhoook()
    webhoook.start.assert_called_once()
    updater.dispatcher.bot.set_my_commands.assert_called_once()
    updater.start_polling.assert_called_once()
    updater.idle.assert_called_once()
