from unittest.mock import MagicMock

import pytest

from geniust import constants
from geniust.functions import user


@pytest.mark.parametrize(
    "update",
    [
        pytest.lazy_fixture("update_callback_query"),
        pytest.lazy_fixture("update_message"),
        pytest.lazy_fixture("update_parametrized_command"),
    ],
)
def test_type_user(update, context):
    if update.message and update.message.text == "/":
        context.args = ["some", "query"]
        parametrized_command = True
    else:
        parametrized_command = False

    res = user.type_user(update, context)

    if getattr(update, "callback_query", None):
        update.callback_query.answer.assert_called_once()
    else:
        update.message.reply_text.assert_called_once()

    if parametrized_command:
        assert res == constants.END
    else:
        assert res == constants.TYPING_USER


@pytest.mark.parametrize(
    "search_dict",
    [pytest.lazy_fixture("search_users_dict"), {"sections": [{"hits": []}]}],
)
def test_search_users(update_message, context, search_dict):
    update = update_message
    genius = context.bot_data["genius"]
    genius.search_users.return_value = search_dict

    if search_dict["sections"][0]["hits"]:
        update.message.text = "test"

    res = user.search_users(update, context)

    if search_dict["sections"][0]["hits"]:
        keyboard = update.message.reply_text.call_args[1]["reply_markup"][
            "inline_keyboard"
        ]
        assert len(keyboard) == 10

    assert res == constants.END


@pytest.fixture
def user_dict_no_description(user_dict):
    user_dict["user"]["about_me"]["plain"] = ""
    return user_dict


@pytest.fixture
def user_dict_no_header(user_dict):
    user_dict["custom_header_image_url"] = None
    return user_dict


@pytest.mark.parametrize(
    "user_data",
    [
        pytest.lazy_fixture("user_dict"),
        pytest.lazy_fixture("user_dict_no_description"),
        pytest.lazy_fixture("user_dict_no_header"),
    ],
)
@pytest.mark.parametrize(
    "update",
    [
        pytest.lazy_fixture("update_callback_query"),
        pytest.lazy_fixture("update_message"),
    ],
)
def test_display_user(update, context, user_data):
    context.bot_data["recommender"] = MagicMock()
    if update.callback_query:
        update.callback_query.data = "user_1"
    else:
        context.args = ["user_1"]
    genius = context.bot_data["genius"]
    genius.user.return_value = user_data

    res = user.display_user(update, context)

    genius.user.assert_called_once_with(1)
    if update.callback_query:
        update.callback_query.answer.assert_called_once()
    assert res == constants.END


@pytest.mark.parametrize(
    "update",
    [
        pytest.lazy_fixture("update_callback_query"),
        pytest.lazy_fixture("update_message"),
    ],
)
def test_display_user_description(update, context, user_dict):
    if update.callback_query:
        update.callback_query.data = "user_1_description"
    else:
        context.args = ["user_1_description"]
    genius = context.bot_data["genius"]
    genius.user.return_value = user_dict

    res = user.display_user_description(update, context)

    if update.callback_query:
        update.callback_query.answer.assert_called_once()

    assert res == constants.END


@pytest.mark.parametrize(
    "update",
    [
        pytest.lazy_fixture("update_callback_query"),
        pytest.lazy_fixture("update_message"),
    ],
)
def test_display_user_header(update, context, user_dict):
    if update.callback_query:
        update.callback_query.data = "user_1_header"
    else:
        context.args = ["user_1_header"]
    genius = context.bot_data["genius"]
    genius.user.return_value = user_dict

    res = user.display_user_header(update, context)

    if update.callback_query:
        update.callback_query.answer.assert_called_once()

    assert res == constants.END
