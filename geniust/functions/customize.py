import logging

from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram.error import BadRequest

from geniust.constants import (
    INCLUDE, CUSTOMIZE_MENU,
    END, LYRICS_LANG, SELECT_ACTION, BOT_LANG,
    OPTION1, OPTION2, OPTION3,
)
from geniust import database, get_user
from geniust.utils import log


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


@log
@get_user
def customize_menu(update, context):
    """main menu for lyrics customizations"""
    language = context.user_data['bot_lang']
    context.user_data['level'] = CUSTOMIZE_MENU
    text = context.bot_data['texts'][language]['customize_menu']
    chat_id = update.callback_query.message.chat.id

    include = context.user_data['include_annotations']
    lyrics_lang = context.user_data['lyrics_lang']
    if lyrics_lang == 'English':
        lyrics_lang = 'only_english'
    elif lyrics_lang == 'Non-English':
        lyrics_lang = 'only_non_english'
    else:
        lyrics_lang = 'enligh_and_non_english'

    msg = (
        text['body']
        .replace('{language}', context.bot_data['texts'][language]['lyrics_language'][lyrics_lang])
        .replace('{include}', context.bot_data['texts'][language][include])
    )

    buttons = [
        [IButton(
            text['lyrics_language'],
            callback_data=str(LYRICS_LANG))],
        [IButton(
            text['annotations'],
            callback_data=str(INCLUDE))],
        [IButton(
            context.bot_data['texts'][language]['back'],
            callback_data=str(END))],
    ]
    keyboard = IBKeyboard(buttons)

    try:
        update.callback_query.answer()
        update.callback_query.edit_message_text(
            text=msg,
            reply_markup=keyboard)
    except (AttributeError, BadRequest) as e:
        logger.info(f'{customize_menu}: {e}')
        context.bot.send_message(
            chat_id=chat_id,
            text=msg,
            reply_markup=keyboard)

    return SELECT_ACTION


@log
@get_user
def lyrics_language(update, context):
    """Set lyrics language from one of three options."""
    language = context.user_data['bot_lang']
    text = context.bot_data['texts'][language]['lyrics_language']
    ud = context.user_data
    ud['level'] = CUSTOMIZE_MENU + 1

    # command
    if update.message or int(update.callback_query.data) == LYRICS_LANG:

        buttons = [
            [IButton(
                text['only_english'],
                callback_data=str(OPTION1))],
            [IButton(
                text['only_non_english'],
                callback_data=str(OPTION2))],
            [IButton(
                text['enligh_and_non_english'],
                callback_data=str(OPTION3))],
            [IButton(
                context.bot_data['texts'][language]['back'],
                callback_data=str(END))]
        ]
        keyboard = IBKeyboard(buttons)

        msg = text['body']

        if update.message:
            ud['command_entry'] = True
            update.message.reply_text(msg, reply_markup=keyboard)
        else:
            update.callback_query.edit_message_text(msg, reply_markup=keyboard)

        return LYRICS_LANG

    chat_id = update.callback_query.message.chat.id
    data = int(update.callback_query.data)
    if data == OPTION1:
        ud['lyrics_lang'] = 'English'
    elif data == OPTION2:
        ud['lyrics_lang'] = 'Non-English'
    else:
        ud['lyrics_lang'] = 'English + Non-English'

    database.update_lyrics_language(chat_id, ud['lyrics_lang'])

    text = text['updated'].replace('{language}', ud['lyrics_lang'])

    update.callback_query.answer()
    update.callback_query.edit_message_text(text)

    return END


@log
@get_user
def bot_language(update, context):
    """Set bot language from one of two options."""
    ud = context.user_data
    language = ud['bot_lang']
    text = context.bot_data['texts'][language]['bot_language']
    ud['level'] = CUSTOMIZE_MENU + 1

    # command
    if update.message or update.callback_query.data == str(BOT_LANG):

        buttons = []
        for key in context.bot_data['texts'].keys():
            buttons.append([IButton(text[key], callback_data=key)])
        keyboard = IBKeyboard(buttons)

        msg = text['body']

        if update.message:
            ud['command_entry'] = True
            update.message.reply_text(msg, reply_markup=keyboard)
        else:
            update.callback_query.edit_message_text(msg, reply_markup=keyboard)

        return BOT_LANG

    chat_id = update.callback_query.message.chat.id
    data = update.callback_query.data
    for key in context.bot_data['texts'].keys():
        if data == key:
            ud['bot_lang'] = data
            break
    else:
        return END

    database.update_bot_language(chat_id, ud['bot_lang'])

    text = text['updated'].replace('{language}', text[ud['bot_lang']])

    update.callback_query.answer()
    update.callback_query.edit_message_text(text)

    return END


@log
@get_user
def include_annotations(update, context):
    """Set whether to include annotations or not"""
    ud = context.user_data
    language = ud['bot_lang']
    text = context.bot_data['texts'][language]['include_annotations']

    # command
    if update.message or int(update.callback_query.data) == INCLUDE:
        buttons = [
            [IButton(context.bot_data['texts'][language][True], str(OPTION1))],
            [IButton(context.bot_data['texts'][language][False], str(OPTION2))],
            [IButton(context.bot_data['texts'][language]['back'], str(END))]
        ]
        keyboard = IBKeyboard(buttons)

        msg = text['body']

        if update.message:
            ud['command_entry'] = True
            update.message.reply_text(msg, reply_markup=keyboard)
        else:
            update.callback_query.edit_message_text(msg, reply_markup=keyboard)

        return INCLUDE

    chat_id = update.callback_query.message.chat.id
    data = int(update.callback_query.data)
    ud['include_annotations'] = True if data == OPTION1 else False

    database.update_include_annotations(chat_id, ud['include_annotations'])

    include = ud['include_annotations']
    text = text['updated'].replace('{include}', context.bot_data['texts'][language][include])

    update.callback_query.answer()
    update.callback_query.edit_message_text(text)

    return END
