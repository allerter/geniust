import logging

from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram.error import BadRequest

from geniust.constants import (
    INCLUDE, CUSTOMIZE_MENU,
    END, LYRICS_LANG, SELECT_ACTION, BOT_LANG,
    OPTION1, OPTION2, OPTION3,
)
from geniust import database

logger = logging.getLogger('geniust')


def customize_menu(update, context):
    """main menu for lyrics customizations"""
    context.user_data['level'] = CUSTOMIZE_MENU
    chat_id = update.callback_query.message.chat.id

    include = context.user_data['include_annotations']
    lyrics_lang = context.user_data['lyrics_lang']
    text = (f'What would you like to customize?'
            f'\nYour customizations will be used for all lyrics requests'
            f' (songs, albums, and inline searches).'
            f'\nCurrent settings:'
            f'\nLyrics Language: <b>{lyrics_lang}</b>'
            f'\nInclude Annotations: <b>{"Yes" if include else "No"}</b>'
            )

    buttons = [
        [IButton(
            'Lyrics Language',
            callback_data=str(LYRICS_LANG))],
        [IButton(
            'Annotations',
            callback_data=str(INCLUDE))],
        [IButton(
            'Back',
            callback_data=str(END))],
    ]
    keyboard = IBKeyboard(buttons)

    try:
        update.callback_query.answer()
        update.callback_query.edit_message_text(
            text=text,
            reply_markup=keyboard)
    except (AttributeError, BadRequest) as e:
        logger.info(f'{customize_menu}: {e}')
        context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard)

    return SELECT_ACTION


def lyrics_language(update, context):
    """Set lyrics language from one of three options."""
    ud = context.user_data
    ud['level'] = CUSTOMIZE_MENU + 1

    text = ('What characters would you like to be in the lyrics?'
            '\nNote that by English I mean ASCII characters. This option is'
            'useful for languages with non-ASCII alphabet (like Persian and Arabic).')

    # command
    if update.message or int(update.callback_query.data) == LYRICS_LANG:

        buttons = [
            [IButton(
                'Only English (ASCII)',
                callback_data=str(OPTION1))],
            [IButton(
                'Only non-English (non-ASCII)',
                callback_data=str(OPTION2))],
            [IButton(
                'English + non-English',
                callback_data=str(OPTION3))],
            [IButton(
                'Back',
                callback_data=str(END))]
        ]
        keyboard = IBKeyboard(buttons)

        if update.message:
            ud['command_entry'] = True
            update.message.reply_text(text, reply_markup=keyboard)
        else:
            context.bot.edit_message_text(text, reply_markup=keyboard)

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

    text = ('Updated your preferences.\n\nCurrent language:'
            f'<b>{context.user_data["lyrics_lang"]}</b>')

    update.callback_query.answer()
    update.callback_query.edit_message_text(text)

    return END


def bot_language(update, context):
    """Set bot language from one of two options."""
    ud = context.user_data
    ud['level'] = CUSTOMIZE_MENU + 1

    text = 'Choose a language.'

    # command
    if update.message or int(update.callback_query.data) == BOT_LANG:

        buttons = [
            [IButton(
                'English',
                callback_data=str(OPTION1))],
            [IButton(
                'Persian',
                callback_data=str(OPTION2))],
        ]
        keyboard = IBKeyboard(buttons)

        if update.message:
            ud['command_entry'] = True
            update.message.reply_text(text, reply_markup=keyboard)
        else:
            context.bot.edit_message_text(text, reply_markup=keyboard)

        return BOT_LANG

    chat_id = update.callback_query.message.chat.id
    data = int(update.callback_query.data)
    if data == OPTION1:
        ud['bot_language'] = 'English'
    elif data == OPTION2:
        update.callback_query.asnwer('Soon!')
        return END

    database.update_lyrics_language(chat_id, ud['lyrics_lang'])

    text = ('Updated your preferences.\n\nCurrent language:'
            f'<b>{context.user_data["lyrics_lang"]}</b>')

    update.callback_query.answer()
    update.callback_query.edit_message_text(text)

    return END


def include_annotations(update, context):
    """Set whether to include annotations or not"""
    ud = context.user_data

    # command
    if update.message or int(update.callback_query.data) == INCLUDE:
        buttons = [
            [IButton('Yes', str(OPTION1))],
            [IButton('No', str(OPTION2))],
            [IButton('Back', str(END))]
        ]
        keyboard = IBKeyboard(buttons)

        text = 'Would you like to include the annotations in the lyrics?'

        if update.message:
            ud['command_entry'] = True
            update.message.reply_text(text, reply_markup=keyboard)
        else:
            context.bot.edit_message_text(text, reply_markup=keyboard)

        return INCLUDE

    chat_id = update.callback_query.message.chat.id
    data = int(update.callback_query.data)
    ud['include_annotations'] = True if data == OPTION1 else False

    database.update_include_annotations(chat_id, ud['include_annotations'])

    include = ud['include_annotations']
    text = (f'Updated your preferences.'
            f'{text}\n\nCurrent setting: <b>{"Yes" if include else "No"}</b>')

    update.callback_query.answer()
    update.callback_query.edit_message_text(text)

    return END
