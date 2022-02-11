import logging

from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram import Update
from telegram.ext import CallbackContext

from geniust import get_user
from geniust.constants import (
    CUSTOMIZE_MENU,
    DONT_INCLUDE_ANNOTATIONS,
    END,
    ENGLISH_AND_NON_ENGLISH,
    INCLUDE,
    INCLUDE_ANNOTATIONS,
    LYRICS_LANG,
    MAIN_MENU,
    ONLY_ENGLIGH,
    ONLY_NON_ENGLISH,
)
from geniust.utils import log

logger = logging.getLogger("geniust")


@log
@get_user
def customize_menu(update: Update, context: CallbackContext) -> int:
    """Main menu for lyrics customizations"""
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["customize_menu"]

    include = context.user_data["include_annotations"]
    lyrics_lang = context.user_data["lyrics_lang"]
    if lyrics_lang == "English":
        lyrics_lang = "only_english"
    elif lyrics_lang == "Non-English":
        lyrics_lang = "only_non_english"
    else:
        lyrics_lang = "enligh_and_non_english"

    language_display = context.bot_data["texts"][language]["lyrics_language"][
        lyrics_lang
    ]
    msg = (
        text["body"]
        .replace("{language}", language_display)
        .replace("{include}", context.bot_data["texts"][language][include])
    )

    buttons = [
        [IButton(text["lyrics_language"], callback_data=str(LYRICS_LANG))],
        [IButton(text["annotations"], callback_data=str(INCLUDE))],
        [
            IButton(
                context.bot_data["texts"][language]["back"],
                callback_data=str(MAIN_MENU),
            )
        ],
    ]
    keyboard = IBKeyboard(buttons)

    update.callback_query.answer()
    update.callback_query.edit_message_text(text=msg, reply_markup=keyboard)

    return END


@log
@get_user
def lyrics_language(update: Update, context: CallbackContext) -> int:
    """Sets lyrics language or displays options"""
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["lyrics_language"]
    ud = context.user_data
    chat_id = update.effective_chat.id

    # command
    if update.message or update.callback_query.data == str(LYRICS_LANG):

        buttons = [
            [IButton(text["only_english"], callback_data=str(ONLY_ENGLIGH))],
            [IButton(text["only_non_english"], callback_data=str(ONLY_NON_ENGLISH))],
            [
                IButton(
                    text["enligh_and_non_english"],
                    callback_data=str(ENGLISH_AND_NON_ENGLISH),
                )
            ],
            [
                IButton(
                    context.bot_data["texts"][language]["back"],
                    callback_data=str(CUSTOMIZE_MENU),
                )
            ],
        ]
        keyboard = IBKeyboard(buttons)

        msg = text["body"]

        if update.message:
            update.message.reply_text(msg, reply_markup=keyboard)
        else:
            update.callback_query.edit_message_text(msg, reply_markup=keyboard)

        return END

    data = update.callback_query.data
    if data == str(ONLY_ENGLIGH):
        ud["lyrics_lang"] = "English"
        language_display = "only_english"
    elif data == str(ONLY_NON_ENGLISH):
        ud["lyrics_lang"] = "Non-English"
        language_display = "only_non_english"
    elif data == str(ENGLISH_AND_NON_ENGLISH):
        language_display = "enligh_and_non_english"
        ud["lyrics_lang"] = "English + Non-English"
    else:
        return END

    context.bot_data["db"].update_lyrics_language(chat_id, ud["lyrics_lang"])

    text = text["updated"].replace("{language}", text[language_display])

    update.callback_query.answer()
    update.callback_query.edit_message_text(text)

    return END


@log
@get_user
def bot_language(update: Update, context: CallbackContext) -> int:
    """Sets bot language or displays options"""
    ud = context.user_data
    language = ud["bot_lang"]
    text = context.bot_data["texts"][language]["bot_language"]
    chat_id = update.effective_chat.id

    # command
    if update.message or update.callback_query.data == "bot_lang":

        buttons = []
        for key in context.bot_data["texts"].keys():
            buttons.append([IButton(text[key], callback_data=f"bot_lang_{key}")])
        buttons.append(
            [
                IButton(
                    context.bot_data["texts"][language]["back"],
                    callback_data=str(MAIN_MENU),
                )
            ]
        )
        keyboard = IBKeyboard(buttons)

        msg = text["body"]

        if update.message:
            update.message.reply_text(msg, reply_markup=keyboard)
        else:
            update.callback_query.edit_message_text(msg, reply_markup=keyboard)

        return END

    data = update.callback_query.data.replace("bot_lang_", "")
    for key in context.bot_data["texts"].keys():
        if data == key:
            ud["bot_lang"] = data
            break
    else:
        return END

    context.bot_data["db"].update_bot_language(chat_id, ud["bot_lang"])

    text = text["updated"].replace("{language}", text[ud["bot_lang"]])

    update.callback_query.answer()
    update.callback_query.edit_message_text(text)

    return END


@log
@get_user
def include_annotations(update: Update, context: CallbackContext) -> int:
    """Sets including annotations or displays options"""
    ud = context.user_data
    language = ud["bot_lang"]
    text = context.bot_data["texts"][language]["include_annotations"]
    chat_id = update.effective_chat.id

    # command
    if update.message or update.callback_query.data == str(INCLUDE):
        buttons = [
            [
                IButton(
                    context.bot_data["texts"][language][True],
                    callback_data=str(INCLUDE_ANNOTATIONS),
                )
            ],
            [
                IButton(
                    context.bot_data["texts"][language][False],
                    callback_data=str(DONT_INCLUDE_ANNOTATIONS),
                )
            ],
            [
                IButton(
                    context.bot_data["texts"][language]["back"],
                    callback_data=str(CUSTOMIZE_MENU),
                )
            ],
        ]
        keyboard = IBKeyboard(buttons)

        msg = text["body"]

        if update.message:
            update.message.reply_text(msg, reply_markup=keyboard)
        else:
            update.callback_query.edit_message_text(msg, reply_markup=keyboard)

        return END

    data = update.callback_query.data
    if data == str(INCLUDE_ANNOTATIONS):
        ud["include_annotations"] = True
    elif data == str(DONT_INCLUDE_ANNOTATIONS):
        ud["include_annotations"] = False
    else:
        return END

    context.bot_data["db"].update_include_annotations(
        chat_id, ud["include_annotations"]
    )

    include = ud["include_annotations"]
    include_display = context.bot_data["texts"][language][include]
    text = text["updated"].replace("{include}", include_display)

    update.callback_query.answer()
    update.callback_query.edit_message_text(text)

    return END
