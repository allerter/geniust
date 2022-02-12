import logging
from typing import Any, Dict, List, Union

from bs4 import BeautifulSoup
from telegram import ForceReply
from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram import Update
from telegram.ext import CallbackContext

from geniust import get_user, utils
from geniust.constants import END, TYPING_USER
from geniust.utils import check_callback_query_user, log

logger = logging.getLogger("geniust")


@log
@get_user
@check_callback_query_user
def type_user(update: Update, context: CallbackContext) -> int:
    """Prompts user to type username"""
    # user has entered the function through the main menu
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["type_user"]

    if update.callback_query:
        update.callback_query.answer()
        # in groups, it's best to send a reply to the user
        reply_to_message = update.callback_query.message.reply_to_message
        if reply_to_message:
            reply_to_message.reply_text(text)
        else:
            update.callback_query.edit_message_text(
                text, reply_markup=ForceReply(selective=True)
            )
    else:
        if context.args:
            if update.message is None and update.edited_message:
                update.message = update.edited_message
            update.message.text = " ".join(context.args)
            search_users(update, context)
            return END
        update.message.reply_text(text, reply_markup=ForceReply(selective=True))

    return TYPING_USER


@log
@get_user
def search_users(update: Update, context: CallbackContext) -> int:
    """Displays a list of usernames based on user input"""
    genius = context.bot_data["genius"]
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["search_users"]
    input_text = update.message.text
    reply_to_message_id = (
        update.message.message_id if update.message.chat.type == "group" else None
    )

    # get <= 10 hits for user input from Genius API search
    json_search = genius.search_users(input_text)
    buttons = []
    for hit in json_search["sections"][0]["hits"][:10]:
        user = hit["result"]
        username = user["name"]
        callback = f"user_{user['id']}"

        buttons.append([IButton(text=username, callback_data=callback)])

    if buttons:
        update.message.reply_text(
            text["choose"],
            reply_markup=IBKeyboard(buttons),
            reply_to_message_id=reply_to_message_id,
        )
    else:
        update.message.reply_text(
            text["no_users"], reply_to_message_id=reply_to_message_id
        )
    return END


@log
@get_user
@check_callback_query_user
def display_user(update: Update, context: CallbackContext) -> int:
    """Displays user"""
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["display_user"]
    bot = context.bot
    genius = context.bot_data["genius"]
    chat_id = update.effective_chat.id

    if update.callback_query:
        _, user_id_str = update.callback_query.data.split("_")
        update.callback_query.answer()
        update.callback_query.message.delete()
        reply_to_message = update.callback_query.message.reply_to_message
        reply_to_message_id = reply_to_message.message_id if reply_to_message else None
    else:
        _, user_id_str = context.args[0].split("_")
        reply_to_message_id = None

    user_id = int(user_id_str)
    user = genius.user(user_id)["user"]
    cover_art = user["photo_url"]
    caption = user_caption(update, context, user, text["caption"])

    buttons: List = [[]]
    if user["about_me"]["plain"]:
        callback_data = f"user_{user['id']}_description"
        buttons[0].append(IButton(text["description"], callback_data=callback_data))
    if user["custom_header_image_url"]:
        callback_data = f"user_{user['id']}_header"
        buttons[0].append(IButton(text["header"], callback_data=callback_data))

    keyboard = IBKeyboard(buttons) if buttons[0] else None
    bot.send_photo(
        chat_id,
        cover_art,
        caption,
        reply_markup=keyboard,
        reply_to_message_id=reply_to_message_id,
    )

    return END


@log
@get_user
@check_callback_query_user
def display_user_description(update: Update, context: CallbackContext) -> int:
    """Displays user's description"""
    chat_id = update.effective_chat.id
    bd = context.bot_data
    ud = context.user_data
    language = ud["bot_lang"]
    genius = context.bot_data["genius"]
    text = bd["texts"][language]["display_user_description"]

    if update.callback_query:
        _, user_id_str, _ = update.callback_query.data.split("_")
        update.callback_query.answer()
        reply_to_message = update.callback_query.message.reply_to_message
        reply_to_message_id = reply_to_message.message_id if reply_to_message else None
    else:
        _, user_id_str, _ = context.args[0].split("_")
        reply_to_message_id = None

    user_id = int(user_id_str)
    user = genius.user(user_id)["user"]

    description = BeautifulSoup(user["about_me"]["html"], "html.parser")
    description = str(utils.remove_unsupported_tags(description))

    caption = text.format(username=user["name"], description=description)
    context.bot.send_message(chat_id, caption, reply_to_message_id=reply_to_message_id)

    return END


@log
@get_user
@check_callback_query_user
def display_user_header(update: Update, context: CallbackContext) -> int:
    """Displays user's header image"""
    chat_id = update.effective_chat.id
    bd = context.bot_data
    ud = context.user_data
    language = ud["bot_lang"]
    genius = context.bot_data["genius"]
    text = bd["texts"][language]["display_user_header"]

    if update.callback_query:
        _, user_id_str, _ = update.callback_query.data.split("_")
        update.callback_query.answer()
        reply_to_message = update.callback_query.message.reply_to_message
        reply_to_message_id = reply_to_message.message_id if reply_to_message else None
    else:
        _, user_id_str, _ = context.args[0].split("_")
        reply_to_message_id = None

    user_id = int(user_id_str)
    user = genius.user(user_id)["user"]

    photo = user["custom_header_image_url"]
    caption = text.format(username=user["name"])
    context.bot.send_photo(
        chat_id, photo, caption, reply_to_message_id=reply_to_message_id
    )

    return END


@log
def user_caption(
    update: Update, context: CallbackContext, user: Dict[str, Any], caption: str
) -> str:
    """Generates caption for user data.

    Args:
        update (Update): Update object to make the update available
            to the error handler in case of errors.
        context (CallbackContext): Update object to make the context available
            to the error handler in case of errors.
        user (Dict[str, Any]): User data.
        caption (str): Caption template.

    Returns:
        str: Formatted caption.
    """
    user_roles = ", ".join(role.capitalize() for role in user["roles_for_display"])
    if not user_roles:
        user_roles = caption["none"]  # type: ignore
    string = (
        caption["body"]  # type: ignore
        .replace("{name}", user["name"])
        .replace("{iq}", user["iq_for_display"])
        .replace("{url}", user["url"])
        .replace("{followers}", str(user["followers_count"]))
        .replace("{following}", str(user["followed_users_count"]))
        .replace("{roles}", user_roles)
        .replace("{annotations}", str(user["stats"]["annotations_count"]))
        .replace("{answers}", str(user["stats"]["answers_count"]))
        .replace("{comments}", str(user["stats"]["comments_count"]))
        .replace("{forum_posts}", str(user["stats"]["forum_posts_count"]))
        .replace("{pyongs}", str(user["stats"]["pyongs_count"]))
        .replace("{questions}", str(user["stats"]["questions_count"]))
        .replace("{transcriptions}", str(user["stats"]["transcriptions_count"]))
        .replace("{all_activities_count}", str(sum(user["stats"].values())))
    )
    if artist := user["artist"]:
        artist = utils.deep_link(artist["name"], artist["id"], "artist", "genius")
        string += caption["artist"].replace("{}", artist)  # type: ignore
    return string
