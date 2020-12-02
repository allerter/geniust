"""
Main script of the bot which contains most of the functions.
"""
import logging
import sys
import threading
import traceback
from typing import Optional, Awaitable

import tornado.ioloop
import tornado.web
from geniust.functions import (
    account,
    album,
    artist,
    song,
    customize,
    inline_query,
    multi
)
from telegram import Bot
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
    InlineQueryHandler
)
from telegram.utils.helpers import mention_html
from telegram.utils.webhookhandler import WebhookServer
from tornado.web import url, RequestHandler

from geniust import get_user, texts, auth, database, username
from geniust.utils import log
# from geniust.constants import SERVER_ADDRESS
from geniust.constants import (
    TYPING_ALBUM, TYPING_SONG,
    SERVER_PORT, BOT_TOKEN, SELECT_ACTION,
    BOT_LANG, LYRICS_LANG, INCLUDE, TYPING_FEEDBACK, LOGIN,
    TYPING_ARTIST, MAIN_MENU, DEVELOPERS, CUSTOMIZE_MENU,
    LOGGED_IN, LOGOUT, ACCOUNT_MENU, END)

# Enable logging
logging.getLogger('telegram').setLevel(logging.INFO)
logging.basicConfig(format='%(asctime)s - %(funcName)s - %(levelname)s - %(message)s')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


class CronHandler(RequestHandler):
    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    def get(self):
        """respond to GET request to make cron job successful"""
        self.write('OK')


class TokenHandler(RequestHandler):
    def initialize(self, auth, database, bot, texts):
        self.auth = auth
        self.database = database
        self.bot = bot
        self.texts = texts

    def get(self):
        """receive and process callback data from Genius"""
        redirected_url = '{}://{}{}'.format(self.request.protocol,
                                            self.request.host,
                                            self.request.uri)
        token = self.auth.get_user_token(redirected_url)
        chat_id = self.get_argument('state')

        self.database.update_token(chat_id, token)

        # redirect user to bot
        self.redirect(f'https://t.me/{username}')

        language = self.database.get_language(chat_id)

        text = self.texts[language]['login']['successful']

        self.bot.send_message(chat_id, text)


class WebhookThread(threading.Thread):
    """start a web hook server
    This webhook is to respond to cron jobs that keep the bot from
    going to sleep in Heroku's free plan and receive tokens from Genius.
    """

    def __init__(self):
        super().__init__()
        app = tornado.web.Application([
            url(r"/notify", CronHandler),
            url(r"/callback.*", TokenHandler, dict(auth=auth,
                                                   database=database,
                                                   bot=Bot(BOT_TOKEN),
                                                   texts=texts)
                ),
        ])
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
def main_menu(update, context):
    """Genius main menu.
    Displays song lyrics, album lyrics, and customize output.

    """
    ud = context.user_data
    chat_id = update.effective_chat.id

    context.user_data['command'] = False
    language = ud['bot_lang']
    text = context.bot_data['texts'][language]['main_menu']

    logger.debug('ID: %s, INCLUDE: %s, LLANG: %s, BOTLANG: %s',
                 chat_id, ud['include_annotations'],
                 ud['lyrics_lang'],
                 language)

    buttons = [
        [
            IButton(
                text['album'],
                callback_data=str(TYPING_ALBUM)),
            IButton(
                text['artist'],
                callback_data=str(TYPING_ARTIST)),
            IButton(
                text['song'],
                callback_data=str(TYPING_SONG)),
        ],

        [
            IButton(
                text['customize_lyrics'],
                callback_data=str(CUSTOMIZE_MENU)),
            IButton(
                text['change_language'],
                callback_data=str(BOT_LANG))
        ],

    ]

    token = context.user_data.get('token')
    if token is None:
        token = context.bot_data['db'].get_token(chat_id)
        context.user_data['token'] = token

    if token is None:
        buttons.append([IButton(text['login'], callback_data=LOGIN)])
    else:
        buttons.append([IButton(text['logged_in'], callback_data=LOGGED_IN)])

    keyboard = IBKeyboard(buttons)

    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.edit_message_text(
            text=text['body'],
            reply_markup=keyboard)
    else:
        context.bot.send_message(
            chat_id=chat_id,
            text=text['body'],
            reply_markup=keyboard)

    return SELECT_ACTION


@log
@get_user
def stop(update, context):
    """End Conversation by command"""
    language = context.user_data['bot_lang']
    text = context.bot_data['texts'][language]['stop']

    update.message.reply_text(text)
    return END


@log
@get_user
def send_feedback(update, context):
    """send user feedback to developers"""
    language = context.user_data['bot_lang']
    reply_text = context.bot_data['texts'][language]['send_feedback']

    if update.effective_chat.username:
        text = (f'User: @{update.effective_chat.username}\n'
                f'Chat ID: {update.message.chat.id}')
    else:
        text = ('User: '
                f'<a href={update.effective_user.id}>'
                f'{update.effective_user.first_name}</a>\n'
                f'Chat ID: {update.message.chat.id}')
    text += update.message.text

    for developer in DEVELOPERS:
        context.bot.send_message(chat_id=developer, text=text)
    context.bot.send_message(
        chat_id=update.message.chat.id,
        text=reply_text)
    return END


@log
@get_user
def end_describing(update, context):
    """End conversation altogether or return to upper level"""
    language = context.user_data['bot_lang']
    text = context.bot_data['texts'][language]['end_describing']

    if update.message:
        update.message.reply_text(text)
        return END

    # noinspection PyUnreachableCode
    level = context.user_data.get('level', MAIN_MENU + 1)

    if level - 1 == MAIN_MENU or level == ACCOUNT_MENU:
        main_menu(update, context)
    elif level - 1 == CUSTOMIZE_MENU:
        customize.customize_menu(update, context)

    return SELECT_ACTION


@log
@get_user
def help_message(update, context):
    """send the /help text to the user"""
    language = context.user_data['bot_lang']
    text = context.bot_data['texts'][language]['help_message']

    update.message.reply_text(text)
    return END


@log
@get_user
def contact_us(update, context):
    """prompt the user to send a message"""
    language = context.user_data['bot_lang']
    text = context.bot_data['texts'][language]['contact_us']

    update.message.reply_text(text)
    return TYPING_FEEDBACK


def error(update, context):
    """handle errors and alert the developers"""
    trace = "".join(traceback.format_tb(sys.exc_info()[2]))
    # lets try to get as much information from the telegram update as possible
    payload = ""
    text = ''
    # normally, we always have an user. If not, its either a channel or a poll update.
    if update:
        if update.effective_user:
            user = mention_html(
                update.effective_user.id,
                update.effective_user.first_name
            )
            payload += f' with the user {user}'
        # there are more situations when you don't get a chat
        if update.effective_chat:
            payload += f' within the chat <i>{update.effective_chat.title}</i>'
            if update.effective_chat.username:
                payload += f' (@{update.effective_chat.username})'
            chat_id = update.effective_chat.id
            if context:
                language = context.user_data['language']
                texts = context.bot_data['texts']
            else:
                language = 'en'
            msg = texts[language]['error']
            context.bot.send_message(chat_id=chat_id,
                                     text=msg)
        # lets put this in a "well" formatted text
        text = (f"Hey.\nThe error <code>{context.error if context else ''}</code>"
                f" happened{payload}. The full traceback:\n\n<code>{trace}</code>")

    if text == '':
        text = 'Empty Error\n' + payload + trace

    # and send it to the dev(s)
    for dev_id in DEVELOPERS:
        context.bot.send_message(dev_id, text, parse_mode='HTML')
    # we raise the error again, so the logger module catches it.
    # If you don't use the logger module, use it.
    raise


def main():
    """Main function that holds the conversation handlers, and starts the bot"""

    updater = Updater(
        token=BOT_TOKEN,
        defaults=Defaults(parse_mode='html',
                          disable_web_page_preview=True,
                          run_async=True)
    )

    dp = updater.dispatcher
    dp.bot_data['texts'] = texts
    dp.bot_data['db'] = database
    my_states = [

        CallbackQueryHandler(
            main_menu,
            pattern='^' + str(MAIN_MENU) + '$'),

        CallbackQueryHandler(
            album.type_album,
            pattern='^' + str(TYPING_ALBUM) + '$'),

        CallbackQueryHandler(
            album.display_album,
            pattern=r'^album_[0-9]+$'),

        CallbackQueryHandler(
            album.display_album_covers,
            pattern=r'^album_[0-9]+_covers$'),

        CallbackQueryHandler(
            album.display_album_tracks,
            pattern=r'^album_[0-9]+_tracks$'),

        CallbackQueryHandler(
            album.display_album_formats,
            pattern=r'^album_[0-9]+_lyrics$'),

        CallbackQueryHandler(
            album.thread_get_album,
            pattern=r'^album_[0-9]+_lyrics_(pdf|tgf|zip)$'),

        CallbackQueryHandler(
            artist.type_artist,
            pattern=f'^{TYPING_ARTIST}$'),

        CallbackQueryHandler(
            artist.display_artist,
            pattern=r'^artist_[0-9]+$'),

        CallbackQueryHandler(
            artist.display_artist_albums,
            pattern=r'^artist_[0-9]+_albums$'),

        CallbackQueryHandler(
            artist.display_artist_songs,
            pattern=r'^artist_[0-9]+_songs_(ppt|rdt|ttl)_[0-9]+$'),

        CallbackQueryHandler(
            song.type_song,
            pattern=f'^{TYPING_SONG}$'),

        CallbackQueryHandler(
            song.display_song,
            pattern=r'^song_[0-9]+$'),

        CallbackQueryHandler(
            song.thread_display_lyrics,
            pattern=r'^song_[0-9]+_lyrics$'),

        CallbackQueryHandler(
            customize.customize_menu,
            pattern='^' + str(CUSTOMIZE_MENU) + '$'),

        CallbackQueryHandler(
            customize.lyrics_language,
            pattern='^' + str(LYRICS_LANG) + '$'),

        CallbackQueryHandler(
            customize.include_annotations,
            pattern='^' + str(INCLUDE) + '$'),

        CallbackQueryHandler(
            customize.bot_language,
            pattern='^' + str(BOT_LANG) + '$'),

        CallbackQueryHandler(
            multi.display_annotation,
            pattern=r'^annotation_[0-9]+$'),

        CallbackQueryHandler(
            multi.upvote_annotation,
            pattern=r'^annotation_[0-9]+_upvote$'),

        CallbackQueryHandler(
            multi.downvote_annotation,
            pattern=r'^annotation_[0-9]+_downvote$'),

        CallbackQueryHandler(
            account.login,
            pattern='^' + str(LOGIN) + '$'),

        CallbackQueryHandler(
            account.logged_in,
            pattern='^' + str(LOGGED_IN) + '$'),

        CallbackQueryHandler(
            account.logout,
            pattern='^' + str(LOGOUT) + '$'),


        CallbackQueryHandler(
            account.display_account,
            pattern=r'^account$'),
    ]

    user_input = {
        TYPING_ALBUM: [
            MessageHandler(
                Filters.text & (~Filters.command),
                album.search_albums),
            CallbackQueryHandler(
                album.type_album,
                pattern='^(?!' + str(END) + ').*$'),
        ],

        TYPING_ARTIST: [
            MessageHandler(
                Filters.text & (~Filters.command),
                artist.search_artists),
            CallbackQueryHandler(
                artist.type_artist,
                pattern='^(?!' + str(END) + ').*$')
        ],

        TYPING_SONG: [
            MessageHandler(
                Filters.text & (~Filters.command),
                song.search_songs),
            CallbackQueryHandler(
                song.type_song,
                pattern='^(?!' + str(END) + ').*$')
        ],

        TYPING_FEEDBACK: [MessageHandler(
            Filters.text & (~Filters.command),
            send_feedback)],

        INCLUDE: [CallbackQueryHandler(
            customize.include_annotations,
            pattern='^(?!' + str(END) + ').*$')],

        LYRICS_LANG: [CallbackQueryHandler(
            customize.lyrics_language,
            pattern='^(?!' + str(END) + ').*$')],

        BOT_LANG: [CallbackQueryHandler(
            customize.bot_language,
            pattern='^(?!' + str(END) + ').*$')],

    }

    # ----------------- MAIN MENU -----------------

    main_menu_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start',
                           main_menu,
                           Filters.regex(r'^\D*$')),
            *my_states,
        ],

        states={
            SELECT_ACTION: my_states,
            **user_input

        },

        fallbacks=[
            CallbackQueryHandler(
                end_describing,
                pattern='^' + str(END) + '$'),
            CommandHandler('cancel', end_describing),
            CommandHandler('stop', stop),
        ],
    )
    dp.add_handler(main_menu_conv_handler)

    # ----------------- COMMANDS -----------------

    commands = [
        CommandHandler('album', album.type_album),
        CommandHandler('artist', artist.type_artist),
        CommandHandler('song', song.type_song),
        CommandHandler('lyrics_language', customize.lyrics_language),
        CommandHandler('bot_language', customize.bot_language),
        CommandHandler('include_annotations', customize.include_annotations),
        CommandHandler('help', help_message),
        CommandHandler('contact_us', contact_us)
    ]

    commands_conv_handler = ConversationHandler(
        entry_points=commands,

        states={
            **user_input
        },

        fallbacks=[
            CallbackQueryHandler(
                end_describing,
                pattern='^' + str(END) + '$'),
            CommandHandler('cancel', end_describing),
            CommandHandler('stop', stop)
        ],
    )
    dp.add_handler(commands_conv_handler)

    # ----------------- INLINE QUERIES -----------------

    inline_query_handlers = [

        InlineQueryHandler(
            inline_query.search_albums,
            pattern=r'^\.album'
        ),

        InlineQueryHandler(
            inline_query.search_artists,
            pattern=r'^\.artist'
        ),

        InlineQueryHandler(
            inline_query.search_songs,
            pattern=r'^\.song'
        ),

        InlineQueryHandler(
            inline_query.inline_menu,
        ),


    ]

    for handler in inline_query_handlers:
        dp.add_handler(handler)

    # ----------------- ARGUMENTED START -----------------

    argumented_start_handlers = [

        CommandHandler(
            'start',
            album.display_album,
            Filters.regex(r'^/start albums_[0-9]+$'),
            pass_args=True
        ),

        CommandHandler(
            'start',
            album.display_album_covers,
            Filters.regex(r'^/start album_[0-9]+_covers$'),
            pass_args=True
        ),

        CommandHandler(
            'start',
            album.display_album_tracks,
            Filters.regex(r'^/start album_[0-9]+_tracks$'),
            pass_args=True
        ),

        CommandHandler(
            'start',
            album.display_album_formats,
            Filters.regex(r'^/start album_[0-9]+_lyrics$'),
            pass_args=True
        ),

        CommandHandler(
            'start',
            artist.display_artist,
            Filters.regex(r'^/start artist_[0-9]+$'),
            pass_args=True
        ),

        CommandHandler(
            'start',
            artist.display_artist_songs,
            Filters.regex(r'^/start artist_[0-9]+_songs_(ppt|rdt|ttl)_[0-9]+$'),
            pass_args=True
        ),

        CommandHandler(
            'start',
            artist.display_artist_albums,
            Filters.regex(r'^/start artist_[0-9]+_albums$'),
            pass_args=True
        ),

        CommandHandler(
            'start',
            song.display_song,
            Filters.regex(r'^/start song_[0-9]+$'),
            pass_args=True
        ),

        CommandHandler(
            'start',
            song.thread_display_lyrics,
            Filters.regex(r'^/start song_[0-9]+_lyrics$'),
            pass_args=True
        ),

        CommandHandler(
            'start',
            multi.display_annotation,
            Filters.regex(r'^/start annotation_[0-9]+$'),
            pass_args=True
        ),
    ]

    for handler in argumented_start_handlers:
        dp.add_handler(handler)

    # log all errors
    dp.add_error_handler(error)

    # web hook server to respond to GET cron jobs at /notify
    # and receive user tokens at /callback
    if SERVER_PORT:
        webhook_thread = WebhookThread()
        webhook_thread.start()
    # if SERVER_PORT:
    #
    #    updater.start_webhook('0.0.0.0', port=SERVER_PORT, url_path=BOT_TOKEN)
    #    updater.bot.setWebhook(SERVER_ADDRESS + BOT_TOKEN)
    # else:
    updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()
