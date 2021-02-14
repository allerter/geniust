from unittest.mock import MagicMock, create_autospec

import pytest
from lyricsgenius import OAuth2
from requests import HTTPError

from geniust.server import CronHandler, TokenHandler
from geniust.db import Database


def test_cron_handler():
    handler = MagicMock()

    CronHandler.get(handler)

    handler.write.assert_called_once()


@pytest.mark.parametrize(
    "state",
    [
        "1_test-state",
        "1_invalid-state",
        "2_test-state",
        "invalid_state",
        "invalid-state",
    ],
)
@pytest.mark.parametrize("code", ["some_code", "invalid_code"])
@pytest.mark.parametrize("user_state", ["test-state", None])
def test_token_handler(context, user_state, code, state):
    handler = MagicMock()
    handler.get_argument = lambda x: code if x == "code" else state
    handler.auth = create_autospec(OAuth2)
    if code == "some_code":
        handler.auth.get_user_token.return_value = "test_token"
    else:
        handler.auth.get_user_token.side_effect = HTTPError()
    handler.database = create_autospec(Database)
    handler.bot = context.bot
    handler.texts = context.bot_data["texts"]
    handler.user_data = {1: {}}
    handler.user_data[1]["bot_lang"] = context.user_data["bot_lang"]
    handler.user_data[1]["state"] = user_state

    handler.request.protocol = "https"
    handler.request.host = "test-app.com"
    handler.request.uri = f"/callback?code={code}&state={state}"

    TokenHandler.get(handler)

    if state == "1_test-state" and user_state == "test-state" and code == "some_code":
        handler.auth.get_user_token.assert_called_once_with(
            "https://test-app.com/callback?code=some_code&state=1_test-state"
        )
        handler.database.update_token.assert_called_once_with(1, "test_token")
        assert handler.bot.send_message.call_args[0][0] == 1
        assert handler.user_data[1]["token"] == "test_token"
        assert "state" not in handler.user_data[1]
        handler.redirect.assert_called_once()
    elif code == "invalid_code":
        handler.database.update_token.assert_not_called()
    else:
        handler.set_status.assert_called_once_with(401)
        handler.finish.assert_called_once()
        handler.auth.get_user_token.assert_not_called()


def test_token_handler_initialize():
    handler = MagicMock()
    auth = "auth"
    bot = "bot"
    database = "database"
    texts = "texts"
    user_data = "user_data"

    res = TokenHandler.initialize(
        handler,
        auth=auth,
        database=database,
        bot=bot,
        texts=texts,
        user_data=user_data,
    )

    assert res is None
    assert handler.auth == auth
    assert handler.database == database
    assert handler.bot == bot
    assert handler.texts == texts
    assert handler.user_data == user_data
