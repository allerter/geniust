import json
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
from geniust.constants import Preferences
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


class GenresHandler(RequestHandler):
    """Returns a list of available genres to the request"""

    def initialize(self, recommender) -> None:
        self.recommender = recommender
        self.logger = logging.getLogger(__name__)

    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")

    @log
    def get(self):
        age = self.get_argument("age", default=None)
        response = {"response": {"status_code": 200}}
        r = response["response"]
        if age is None:
            r["genres"] = self.recommender.genres
        else:
            try:
                age = int(age)
            except Exception as e:
                self.logger.debug(e)
                self.set_status(400)
                r["error"] = "invalid value for age parameter."
                r["status_code"] = 400
            else:
                r["genres"] = self.recommender.genres_by_age(age)
                r["age"] = age

        res = json.dumps(response)
        self.write(res)


class SearchHandler(RequestHandler):
    """Searches artists and returns matches"""

    def initialize(self, recommender) -> None:
        self.recommender = recommender
        self.logger = logging.getLogger(__name__)

    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")

    @log
    def get(self):
        artist = self.get_argument("artist", default=None)
        response = {"response": {"status_code": 200}}
        r = response["response"]
        if artist is None:
            self.set_status(404)
            r["error"] = "404 Not Found"
            r["status_code"] = 404
        else:
            r["artists"] = self.recommender.search_artist(artist)
            r["artist"] = artist

        res = json.dumps(response)
        self.write(res)


class PreferencesHandler(RequestHandler):
    """Returns preferences based user's data on Spotify/Genius"""

    def initialize(self, auths, recommender) -> None:
        self.auths = auths
        self.recommender = recommender
        self.logger = logging.getLogger(__name__)

    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")

    @log
    def get(self):
        genius_code = self.get_argument("genius_code", default=None)
        spotify_code = self.get_argument("spotify_code", default=None)
        response = {"response": {"status_code": 200}}
        r = response["response"]
        if genius_code is None and spotify_code is None:
            self.set_status(404)
            r["error"] = "404 Not Found"
            r["status_code"] = 404
            token = None
        elif genius_code:
            token = self.auths["genius"].get_user_token(code=genius_code)
            platform = "genius"
        else:
            token = self.auths["spotify"]._cred.request_user_token(spotify_code)
            token = token.access_token
            platform = "spotify"

        if token is not None:
            preferences = self.recommender.preferences_from_platform(token, platform)
            if preferences is not None:
                r["genres"] = preferences.genres
                r["artists"] = preferences.artists
            else:
                r["genres"] = None
                r["artists"] = None

        res = json.dumps(response)
        self.write(res)


class RecommendationsHandler(RequestHandler):
    """Returns song recommendations based on user's preferences"""

    def initialize(self, recommender) -> None:
        self.recommender = recommender
        self.logger = logging.getLogger(__name__)

    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")

    @log
    def get(self):
        genres = self.get_argument("genres", default=None)
        artists = self.get_argument("artists", default=None)
        song_type = self.get_argument("song_type", default="any")
        response = {"response": {"status_code": 200}}
        r = response["response"]

        # genres are required
        if genres is None:
            self.set_status(400)
            r["error"] = "genres parameter required."
            r["status_code"] = 400
            res = json.dumps(response)
            self.write(res)
            return

        # genres must be valid
        genres = genres.split(",")
        invalid_genre = False
        for genre in genres:
            if genre not in self.recommender.genres:
                invalid_genre = True
                break
        if invalid_genre:
            self.set_status(400)
            r["error"] = "invalid genre in genres."
            r["status_code"] = 400
            res = json.dumps(response)
            self.write(res)
            return

        # artists must be valid
        if artists is not None:
            artists = artists.split(",")
            invalid_artist = False
            for request_artist in artists:
                if request_artist not in self.recommender.artists_names:
                    invalid_artist = True
                    break
            if invalid_artist:
                self.set_status(400)
                r["error"] = "invalid artist in artists."
                r["status_code"] = 400
                res = json.dumps(response)
                self.write(res)
                return
        else:
            artists = []

        valid_song_types = ("any", "any_file", "preview", "full", "preview,full")
        if song_type not in valid_song_types:
            self.set_status(400)
            r["error"] = (
                "invalid song type. must be one of 'any',"
                " 'any_file', 'preview', 'full', 'preview,full'"
            )
            r["status_code"] = 400
            res = json.dumps(response)
            self.write(res)
            return

        user_preferences = Preferences(genres=genres, artists=artists)
        tracks = [
            x.to_dict()
            for x in self.recommender.shuffle(user_preferences, song_type=song_type)
        ]

        r["tracks"] = tracks
        res = json.dumps(response)
        self.write(res)


class WebhookThread(threading.Thread):  # pragma: no cover
    """Starts a web-hook server

    This webhook is intended to respond to cron jobs that keep the bot from
    going to sleep in Heroku's free plan and receive tokens from Genius.
    """

    def __init__(
        self, bot_token, server_port, auths, database, texts, username, dispatcher
    ):
        super().__init__()
        recommender = dispatcher.bot_data["recommender"]
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
                url(r"/api/genres", GenresHandler, dict(recommender=recommender)),
                url(r"/api/search", SearchHandler, dict(recommender=recommender)),
                url(
                    r"/api/preferences",
                    PreferencesHandler,
                    dict(auths=auths, recommender=recommender),
                ),
                url(
                    r"/api/recommendations",
                    RecommendationsHandler,
                    dict(recommender=recommender),
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
