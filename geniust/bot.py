#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This program is dedicated to the public domain under the MIT license.

"""
Main script of the bot which contains most of the functions.
"""

from telegram import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InlineQueryResultArticle,
    InputTextMessageContent
)
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackQueryHandler,
    InlineQueryHandler
)
from telegram.constants import MAX_MESSAGE_LENGTH
from telegram.utils.helpers import mention_html, create_deep_linked_url
from telegram.ext.dispatcher import run_async
from telegram.error import BadRequest, TimedOut, NetworkError
from tornado.web import url, RequestHandler
from telegram.utils.webhookhandler import WebhookServer
from bs4 import BeautifulSoup
import psycopg2
import tornado.ioloop
import tornado.web
import requests

import string_funcs
import api
from zip_album import create_zip
from pdf import create_pdf
from lyrics_to_telegraph import create_pages
from constants import (
    DEVELOPERS,
    BOT_TOKEN,
    GENIUS_TOKEN,
    DATABASE_URL,
    SERVER_PORT,
    SERVER_ADDRESS
)

from urllib.parse import urlparse
from uuid import uuid4
import logging
import traceback
import sys
import re
import threading


# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.DEBUG)
logging.getLogger('telethon').setLevel(logging.CRITICAL)
logger = logging.getLogger(__name__)

# Shortcut for ConversationHandler.END
END = ConversationHandler.END

# State definitions for conversation
(SELECT_ACTION, GENIUS, TELEGRAPH, CHECK_GENIUS_ALBUM, CUSTOMIZE_GENIUS, TYPING,
 OPTION1, OPTION2, OPTION3, OPTION4, IDENTIFIER, AUTHOR_NAME, AUTHOR_URL, ANNOTATIONS,
 LYRICS_LANG, START_OVER, INCLUDE, TYPING_ALBUM, STATISTICS, CURRENT_LEVEL,
 CREATE_ACCOUNT, CREATE_PAGES, CUSTOMIZE_TELEGRAPH, LOGIN, DESCRIPTION, SELF,
 CHECK_GENIUS_SONG, TYPING_SONG, TYPING_ACCOUNT, DOWNLOAD_ALBUM) = range(30)


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


def database(chat_id=None, action='select', data=None, update=None, table='data'):
    """all the database requests go through here"""
    res = ''
    if action == 'create':
        if table == 'data' or chat_id:
            data = [data['chat_id'], data['include_annotations'], data['lyrics_lang']]
            data = f"""({data[0]}, {data[1]}, '{data[2]}')"""
        query = f"""INSERT INTO {table} VALUES {data};"""
    elif action == 'update':
        query = f"UPDATE data SET {update} = %s WHERE chat_id = {chat_id}"
    elif action == 'select':
        if table == 'data' or chat_id:
            query = f"""SELECT * FROM data WHERE chat_id = {chat_id};"""

    # connect to database
    with psycopg2.connect(DATABASE_URL, sslmode='require') as con:
        with con.cursor() as cursor:
            if action == 'update':
                cursor.execute(query, (data, ))
            else:
                cursor.execute(query)
            if action == 'select':
                res = cursor.fetchall()
    if res and table == 'data':
        res = res[0]
        res = {'chat_id': res[0], 'include_annotations': res[1], 'lyrics_lang': res[2]}
    return res


def create_user(user_data):
    """Check for user in database, and create one if there's none"""
    chat_id = user_data['chat_id']

    res = database(chat_id=chat_id, action='select')
    if res:
        user_data.update(res)
    else:
        # create user data with default preferences
        data = {}
        data['lyrics_lang'] = 'English + Non-English'
        data['include_annotations'] = False
        user_data.update(data)
        database(chat_id=chat_id, action='create', data=user_data)


@run_async
def genius(update, context):
    """Genius main menu to get song lyrics, album lyrics, and customize output"""
    context.user_data[CURRENT_LEVEL] = SELF
    context.user_data['command'] = False
    if update.message:
        chat_id = update.message.chat.id
        context.user_data['chat_id'] = chat_id
    else:
        chat_id = context.user_data['chat_id'] = update.callback_query.message.chat.id
    # check if user data is present
    if not context.user_data.get('lyrics_lang'):
        create_user(context.user_data)
    text = 'What would you like to do?'
    buttons = [[
        InlineKeyboardButton(text='Song Lyrics',
                             callback_data=str(CHECK_GENIUS_SONG)),
        InlineKeyboardButton(text='Album Lyrics',
                             callback_data=str(CHECK_GENIUS_ALBUM))
    ],
        [
        InlineKeyboardButton(text='Customize Lyrics',
                             callback_data=str(CUSTOMIZE_GENIUS))
    ],
        [
        InlineKeyboardButton(text='Done',
                             callback_data=str(END))
    ]]
    keyboard = InlineKeyboardMarkup(buttons)
    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)
    else:
        context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)
    return SELECT_ACTION


@run_async
def stop(update, context):
    """End Conversation by command"""
    update.message.reply_text('Stopped.')
    return END


@run_async
def inline_query(update, context):
    """Handle inline queries and /start that has arguments."""
    context.user_data[CURRENT_LEVEL] = GENIUS
    genius_api = api.Genius(GENIUS_TOKEN)
    if update.inline_query:
        text = update.inline_query.query
        text = text.split('@')
        if text[0] == '':
            text = 'HOW TO SEARCH'
            description = 'Short tutorial on searching songs and albums'
            answer_text = ('Normally inline mode will look for songs.'
                'But if you want to search album lyrics,'
                'just add a "@" at the end of your search. For example:\n'
                'Searching songs:\n<code>@genius_the_bot some title</code>\n'
                'Searching albums:\n<code>@genius_the_bot some title @</code>')
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(
                text='Search...', switch_inline_query_current_chat='')]]
            )
            answer = InlineQueryResultArticle(
                id=uuid4(),
                title=text,
                description=description,
                input_message_content=InputTextMessageContent(answer_text,
                                                              parse_mode='HTML'),
                reply_markup=keyboard
            )
            update.inline_query.answer([answer])
            return END
        if len(text) == 1:
            # length of one means no '@' in query, so the bot will search songs
            json_search = genius_api._make_api_request((text, 'search'))
            n_hits = min(5, len(json_search['hits']))
            hits = []
            for i in range(n_hits):
                search_hit = json_search['hits'][i]['result']
                found_song = search_hit['title']
                found_artist = search_hit['primary_artist']['name']
                text = string_funcs.format_title(found_artist, found_song)
                song_id = search_hit['id']
                song_url = search_hit['url']
                description = 'Translation' if 'Genius' in found_artist else ''
                answer_text = f'<a href="{song_url}">Song page on Genius</a>'
                button_url = create_deep_linked_url(
                    context.bot.get_me().username,
                    str(song_id)
                )
                keyboard = InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text='Get lyrics',
                                           url=button_url)],
                    [InlineKeyboardButton(text='Search...',
                                          switch_inline_query_current_chat='')]]
                )
                answer = InlineQueryResultArticle(
                    id=uuid4(),
                    title=text,
                    thumb_url=search_hit['song_art_image_thumbnail_url'],
                    input_message_content=InputTextMessageContent(
                        answer_text,
                        parse_mode='HTML'),
                    reply_markup=keyboard,
                    description=description
                )
                # It's possible to provide results that are captioned photos
                # of the song cover art, but that requires using InlineQueryResultPhoto
                # and user might not be able to choose the right song this way,
                # since all they get is only the cover arts of the hits.
                # answer = InlineQueryResultPhoto(id=uuid4(),
                #    photo_url=search_hit['song_art_image_url'],
                #    thumb_url=search_hit['song_art_image_thumbnail_url'],
                #    reply_markup=keyboard, description=description)
                hits.append(answer)
        else:
            json_search = genius_api.search_genius_web(text)
            hits = []
            for i, hit in enumerate(json_search['sections'][4]['hits']):
                album = hit['result']
                album_url = album['url']
                album_id = album['id']
                artist_id = album['artist']['id']
                # can't use string_funcs.format_title here
                # because of the album name in response
                if 'Genius' in album['name_with_artist']:
                    text = album['name']
                    description = 'Translation'
                else:
                    text = album['full_title'].split(' by ')
                    text = f'{text[1]} - {text[0]}'
                    description = ''
                answer_text = f'<a href="{album_url}">Album page on Genius</a>'
                button_url_1 = create_deep_linked_url(
                    context.bot.get_me().username,
                    str(f'{artist_id}_{album_id}_{OPTION1}'))
                button_url_2 = create_deep_linked_url(
                    context.bot.get_me().username,
                    str(f'{artist_id}_{album_id}_{OPTION2}'))
                button_url_3 = create_deep_linked_url(
                    context.bot.get_me().username,
                    str(f'{artist_id}_{album_id}_{OPTION3}'))
                keyboard = InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text='PDF', url=button_url_1)],
                    [InlineKeyboardButton(text='ZIP', url=button_url_2)],
                    [InlineKeyboardButton(text='TELEGRA.PH', url=button_url_3)],
                    [InlineKeyboardButton(text='Search...',
                                          switch_inline_query_current_chat='')]]
                )
                answer = InlineQueryResultArticle(
                    id=uuid4(),
                    title=text,
                    thumb_url=album['cover_art_thumbnail_url'],
                    input_message_content=InputTextMessageContent(
                        answer_text,
                        parse_mode='HTML'),
                    reply_markup=keyboard, description=description
                )

                hits.append(answer)
        if len(hits) == 0:
            button_url = create_deep_linked_url(context.bot.get_me().username)
            keyboard = keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton(text='Start a chat', url=button_url)]]
            )
            answer_text = f'Search in a chat with the bot:'
            hits = [InlineQueryResultArticle(
                id=uuid4(), title='Nothing Found...',
                input_message_content=InputTextMessageContent(answer_text),
                reply_markup=keyboard)
            ]
        update.inline_query.answer(hits)
    # this part is for when users who have used inline queries,
    # click /start to get song or album lyrics
    elif context.args:
        data = context.args[0].split('_')
        context.user_data['chat_id'] = update.message.chat.id
        if not context.user_data.get('lyrics_lang'):
            create_user(context.user_data)
        # song data: {song_id}
        # album data: {artist_id}_{album_id}_{OPTION}
        if len(data) == 1:
            p = threading.Thread(target=print_lyrics,
                                 args=(context.bot,
                                       context.user_data,
                                       int(data[0]),
                                       genius_api,))
            p.start()
            p.join()
        else:
            artist_id, album_id, album_format = [int(x) for x in data]
            found = False
            page = 1
            while not found:
                res = genius_api._make_public_request(
                    f'artists/{artist_id}/albums',
                    page
                )
                for album in res['albums']:
                    if int(album['id']) == album_id:
                        album_url = album['url']
                        found = True
                        break
                else:
                    page += 1
            p = threading.Thread(
                target=get_album,
                args=(GENIUS_TOKEN, album_url,
                      update.message, context.user_data,
                      album_format, context.bot,))
            p.start()
            p.join()
    return END


@run_async
def check_album_link(update, context):
    """Checks album link or return search results, or prompt user for format"""
    context.user_data[CURRENT_LEVEL] = GENIUS
    genius_api = api.Genius(GENIUS_TOKEN)
    # the case where user enters the function by message which is either
    # the /album_lyrics command, sending song link, or a title to search.
    if update.message:
        text = update.message.text
        chat_id = update.message.chat.id
        # if user enters by command
        if text == '/album_lyrics':
            if not context.user_data.get('lyrics_lang'):
                chat_id = update.message.chat.id
                res = database(chat_id=chat_id, action='select')
                context.user_data.update(res)
            update.message.reply_text('Send me an album link or album name to search.')
            return TYPING_ALBUM
        parsed_url = urlparse(text)
        # if the message is a link
        if parsed_url[0] and parsed_url[1]:
            page = requests.get(text)
            html = BeautifulSoup(page.text, "html.parser")
            image_link = str(html.find_all("meta"))
            # check album validy by finding album_id from meta tag
            m = re.search(r'{"name":"album_id","values":\["([0-9]+)', image_link)
            if not m:
                update.message.reply_text('Invalid link.\nSend a new link.')
                return TYPING_SONG
        # the message is a name (not a valid link)
        else:
            json_search = genius_api.search_genius_web(text)
            hits = []
            for i, hit in enumerate(json_search['sections'][4]['hits']):
                album = hit['result']
                album_id = album['id']
                artist_id = album['artist']['id']
                if 'Genius' in album['name_with_artist']:
                    text = album['name']
                else:
                    text = album['full_title'].split(' by ')
                    text = f'{text[1]} - {text[0]}'
                hits.append([InlineKeyboardButton(
                    text=text,
                    callback_data=str(f'{artist_id}_{album_id}'))]
                )
            hits.append([InlineKeyboardButton(text='None', callback_data=str(END))])
            keyboard = InlineKeyboardMarkup(hits)
            update.message.reply_text(text='Choose an album', reply_markup=keyboard)
            return CHECK_GENIUS_ALBUM
    # user has chosen one of the hits or selected Album Lyrics from the main menu
    elif update.callback_query:
        data = update.callback_query.data.split('_')
        # user entering Album Lyrics
        if len(data) == 1:
            update.callback_query.answer()
            msg = 'Send me an album link or album name to search.'
            update.callback_query.edit_message_text(text=msg)
            return TYPING_ALBUM
        # user has selected a hit
        else:
            artist_id, album_id = [int(x) for x in data]
            found = False
            page = 1
            while not found:
                res = genius_api._make_public_request(
                    f'artists/{artist_id}/albums',
                    page
                )
                for album in res['albums']:
                    if int(album['id']) == album_id:
                        text = album['url']
                        found = True
                        break
                else:
                    page += 1

            chat_id = update.callback_query.message.chat.id
            context.bot.delete_message(
                chat_id=chat_id,
                message_id=update.callback_query.message.message_id
            )

    buttons = [[
        InlineKeyboardButton(text='PDF', callback_data=str(OPTION1)),
    ],
        [
        InlineKeyboardButton(text='ZIP', callback_data=str(OPTION2))
    ],
        [
        InlineKeyboardButton(text='TELEGRA.PH', callback_data=str(OPTION3))
    ]]
    keyboard = InlineKeyboardMarkup(buttons)
    context.bot.send_message(
        text='Choose a format',
        chat_id=chat_id,
        reply_markup=keyboard
    )
    context.user_data['album_url'] = text
    return DOWNLOAD_ALBUM


@run_async
def get_album_format(update, context):
    """Create a thread to download the album"""
    message = update.callback_query.message
    album_format = int(update.callback_query.data)
    p = threading.Thread(
        target=get_album,
        args=(GENIUS_TOKEN, context.user_data['album_url'],
              message, context.user_data, album_format, context.bot,))
    p.start()
    p.join()
    return END


def get_album(GENIUS_TOKEN, link, message, user_data, album_format, bot):
    """Download and send the album to the user in the selected format"""
    chat_id = message.chat.id
    genius_api = api.Genius(GENIUS_TOKEN)
    text = 'Downloading album...'

    # try clause for the callback query users and
    # the except clause for inline query users
    try:
        progress = bot.edit_message_text(chat_id=chat_id, text=text,
                                         message_id=message.message_id)
    except BadRequest:
        progress = bot.send_message(chat_id=chat_id, text=text,
                                    message_id=message.message_id,)

    # get album
    album = api.async_album_search(api=genius_api, link=link,
                                   include_annotations=user_data['include_annotations'])
    # result should be a dict if the operation was successful
    if not isinstance(album, dict):
        text = "Couldn't get the album."
        bot.send_message(chat_id=chat_id, text=text)
        logger.critical(f"Couldn't get album: {album}")
        return END

    # convert
    text = 'Converting to specified format...'
    bot.edit_message_text(chat_id=progress.chat.id,
                          message_id=progress.message_id, text=text)
    if album_format == OPTION1:  # PDF
        file = create_pdf(album, user_data)
    elif album_format == OPTION2:  # ZIP
        file = create_zip(album, user_data)
    elif album_format == OPTION3:  # TELEGRA.PH
        link = create_pages(user_data=user_data, data=album)
        bot.send_message(chat_id=chat_id, text=link)

    # send the file
    if album_format == OPTION1 or album_format == OPTION2:
        i = 1
        while True:
            if i != 0 and i < 6:
                try:
                    bot.send_document(chat_id=chat_id, document=file,
                                      caption=file.name[:-4], timeout=20,)
                except (TimedOut, NetworkError):
                    i += 1
                else:
                    i = 0
            if i == 0:
                break
    text = "Here's the album:"
    bot.edit_message_text(chat_id=progress.chat.id,
                          message_id=progress.message_id, text=text)


def print_lyrics(bot, user_data, song_id, genius_api, message_id=None):
    """retrieve and send song lyrics to user"""
    if user_data.get('lyrics_lang'):
        lyrics_language = user_data['lyrics_lang']
        include_annotations = user_data['include_annotations']
    else:
        # default settings for new users (probably unnecessary)
        lyrics_language = 'English + Non-English'
        include_annotations = False
    if message_id:
        bot.edit_message_text(chat_id=user_data['chat_id'],
                              message_id=message_id, text='getting lyrics...')
    else:
        message_id = bot.send_message(
            chat_id=user_data['chat_id'],
            text='getting lyrics...')['message_id']
    json_song = api._API._make_api_request(genius_api, (song_id, 'song'))
    lyrics = api._API._scrape_song_lyrics_from_url(
        genius_api,
        json_song['song']['url'],
        song_id,
        include_annotations=include_annotations,
        telegram_song=True,
        lyrics_language=lyrics_language)[0]

    # formatting lyrics language
    lyrics = string_funcs.format_language(lyrics, lyrics_language)
    for res in re.findall(r'<a[^>]*>(.*[\n]*.*?)</a>', lyrics):
        lyrics = lyrics.replace(res, string_funcs.format_language(res, lyrics_language))
    lyrics = lyrics.replace('!--!', '').replace('!__!', '')
    exp = (r'<(?:\/(?!(?:a|b|br|strong|em|i)>)[^>]*|'
           r'(?!\/)(?!(?:a\s+[^\s>]+|b|br|strong|em|i)>)[^>]*)>')
    lyrics = re.sub(exp, '', lyrics)
    # edit the message for callback query users
    if message_id:
        bot.edit_message_text(chat_id=user_data['chat_id'],
                              message_id=message_id,
                              text="Here's the lyrics:")

    len_lyrics = len(lyrics)
    sent = 0
    i = 0
    # missing_a = False
    # link = ''
    # get_link = re.compile(r'<a[^>]+href=\"(.*?)\"[^>]*>')
    # this sends the lyrics in messages if it exceeds message length limit
    # it's possible that the final <a> won't be closed because of slicing the message so
    # that's dealt with too
    max_length = MAX_MESSAGE_LENGTH
    while sent < len_lyrics:
        text = lyrics[i * max_length: (i * max_length) + max_length]
        a_start = text.count('<a')
        a_end = text.count('</a>')
        if a_start != a_end:
            a_pos = text.rfind('<a')
            text = text[:a_pos]
        bot.send_message(
            chat_id=user_data['chat_id'],
            text=text,
            parse_mode='HTML',
            disable_web_page_preview=True)
        sent += len(text)
        i += 1


@run_async
def check_song(update, context):
    """Handle incoming song request"""
    context.user_data[CURRENT_LEVEL] = GENIUS
    genius_api = api.Genius(GENIUS_TOKEN)

    # user has entered the function through main menu or has selected a hit
    if update.callback_query:
        if int(update.callback_query.data) == CHECK_GENIUS_SONG:
            update.callback_query.answer()
            msg = 'Send me either a Genius song link, or a title to search'
            update.callback_query.edit_message_text(msg)
            return TYPING_SONG
        else:
            song_id = int(update.callback_query.data)
            # get song
            p = threading.Thread(
                target=print_lyrics,
                args=(context.bot, context.user_data, song_id, genius_api,
                      update.callback_query.message.message_id,))
            # p.daemon = True
            p.start()
            p.join()
    # user has sent either a song link, a title to search or /song_lyrics
    elif update.message:
        context.user_data['chat_id'] = chat_id = update.message.chat.id
        text = update.message.text

        # user has entered the function using command
        if text == '/song_lyrics':
            if not context.user_data.get('lyrics_lang'):
                res = database(chat_id=chat_id, action='select')
                context.user_data.update(res)
            msg = 'Send me either a Genius song link, or a title to search'
            update.message.reply_text(msg)
            return TYPING_SONG
        parsed_url = urlparse(text)
        # check if the message is a URL
        if parsed_url[0] and parsed_url[1]:
            page = requests.get(text)
            html = BeautifulSoup(page.text, "html.parser")
            image_link = str(html.find_all("meta"))
            # check page validity by finding song_id from the meta tag
            m = re.search(r'{"name":"song_id","values":\["([0-9]+)', image_link)
            if m:
                song_id = m.group(1)
            else:
                update.message.reply_text('Invalid link.\nSend a new link')
                return TYPING_SONG
            # get song
            p = threading.Thread(
                target=print_lyrics,
                args=(context.bot, context.user_data, song_id, genius_api,))
            # p.daemon = True
            p.start()
            p.join()
        # user has sent a title (which is an invalid link)
        else:
            # get <= 10 hits for user input from Genius API search
            json_search = genius_api._make_api_request((text, 'search'))
            n_hits = min(10, len(json_search['hits']))
            buttons = []
            for i in range(n_hits):
                search_hit = json_search['hits'][i]['result']
                found_song = search_hit['title']
                found_artist = search_hit['primary_artist']['name']
                text = string_funcs.format_title(found_artist, found_song)
                buttons.append([InlineKeyboardButton(
                    text=text,
                    callback_data=str(search_hit['id']))]
                )

            buttons.append([InlineKeyboardButton(text='None', callback_data=str(END))])
            keyboard = InlineKeyboardMarkup(buttons)
            update.message.reply_text(text='Choose a song', reply_markup=keyboard)
            return CHECK_GENIUS_SONG
    return END


@run_async
def customize_genius(update, context):
    """main menu for lyrics customizations"""
    context.user_data[CURRENT_LEVEL] = GENIUS
    chat_id = update.callback_query.message.chat.id
    buttons = [
        [InlineKeyboardButton(text='Lyrics Language', callback_data=str(LYRICS_LANG))],
        [InlineKeyboardButton(text='Annotations', callback_data=str(INCLUDE))],
        [InlineKeyboardButton(text='Back', callback_data=str(END))],
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    include = context.user_data['include_annotations']
    lyrics_lang = context.user_data['lyrics_lang']
    text = ('What would you like to customize?'
            '\nYour customizations will be used for all lyrics requests'
            ' (songs, albums, and inline searches).'
            '\nCurrent settings:'
            f'\nLyrics Language: <b>{lyrics_lang}</b>'
            f'\nInclude Annotations: <b>{"Yes" if include else "No"}</b>'
            )

    try:
        update.callback_query.answer()
        update.callback_query.edit_message_text(
            text=text,
            reply_markup=keyboard,
            parse_mode='HTML')
    except (AttributeError, BadRequest):
        context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode='HTML')
    return SELECT_ACTION


@run_async
def set_lyrics_language(update, context):
    """Set lyrics language from one of three options."""
    ud = context.user_data
    buttons = [
        [InlineKeyboardButton(
            text='Only English (ASCII)',
            callback_data=str(OPTION1))],
        [InlineKeyboardButton(
            text='Only non-English (non-ASCII)',
            callback_data=str(OPTION2))],
        [InlineKeyboardButton(
            text='English + non-English',
            callback_data=str(OPTION3))],
        [InlineKeyboardButton(
            text='Back',
            callback_data=str(END))]
    ]
    keyboard = InlineKeyboardMarkup(buttons)
    text = ('What characters would you like to be in the lyrics?'
            '\nNote that by English I mean ASCII characters. This option is'
            'useful for languages with non-ASCII alphabet (like Persian and Arabic).')
    # command
    if update.message:
        ud['chat_id'] = chat_id = update.message.chat.id
        ud['command'] = True
        if not ud.get('lyrics_lang'):
            create_user(ud)
        update.message.reply_text(text, reply_markup=keyboard)
        return LYRICS_LANG
    # callback query
    else:
        ud[CURRENT_LEVEL] = CUSTOMIZE_GENIUS
        chat_id = update.callback_query.message.chat.id

    data = int(update.callback_query.data)
    if data >= OPTION1 and data <= OPTION3:
        ud = context.user_data
        if data == OPTION1:
            ud['lyrics_lang'] = 'English'
        elif data == OPTION2:
            ud['lyrics_lang'] = 'Non-English'
        else:
            ud['lyrics_lang'] = 'English + Non-English'
        database(
            chat_id=chat_id,
            action='update',
            data=ud['lyrics_lang'],
            update='lyrics_lang'
        )
        text = f'Updated your preferences.\n{text}'
        if ud.get('command'):
            if ud['command']:
                text = ('Updated your preferences.\n\nCurrent language:'
                        f'<b>{context.user_data["lyrics_lang"]}</b>')
                update.callback_query.answer()
                update.callback_query.edit_message_text(text=text, parse_mode='HTML')
                return END

    text = f'{text}\n\nCurrent language: <b>{context.user_data["lyrics_lang"]}</b>'

    try:
        update.callback_query.answer()
        update.callback_query.edit_message_text(
            text=text,
            reply_markup=keyboard,
            parse_mode='HTML')
    except BadRequest:
        pass
    return LYRICS_LANG


@run_async
def choose_include_annotations(update, context):
    """Set whether to include annotations or not"""
    ud = context.user_data

    buttons = [
        [InlineKeyboardButton(text='Yes', callback_data=str(OPTION1))],
        [InlineKeyboardButton(text='No', callback_data=str(OPTION2))],
        [InlineKeyboardButton(text='Back', callback_data=str(END))]
    ]
    keyboard = InlineKeyboardMarkup(buttons)
    text = 'Would you like to include the annotations in the lyrics?'

    # command
    if update.message:
        ud['chat_id'] = chat_id = update.message.chat.id
        ud['command'] = True
        if not ud.get('lyrics_lang'):
            create_user(ud)
        update.message.reply_text(text=text, reply_markup=keyboard)
        return ANNOTATIONS
    # callback query
    else:
        ud[CURRENT_LEVEL] = CUSTOMIZE_GENIUS
        chat_id = update.callback_query.message.chat.id
    # set choice
    data = int(update.callback_query.data)
    if data == OPTION1 or data == OPTION2:
        ud['include_annotations'] = True if data == OPTION1 else False
        database(
            chat_id=chat_id,
            action='update',
            data=ud['include_annotations'],
            update='include_annotations'
        )
        text = f'Updated your preferences.\n{text}'
        if ud.get('command'):
            if ud['command']:
                include = ud['include_annotations']
                text = f'{text}\n\nCurrent setting: <b>{"Yes" if include else "No"}</b>'
                update.callback_query.answer()
                update.callback_query.edit_message_text(text=text, parse_mode='HTML')
                return END
    include = ud['include_annotations']
    text = f'{text}\n\nCurrent setting: <b>{"Yes" if include else "No"}</b>'

    try:
        update.callback_query.answer()
        update.callback_query.edit_message_text(
            text=text,
            reply_markup=keyboard,
            parse_mode='HTML')
    except BadRequest:
        pass
    return ANNOTATIONS


@run_async
def save_input(update, context):
    """send user feedback to developers"""
    if update.effective_chat.username:
        text = f'User: @{update.effective_chat.username}\n'
    else:
        text = ('User: '
                f'<a href={update.effective_user.id}>'
                f'{update.effective_user.first_name}</a>\n')
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


@run_async
def end_describing(update, context):
    """End conversation altogether or return to upper level"""
    ud = context.user_data
    qd = update.callback_query
    if ud.get(CURRENT_LEVEL) and not update.message:
        level = ud[CURRENT_LEVEL]
    else:
        if qd:
            context.bot.edit_message_text(text='Canceled.')
        else:
            update.message.reply_text('Canceled.')
        return END

    # if the user entered the conversation using any command except /start
    if ud.get('command'):
        if ud['command']:
            return END
    # main menu
    if level == SELF:
        # if the 'Done' button was clicked, delete the main menu, otherwise
        # return to main menu
        keyboards = update.callback_query.message['reply_markup']['inline_keyboard']
        keyboards = [y['text'] for x in keyboards for y in x]
        if keyboards[-1] == 'Done':
            context.bot.delete_message(
                chat_id=qd.message.chat.id,
                message_id=qd.message.message_id)
            return END
        genius(update, context)
    # genius main menu
    elif level == GENIUS:
        genius(update, context)
    # customize genius menu
    elif level == CUSTOMIZE_GENIUS:
        customize_genius(update, context)
    return SELECT_ACTION


@run_async
def help_message(update, context):
    """send the /help text to the user"""
    with open('help.txt', 'r') as f:
        text = f.read()
    update.message.reply_html(text)
    return END


@run_async
def contact_us(update, context):
    """prompt the user to send a message"""
    print(update.message.chat.id)
    update.message.reply_text("Send us what's on your mind :)")
    return TYPING


@run_async
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
        # lets put this in a "well" formatted text
        text = (f"Hey.\n The error <code>{context.error}</code> happened{payload}."
                f"The full traceback:\n\n<code>{trace}</code>")
        chat_id = update.effective_chat.chat.id
        msg = f'An error occurred: {context.error}\nStart again by clicking /start'
        context.bot.send_message(chat_id=chat_id,
                                 text=msg)
    # and send it to the dev(s)
    if text == '':
        text = 'Empty Error\n' + payload + trace
    for dev_id in DEVELOPERS:
        context.bot.send_message(dev_id, text, parse_mode='HTML')
    # we raise the error again, so the logger module catches it.
    # If you don't use the logger module, use it.
    raise


def main():
    """Main function that holds the conversation handlers, and starts the bot"""
    updater = Updater(BOT_TOKEN, workers=100, use_context=True)
    dp = updater.dispatcher
    my_states = [
        CallbackQueryHandler(
            genius,
            pattern='^' + str(GENIUS) + '$'),
        CallbackQueryHandler(
            check_album_link,
            pattern='^' + str(CHECK_GENIUS_ALBUM) + '$'),

        CallbackQueryHandler(
            check_song,
            pattern='^' + str(CHECK_GENIUS_SONG) + '$'),

        CallbackQueryHandler(
            customize_genius,
            pattern='^' + str(CUSTOMIZE_GENIUS) + '$'),

        CallbackQueryHandler(
            set_lyrics_language,
            pattern='^' + str(LYRICS_LANG) + '$'),

        CallbackQueryHandler(
            choose_include_annotations,
            pattern='^' + str(INCLUDE) + '$'),
    ]
    user_input = {
        TYPING_ALBUM: [MessageHandler(
            Filters.text & (~Filters.command),
            check_album_link)],

        TYPING_SONG: [MessageHandler(
            Filters.text & (~Filters.command),
            check_song)],

        TYPING: [MessageHandler(
            Filters.text & (~Filters.command),
            save_input)],

        ANNOTATIONS: [CallbackQueryHandler(
            choose_include_annotations,
            pattern='^(?!' + str(END) + ').*$')],

        LYRICS_LANG: [CallbackQueryHandler(
            set_lyrics_language,
            pattern='^(?!' + str(END) + ').*$')],

        CHECK_GENIUS_SONG: [CallbackQueryHandler(
            check_song,
            pattern='^(?!' + str(END) + ').*$')],

        CHECK_GENIUS_ALBUM: [CallbackQueryHandler(
            check_album_link,
            pattern='^(?!' + str(END) + ').*$')],

        DOWNLOAD_ALBUM: [CallbackQueryHandler(
            get_album_format,
            pattern='^(?!' + str(END) + ').*$')]
    }
    # main conversation handler
    main_menu_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler(
                'start',
                genius,
                Filters.regex(r'^\D*$')),

            CommandHandler(
                "start",
                inline_query,
                Filters.regex(r'[\d]+'), pass_args=True)
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

    # commands handler
    commands = [CommandHandler('song_lyrics', check_song),
                CommandHandler('album_lyrics', check_album_link),
                CommandHandler('lyrics_language', set_lyrics_language),
                CommandHandler('include_annotations', choose_include_annotations),
                CommandHandler('help', help_message),
                CommandHandler('contact_us', contact_us)
                ]
    commands_conv_handler = ConversationHandler(
        entry_points=commands,

        states={
            SELECT_ACTION: [
                CallbackQueryHandler(
                    check_album_link,
                    pattern='^' + str(CHECK_GENIUS_ALBUM) + '$'),

                CallbackQueryHandler(
                    check_song,
                    pattern='^' + str(CHECK_GENIUS_SONG) + '$')
            ],
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
    # log all errors
    dp.add_error_handler(error)
    dp.add_handler(commands_conv_handler)
    # inline query handlers
    dp.add_handler(InlineQueryHandler(inline_query))
    dp.add_handler(CommandHandler(
        "start",
        inline_query,
        Filters.regex(r'[\d]+'), pass_args=True)
    )

    # web hook server to respond to GET cron jobs at /notify
    # if SERVER_PORT:
    #     webhook_thread = WebhookThread()
    #     webhook_thread.start()
    # start polling
    # updater.start_polling()
    updater.start_webhook('0.0.0.0', port=SERVER_PORT, url_path=BOT_TOKEN)
    updater.bot.setWebhook(SERVER_ADDRESS + BOT_TOKEN)
    updater.idle()


if __name__ == '__main__':
    main()
