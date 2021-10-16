import logging
import secrets
from typing import Any, Dict

import tekore as tk
from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram import Update
from telegram.ext import CallbackContext

from geniust import api, auths, get_user, utils
from geniust.constants import END, LOGOUT, MAIN_MENU
from geniust.utils import log

logger = logging.getLogger("geniust")


@log
@get_user
def login_choices(update: Update, context: CallbackContext):
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["login_choices"]
    ud = context.user_data
    bd = context.bot_data

    buttons = []
    if ud["genius_token"] is None:
        buttons.append(
            [IButton(bd["texts"][language]["genius"], callback_data="login_genius")]
        )
    if ud["spotify_token"] is None:
        buttons.append(
            [IButton(bd["texts"][language]["spotify"], callback_data="login_spotify")]
        )

    caption = text["choose"] if buttons else text["logged_in"]
    update.message.reply_text(caption, reply_markup=IBKeyboard(buttons))

    return END


@log
@get_user
def login(update: Update, context: CallbackContext) -> int:
    """Prompts user to log into a platform"""
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["login"]
    chat_id = update.effective_chat.id
    platform = update.callback_query.data.split("_")[1]

    unique_value = secrets.token_urlsafe().replace("_", "-")
    state = f"{chat_id}_{platform}_{unique_value}"
    if platform == "genius":
        auth = auths["genius"]
        auth.state = state
        url = auth.url
    else:
        url = auths["spotify"]._cred.user_authorisation_url(
            tk.scope.user_top_read, state, show_dialog=True
        )

    context.user_data["state"] = unique_value

    buttons = [[IButton(text["button"], url)]]
    keyboard = IBKeyboard(buttons)

    msg = text["genius"] if platform == "genius" else text["spotify"]
    update.callback_query.answer()
    update.callback_query.message.delete()
    context.bot.send_message(chat_id, msg, reply_markup=keyboard)

    return END


@log
@get_user
def logged_in(update: Update, context: CallbackContext) -> int:
    """Displays options for a logged-in user"""
    bd = context.bot_data
    ud = context.user_data
    language = ud["bot_lang"]
    texts = bd["texts"][language]["logged_in"]

    buttons = [
        [IButton(texts["view_account"], callback_data="account")],
        [IButton(texts["log_out"], callback_data=str(LOGOUT))],
        [IButton(bd["texts"][language]["back"], callback_data=str(MAIN_MENU))],
    ]
    keyboard = IBKeyboard(buttons)

    update.callback_query.answer()
    update.callback_query.edit_message_text(texts["body"], reply_markup=keyboard)

    return END


@log
@get_user
def logout(update: Update, context: CallbackContext) -> int:
    """Logs user out"""
    chat_id = update.effective_chat.id
    bd = context.bot_data
    ud = context.user_data
    language = ud["bot_lang"]
    text = bd["texts"][language]["logout"]

    bd["db"].delete_token(chat_id, "genius")
    ud["genius_token"] = None
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
    language = ud["bot_lang"]
    texts = bd["texts"][language]["display_account"]
    genius = bd["genius"]

    update.callback_query.message.delete()

    account = api.GeniusT(ud["genius_token"]).account()["user"]

    avatar = utils.fix_image_format(genius, account["avatar"]["medium"]["url"])
    caption = account_caption(update, context, account, texts["caption"])
    context.bot.send_photo(chat_id, avatar, caption)

    return END


@log
def account_caption(
    update: Update, context: CallbackContext, account: Dict[str, Any], caption: str
) -> str:
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
        caption["body"]  # type: ignore
        .replace("{name}", account["name"])
        .replace("{unread_group}", str(account["unread_groups_inbox_count"]))
        .replace("{unread_main}", str(account["unread_main_activity_inbox_count"]))
        .replace("{unread_messages}", str(account["unread_messages_count"]))
        .replace("{unread_newsfeed}", str(account["unread_newsfeed_inbox_count"]))
        .replace("{iq}", account["iq_for_display"])
        .replace("{url}", account["url"])
        .replace("{followers}", str(account["followers_count"]))
        .replace("{following}", str(account["followed_users_count"]))
        .replace("{role}", account["human_readable_role_for_display"])
        .replace("{annotations}", str(account["stats"]["annotations_count"]))
        .replace("{answers}", str(account["stats"]["answers_count"]))
        .replace("{comments}", str(account["stats"]["comments_count"]))
        .replace("{forum_posts}", str(account["stats"]["forum_posts_count"]))
        .replace("{pyongs}", str(account["stats"]["pyongs_count"]))
        .replace("{questions}", str(account["stats"]["questions_count"]))
        .replace("{transcriptions}", str(account["stats"]["transcriptions_count"]))
        .replace("{all_activities_count}", str(sum(account["stats"].values())))
    )
    if artist := account["artist"]:
        artist = utils.deep_link(artist["name"], artist["id"], "artist", "genius")
        string += caption["artist"].replace("{}", artist)  # type: ignore
    return string
