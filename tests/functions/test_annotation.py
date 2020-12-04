import json
import re
from os.path import join
from unittest.mock import patch, MagicMock

import pytest
from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard

from geniust import constants
from geniust.functions import annotation


@pytest.fixture(scope='module')
def annotation_dict_fixture(data_path):
    with open(join(data_path, 'annotation.json'), 'r') as f:
        return json.load(f)


@pytest.fixture(scope='module')
def voters_dict(data_path):
    with open(join(data_path, 'annotation_voters.json'), 'r') as f:
        return json.load(f)


@pytest.mark.parametrize('update, annotation_dict, voters',
                         [
                             (pytest.lazy_fixture('update_callback_query'),
                              pytest.lazy_fixture('annotation_dict_fixture'),
                              pytest.lazy_fixture('voters_dict')),

                             (pytest.lazy_fixture('update_message'),
                              {'annotation': {'body': {'html': ''}}},
                              {'voters': {'votes_total': 0, 'up': [], 'down':[]}}),
                         ])
def test_display_annotation(update, context, annotation_dict, voters):
    if update.callback_query:
        update.callback_query.data = 'annotation_1'
    else:
        context.args[0] = 'annotation_1'

    genius = context.bot_data['genius']
    genius.annotation.return_value = annotation_dict
    genius.voters.return_value = voters

    res = annotation.display_annotation(update, context)

    if annotation_dict['annotation']['body']['html']:
        genius.voters.assert_called_once_with(annotation_id=1)

        keyboard = (context.bot.send_message
                    .call_args[1]['reply_markup']['inline_keyboard'])

        assert len(keyboard[0]) == 2

        upvote_button = keyboard[0][0]
        downvote_button = keyboard[0][1]

        voters = voters['voters']
        if voters['votes_total']:
            assert str(len(voters['up'])) in upvote_button.text
            assert upvote_button.callback_data == 'annotation_1_upvote'

            assert str(len(voters['down'])) in downvote_button.text
            assert downvote_button.callback_data == 'annotation_1_downvote'
        else:
            assert '0' in upvote_button.text
            assert upvote_button.callback_data == 'annotation_1_upvote'

            assert '0' in downvote_button.text
            assert downvote_button.callback_data == 'annotation_1_downvote'

    # annotation ID = 1
    assert genius.annotation.call_args[0][0] == 1

    if update.callback_query:
        update.callback_query.answer.assert_called_once()

    assert res == constants.END


@pytest.fixture
def voters_but_voted(account_dict, voters_dict):
    voters_dict['voters']['up'].append(account_dict['user'])
    voters_dict['voters']['down'].append(account_dict['user'])
    return voters_dict


@pytest.mark.parametrize('voters, token',
                        [
                         (pytest.lazy_fixture('voters_dict'), 'test_token'),
                         (pytest.lazy_fixture('voters_but_voted'), 'test_token'),
                         (pytest.lazy_fixture('voters_dict'), None),
                         ])
def test_upvote_annotation(update_callback_query, context, account_dict, voters, token):
    update = update_callback_query
    update.callback_query.data = 'annotation_1_upvote'
    keyboard = IBKeyboard([[IButton('1'), IButton('1')]])
    update.callback_query.message.configure_mock(reply_markup=keyboard)
    context.user_data['token'] = token

    client = MagicMock()
    client().account.return_value = account_dict
    client().voters.return_value = voters

    with patch('geniust.api.GeniusT', client):
        res = annotation.upvote_annotation(update, context)

    upvote_value = int(re.findall(r'\d+', keyboard.inline_keyboard[0][0].text)[0])
    downvote_value = int(re.findall(r'\d+', keyboard.inline_keyboard[0][1].text)[0])

    voters = voters['voters']
    if context.user_data['token'] is None:
        assert upvote_value == 1
        # only called twice to assign account and voters
        assert client.call_count == 2
    elif (account_dict['user']['id'] in [x['id'] for x in voters['up']]
            or account_dict['user']['id'] in [x['id'] for x in voters['down']]):
        assert upvote_value == 0
        client().unvote_annotation.assert_called_once_with(1)
    else:
        assert upvote_value == 2
        client().upvote_annotation.assert_called_once_with(1)

    assert downvote_value == 1

    assert res == constants.END


@pytest.mark.parametrize('voters, token',
                        [
                         (pytest.lazy_fixture('voters_dict'), 'test_token'),
                         (pytest.lazy_fixture('voters_but_voted'), 'test_token'),
                         (pytest.lazy_fixture('voters_dict'), None),
                         ])
def test_downvote_annotation(update_callback_query,
                             context,
                             account_dict,
                             voters,
                             token):
    update = update_callback_query
    update.callback_query.data = 'annotation_1_upvote'
    keyboard = IBKeyboard([[IButton('1'), IButton('1')]])
    update.callback_query.message.configure_mock(reply_markup=keyboard)
    context.user_data['token'] = token

    client = MagicMock()
    client().account.return_value = account_dict
    client().voters.return_value = voters

    with patch('geniust.api.GeniusT', client):
        res = annotation.downvote_annotation(update, context)

    upvote_value = int(re.findall(r'\d+', keyboard.inline_keyboard[0][0].text)[0])
    downvote_value = int(re.findall(r'\d+', keyboard.inline_keyboard[0][1].text)[0])

    voters = voters['voters']
    if context.user_data['token'] is None:
        assert downvote_value == 1
        # only called twice to assign account and voters
        assert client.call_count == 2
    elif (account_dict['user']['id'] in [x['id'] for x in voters['up']]
            or account_dict['user']['id'] in [x['id'] for x in voters['down']]):
        assert downvote_value == 0
        client().unvote_annotation.assert_called_once_with(1)
    else:
        assert downvote_value == 2
        client().downvote_annotation.assert_called_once_with(1)

    assert upvote_value == 1
    assert res == constants.END
