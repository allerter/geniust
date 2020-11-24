"""
Main script of the bot which contains most of the functions.
"""
import os
import logging
import traceback
import sys
import threading

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
from telegram import Bot
from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram.utils.helpers import mention_html
from tornado.web import url, RequestHandler
from telegram.utils.webhookhandler import WebhookServer
import tornado.ioloop
import tornado.web

from functions import (
    album,
    artist,
    song,
    customize,
    inline_query
)
from constants import (
    BOT_TOKEN, DEVELOPERS,
    END, LYRICS_LANG, BOT_LANG, INCLUDE, MAIN_MENU, SELECT_ACTION,
    TYPING_ALBUM, TYPING_ARTIST, TYPING_SONG, TYPING_FEEDBACK,
    SERVER_PORT, SERVER_ADDRESS,
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logging.getLogger('telegram').setLevel(logging.INFO)
# logging.getLogger('telethon').setLevel(logging.ERROR)
# logger = logging.getLogger('geniust')


class PostHandler(RequestHandler):
    def get(self):
        """respond to GET request to make cron job successful"""
        self.write('OK')


class WebhookThread(threading.Thread):
    """start a web hook server
    This webhook is to respond to cron jobs that keep the bot from
    going to sleep in Heroku's free plan.
    """

    def __init__(self):
        super().__init__()
        app = tornado.web.Application([
            url(r"/notify", PostHandler),
        ])
        self.webhooks = WebhookServer("0.0.0.0", SERVER_PORT, app, None)

    def run(self):
        """start web hook server"""
        self.webhooks.serve_forever()

    def shutdown(self):
        """shut down web hook server"""
        self.webhooks.shutdown()


def main_menu(update, context):
    """Genius main menu.
    Displays song lyrics, album lyrics, and customize output.

    """
    print(context.args)
    print('here')
    context.user_data['command'] = False
    if update.message:
        chat_id = update.message.chat.id
        context.user_data['chat_id'] = chat_id
    else:
        chat_id = update.callback_query.message.chat.id
        context.user_data['chat_id'] = chat_id

    text = 'What would you like to do?'

    buttons = [
        [
            IButton(
                'Album',
                callback_data=str(TYPING_ALBUM)),
            IButton(
                'Artist',
                callback_data=str(TYPING_ARTIST)),
            IButton(
                'Song',
                callback_data=str(TYPING_SONG)),

        ],

        [
            IButton(
                'Customize Lyrics',
                callback_data=str(LYRICS_LANG)),
            IButton(
                'Change Language',
                callback_data=str(BOT_LANG))
        ],

    ]
    keyboard = IBKeyboard(buttons)

    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.edit_message_text(
            text=text,
            reply_markup=keyboard)
    else:
        context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard)

    return SELECT_ACTION


def stop(update, context):
    """End Conversation by command"""
    update.message.reply_text('Stopped.')
    return END


def send_feedback(update, context):
    """send user feedback to developers"""
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
        context.bot.send_message(
            chat_id=developer,
            text=text,
            parse_mode='HTML')
    context.bot.send_message(
        chat_id=update.message.chat.id,
        text='Thanks for the feedback!')
    return END


def end_describing(update, context):
    """End conversation altogether or return to upper level"""
    if update.message:
        update.message.reply_text('canceled.')
        return END

    assert False, "Shouldn't be here"
    level = context.user_data.get('level', MAIN_MENU + 1)

    if level - 1 == MAIN_MENU:
        main_menu(update, context)
    # customize genius menu
    elif level - 1 == 1:
        customize.customize_menu(update, context)
    return SELECT_ACTION


def help_message(update, context):
    """send the /help text to the user"""
    with open(os.path.join('text', 'help.txt'), 'r') as f:
        text = f.read()
    update.message.reply_html(text)
    return END


def contact_us(update, context):
    """prompt the user to send a message"""
    update.message.reply_text("Send us what's on your mind :)")
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
            msg = f'An error occurred: {context.error}\nStart again by clicking /start'
            context.bot.send_message(chat_id=chat_id,
                                     text=msg)
        # lets put this in a "well" formatted text
        text = (f"Hey.\n The error <code>{context.error}</code> happened{payload}."
                f"The full traceback:\n\n<code>{trace}</code>")

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
        bot=Bot(BOT_TOKEN,
                defaults=Defaults(parse_mode='html',
                                  disable_web_page_preview=True)),
    )

    dp = updater.dispatcher
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
            pattern=r'^album_[0-9]+_aio$'),

        CallbackQueryHandler(
            album.thread_get_album,
            pattern=r'^album_[0-9]+_aio_(pdf|tgf|zip)$'),

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
            pattern=r'^artist_[0-9]+_songs_(ppl|rdt|ttl)$'),

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
            customize.lyrics_language,
            pattern='^' + str(LYRICS_LANG) + '$'),

        CallbackQueryHandler(
            customize.include_annotations,
            pattern='^' + str(INCLUDE) + '$'),

        CallbackQueryHandler(
            customize.bot_language,
            pattern='^' + str(BOT_LANG) + '$'),
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
            pattern=r'^\.album\s.{1,}'
        ),

        InlineQueryHandler(
            inline_query.search_artists,
            pattern=r'^\.artist\s.{1,}'
        ),

        InlineQueryHandler(
            inline_query.search_songs,
            pattern=r'^\.song\s.{1,}'
        ),

        InlineQueryHandler(
            inline_query.menu,
        ),


    ]

    for handler in inline_query_handlers:
        dp.add_handler(handler)

    # ----------------- ARGUMENTED START -----------------

    argumented_start_handlers = [

        CommandHandler(
            'start',
            album.display_album,
            Filters.regex(r'^/start album_[0-9]+$'),
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
            Filters.regex(r'^/start album_[0-9]+_aio$'),
            pass_args=True
        ),

        CommandHandler(
            'start',
            artist.display_artist_songs,
            Filters.regex(r'^/start artist_[0-9]+_songs_(ppl|rdt|ttl)$'),
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
    ]

    for handler in argumented_start_handlers:
        dp.add_handler(handler)


    # log all errors
    dp.add_error_handler(error)

    # web hook server to respond to GET cron jobs at /notify
    # if SERVER_PORT:
    #     webhook_thread = WebhookThread()
    #     webhook_thread.start()
    if SERVER_PORT:
        updater.start_webhook('0.0.0.0', port=SERVER_PORT, url_path=BOT_TOKEN)
        updater.bot.setWebhook(SERVER_ADDRESS + BOT_TOKEN)
    else:
        updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()
