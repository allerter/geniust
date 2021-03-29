import threading
import logging

import tekore as tk
import tornado.web
import tornado.ioloop
from requests import HTTPError
from telegram import Bot
from telegram.utils.webhookhandler import WebhookServer
from tornado.web import url, RequestHandler

from geniust.db import Database
from geniust.utils import log


class CronHandler(RequestHandler):
    """Handles cron-job requests"""

    def get(self):
        """Responds to GET request to make cron job successful"""
        self.write("OK")

    def head(self):
        """ Satisfy UptimeRobot that this url exists"""
        self.finish()


class TokenHandler(RequestHandler):
    """Handles redirected URLs from Genius

    This class will handle the URLs that Genius
    redirects to the web server, processing the
    query's parameters and retrieving a token
    from Genius for the corresponding user.
    """

    def initialize(
        self,
        auths: dict,
        database: Database,
        bot: Bot,
        texts: dict,
        user_data: dict,
        username: str,
    ) -> None:
        self.auths = auths
        self.database = database
        self.bot = bot
        self.texts = texts
        self.user_data = user_data
        self.username = username
        self.logger = logging.getLogger(__name__)

    @log
    def get(self):
        """Receives and processes callback data from Genius"""
        error = self.get_argument("error", default=None)
        if error is not None:  # User denied access
            self.logger.debug(error)
            self.redirect(f"https://t.me/{self.username}")
            return

        state = self.get_argument("state")
        code = self.get_argument("code")
        if not all([code, state]):
            self.set_status(400)
            self.finish("state/code unvailable")
            return

        if len(state.split("_")) == 3:
            chat_id_str, platform, received_value = state.split("_")
        else:
            chat_id_str = "0"
            platform = None
            received_value = state

        try:
            chat_id = int(chat_id_str)
        except ValueError:
            chat_id = 0

        original_value = (
            self.user_data[chat_id].pop("state", None)
            if chat_id in self.user_data
            else None
        )

        # ensure state parameter is correct
        if original_value != received_value:
            self.set_status(400)
            self.finish("Invalid state parameter.")
            self.logger.debug(
                'Invalid state "%s" for user %s', repr(received_value), chat_id
            )
            return

        # get token from code
        redirected_url = "{}://{}{}".format(
            self.request.protocol, self.request.host, self.request.uri
        )
        if platform == "genius":
            try:
                token = self.auths["genius"].get_user_token(url=redirected_url)
            except HTTPError as e:
                self.logger.debug("%s for %s", str(e), state)
                return
        else:
            try:
                token = self.auths["spotify"]._cred.request_user_token(code)
                token = token.refresh_token
            except AssertionError:
                self.set_status(400)
                self.finish("Invalid state parameter")
                return
            except tk.BadRequest as e:
                self.set_status(e.response.status_code)
                self.finish(str(e))
                return
        # add token to db and user data
        self.database.update_token(chat_id, token, platform)
        self.user_data[chat_id][f"{platform}_token"] = token

        # redirect user to bot
        self.redirect(f"https://t.me/{self.username}")

        # inform user
        language = self.user_data[chat_id].get("bot_lang", "en")
        text = self.texts[language]["login"]["successful"]
        self.bot.send_message(chat_id, text)


class WebhookThread(threading.Thread):  # pragma: no cover
    """Starts a web-hook server

    This webhook is intended to respond to cron jobs that keep the bot from
    going to sleep in Heroku's free plan and receive tokens from Genius.
    """

    def __init__(
        self, bot_token, server_port, auths, database, texts, username, dispatcher
    ):
        super().__init__()
        app = tornado.web.Application(
            [
                url(r"/get", CronHandler),
                url(
                    r"/callback",
                    TokenHandler,
                    dict(
                        auths=auths,
                        database=database,
                        bot=Bot(bot_token),
                        texts=texts,
                        user_data=dispatcher.user_data,
                        username=username,
                    ),
                ),
            ]
        )
        # noinspection PyTypeChecker
        self.webhooks = WebhookServer("0.0.0.0", server_port, app, None)

    def run(self):
        """start web hook server"""
        self.webhooks.serve_forever()

    def shutdown(self):
        """shut down web hook server"""
        self.webhooks.shutdown()
