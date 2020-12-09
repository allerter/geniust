import logging
import re

from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram import Update
from telegram.ext import CallbackContext

from geniust.constants import END
from geniust import get_user
from geniust.utils import log, remove_unsupported_tags
from geniust import api

from bs4 import BeautifulSoup

logger = logging.getLogger()


@log
@get_user
def display_annotation(update: Update, context: CallbackContext) -> int:
    """Displays annotation"""
    genius = context.bot_data["genius"]
    language = context.user_data["bot_lang"]
    placeholder_text = context.bot_data["texts"][language]["display_annotation"]
    chat_id = update.effective_chat.id

    if update.callback_query:
        update.callback_query.answer()
        annotation_id = int(update.callback_query.data.split("_")[1])

    else:
        annotation_id = int(context.args[0].split("_")[1])

    annotation = genius.annotation(annotation_id, text_format="html")
    annotation = annotation["annotation"]["body"]["html"]
    if not annotation:
        annotation = placeholder_text
        context.bot.send_message(chat_id, annotation)
        return END

    annotation = BeautifulSoup(annotation, "html.parser")
    annotation = str(remove_unsupported_tags(annotation))

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

    context.bot.send_message(chat_id, annotation, reply_markup=keyboard)

    return END


@log
@get_user
def upvote_annotation(update: Update, context: CallbackContext) -> int:
    """Upvotes/unvotes annotation on behalf of the user"""
    chat_id = update.effective_chat.id
    language = context.user_data["bot_lang"]
    texts = context.bot_data["texts"][language]["upvote_annotation"]
    message = update.callback_query.message

    annotation_id = int(update.callback_query.data.split("_")[1])
    token = context.user_data["token"]

    if token is None:
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

    annotation_id = int(update.callback_query.data.split("_")[1])
    token = context.user_data["token"]

    if token is None:
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
