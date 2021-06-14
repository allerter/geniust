import logging
import traceback
import warnings
from typing import Any, Dict

import lyricsgenius as lg
import tekore as tk
from notifiers.logging import NotificationHandler
from requests.exceptions import HTTPError
from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram import Message, Update, error
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    Defaults,
    Filters,
    InlineQueryHandler,
    MessageFilter,
    MessageHandler,
    TypeHandler,
    Updater,
)

from geniust import auths, get_user, texts, username
from geniust.api import GeniusT, Recommender

# from geniust.constants import SERVER_ADDRESS
from geniust.constants import (
    BOT_TOKEN,
    BTC_ADDRESS,
    CUSTOMIZE_MENU,
    DATABASE_URL,
    DEVELOPERS,
    DONATE,
    DONT_INCLUDE_ANNOTATIONS,
    END,
    ENGLISH_AND_NON_ENGLISH,
    GENIUS_TOKEN,
    HELP,
    INCLUDE,
    INCLUDE_ANNOTATIONS,
    LOG_LEVEL,
    LOGGED_IN,
    LOGOUT,
    LYRICS_LANG,
    MAIN_MENU,
    ONLY_ENGLIGH,
    ONLY_NON_ENGLISH,
    SELECT_ACTION,
    SELECT_ARTISTS,
    SELECT_GENRES,
    SERVER_PORT,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    TYPING_ALBUM,
    TYPING_ARTIST,
    TYPING_FEEDBACK,
    TYPING_LYRIC_CARD_CUSTOM,
    TYPING_LYRIC_CARD_LYRICS,
    TYPING_LYRICS,
    TYPING_SONG,
    TYPING_USER,
)
from geniust.db import Database
from geniust.functions import (
    account,
    album,
    annotation,
    artist,
    customize,
    inline_query,
    lyric_card,
    recommender,
    song,
    user,
)
from geniust.server import WebhookThread
from geniust.utils import log

warnings.filterwarnings(
    "ignore", message="If 'per_", module="telegram.ext.conversationhandler"
)

# Enable logging
LOG_LEVEL_NUM: int = getattr(logging, LOG_LEVEL)
logging.getLogger("telegram").setLevel(
    logging.INFO if LOG_LEVEL_NUM <= logging.INFO else LOG_LEVEL
)
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("geniust")
logger.setLevel(LOG_LEVEL)
# If we're debugging, we already have access to the logs and don't need
# the notification handler to send us the errors
if LOG_LEVEL_NUM > logging.DEBUG:
    defaults = {"token": BOT_TOKEN, "chat_id": DEVELOPERS[0]}
    notification_handler = NotificationHandler("telegram", defaults=defaults)
    notification_handler.setLevel(logging.ERROR)
    logging.getLogger().addHandler(notification_handler)


class NewShuffleUser(MessageFilter):
    def __init__(self, database, user_data):
        self.user_data = user_data
        self.database = database

    @log
    def filter(self, message: Message) -> bool:
        """determines whether user should enter conv or not

        Args:
            message (telegram.Message): Message from user.

        Returns:
            bool: True if user has no preferences, else False.
        """
        chat_id = message.from_user.id
        if "bot_lang" not in self.user_data[chat_id]:
            self.database.user(chat_id, self.user_data[chat_id])

        return True if not self.user_data[chat_id]["preferences"] else False


@log
@get_user
def main_menu(update: Update, context: CallbackContext) -> int:
    """Displays main menu"""
    ud = context.user_data
    chat_id = update.effective_chat.id
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
            IButton(text["user"], callback_data=str(TYPING_USER)),
        ],
        [IButton(text["lyrics"], callback_data=str(TYPING_LYRICS))],
        [
            IButton(text["lyric_card"], callback_data=str(TYPING_LYRIC_CARD_LYRICS)),
            IButton(
                text["lyric_card_custom"], callback_data=str(TYPING_LYRIC_CARD_CUSTOM)
            ),
        ],
        [
            IButton(text["customize_lyrics"], callback_data=str(CUSTOMIZE_MENU)),
            IButton(text["change_language"], callback_data="bot_lang"),
        ],
        [IButton(text["help"], callback_data=str(HELP))],
        [IButton(text["donate"], callback_data=str(DONATE))],
    ]

    token = context.user_data.get(
        "genius_token", context.user_data.get("spotify_token")
    )
    if token is not None:
        buttons.append([IButton(text["view_accounts"], callback_data=str(LOGGED_IN))])

    if context.user_data["preferences"] is not None:
        buttons.append([IButton(text["reset_shuffle"], callback_data="shuffle_reset")])
    else:
        buttons.append([IButton(text["shuffle"], callback_data="shuffle")])

    keyboard = IBKeyboard(buttons)

    send_as_message = False
    if update.callback_query:
        update.callback_query.answer()
        try:
            update.callback_query.edit_message_text(
                text=text["body"], reply_markup=keyboard
            )
        except error.BadRequest:
            update.callback_query.delete_message()
            send_as_message = True
    else:
        send_as_message = True

    if send_as_message:
        context.bot.send_message(
            chat_id=chat_id, text=text["body"], reply_markup=keyboard
        )

    return END


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
            f"Chat ID: {update.message.chat.id}\n"
            f"Bot Lang: {language}\n\n"
        )
    else:
        text = (
            "User: "
            f"<a href={update.effective_user.id}>"
            f"{update.effective_user.first_name}</a>\n"
            f"Chat ID: {update.message.chat.id}\n"
            f"Bot Lang: {language}\n\n"
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
    texts = context.bot_data["texts"][language]
    chat_id = update.effective_user.id
    ud = context.user_data

    if "lyric_card" in ud:
        removal_job = context.job_queue.get_jobs_by_name(f"remove_lyric_info_{chat_id}")
        if removal_job:
            removal_job[0].schedule_removal()
        ud.pop("lyric_card")

    if update.callback_query:
        query = update.callback_query.data
        if query == str(CUSTOMIZE_MENU):
            return customize.customize_menu(update, context)
        elif query == str(MAIN_MENU):
            return main_menu(update, context)

    text = texts["canceled"] if update.message else texts["end_describing"]
    context.bot.send_message(chat_id, text)
    return END


@log
@get_user
def help_message(update: Update, context: CallbackContext) -> int:
    """Sends the /help text to the user"""
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["help_message"].format(username=username)

    keyboard = IBKeyboard(
        [
            [
                IButton(
                    text=context.bot_data["texts"][language]["inline_mode"],
                    switch_inline_query_current_chat="",
                )
            ]
        ]
    )

    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        update.message.reply_text(text, reply_markup=keyboard)

    return END


@log
@get_user
def contact_us(update: Update, context: CallbackContext) -> int:
    """Prompts the user to send a message"""
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["contact_us"]

    update.message.reply_text(text)
    return TYPING_FEEDBACK


@log
@get_user
def donate(update: Update, context: CallbackContext) -> int:
    """Sends the /donate message to the user"""
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["donate"]
    text = text.format(BTC_ADDRESS)

    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.edit_message_text(text)
    else:
        update.message.reply_text(text)

    return END


def error_handler(update: Update, context: CallbackContext) -> None:
    """Handles errors and alerts the developers"""
    exception = context.error
    user_data = context.user_data.copy()
    for key in ("genius_token", "spotify_token"):
        token = user_data.get(key)
        user_data[key] = "XXX" if token is not None else None
    # This log message will be sent to the devs by notifier's NotificationHandler.
    # So no need to send a message explicitly.
    error_msg = (
        "Exception while handling an update:"
        f"\n\nUpdate:\n{update}"
        f"\n\nUser Data:\n{user_data}\n\nTraceback:\n"
    )
    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__
    )
    tb_string = "".join(tb_list)
    # Only get the last traceback to make the error log shorter
    tb_string = tb_string[tb_string.rfind("Traceback (most recent call last):") :]
    error_msg += tb_string
    if len(error_msg) > 4096:
        diff = len(error_msg) - 4096
        error_msg = error_msg[diff:]
    logger.error(error_msg)

    # normally, we always have an user. If not, its either a channel or a poll update.
    if update and update.effective_user:
        language = user_data.get("bot_lang", "en")
        chat_id = update.effective_user.id
        if chat_id in DEVELOPERS and LOG_LEVEL_NUM == logging.DEBUG:
            return
        try:
            if isinstance(exception, HTTPError) and exception.args[0] == 403:
                msg = texts[language]["genius_403_error"]
            else:
                msg = texts[language]["error"]
        except NameError:
            logger.error("texts global was unaccessable in error handler")
            msg = "Something went wrong. Start again using /start"

        invalid_query = (
            "query is too old and response timeout expired or query id is invalid"
        )
        if update.inline_query:
            if invalid_query not in str(context.error).lower():
                update.inline_query.answer([])
        else:
            context.bot.send_message(chat_id=chat_id, text=msg)


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
    database = Database(DATABASE_URL.replace("postgres", "postgresql+psycopg2"))
    dp.bot_data["db"]: Database = database
    dp.bot_data["genius"]: GeniusT = GeniusT()
    dp.bot_data["lyricsgenius"]: lg.Genius = lg.Genius(
        GENIUS_TOKEN,
        retries=2,
        sleep_time=0,
        verbose=False,
    )
    dp.bot_data["spotify"]: tk.Spotify = tk.Spotify(
        tk.RefreshingCredentials(
            SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
        ).request_client_token()
    )
    dp.bot_data["recommender"] = Recommender()

    # ----------------- MAIN MENU -----------------

    main_menu_handler = CommandHandler("start", main_menu, Filters.regex(r"^\D*$"))
    dp.add_handler(main_menu_handler)

    # ----------------- COMMANDS -----------------

    callback_query_handlers = [
        CallbackQueryHandler(main_menu, pattern="^" + str(MAIN_MENU) + "$"),
        CallbackQueryHandler(album.type_album, pattern="^" + str(TYPING_ALBUM) + "$"),
        CallbackQueryHandler(
            album.display_album, pattern=r"^album_.*_(genius|spotify)$"
        ),
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
        CallbackQueryHandler(
            artist.display_artist, pattern=r"^artist_.*_(genius|spotify)$"
        ),
        CallbackQueryHandler(
            artist.display_artist_albums, pattern=r"^artist_[0-9]+_albums$"
        ),
        CallbackQueryHandler(
            artist.display_artist_songs,
            pattern=r"^artist_[0-9]+_songs_(ppt|rdt|ttl)_[0-9]+$",
        ),
        CallbackQueryHandler(song.type_lyrics, pattern=f"^{TYPING_LYRICS}$"),
        CallbackQueryHandler(song.type_song, pattern=f"^{TYPING_SONG}$"),
        CallbackQueryHandler(
            song.display_song, pattern=r"^song_[\d\S]+_(genius|spotify)$"
        ),
        CallbackQueryHandler(song.display_lyrics, pattern=r"^song_[0-9]+_lyrics$"),
        CallbackQueryHandler(
            song.download_song,
            pattern=r"^song_[\d\S]+_(recommender|spotify)_(preview|download)$",
        ),
        CallbackQueryHandler(
            customize.customize_menu, pattern="^" + str(CUSTOMIZE_MENU) + "$"
        ),
        CallbackQueryHandler(
            customize.lyrics_language,
            pattern=(
                fr"^{LYRICS_LANG}|"
                fr"{ONLY_ENGLIGH}|"
                fr"{ONLY_NON_ENGLISH}|"
                fr"{ENGLISH_AND_NON_ENGLISH}$"
            ),
        ),
        CallbackQueryHandler(
            customize.include_annotations,
            pattern=(
                fr"^{INCLUDE}|"
                fr"{INCLUDE_ANNOTATIONS}|"
                fr"{DONT_INCLUDE_ANNOTATIONS}$"
            ),
        ),
        CallbackQueryHandler(customize.bot_language, pattern=r"^bot_lang.*$"),
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
        # User
        CallbackQueryHandler(user.type_user, pattern=f"^{TYPING_USER}$"),
        CallbackQueryHandler(user.display_user, pattern=r"^user_[0-9]+$"),
        CallbackQueryHandler(
            user.display_user_description, pattern=r"^user_[0-9]+_description$"
        ),
        CallbackQueryHandler(user.display_user_header, pattern=r"^user_[0-9]+_header$"),
        CallbackQueryHandler(
            lyric_card.type_lyrics, pattern=fr"^{TYPING_LYRIC_CARD_LYRICS}$"
        ),
        CallbackQueryHandler(
            lyric_card.custom_lyric_card, pattern=fr"^{TYPING_LYRIC_CARD_CUSTOM}$"
        ),
        CallbackQueryHandler(donate, pattern=fr"^{DONATE}$"),
        CallbackQueryHandler(help_message, pattern=fr"^{HELP}$"),
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
        TYPING_LYRICS: [
            MessageHandler(Filters.text & (~Filters.command), song.search_lyrics),
            CallbackQueryHandler(song.type_lyrics, pattern="^(?!" + str(END) + ").*$"),
        ],
        TYPING_LYRIC_CARD_LYRICS: [
            MessageHandler(Filters.text & (~Filters.command), lyric_card.search_lyrics),
            CallbackQueryHandler(
                lyric_card.type_lyrics, pattern="^(?!" + str(END) + ").*$"
            ),
        ],
        TYPING_LYRIC_CARD_CUSTOM: [
            MessageHandler(
                Filters.photo | (Filters.text & (~Filters.command)),
                lyric_card.custom_lyric_card,
            ),
        ],
        TYPING_SONG: [
            MessageHandler(Filters.text & (~Filters.command), song.search_songs),
            CallbackQueryHandler(song.type_song, pattern="^(?!" + str(END) + ").*$"),
        ],
        TYPING_USER: [
            MessageHandler(Filters.text & (~Filters.command), user.search_users),
            CallbackQueryHandler(user.type_user, pattern="^(?!" + str(END) + ").*$"),
        ],
        TYPING_FEEDBACK: [
            MessageHandler(Filters.text & (~Filters.command), send_feedback)
        ],
    }

    commands = [
        CommandHandler("album", album.type_album),
        CommandHandler("artist", artist.type_artist),
        CommandHandler("lyric_card", lyric_card.type_lyrics),
        CommandHandler("lyric_card_custom", lyric_card.custom_lyric_card),
        CommandHandler("song", song.type_song),
        CommandHandler("song_by_lyrics", song.type_lyrics),
        CommandHandler("user", user.type_user),
        CommandHandler("contact_us", contact_us),
    ]
    commands.extend(callback_query_handlers)
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

    non_input_commands = [
        CommandHandler("lyrics_language", customize.lyrics_language),
        CommandHandler("bot_language", customize.bot_language),
        CommandHandler("include_annotations", customize.include_annotations),
        CommandHandler("donate", donate),
        CommandHandler("login", account.login_choices),
        CommandHandler("help", help_message),
    ]
    for command in non_input_commands:
        dp.add_handler(command)

    # Tuple of (command, description) tuples
    commands = tuple(texts["en"]["commands"].items())
    dp.bot.set_my_commands(commands)

    # ----------------- INLINE QUERIES -----------------

    inline_query_handlers = [
        InlineQueryHandler(inline_query.search_albums, pattern=r"^\.album"),
        InlineQueryHandler(inline_query.search_artists, pattern=r"^\.artist"),
        InlineQueryHandler(inline_query.search_lyrics, pattern=r"^\.lyrics"),
        InlineQueryHandler(inline_query.lyric_card, pattern=r"^\.lyric_card"),
        InlineQueryHandler(inline_query.search_songs, pattern=r"^\.song"),
        InlineQueryHandler(inline_query.search_users, pattern=r"^\.user"),
        InlineQueryHandler(inline_query.inline_menu),
    ]

    for handler in inline_query_handlers:
        dp.add_handler(handler)

    # ----------------- ARGUMENTED START (DEEP LINKING) -----------------

    argumented_start_handlers = [
        CommandHandler(
            "start",
            album.display_album,
            Filters.regex(r"^/start album_.*_(genius|spotify)$"),
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
                r"^/start song_[\d\S]+_(recommender|spotify)_(preview|download)$"
            ),
            pass_args=True,
        ),
        CommandHandler(
            "start",
            song.display_lyrics,
            Filters.regex(r"^/start song_[0-9]+_lyrics$"),
            pass_args=True,
        ),
        CommandHandler(
            "start",
            annotation.display_annotation,
            Filters.regex(r"^/start annotation_[0-9]+$"),
            pass_args=True,
        ),
        # User
        CommandHandler(
            "start",
            user.display_user,
            Filters.regex(r"^/start user_[0-9]+$"),
            pass_args=True,
        ),
        CommandHandler(
            "start",
            user.display_user_description,
            Filters.regex(r"^/start user_[0-9]+_description$"),
            pass_args=True,
        ),
        CommandHandler(
            "start",
            user.display_user_header,
            Filters.regex(r"^/start user_[0-9]+_header$"),
            pass_args=True,
        ),
    ]

    for handler in argumented_start_handlers:
        dp.add_handler(handler)

    # ----------------- SHUFFLE PREFERENCES -----------------

    shuffle_preferences_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler(
                "shuffle",
                recommender.welcome_to_shuffle,
                NewShuffleUser(database=database, user_data=dp.user_data),
            ),
            CallbackQueryHandler(
                recommender.welcome_to_shuffle,
                pattern=r"^shuffle$",
            ),
            CommandHandler("shuffle", recommender.display_recommendations),
            CallbackQueryHandler(recommender.reset_shuffle, pattern=r"^shuffle_reset$"),
        ],
        states={
            SELECT_ACTION: [
                CallbackQueryHandler(
                    recommender.input_preferences, pattern=r"^shuffle_manual$"
                ),
                CallbackQueryHandler(
                    recommender.process_preferences,
                    pattern=r"^shuffle_(genius|spotify)$",
                ),
                CallbackQueryHandler(
                    account.login, pattern=r"^login_(genius|spotify)$"
                ),
            ],
            SELECT_GENRES: [
                CallbackQueryHandler(
                    recommender.select_genres, pattern=r"^(done|genre|genre_[0-9]+)$"
                ),
                CallbackQueryHandler(recommender.input_age, pattern=r"^age$"),
                MessageHandler(Filters.text, recommender.input_age),
            ],
            SELECT_ARTISTS: [
                CallbackQueryHandler(
                    recommender.select_artists, pattern=r"^(artist_([0-9]+|none)|done)$"
                ),
                CallbackQueryHandler(recommender.input_artist, pattern=r"^input$"),
                MessageHandler(Filters.text, recommender.select_artists),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", end_describing),
            CommandHandler("stop", stop),
            TypeHandler(Update, end_describing),
        ],
    )
    dp.add_handler(shuffle_preferences_conv_handler)

    # log all errors
    dp.add_error_handler(error_handler)

    # web hook server to respond to GET cron jobs at /notify
    # and receive user tokens at /callback
    if SERVER_PORT:
        webhook_thread = WebhookThread(
            BOT_TOKEN, SERVER_PORT, auths, database, texts, username, dp
        )
        webhook_thread.start()
    # if SERVER_PORT:
    #
    #    updater.start_webhook('0.0.0.0', port=SERVER_PORT, url_path=BOT_TOKEN)
    #    updater.bot.setWebhook(SERVER_ADDRESS + BOT_TOKEN)
    # else:
    updater.start_polling()

    updater.idle()


if __name__ == "__main__":
    main()
