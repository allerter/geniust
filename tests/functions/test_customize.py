import pytest

from geniust import constants
from geniust.functions import customize


@pytest.mark.parametrize(
    "lyrics_language", ["English", "Non-English", "English + Non-English"]
)
def test_cusotmize_menu(update_callback_query, context, lyrics_language):
    update = update_callback_query
    context.user_data["lyrics_lang"] = lyrics_language

    res = customize.customize_menu(update, context)

    keyboard = update.callback_query.edit_message_text.call_args[1]["reply_markup"][
        "inline_keyboard"
    ]

    assert len(keyboard) == 3

    update.callback_query.answer.assert_called_once()

    assert res == constants.END


@pytest.mark.parametrize(
    "update, option",
    [
        (pytest.lazy_fixture("update_callback_query"), constants.ONLY_ENGLIGH),
        (pytest.lazy_fixture("update_callback_query"), constants.ONLY_NON_ENGLISH),
        (
            pytest.lazy_fixture("update_callback_query"),
            constants.ENGLISH_AND_NON_ENGLISH,
        ),
        (pytest.lazy_fixture("update_callback_query"), constants.LYRICS_LANG),
        (pytest.lazy_fixture("update_callback_query"), "invalid"),
        (pytest.lazy_fixture("update_message"), None),
    ],
)
def test_lyrics_language(update, context, option):
    if update.callback_query:
        update.callback_query.data = str(option)

    res = customize.lyrics_language(update, context)

    if update.callback_query and option != constants.LYRICS_LANG:

        if option == constants.ONLY_ENGLIGH:
            assert context.user_data["lyrics_lang"] == "English"
        elif option == constants.ONLY_NON_ENGLISH:
            assert context.user_data["lyrics_lang"] == "Non-English"
        elif option == constants.ENGLISH_AND_NON_ENGLISH:
            assert context.user_data["lyrics_lang"] == "English + Non-English"
        else:
            return
        assert res == constants.END
        update.callback_query.answer.assert_called_once()
        context.bot_data["db"].update_lyrics_language.assert_called_once()
    else:
        if update.callback_query:
            keyboard = update.callback_query.edit_message_text.call_args[1][
                "reply_markup"
            ]["inline_keyboard"]
        else:
            keyboard = update.message.reply_text.call_args[1]["reply_markup"][
                "inline_keyboard"
            ]
        assert len(keyboard) == 4
        assert res == constants.END


@pytest.mark.parametrize(
    "update, option",
    [
        (pytest.lazy_fixture("update_callback_query"), "bot_lang"),
        (pytest.lazy_fixture("update_callback_query"), "bot_lang_en"),
        (pytest.lazy_fixture("update_callback_query"), "bot_lang_fa"),
        (pytest.lazy_fixture("update_callback_query"), "invalid"),
        (pytest.lazy_fixture("update_message"), None),
    ],
)
def test_bot_language(update, context, option):
    if update.callback_query:
        update.callback_query.data = str(option)

    res = customize.bot_language(update, context)

    if update.callback_query and option != "bot_lang":
        if option != "invalid":
            assert context.user_data["bot_lang"] == option.replace("bot_lang_", "")
        else:
            return
        update.callback_query.answer.assert_called_once()
        context.bot_data["db"].update_bot_language.assert_called_once()
        assert res == constants.END
    else:
        if update.callback_query:
            keyboard = update.callback_query.edit_message_text.call_args[1][
                "reply_markup"
            ]["inline_keyboard"]
        else:
            keyboard = update.message.reply_text.call_args[1]["reply_markup"][
                "inline_keyboard"
            ]
        assert len(keyboard) == len(list(context.bot_data["texts"])) + 1
        assert res == constants.END


@pytest.mark.parametrize(
    "update, option",
    [
        (pytest.lazy_fixture("update_callback_query"), constants.INCLUDE_ANNOTATIONS),
        (
            pytest.lazy_fixture("update_callback_query"),
            constants.DONT_INCLUDE_ANNOTATIONS,
        ),
        (pytest.lazy_fixture("update_callback_query"), "invalid"),
        (pytest.lazy_fixture("update_callback_query"), constants.INCLUDE),
        (pytest.lazy_fixture("update_message"), None),
    ],
)
def test_include_annotations(update, context, option):
    if update.callback_query:
        update.callback_query.data = str(option)

    res = customize.include_annotations(update, context)

    if update.callback_query and option != constants.INCLUDE:
        if option == constants.INCLUDE_ANNOTATIONS:
            assert context.user_data["include_annotations"] is True
        elif option == constants.DONT_INCLUDE_ANNOTATIONS:
            assert context.user_data["include_annotations"] is False
        else:
            return
        update.callback_query.answer.assert_called_once()
        context.bot_data["db"].update_include_annotations.assert_called_once()
        assert res == constants.END
    else:
        if update.callback_query:
            keyboard = update.callback_query.edit_message_text.call_args[1][
                "reply_markup"
            ]["inline_keyboard"]
        else:
            keyboard = update.message.reply_text.call_args[1]["reply_markup"][
                "inline_keyboard"
            ]
        assert len(keyboard) == 3
        assert res == constants.END
