import json
from os.path import join

import pytest

from geniust import constants
from geniust.functions import customize


def test_cusotmize_menu(update_callback_query, context):
    update = update_callback_query

    res = customize.customize_menu(update, context)

    keyboard = (update.callback_query.edit_message_text
                .call_args[1]['reply_markup']['inline_keyboard'])

    assert len(keyboard) == 3

    update.callback_query.answer.assert_called_once()

    assert res == constants.SELECT_ACTION


@pytest.mark.parametrize('update', [pytest.lazy_fixture('update_callback_query'),
                                    pytest.lazy_fixture('update_message'),
                                    ])
def test_lyrics_language(update, context):
    if update.callback_query:
        update.callback_query.data = str(constants.OPTION1)

    res = customize.lyrics_language(update, context)

    if update.callback_query:
        update.callback_query.answer.assert_called_once()
        context.bot_data['db'].update_lyrics_language.assert_called_once()
        assert context.user_data['lyrics_lang'] == 'English'
        assert res == constants.END
    else:
        keyboard = (update.message.reply_text
                    .call_args[1]['reply_markup']['inline_keyboard'])
        assert len(keyboard) == 4
        assert res == constants.LYRICS_LANG


@pytest.mark.parametrize('update', [pytest.lazy_fixture('update_callback_query'),
                                    pytest.lazy_fixture('update_message'),
                                    ])
def test_bot_language(update, context):
    if update.callback_query:
        update.callback_query.data = 'en'

    res = customize.bot_language(update, context)

    if update.callback_query:
        update.callback_query.answer.assert_called_once()
        context.bot_data['db'].update_bot_language.assert_called_once()
        assert context.user_data['bot_lang'] == 'en'
        assert res == constants.END
    else:
        keyboard = (update.message.reply_text
                    .call_args[1]['reply_markup']['inline_keyboard'])
        assert len(keyboard) == len(list(context.bot_data['texts']))
        assert res == constants.BOT_LANG


@pytest.mark.parametrize('update', [pytest.lazy_fixture('update_callback_query'),
                                    pytest.lazy_fixture('update_message'),
                                    ])
def test_include_annotations(update, context):
    if update.callback_query:
        update.callback_query.data = str(constants.OPTION2)

    res = customize.include_annotations(update, context)

    if update.callback_query:
        update.callback_query.answer.assert_called_once()
        context.bot_data['db'].update_include_annotations.assert_called_once()
        assert context.user_data['include_annotations'] is False
        assert res == constants.END
    else:
        keyboard = (update.message.reply_text
                    .call_args[1]['reply_markup']['inline_keyboard'])
        assert len(keyboard) == 3
        assert res == constants.INCLUDE
