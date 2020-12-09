import pytest

from geniust import constants
from geniust.functions import customize


@pytest.mark.parametrize('lyrics_language', ['English',
                                             'Non-English',
                                             'English + Non-English'])
def test_cusotmize_menu(update_callback_query, context, lyrics_language):
    update = update_callback_query
    context.user_data['lyrics_lang'] = lyrics_language

    res = customize.customize_menu(update, context)

    keyboard = (update.callback_query.edit_message_text
                .call_args[1]['reply_markup']['inline_keyboard'])

    assert len(keyboard) == 3

    update.callback_query.answer.assert_called_once()

    assert res == constants.SELECT_ACTION


@pytest.mark.parametrize('update, option',
        [(pytest.lazy_fixture('update_callback_query'), constants.OPTION1),
         (pytest.lazy_fixture('update_callback_query'), constants.OPTION2),
         (pytest.lazy_fixture('update_callback_query'), constants.OPTION3),
         (pytest.lazy_fixture('update_callback_query'), constants.LYRICS_LANG),
         (pytest.lazy_fixture('update_callback_query'), 'invalid'),
         (pytest.lazy_fixture('update_message'), None)
         ])
def test_lyrics_language(update, context, option):
    if update.callback_query:
        update.callback_query.data = str(option)

    res = customize.lyrics_language(update, context)

    if update.callback_query and option != constants.LYRICS_LANG:

        if option == constants.OPTION1:
            assert context.user_data['lyrics_lang'] == 'English'
        elif option == constants.OPTION2:
            assert context.user_data['lyrics_lang'] == 'Non-English'
        elif option == constants.OPTION3:
            assert context.user_data['lyrics_lang'] == 'English + Non-English'
        else:
            return
        assert res == constants.END
        update.callback_query.answer.assert_called_once()
        context.bot_data['db'].update_lyrics_language.assert_called_once()
    else:
        if update.callback_query:
            keyboard = (update.callback_query.edit_message_text
                        .call_args[1]['reply_markup']['inline_keyboard'])
        else:
            keyboard = (update.message.reply_text
                        .call_args[1]['reply_markup']['inline_keyboard'])
        assert len(keyboard) == 4
        assert res == constants.LYRICS_LANG


@pytest.mark.parametrize('update, option',
        [(pytest.lazy_fixture('update_callback_query'), constants.BOT_LANG),
         (pytest.lazy_fixture('update_callback_query'), 'en'),
         (pytest.lazy_fixture('update_callback_query'), 'fa'),
         (pytest.lazy_fixture('update_callback_query'), 'invalid'),
         (pytest.lazy_fixture('update_message'), None),
         ])
def test_bot_language(update, context, option):
    if update.callback_query:
        update.callback_query.data = str(option)

    res = customize.bot_language(update, context)

    if update.callback_query and option != constants.BOT_LANG:
        if option != 'invalid':
            assert context.user_data['bot_lang'] == option
        else:
            return
        update.callback_query.answer.assert_called_once()
        context.bot_data['db'].update_bot_language.assert_called_once()
        assert res == constants.END
    else:
        if update.callback_query:
            keyboard = (update.callback_query.edit_message_text
                        .call_args[1]['reply_markup']['inline_keyboard'])
        else:
            keyboard = (update.message.reply_text
                        .call_args[1]['reply_markup']['inline_keyboard'])
        assert len(keyboard) == len(list(context.bot_data['texts']))
        assert res == constants.BOT_LANG


@pytest.mark.parametrize('update, option',
        [(pytest.lazy_fixture('update_callback_query'), constants.OPTION1),
         (pytest.lazy_fixture('update_callback_query'), constants.OPTION2),
         (pytest.lazy_fixture('update_callback_query'), 'invalid'),
         (pytest.lazy_fixture('update_callback_query'), constants.INCLUDE),
         (pytest.lazy_fixture('update_message'), None),
         ])
def test_include_annotations(update, context, option):
    if update.callback_query:
        update.callback_query.data = str(option)

    res = customize.include_annotations(update, context)

    if update.callback_query and option != constants.INCLUDE:
        if option == constants.OPTION1:
            assert context.user_data['include_annotations'] is True
        elif option == constants.OPTION2:
            assert context.user_data['include_annotations'] is False
        else:
            return
        update.callback_query.answer.assert_called_once()
        context.bot_data['db'].update_include_annotations.assert_called_once()
        assert res == constants.END
    else:
        if update.callback_query:
            keyboard = (update.callback_query.edit_message_text
                        .call_args[1]['reply_markup']['inline_keyboard'])
        else:
            keyboard = (update.message.reply_text
                        .call_args[1]['reply_markup']['inline_keyboard'])
        assert len(keyboard) == 3
        assert res == constants.INCLUDE
