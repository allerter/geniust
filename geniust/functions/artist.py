import logging
import re

from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard

from geniust.constants import (
    TYPING_ARTIST, END,
)
from geniust import (
    genius, utils, get_user, texts
)
from geniust.utils import log


logger = logging.getLogger()


@log
@get_user
def type_artist(update, context):
    # user has entered the function through the main menu
    language = context.user_data['bot_lang']
    text = texts[language]['type_artist']

    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.edit_message_text(text)
    else:
        update.message.reply_text(text)

    return TYPING_ARTIST


@log
@get_user
def search_artists(update, context):
    """Checks artist link or return search results, or prompt user for format"""
    language = context.user_data['bot_lang']
    text = texts[language]['search_artists']
    input_text = update.message.text

    res = genius.search_artists(input_text)
    buttons = []
    for hit in res['sections'][0]['hits'][:10]:
        artist = hit['result']
        artist_id = artist['id']
        title = artist['name']
        callback_data = f"ar{artist_id}"

        buttons.append([IButton(title, callback_data=callback_data)])

    if buttons:
        update.message.reply_text(text['choose'], reply_markup=IBKeyboard(buttons))
    else:
        update.message.reply_text(text['no_artists'])

    return END


@log
@get_user
def display_artist(update, context):
    language = context.user_data['bot_lang']
    text = texts[language]['display_artist']
    bot = context.bot
    if update.callback_query:
        chat_id = update.callback_query.message.chat.id
        artist_id = int(update.callback_query.data[2:])
        update.callback_query.answer()
        update.callback_query.edit_message_reply_markup(None)
    else:
        chat_id = update.message.chat.id
        artist_id = int(context.args[0][2:])

    artist = genius.artist(artist_id)['artist']
    cover_art = artist['image_url']
    caption = artist_caption(artist, text['caption'], language)

    buttons = [
        [IButton(
            text['albums'],
            callback_data=f"ar{artist['id']}a")],
        [IButton(
            text['songs_by_popularity'],
            callback_data=f"ar{artist['id']}sp1")],
        [IButton(
            text['songs_by_release_data'],
            callback_data=f"ar{artist['id']}sr1")],
        [IButton(
            text['songs_by_title'],
            callback_data=f"ar{artist['id']}st1")],
    ]

    if artist['description_annotation']['annotations'][0]['body']['plain']:
        annotation_id = artist['description_annotation']['id']
        button = IButton(text['description'],
                         callback_data=f"an{annotation_id}")
        buttons[0].append(button)

    bot.send_photo(
        chat_id,
        cover_art,
        caption,
        reply_markup=IBKeyboard(buttons))


artist_albums_data = re.compile(r'ar(\d+)a')


@log
@get_user
def display_artist_albums(update, context):
    language = context.user_data['bot_lang']
    text = texts[language]['display_artist_albums']

    if update.callback_query:
        update.callback_query.answer()
        message = update.callback_query.message
        chat_id = update.callback_query.message.chat.id

        data = artist_albums_data.findall(update.callback_query.data)[0]
        artist_id = int(data[0])
    else:
        message = None
        chat_id = update.message.chat.id

        data = artist_songs_data.findall(context.args[0])[0]
        artist_id = int(data[0])

    albums = []

    albums_list = genius.artist_albums(artist_id, per_page=50)
    for album in albums_list['albums']:
        name = text['album'].replace('{}', utils.deep_link(album))

        albums.append(name)

    if albums:
        artist = albums_list['albums'][0]['artist']['name']
        albums = f"{text['albums'].replace('{}', artist)}\n{''.join(albums)}"
    else:
        artist = genius.artist(artist_id)['artist']['name']
        text = text['no_albums'].replace('{}', artist)
        context.bot.send_message(chat_id, text)
        return END

    if message and len(message.caption) + len(albums) < 1024:
        update.callback_query.edit_message_caption(message.caption + albums)
    else:
        context.bot.send_message(chat_id, albums)

    return END


artist_songs_data = re.compile(r'ar(\d+)s([a-z])(\d+)')


@log
@get_user
def display_artist_songs(update, context):
    language = context.user_data['bot_lang']
    text = texts[language]['display_artist_songs']

    if update.callback_query:
        update.callback_query.answer()
        message = update.callback_query.message
        # A message with a photo means the user came from display_artist
        # and so we send the songs as a new message
        message = message if message.photo is None else None
        chat_id = update.callback_query.message.chat.id

        data = artist_songs_data.findall(update.callback_query.data)[0]
        artist_id, sort, page = int(data[0]), data[1], int(data[2])
    else:
        message = None
        chat_id = update.message.chat.id

        data = artist_songs_data.findall(context.args[0])[0]
        artist_id, sort, page = int(data[0]), data[1], int(data[2])

    if sort == 'p':
        sort = 'popularity'
    elif sort == 'r':
        sort = 'release_date'
    else:
        sort = 'title'

    songs = []
    per_page = 50
    songs_list = genius.artist_songs(artist_id, per_page=per_page, page=page, sort=sort)
    next_page = songs_list['next_page']
    previous_page = page - 1 if page != 1 else None

    for i, song in enumerate(songs_list['songs']):
        num = per_page * (page - 1) + i + 1
        title = f"\n{num:02} - {utils.deep_link(song)}"

        views = song['stats'].get('pageviews')
        if sort == 'popularity' and views:
            views = utils.human_format(views)
            title += f' ({views})'

        songs.append(title)

    if songs:
        artist = songs_list['songs'][0]['primary_artist']['name']
        msg = (
            text['songs']
            .replace('{artist}', artist)
            .replace('{sort}', text[sort])
        )
        songs = f"{msg}\n{''.join(songs)}"
    else:
        artist = genius.artist(artist_id)['artist']['name']
        text = text['no_songs'].replace('{}', artist)
        context.bot.send_message(chat_id, text)
        return END

    logger.debug('%s - %s - %s', previous_page, page, next_page)

    if previous_page:
        msg = text['previous_page'].replace('{}', str(previous_page))
        previous_button = IButton(
            msg,
            callback_data=f'ar{artist_id}s{sort[0]}{previous_page}')
    else:
        previous_button = IButton('⬛️', callback_data='None')

    current_button = IButton(str(page), callback_data='None')

    if next_page:
        msg = text['next_page'].replace('{}', str(next_page))
        next_button = IButton(
            msg,
            callback_data=f'ar{artist_id}s{sort[0]}{next_page}')
    else:
        next_button = IButton('⬛️', callback_data='None')

    if previous_page or next_page:
        buttons = [[previous_button, current_button, next_button]]
        keyboard = IBKeyboard(buttons)
    else:
        keyboard = None

    if message:
        update.callback_query.edit_message_caption(songs, reply_markup=keyboard)
    else:
        context.bot.send_message(chat_id, songs, reply_markup=keyboard)

    return END


@log
def artist_caption(artist, caption, language):
    alternate_names = ''
    social_media = ''
    social_media_links = []

    if artist.get('alternate_names'):
        names = ', '.join(artist['alternate_names'])
        alternate_names = caption['alternate_names'].replace('{}', names)

    if artist.get('facebook_name'):
        url = f"https://www.facebook.com/{artist['facebook_name']}"
        social_media_links.append(f"""<a href="{url}">Facebook</a>""")
    if artist.get('instagram_name'):
        url = f"https://www.instagram.com/{artist['instagram_name']}"
        social_media_links.append(f"""<a href="{url}">Instagram</a>""")
    if artist.get('twitter_name'):
        url = f"https://www.twitter.com/{artist['twitter_name']}"
        social_media_links.append(f"""<a href="{url}">Twitter</a>""")
    if social_media_links:
        links = " | ".join(social_media_links)
        social_media = caption['social_media'].replace('{}', links)

    followers_count = utils.human_format(artist['followers_count'])

    is_verified = texts[language][artist['is_verified']]

    string = (
        caption['body']
        .replace('{name}', artist['name'])
        .replace('{url}', artist['url'])
        .replace('{verified}', is_verified)
        .replace('{followers}', followers_count)
        + social_media
        + alternate_names
    )

    return string.strip()
