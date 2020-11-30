import logging
import re

from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard

from geniust.constants import END
from geniust import genius, get_user
from geniust.utils import log, remove_unsupported_tags
from geniust.api import GeniusT

from bs4 import BeautifulSoup

logger = logging.getLogger()


@log
@get_user
def display_annotation(update, context):
    language = context.user_data['bot_lang']
    placeholder_text = context.bot_data['texts'][language]['display_annotation']

    if update.callback_query:
        chat_id = update.callback_query.message.chat.id
        annotation_id = int(update.callback_query.data.split('_')[1])
        update.callback_query.answer()
    else:
        chat_id = update.message.chat.id
        annotation_id = int(context.args[0].split('_')[1])

    annotation = genius.annotation(annotation_id, text_format='html')
    annotation = annotation['annotation']['body']['html']
    if not annotation:
        annotation = placeholder_text
        context.bot.send_message(chat_id, annotation)
        return END

    annotation = BeautifulSoup(annotation, 'html.parser')
    annotation = str(remove_unsupported_tags(annotation))

    voters = genius.voters(annotation_id=annotation_id)['voters']

    upvotes = len(voters['up'])
    downvotes = len(voters['down'])

    buttons = [
        [
            IButton(f'👍 {upvotes}',
                    callback_data=f'annotation_{annotation_id}_upvote'),
            IButton(f'👎 {downvotes}',
                    callback_data=f'annotation_{annotation_id}_downvote')
        ],
    ]
    keyboard = IBKeyboard(buttons)

    logger.debug('sending annotation %s', annotation_id)

    context.bot.send_message(chat_id, annotation, reply_markup=keyboard)

    return END


@log
@get_user
def upvote_annotation(update, context):
    chat_id = update.effective_chat.id
    language = context.user_data['bot_lang']
    texts = context.bot_data['texts'][language]['upvote_annotation']
    message = update.callback_query.message

    annotation_id = update.callback_query.data.split('_')[1]
    token = context.user_data['token']

    if token is None:
        context.bot.send_message(chat_id, texts['login_necessary'])
        return END

    genius_t = GeniusT(token)
    account = genius_t.account()['user']['id']
    voters = genius.voters(annotation_id=annotation_id)['voters']
    print(account in [x['id'] for x in voters['up']])
    if account in [x['id'] for x in voters['up']]:
        genius_t.unvote_annotation(annotation_id)
        update.callback_query.answer(texts['unvoted'])
        change = -1
    else:
        genius_t.upvote_annotation(annotation_id)
        update.callback_query.answer(texts['voted'])
        change = 1

    upvotes = message.reply_markup.inline_keyboard[0][0].text
    upvotes = int(re.search(r'\d+', upvotes)[0])
    new_text = '👍 ' + str(upvotes + change)
    message.reply_markup.inline_keyboard[0][0].text = new_text

    update.callback_query.edit_message_reply_markup(message.reply_markup)

    return END


@log
@get_user
def downvote_annotation(update, context):
    chat_id = update.effective_chat.id
    language = context.user_data['bot_lang']
    texts = context.bot_data['texts'][language]['downvote_annotation']
    message = update.callback_query.message

    annotation_id = update.callback_query.data.split('_')[1]
    token = context.user_data['token']

    if token is None:
        update.callback_query.answer()
        context.bot.send_message(chat_id, texts['login_necessary'])
        return END

    genius_t = GeniusT(token)
    account = genius_t.account()['user']['id']
    voters = genius.voters(annotation_id=annotation_id)['voters']
    if account in [x['id'] for x in voters['down']]:
        genius_t.unvote_annotation(annotation_id)
        update.callback_query.answer(texts['unvoted'])
        change = -1
    else:
        genius_t.downvote_annotation(annotation_id)
        update.callback_query.answer(texts['voted'])
        change = 1

    downvotes = message.reply_markup.inline_keyboard[0][-1].text
    downvotes = int(re.search(r'\d+', downvotes)[0])
    new_text = '👎 ' + str(downvotes + change)
    message.reply_markup.inline_keyboard[0][-1].text = new_text

    update.callback_query.edit_message_reply_markup(message.reply_markup)

    return END
