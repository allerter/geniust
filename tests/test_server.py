from unittest.mock import MagicMock, create_autospec

import pytest
import tekore as tk
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
        "1_genius_test-state",
        "1_spotify_test-state",
        "1_genius_invalid-state",
        "1_spotify_invalid-state",
    ],
)
@pytest.mark.parametrize("code", ["some_code", "invalid_code", "error"])
@pytest.mark.parametrize("user_state", ["test-state", None])
def test_token_handler(context, user_state, code, state):
    if len(state.split('_')) == 3:
        platform = state.split('_')[1]
    else:
        platform = None

    def get_argument(arg, default=None):
        if arg == "error" and code == "error":
            return "error"
        elif arg == "error":
            return default
        elif arg == "code":
            return code
        else:
            return state
    handler = MagicMock()
    handler.get_argument = get_argument
    handler.auths = context.bot_data["auths"]
    if code == "some_code" and platform == "genius":
        handler.auths['genius'].get_user_token.side_effect = None
        handler.auths['genius'].get_user_token.return_value = "test_token"
    elif code == "invalid_code" and platform == "genius":
        handler.auths['genius'].get_user_token.side_effect = HTTPError()
    elif code == "some_code" and platform == "spotify":
        handler.auths['spotify']._cred.request_user_token().refresh_token = "test_token"
    elif code == "invalid_code" and platform == "spotify":
        res = MagicMock()
        res.response.status_code = 400
        error = tk.BadRequest("", None, res)
        handler.auths['spotify']._cred.request_user_token.side_effect = error
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

    if (state == "1_genius_test-state"
        and user_state == "test-state"
            and code == "some_code"):
        handler.auths['genius'].get_user_token.assert_called_once_with(
            "https://test-app.com/callback?code=some_code&state=1_genius_test-state"
        )
        handler.database.update_token.assert_called_once_with(1, "test_token", platform)
        assert handler.bot.send_message.call_args[0][0] == 1
        assert handler.user_data[1][f"{platform}_token"] == "test_token"
        assert "state" not in handler.user_data[1]
        handler.redirect.assert_called_once()
    elif (state == "1_spotify_test-state"
          and user_state == "test-state"
            and code == "some_code"):
        handler.database.update_token.assert_called_once_with(1, "test_token", platform)
        assert handler.bot.send_message.call_args[0][0] == 1
        assert handler.user_data[1][f"{platform}_token"] == "test_token"
        assert "state" not in handler.user_data[1]
        handler.redirect.assert_called_once()
    elif code == "error":
        handler.redirect.assert_called_once()
    elif code == "invalid_code" or user_state is None:
        handler.database.update_token.assert_not_called()
    else:
        handler.set_status.assert_called_once_with(400)
        handler.finish.assert_called_once()


def test_token_handler_initialize():
    handler = MagicMock()
    auths = "auth"
    bot = "bot"
    database = "database"
    texts = "texts"
    user_data = "user_data"
    username = "username"

    res = TokenHandler.initialize(
        handler,
        auths=auths,
        database=database,
        bot=bot,
        texts=texts,
        user_data=user_data,
        username=username,
    )

    assert res is None
    assert handler.auths == auths
    assert handler.database == database
    assert handler.bot == bot
    assert handler.texts == texts
    assert handler.user_data == user_data
    assert handler.username == username
