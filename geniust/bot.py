import json
import logging
import sys
import threading
import traceback
from typing import Dict, Any

import tornado.ioloop
import tornado.web
import tekore as tk
from notifiers.logging import NotificationHandler
from requests import HTTPError
from telegram import Bot, Update
from telegram.ext import CallbackContext
from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram.ext import (
    Defaults,
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    MessageFilter,
)
from telegram.utils.helpers import mention_html
from telegram.utils.webhookhandler import WebhookServer
from tornado.web import url, RequestHandler

from geniust.functions import (
    account,
    album,
    artist,
    recommender,
    song,
    customize,
    inline_query,
    annotation,
)
from geniust import get_user, texts, auths, database, username
from geniust.utils import log
from geniust.db import Database
from geniust.api import GeniusT, FaMusic

# from geniust.constants import SERVER_ADDRESS
from geniust.constants import (
    TYPING_ALBUM,
    TYPING_SONG,
    SERVER_PORT,
    BOT_TOKEN,
    SELECT_ACTION,
    SELECT_ARTISTS,
    SELECT_GENRES,
    BOT_LANG,
    LYRICS_LANG,
    INCLUDE,
    TYPING_FEEDBACK,
    TYPING_ARTIST,
    MAIN_MENU,
    DEVELOPERS,
    CUSTOMIZE_MENU,
    LOGGED_IN,
    LOGOUT,
    ACCOUNT_MENU,
    END,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    Preferences,
)

# Enable logging
logging.getLogger("telegram").setLevel(logging.INFO)
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger('geniust')
logger.setLevel(logging.DEBUG)
defaults = {
    'token': BOT_TOKEN,
    'chat_id': DEVELOPERS[0]
}
hdlr = NotificationHandler('telegram', defaults=defaults)
hdlr.setLevel(logging.ERROR)
logging.getLogger().addHandler(hdlr)


class NewShuffleUser(MessageFilter):

    def __init__(self, user_data):
        self.user_data = user_data

    @log
    def filter(self, message):
        chat_id = message.from_user.id
        if "bot_lang" not in self.user_data[chat_id]:
            database.user(chat_id, self.user_data[chat_id])

        return True if not self.user_data[chat_id]['preferences'] else False


class CronHandler(RequestHandler):
    """Handles cron-job requests"""

    def get(self):
        """Responds to GET request to make cron job successful"""
        self.write("OK")


class TokenHandler(RequestHandler):
    """Handles redirected URLs from Genius

    This class will handle the URLs that Genius
    redirects to the web server, processing the
    query's parameters and retrieving a token
    from Genius for the corresponding user.
    """

    def initialize(
        self, auths: dict, database: Database, bot: Bot, texts: dict, user_data: dict
    ) -> None:
        self.auths = auths
        self.database = database
        self.bot = bot
        self.texts = texts
        self.user_data = user_data

    @log
    def get(self):
        """Receives and processes callback data from Genius"""
        error = self.get_argument("error", default=None)
        if error is not None:  # User denied access
            logger.debug(error)
            self.redirect(f"https://t.me/{username}")
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
            logger.debug(
                'Invalid state "%s" for user %s', repr(received_value), chat_id
            )
            return

        # get token from code
        redirected_url = "{}://{}{}".format(
            self.request.protocol, self.request.host, self.request.uri
        )
        if platform == 'genius':
            try:
                token = self.auths['genius'].get_user_token(redirected_url)
            except HTTPError as e:
                logger.debug("%s for %s", str(e), state)
                return
        else:
            try:
                token = self.auths['spotify']._cred.request_user_token(code)
                token = token.refresh_token
            except AssertionError:
                self.set_status(400)
                self.finish('Invalid state parameter')
                return
            except tk.BadRequest as e:
                self.set_status(e.response.status_code)
                self.finish(str(e))
                return
        # add token to db and user data
        self.database.update_token(chat_id, token, platform)
        self.user_data[chat_id][f"{platform}_token"] = token

        # redirect user to bot
        self.redirect(f"https://t.me/{username}")

        # inform user
        language = self.user_data[chat_id].get("bot_lang", "en")
        text = self.texts[language]["login"]["successful"]
        self.bot.send_message(chat_id, text)


class GenresHandler(RequestHandler):

    def initialize(
        self, recommender
    ) -> None:
        self.recommender = recommender

    def set_default_headers(self):
        self.set_header("Content-Type", 'application/json')

    @log
    def get(self):
        age = self.get_argument("age", default=None)
        response = {'response': {'status_code': 200}}
        r = response['response']
        if age is None:
            r['genres'] = self.recommender.genres
        else:
            try:
                age = int(age)
            except Exception as e:
                logger.debug(e)
                self.set_status(400)
                r['error'] = 'invalid value for age parameter.'
                r['status_code'] = 400
            else:
                r['genres'] = self.recommender.genres_by_age(age)
                r['age'] = age

        res = json.dumps(response)
        self.write(res)


class SearchHandler(RequestHandler):

    def initialize(
        self, recommender
    ) -> None:
        self.recommender = recommender

    def set_default_headers(self):
        self.set_header("Content-Type", 'application/json')

    @log
    def get(self):
        artist = self.get_argument("artist", default=None)
        response = {'response': {'status_code': 200}}
        r = response['response']
        if artist is None:
            self.set_status(404)
            r['error'] = '404 Not Found'
            r['status_code'] = 404
        else:
            r['artists'] = self.recommender.search_artist(artist)
            r['artist'] = artist

        res = json.dumps(response)
        self.write(res)


class RecommendationsHandler(RequestHandler):

    def initialize(
        self, recommender
    ) -> None:
        self.recommender = recommender

    def set_default_headers(self):
        self.set_header("Content-Type", 'application/json')

    @log
    def get(self):
        genres = self.get_argument("genres", default=None)
        artists = self.get_argument("artists", default=None)
        song_type = self.get_argument("song_type", default='any')
        response = {'response': {'status_code': 200}}
        r = response['response']

        # genres are required
        if genres is None:
            self.set_status(400)
            r['error'] = 'genres parameter required.'
            r['status_code'] = 400
            res = json.dumps(response)
            self.write(res)
            return

        # genres must be valid
        genres = genres.split(',')
        invalid_genre = False
        for genre in genres:
            if genre not in self.recommender.genres:
                invalid_genre = True
                break
        if invalid_genre:
            self.set_status(400)
            r['error'] = 'invalid genre in genres.'
            r['status_code'] = 400
            res = json.dumps(response)
            self.write(res)
            return

        # artists must be valid
        if artists is not None:
            artists = artists.split(',')
            invalid_artist = False
            for request_artist in artists:
                if request_artist not in self.recommender.artists_names:
                    invalid_artist = True
                    break
            if invalid_artist:
                self.set_status(400)
                r['error'] = 'invalid artist in artists.'
                r['status_code'] = 400
                res = json.dumps(response)
                self.write(res)
                return
        else:
            artists = []

        valid_song_types = ('any', 'any_file', 'preview', 'full', 'preview,full')
        if song_type not in valid_song_types:
            self.set_status(400)
            r['error'] = "invalid song type. must be one of 'any', 'any_file', 'preview', 'full', 'preview,full'"
            r['status_code'] = 400
            res = json.dumps(response)
            self.write(res)
            return

        user_preferences = Preferences(genres=genres, artists=artists)
        tracks = [x.to_dict()
                  for x in self.recommender.shuffle(
            user_preferences,
            song_type=song_type)
        ]

        r['tracks'] = tracks
        res = json.dumps(response)
        self.write(res)


class WebhookThread(threading.Thread):  # pragma: no cover
    """Starts a web-hook server

    This webhook is intended to respond to cron jobs that keep the bot from
    going to sleep in Heroku's free plan and receive tokens from Genius.
    """

    def __init__(self, dispatcher):
        super().__init__()
        recommender = dispatcher.bot_data['recommender']
        app = tornado.web.Application(
            [
                url(r"/get", CronHandler),
                url(
                    r"/callback",
                    TokenHandler,
                    dict(
                        auths=auths,
                        database=database,
                        bot=Bot(BOT_TOKEN),
                        texts=texts,
                        user_data=dispatcher.user_data,
                    ),
                ),
                url(r"/api/genres", GenresHandler, dict(recommender=recommender)),
                url(r"/api/search", SearchHandler, dict(recommender=recommender)),
                url(r"/api/recommendations", RecommendationsHandler,
                    dict(recommender=recommender))
            ]
        )
        # noinspection PyTypeChecker
        self.webhooks = WebhookServer("0.0.0.0", SERVER_PORT, app, None)

    def run(self):
        """start web hook server"""
        self.webhooks.serve_forever()

    def shutdown(self):
        """shut down web hook server"""
        self.webhooks.shutdown()


@log
@get_user
def main_menu(update: Update, context: CallbackContext) -> int:
    """Displays main menu"""
    ud = context.user_data
    chat_id = update.effective_chat.id
    context.user_data["command"] = False
    language = ud["bot_lang"]
    text = context.bot_data["texts"][language]["main_menu"]

    logger.debug(
        "ID: %s, INCLUDE: %s, LLANG: %s, BOTLANG: %s",
        chat_id,
        ud["include_annotations"],
        ud["lyrics_lang"],
        language,
    )

    buttons = [
        [
            IButton(text["album"], callback_data=str(TYPING_ALBUM)),
            IButton(text["artist"], callback_data=str(TYPING_ARTIST)),
            IButton(text["song"], callback_data=str(TYPING_SONG)),
        ],
        [
            IButton(text["customize_lyrics"], callback_data=str(CUSTOMIZE_MENU)),
            IButton(text["change_language"], callback_data=str(BOT_LANG)),
        ],
    ]

    token = context.user_data.get("genius_token",
                                  context.user_data.get('spotify_token'))
    if token is not None:
        buttons.append([IButton(text["view_accounts"], callback_data=str(LOGGED_IN))])

    if context.user_data['preferences'] is not None:
        buttons.append([IButton(text['reset_shuffle'], callback_data='shuffle_reset')])

    keyboard = IBKeyboard(buttons)

    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.edit_message_text(
            text=text["body"], reply_markup=keyboard
        )
    else:
        context.bot.send_message(
            chat_id=chat_id, text=text["body"], reply_markup=keyboard
        )

    return SELECT_ACTION


@log
@get_user
def stop(update: Update, context: CallbackContext) -> int:
    """Ends Conversation by command"""
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["stop"]

    update.message.reply_text(text)
    return END


@log
@get_user
def send_feedback(update: Update, context: CallbackContext) -> int:
    """Sends user feedback to developers"""
    language = context.user_data["bot_lang"]
    reply_text = context.bot_data["texts"][language]["send_feedback"]

    if update.effective_chat.username:
        text = (
            f"User: @{update.effective_chat.username}\n"
            f"Chat ID: {update.message.chat.id}"
        )
    else:
        text = (
            "User: "
            f"<a href={update.effective_user.id}>"
            f"{update.effective_user.first_name}</a>\n"
            f"Chat ID: {update.message.chat.id}"
        )
    text += update.message.text

    for developer in DEVELOPERS:
        context.bot.send_message(chat_id=developer, text=text)
    context.bot.send_message(chat_id=update.message.chat.id, text=reply_text)
    return END


@log
@get_user
def end_describing(update: Update, context: CallbackContext) -> int:
    """Ends conversation altogether or returns to upper level"""
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["end_describing"]

    if update.message:
        update.message.reply_text(text)
        return END

    # noinspection PyUnreachableCode
    level = context.user_data.get("level", MAIN_MENU + 1)

    if level - 1 == MAIN_MENU or level == ACCOUNT_MENU:
        main_menu(update, context)
    elif level - 1 == CUSTOMIZE_MENU:
        customize.customize_menu(update, context)

    return SELECT_ACTION


@log
@get_user
def help_message(update: Update, context: CallbackContext) -> int:
    """Sends the /help text to the user"""
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["help_message"]

    update.message.reply_text(text)
    return END


@log
@get_user
def contact_us(update: Update, context: CallbackContext) -> int:
    """Prompts the user to send a message"""
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["contact_us"]

    update.message.reply_text(text)
    return TYPING_FEEDBACK


def error(update: Update, context: CallbackContext) -> None:
    """Handles errors and alerts the developers"""
    trace = "".join(traceback.format_tb(sys.exc_info()[2]))
    # lets try to get as much information from the telegram update as possible
    payload = ""
    text = ""
    # normally, we always have an user. If not, its either a channel or a poll update.
    if update:
        if update.effective_user:
            user = mention_html(
                update.effective_user.id, update.effective_user.first_name
            )
            payload += f" with the user {user}"
        # there are more situations when you don't get a chat
        if update.effective_chat:
            payload += f" within the chat <i>{update.effective_chat.title}</i>"
            if update.effective_chat.username:
                payload += f" (@{update.effective_chat.username})"
            chat_id = update.effective_chat.id

            if context:
                language = context.user_data["bot_lang"]
            else:
                language = "en"

            try:
                msg = texts[language]["error"]
            except NameError:
                logger.error("texts global was unaccessable in error handler")
                msg = "Something went wrong. Start again using /start"

            context.bot.send_message(chat_id=chat_id, text=msg)
        # lets put this in a "well" formatted text
        text = (
            f"Hey.\nThe error <code>{context.error if context else ''}</code>"
            f" happened{payload}. The full traceback:\n\n<code>{trace}</code>"
        )
    if text == "":
        text = "Empty Error\n" + payload + trace

    # and send it to the dev(s)
    for dev_id in DEVELOPERS:
        context.bot.send_message(dev_id, text, parse_mode="HTML")
    # we raise the error again, so the logger module catches it.
    # If you don't use the logger module, use it.
    raise  # type: ignore


def main():
    """Main function that holds the handlers and starts the bot"""
    updater = Updater(
        token=BOT_TOKEN,
        defaults=Defaults(
            parse_mode="html", disable_web_page_preview=True, run_async=True
        ),
    )

    dp = updater.dispatcher
    dp.bot_data["texts"]: Dict[Any, str] = texts
    dp.bot_data["db"]: Database = database
    dp.bot_data["genius"]: GeniusT = GeniusT()
    dp.bot_data['famusic']: FaMusic = FaMusic()
    dp.bot_data['spotify']: tk.Spotify = tk.Spotify(
        tk.RefreshingCredentials(SPOTIFY_CLIENT_ID,
                                 SPOTIFY_CLIENT_SECRET).request_client_token()
    )
    dp.bot_data['recommender'] = recommender.Recommender()

    my_states = [
        CallbackQueryHandler(main_menu, pattern="^" + str(MAIN_MENU) + "$"),
        CallbackQueryHandler(album.type_album, pattern="^" + str(TYPING_ALBUM) + "$"),
        CallbackQueryHandler(album.display_album,
                             pattern=r"^album_.*_(genius|spotify)$"),
        CallbackQueryHandler(
            album.display_album_covers, pattern=r"^album_[0-9]+_covers$"
        ),
        CallbackQueryHandler(
            album.display_album_tracks, pattern=r"^album_[0-9]+_tracks$"
        ),
        CallbackQueryHandler(
            album.display_album_formats, pattern=r"^album_[0-9]+_lyrics$"
        ),
        CallbackQueryHandler(
            album.thread_get_album, pattern=r"^album_[0-9]+_lyrics_(pdf|tgf|zip)$"
        ),
        CallbackQueryHandler(artist.type_artist, pattern=f"^{TYPING_ARTIST}$"),
        CallbackQueryHandler(artist.display_artist,
                             pattern=r"^artist_.*_(genius|spotify)$"),
        CallbackQueryHandler(
            artist.display_artist_albums, pattern=r"^artist_[0-9]+_albums$"
        ),
        CallbackQueryHandler(
            artist.display_artist_songs,
            pattern=r"^artist_[0-9]+_songs_(ppt|rdt|ttl)_[0-9]+$",
        ),
        CallbackQueryHandler(song.type_song, pattern=f"^{TYPING_SONG}$"),
        CallbackQueryHandler(
            song.display_song, pattern=r"^song_[\d\S]+_(genius|spotify)$"),
        CallbackQueryHandler(
            song.thread_display_lyrics, pattern=r"^song_[0-9]+_lyrics$"
        ),
        CallbackQueryHandler(
            song.download_song,
            pattern=r"^song_[\d\S]+_(recommender|spotify)_(preview|download)$"
        ),
        CallbackQueryHandler(
            customize.customize_menu, pattern="^" + str(CUSTOMIZE_MENU) + "$"
        ),
        CallbackQueryHandler(
            customize.lyrics_language, pattern="^" + str(LYRICS_LANG) + "$"
        ),
        CallbackQueryHandler(
            customize.include_annotations, pattern="^" + str(INCLUDE) + "$"
        ),
        CallbackQueryHandler(customize.bot_language, pattern="^" + str(BOT_LANG) + "$"),
        CallbackQueryHandler(
            annotation.display_annotation, pattern=r"^annotation_[0-9]+$"
        ),
        CallbackQueryHandler(
            annotation.upvote_annotation, pattern=r"^annotation_[0-9]+_upvote$"
        ),
        CallbackQueryHandler(
            annotation.downvote_annotation, pattern=r"^annotation_[0-9]+_downvote$"
        ),

        CallbackQueryHandler(account.login, pattern=r"^login_(spotify|genius)$"),
        CallbackQueryHandler(account.logged_in, pattern="^" + str(LOGGED_IN) + "$"),
        CallbackQueryHandler(account.logout, pattern="^" + str(LOGOUT) + "$"),
        CallbackQueryHandler(account.display_account, pattern=r"^account$"),
    ]

    user_input = {
        TYPING_ALBUM: [
            MessageHandler(Filters.text & (~Filters.command), album.search_albums),
            CallbackQueryHandler(album.type_album, pattern="^(?!" + str(END) + ").*$"),
        ],
        TYPING_ARTIST: [
            MessageHandler(Filters.text & (~Filters.command), artist.search_artists),
            CallbackQueryHandler(
                artist.type_artist, pattern="^(?!" + str(END) + ").*$"
            ),
        ],
        TYPING_SONG: [
            MessageHandler(Filters.text & (~Filters.command), song.search_songs),
            CallbackQueryHandler(song.type_song, pattern="^(?!" + str(END) + ").*$"),
        ],
        TYPING_FEEDBACK: [
            MessageHandler(Filters.text & (~Filters.command), send_feedback)
        ],
        INCLUDE: [
            CallbackQueryHandler(
                customize.include_annotations, pattern="^(?!" + str(END) + ").*$"
            )
        ],
        LYRICS_LANG: [
            CallbackQueryHandler(
                customize.lyrics_language, pattern="^(?!" + str(END) + ").*$"
            )
        ],
        BOT_LANG: [
            CallbackQueryHandler(
                customize.bot_language, pattern="^(?!" + str(END) + ").*$"
            )
        ],
    }

    # ----------------- MAIN MENU -----------------

    main_menu_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", main_menu, Filters.regex(r"^\D*$")),
            *my_states,
        ],
        states={SELECT_ACTION: my_states, **user_input},
        fallbacks=[
            CallbackQueryHandler(end_describing, pattern="^" + str(END) + "$"),
            CommandHandler("cancel", end_describing),
            CommandHandler("stop", stop),
        ],
    )
    dp.add_handler(main_menu_conv_handler)

    # ----------------- COMMANDS -----------------

    commands = [
        CommandHandler("album", album.type_album),
        CommandHandler("artist", artist.type_artist),
        CommandHandler("song", song.type_song),
        CommandHandler("lyrics_language", customize.lyrics_language),
        CommandHandler("bot_language", customize.bot_language),
        CommandHandler("include_annotations", customize.include_annotations),
        CommandHandler('login', account.login_choices),
        CommandHandler("help", help_message),
        CommandHandler("contact_us", contact_us),
    ]

    commands_conv_handler = ConversationHandler(
        entry_points=commands,
        states={**user_input},
        fallbacks=[
            CallbackQueryHandler(end_describing, pattern="^" + str(END) + "$"),
            CommandHandler("cancel", end_describing),
            CommandHandler("stop", stop),
        ],
    )
    dp.add_handler(commands_conv_handler)

    # ----------------- INLINE QUERIES -----------------

    inline_query_handlers = [
        InlineQueryHandler(inline_query.search_albums, pattern=r"^\.album"),
        InlineQueryHandler(inline_query.search_artists, pattern=r"^\.artist"),
        InlineQueryHandler(inline_query.search_songs, pattern=r"^\.song"),
        InlineQueryHandler(
            inline_query.inline_menu,
        ),
    ]

    for handler in inline_query_handlers:
        dp.add_handler(handler)

    # ----------------- ARGUMENTED START -----------------

    argumented_start_handlers = [
        CommandHandler(
            "start",
            album.display_album,
            Filters.regex(r"^/start albums_.*_(genius|spotify)$"),
            pass_args=True,
        ),
        CommandHandler(
            "start",
            album.display_album_covers,
            Filters.regex(r"^/start album_.*_covers$"),
            pass_args=True,
        ),
        CommandHandler(
            "start",
            album.display_album_tracks,
            Filters.regex(r"^/start album_.*_tracks$"),
            pass_args=True,
        ),
        CommandHandler(
            "start",
            album.display_album_formats,
            Filters.regex(r"^/start album_[0-9]+_lyrics$"),
            pass_args=True,
        ),
        CommandHandler(
            "start",
            artist.display_artist,
            Filters.regex(r"^/start artist_[0-9]+_(genius|spotify)$"),
            pass_args=True,
        ),
        CommandHandler(
            "start",
            artist.display_artist_songs,
            Filters.regex(r"^/start artist_[0-9]+_songs_(ppt|rdt|ttl)_[0-9]+$"),
            pass_args=True,
        ),
        CommandHandler(
            "start",
            artist.display_artist_albums,
            Filters.regex(r"^/start artist_[0-9]+_albums$"),
            pass_args=True,
        ),
        CommandHandler(
            "start",
            song.display_song,
            Filters.regex(r"^/start song_[\d\S]+_(genius|spotify)$"),
            pass_args=True,
        ),
        CommandHandler(
            "start",
            song.download_song,
            Filters.regex(
                r"^/start song_[\d\S]+_(recommender|spotify)_(preview|download)$"),
            pass_args=True,
        ),
        CommandHandler(
            "start",
            song.thread_display_lyrics,
            Filters.regex(r"^/start song_[0-9]+_lyrics$"),
            pass_args=True,
        ),
        CommandHandler(
            "start",
            annotation.display_annotation,
            Filters.regex(r"^/start annotation_[0-9]+$"),
            pass_args=True,
        ),
    ]

    for handler in argumented_start_handlers:
        dp.add_handler(handler)

    # ----------------- SHUFFLE PREFERENCES -----------------

    shuffle_preferences_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler(
                'shuffle',
                recommender.welcome_to_shuffle,
                NewShuffleUser(user_data=dp.user_data)),

            CommandHandler(
                "shuffle",
                recommender.display_recommendations),

            CallbackQueryHandler(
                recommender.reset_shuffle,
                pattern=r"^shuffle_reset$")
        ],
        states={
            SELECT_ACTION: [

                CallbackQueryHandler(
                    recommender.input_preferences,
                    pattern=r"^shuffle_manual$"),

                CallbackQueryHandler(
                    recommender.process_preferences,
                    pattern=r"^shuffle_(genius|spotify)$"),

                CallbackQueryHandler(
                    account.login,
                    pattern=r"^login_(genius|spotify)$"),
            ],
            SELECT_GENRES: [
                CallbackQueryHandler(
                    recommender.select_genres,
                    pattern=r"^(done|genre|genre_[0-9]+)$"),
                CallbackQueryHandler(
                    recommender.input_age,
                    pattern=r"^age$"),
                MessageHandler(Filters.text, recommender.input_age)
            ],
            SELECT_ARTISTS: [
                CallbackQueryHandler(
                    recommender.select_artists,
                    pattern=r"^(artist_([0-9]+|none)|done)$"),
                CallbackQueryHandler(
                    recommender.input_artist,
                    pattern=r"^input$"),
                MessageHandler(Filters.text, recommender.select_artists)
            ],

        },
        fallbacks=[
            CallbackQueryHandler(end_describing, pattern="^" + str(END) + "$"),
            CommandHandler("cancel", end_describing),
            CommandHandler("stop", stop),
        ],
    )
    dp.add_handler(shuffle_preferences_conv_handler)

    # log all errors
    dp.add_error_handler(error)

    # web hook server to respond to GET cron jobs at /notify
    # and receive user tokens at /callback
    if SERVER_PORT:
        webhook_thread = WebhookThread(dp)
        webhook_thread.start()
    # if SERVER_PORT:
    #
    #    updater.start_webhook('0.0.0.0', port=SERVER_PORT, url_path=BOT_TOKEN)
    #    updater.bot.setWebhook(SERVER_ADDRESS + BOT_TOKEN)
    # else:
    updater.start_polling(clean=True)

    updater.idle()


if __name__ == "__main__":
    main()
