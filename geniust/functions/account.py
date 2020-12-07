import logging
from typing import Any, Dict

from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram import Update
from telegram.ext import CallbackContext

from geniust.constants import LOGOUT, ACCOUNT_MENU, SELECT_ACTION, END
from geniust import utils, auth, get_user
from geniust.utils import log
from geniust import api

logger = logging.getLogger()


@log
@get_user
def login(update: Update, context: CallbackContext) -> int:
    """Prompts user to log into Genius.com"""
    language = context.user_data['bot_lang']
    text = context.bot_data['texts'][language]['login']

    auth.state = update.effective_chat.id
    url = auth.url

    buttons = [[IButton(text['button'], url)]]
    keyboard = IBKeyboard(buttons)

    msg = text['body']
    update.callback_query.answer()
    update.callback_query.edit_message_text(msg,
                                            reply_markup=keyboard)

    return END


@log
@get_user
def logged_in(update: Update, context: CallbackContext) -> int:
    """Displays options for a logged-in user"""
    bd = context.bot_data
    ud = context.user_data
    ud['level'] = ACCOUNT_MENU
    language = ud['bot_lang']
    texts = bd['texts'][language]['logged_in']

    buttons = [
        [IButton(texts['view_account'], callback_data='account')],
        [IButton(texts['log_out'], callback_data=str(LOGOUT))],
        [IButton(bd['texts'][language]['back'], callback_data=str(END))],
    ]
    keyboard = IBKeyboard(buttons)

    update.callback_query.answer()
    update.callback_query.edit_message_text(texts['body'],
                                            reply_markup=keyboard)

    return SELECT_ACTION


@log
@get_user
def logout(update: Update, context: CallbackContext) -> int:
    """Logs user out"""
    chat_id = update.effective_chat.id
    bd = context.bot_data
    ud = context.user_data
    language = ud['bot_lang']
    text = bd['texts'][language]['logout']

    bd['db'].delete_token(chat_id)
    update.callback_query.answer()
    update.callback_query.edit_message_text(text)

    return END


@log
@get_user
def display_account(update: Update, context: CallbackContext) -> int:
    """Displays uer's account data"""
    chat_id = update.effective_chat.id
    bd = context.bot_data
    ud = context.user_data
    ud['level'] = ACCOUNT_MENU + 1
    language = ud['bot_lang']
    texts = bd['texts'][language]['display_account']

    if update.callback_query:
        update.callback_query.message.delete()

    account = api.GeniusT(ud['token']).account()['user']
    avatar = account['avatar']['medium']['url']
    caption = account_caption(update, context, account, texts['caption'])\

    context.bot.send_photo(chat_id, avatar, caption)

    return END


@log
def account_caption(update: Update,
                    context: CallbackContext,
                    account: Dict[str, Any],
                    caption: str) -> str:
    """Generates caption for user account data.

    Args:
        update (Update): Update object to make the update available
            to the error handler in case of errors.
        context (CallbackContext): Update object to make the context available
            to the error handler in case of errors.
        account (Dict[str, Any]): Account data.
        caption (str): Caption template.

    Returns:
        str: Formatted caption.
    """
    string = (
        caption['body']  # type: ignore
        .replace('{name}', account['name'])
        .replace('{unread_group}', str(account['unread_groups_inbox_count']))
        .replace('{unread_main}', str(account['unread_main_activity_inbox_count']))
        .replace('{unread_messages}', str(account['unread_messages_count']))
        .replace('{unread_newsfeed}', str(account['unread_newsfeed_inbox_count']))
        .replace('{iq}', account['iq_for_display'])
        .replace('{url}', account['url'])
        .replace('{followers}', str(account['followers_count']))
        .replace('{following}', str(account['followed_users_count']))
        .replace('{role}', account['human_readable_role_for_display'])
        .replace('{annotations}', str(account['stats']['annotations_count']))
        .replace('{answers}', str(account['stats']['answers_count']))
        .replace('{comments}', str(account['stats']['comments_count']))
        .replace('{forum_posts}', str(account['stats']['forum_posts_count']))
        .replace('{pyongs}', str(account['stats']['pyongs_count']))
        .replace('{questions}', str(account['stats']['questions_count']))
        .replace('{transcriptions}', str(account['stats']['transcriptions_count']))
    )
    if account['artist']:
        artist = utils.deep_link(account['artist'])
        string += caption['artist'].replace('{}', artist)  # type: ignore
    return string
