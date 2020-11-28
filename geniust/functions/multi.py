import logging

from geniust.constants import END
from geniust import genius, get_user, texts
from geniust.utils import log, remove_unsupported_tags

from bs4 import BeautifulSoup


logger = logging.getLogger()


@log
@get_user
def display_annotation(update, context):
    language = context.user_data['bot_lang']
    placeholder_text = texts[language]['display_annotation']

    if update.callback_query:
        chat_id = update.callback_query.message.chat.id
        annotation_id = int(update.callback_query.data[2:])
        update.callback_query.answer()
    else:
        chat_id = update.message.chat.id
        annotation_id = int(context.args[0][2:])

    annotation = genius.annotation(annotation_id, text_format='html')
    annotation = annotation['annotation']['body']['html']
    if annotation:
        annotation = BeautifulSoup(annotation, 'html.parser')
    else:
        annotation = placeholder_text
    annotation = str(remove_unsupported_tags(annotation))

    logger.debug('sending annotation %s', annotation_id)

    context.bot.send_message(chat_id, annotation)

    return END
