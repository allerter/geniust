from unittest.mock import patch, MagicMock

import pytest

from geniust import constants, bot


def test_main_menu(update_callback_query, context):

    update = update_callback_query
    user = context.user_data
    # Return None when bot tries to get the token
    context.bot_data['db'].get_token.return_value = None
    res = bot.main_menu(update, context)

    keyboard = (update.callback_query.edit_message_text
                .call_args[1]['reply_markup']['inline_keyboard'])

    # Check if bot returned correct keyboard for logged-in/out users
    if user['token'] is None:
        context.bot_data['db'].get_token.assert_called_once()
        assert keyboard[-1][0]['callback_data'] == constants.LOGIN
    else:
        assert keyboard[-1][0]['callback_data'] == constants.LOGGED_IN

    # Check if bot answered the callback query
    update.callback_query.answer.assert_called_once()

    # Check if bot returned the correct state to maintain the conversation
    assert res == constants.SELECT_ACTION


def test_stop(update_message, context):
    update = update_message

    res = bot.stop(update, context)
    update.message.reply_text.assert_called_once()
    assert res == constants.END


def test_send_feedback(update_message, context):
    update = update_message

    chat_id = context.user_data['chat_id']
    update.message.chat.id = chat_id

    username = 'test_username'
    update.effective_chat.username = username

    text = 'test_text'
    update.message.text = text

    res = bot.send_feedback(update, context)

    assert context.bot.send_message.call_count == len(constants.DEVELOPERS) + 1
    assert context.bot.send_message.call_args[1]['chat_id'] == chat_id

    assert res == constants.END


@pytest.mark.parametrize("level", [constants.MAIN_MENU,
                                   constants.ACCOUNT_MENU,
                                   constants.CUSTOMIZE_MENU,
                                   ])
@pytest.mark.skip('24 tests!')
def test_end_describing(update_callback_query, context, level):
    update = update_callback_query
    context.user_data['level'] = level

    main_menu = MagicMock()
    customize_menu = MagicMock()

    with patch('geniust.bot.main_menu', main_menu), \
            patch('geniust.functions.customize.customize_menu', customize_menu):
        res = bot.end_describing(update, context)

    if level == constants.MAIN_MENU:
        main_menu.assert_not_called()
        customize_menu.assert_not_called()
    elif level == constants.ACCOUNT_MENU or level == constants.CUSTOMIZE_MENU:
        main_menu.assert_called_once()

    assert res == constants.SELECT_ACTION


def test_help_message(update_message, context):
    update = update_message

    res = bot.help_message(update, context)

    update.message.reply_text.assert_called_once()
    assert res == constants.END


def test_contact_us(update_message, context):
    update = update_message

    res = bot.contact_us(update, context)

    update.message.reply_text.assert_called_once()
    assert res == constants.TYPING_FEEDBACK
