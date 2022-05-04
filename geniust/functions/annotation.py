import logging
import re

from bs4 import BeautifulSoup
from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram import Update
from telegram.ext import CallbackContext

from geniust import api, get_user
from geniust.constants import END
from geniust.utils import check_callback_query_user, log, remove_unsupported_tags

logger = logging.getLogger("geniust")


@log
@get_user
@check_callback_query_user
def display_annotation(update: Update, context: CallbackContext) -> int:
    """Displays annotation"""
    genius = context.bot_data["genius"]
    language = context.user_data["bot_lang"]
    placeholder_text = context.bot_data["texts"][language]["display_annotation"]
    chat_id = update.effective_chat.id

    if update.callback_query:
        update.callback_query.answer()
        annotation_id = int(update.callback_query.data.split("_")[1])
        reply_to_message = update.callback_query.message.reply_to_message
        reply_to_message_id = reply_to_message.message_id if reply_to_message else None
    else:
        annotation_id = int(context.args[0].split("_")[1])
        reply_to_message_id = None

    annotation = genius.annotation(annotation_id, text_format="html")
    annotation = annotation["annotation"]["body"]["html"]
    if not annotation:
        annotation = placeholder_text
        context.bot.send_message(
            chat_id, annotation, reply_to_message_id=reply_to_message_id
        )
        return END

    annotation = BeautifulSoup(annotation, "html.parser")
    # Previews are meant for web viewers, so their text is of no use to us
    for embed_preview in annotation.find_all("div", class_="embedly_preview"):
        embed_preview.decompose()
    annotation = remove_unsupported_tags(annotation)
    annotation = re.sub(r"<br[/]>", "\n", str(annotation))
    voters = genius.voters(annotation_id=annotation_id)["voters"]

    upvotes = len(voters["up"])
    downvotes = len(voters["down"])

    buttons = [
        [
            IButton(f"👍 {upvotes}", callback_data=f"annotation_{annotation_id}_upvote"),
            IButton(
                f"👎 {downvotes}", callback_data=f"annotation_{annotation_id}_downvote"
            ),
        ],
    ]
    keyboard = IBKeyboard(buttons)

    logger.debug("sending annotation %s", annotation_id)

    context.bot.send_message(
        chat_id,
        annotation,
        reply_markup=keyboard,
        reply_to_message_id=reply_to_message_id,
    )

    return END


@log
@get_user
def upvote_annotation(update: Update, context: CallbackContext) -> int:
    """Upvotes/unvotes annotation on behalf of the user"""
    chat_id = update.effective_chat.id
    language = context.user_data["bot_lang"]
    texts = context.bot_data["texts"][language]["upvote_annotation"]
    message = update.callback_query.message
    is_chat_group = (
        True if "group" in update.callback_query.message.chat.type else False
    )

    annotation_id = int(update.callback_query.data.split("_")[1])
    token = context.user_data["genius_token"]

    if token is None:
        if is_chat_group:
            update.callback_query.answer(texts["login_necessary"])
        else:
            update.callback_query.answer()
            context.bot.send_message(chat_id, texts["login_necessary"])
        return END

    genius_user = api.GeniusT(token)
    account = genius_user.account()["user"]["id"]
    voters = genius_user.voters(annotation_id=annotation_id)["voters"]

    if account in [x["id"] for x in voters["up"]]:
        genius_user.unvote_annotation(annotation_id)
        update.callback_query.answer(texts["unvoted"])
        change = -1
    else:
        genius_user.upvote_annotation(annotation_id)
        update.callback_query.answer(texts["voted"])
        change = 1

    match = re.search(r"\d+", message.reply_markup.inline_keyboard[0][0].text)
    upvotes: int = int(match[0]) if match else 0
    new_text = "👍 " + str(upvotes + change)
    message.reply_markup.inline_keyboard[0][0].text = new_text

    update.callback_query.edit_message_reply_markup(message.reply_markup)

    return END


@log
@get_user
def downvote_annotation(update: Update, context: CallbackContext) -> int:
    """Downvotes/unvotes annotation on behalf of the user"""
    chat_id = update.effective_chat.id
    language = context.user_data["bot_lang"]
    texts = context.bot_data["texts"][language]["downvote_annotation"]
    message = update.callback_query.message
    is_chat_group = (
        True if "group" in update.callback_query.message.chat.type else False
    )

    annotation_id = int(update.callback_query.data.split("_")[1])
    token = context.user_data["genius_token"]

    if token is None:
        if is_chat_group:
            update.callback_query.answer(texts["login_necessary"])
        else:
            update.callback_query.answer()
            context.bot.send_message(chat_id, texts["login_necessary"])
        return END

    genius_t = api.GeniusT(token)
    account = genius_t.account()["user"]["id"]
    voters = genius_t.voters(annotation_id=annotation_id)["voters"]
    if account in [x["id"] for x in voters["down"]]:
        genius_t.unvote_annotation(annotation_id)
        update.callback_query.answer(texts["unvoted"])
        change = -1
    else:
        genius_t.downvote_annotation(annotation_id)
        update.callback_query.answer(texts["voted"])
        change = 1

    match = re.search(r"\d+", message.reply_markup.inline_keyboard[0][-1].text)
    downvotes: int = int(match[0]) if match else 0
    new_text = "👎 " + str(downvotes + change)
    message.reply_markup.inline_keyboard[0][-1].text = new_text

    update.callback_query.edit_message_reply_markup(message.reply_markup)

    return END
