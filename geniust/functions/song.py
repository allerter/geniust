import logging
import threading
import re

from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram.constants import MAX_MESSAGE_LENGTH

from geniust.constants import (
    END, TYPING_SONG
)
from geniust import (
    genius,
    utils,
    get_user, texts
)
from geniust.api import GeniusT
from geniust.utils import log


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


@log
@get_user
def display_song(update, context):
    language = context.user_data['bot_lang']
    text = texts[language]['display_song']
    bot = context.bot

    if update.callback_query:
        chat_id = update.callback_query.message.chat.id
        song_id = int(update.callback_query.data[1:])
        update.callback_query.answer()
        update.callback_query.edit_message_reply_markup(None)
    else:
        chat_id = update.message.chat.id
        song_id = int(context.args[0][1:])

    song = genius.song(song_id)['song']
    cover_art = song['song_art_image_url']
    caption = song_caption(song, text['caption'], language)
    callback_data = f"s{song['id']}l"

    buttons = [[IButton(text['lyrics'], callback_data=callback_data)]]

    if song['description_annotation']['annotations'][0]['body']['plain']:
        annotation_id = song['description_annotation']['id']
        button = IButton(text['description'],
                         callback_data=f"an{annotation_id}")
        buttons[0].append(button)

    bot.send_photo(
        chat_id,
        cover_art,
        caption,
        reply_markup=IBKeyboard(buttons))

    return END


@log
def display_lyrics(update, context, song_id, text):
    """retrieve and send song lyrics to user"""
    user_data = context.user_data
    bot = context.bot
    chat_id = update.effective_chat.id

    genius_t = GeniusT()

    if user_data.get('lyrics_lang'):
        lyrics_language = user_data['lyrics_lang']
        include_annotations = user_data['include_annotations']
    else:
        # default settings for new users (probably unnecessary)
        lyrics_language = 'English + Non-English'
        include_annotations = True

    logger.debug(f'{lyrics_language} | {include_annotations} | {song_id}')

    message_id = bot.send_message(
        chat_id=chat_id,
        text=text)['message_id']

    lyrics = genius_t.lyrics(
        song_id=song_id,
        song_url=genius.song(song_id)['song']['url'],
        include_annotations=include_annotations,
        telegram_song=True,
    )

    # formatting lyrics language
    lyrics = utils.format_language(lyrics, lyrics_language)
    lyrics = utils.remove_unsupported_tags(lyrics)
    lyrics = re.sub(r'<[/]*(br|div|p).*[/]*?>', '', str(lyrics))

    # edit the message for callback query users
    bot.delete_message(chat_id=chat_id,
                       message_id=message_id)

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
        bot.send_message(chat_id, text)
        sent += len(text)
        i += 1


@log
@get_user
def thread_display_lyrics(update, context):
    language = context.user_data['bot_lang']
    text = texts[language]['display_lyrics']

    if update.callback_query:
        update.callback_query.answer()
        song_id = int(update.callback_query.data[1:-1])
    else:
        song_id = int(update.callback_query.data[1:-1])

    # get and send song to user
    p = threading.Thread(
        target=display_lyrics,
        args=(update, context, song_id, text,)
    )
    p.start()
    p.join()
    return END


@log
@get_user
def type_song(update, context):
    # user has entered the function through the main menu
    language = context.user_data['bot_lang']
    msg = texts[language]['type_song']

    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.edit_message_text(msg)
    else:
        update.message.reply_text(msg)

    return TYPING_SONG


@log
@get_user
def search_songs(update, context):
    """Handle incoming song request"""
    language = context.user_data['bot_lang']
    text = texts[language]['search_songs']
    input_text = update.message.text

    # get <= 10 hits for user input from Genius API search
    json_search = genius.search_songs(input_text)['sections'][0]
    buttons = []
    for hit in json_search['hits'][:10]:
        song = hit['result']
        title = song['title']
        artist = song['primary_artist']['name']
        title = utils.format_title(artist, title)
        callback = f"s{song['id']}"

        buttons.append([IButton(text=title, callback_data=callback)])

    if buttons:
        update.message.reply_text(text['choose'], reply_markup=IBKeyboard(buttons))
    else:
        update.message.reply_text(text['no_songs'])
    return END


@log
def song_caption(song, caption, language):
    release_date = ''
    features = ''
    album = ''
    producers = ''
    writers = ''
    relationships = ''
    tags = ''

    if song.get('release_date'):
        release_date = song['release_date_for_display']

    if song.get('featured_artists'):
        features = ', '.join([utils.deep_link(x) for x in song['featured_artists']])
        features = caption['features'].replace('{}', features)

    if song.get('albums'):
        album = ', '.join(utils.deep_link(album) for album in song['albums'])
        album = caption['albums'].replace('{}', album)

    if song.get('producer_artists'):
        producers = ', '.join([utils.deep_link(x) for x in song['producer_artists']])
        producers = caption['producers'].replace('{}', producers)

    if song.get('writer_artists'):
        writers = ', '.join([utils.deep_link(x) for x in song['writer_artists']])
        writers = caption['writers'].replace('{}', writers)

    if song.get('song_relationships'):
        relationships = []
        for relation in [x for x in song['song_relationships'] if x['songs']]:
            if relation['type'] in caption:
                type_ = caption[relation['type']]
            else:
                type_ = ' '.join([x.capitalize() for x in relation['type'].split('_')])
            songs = ', '.join([utils.deep_link(x) for x in relation['songs']])
            string = f"\n<b>{type_}</b>:\n{songs}"

            relationships.append(string)
        relationships = ''.join(relationships)

    genius_url = f"""<a href="{song['url']}">Genius</a>"""
    external_links = caption['external_links'].replace('{}', genius_url)
    if song.get('media'):
        media = []
        for m in [x for x in song['media']]:
            provider = m['provider'].capitalize()
            url = m['url']
            string = f"""<a href="{url}">{provider}</a>"""

            media.append(string)
        external_links += ' | ' + ' | '.join(media)

    hot = texts[language][song['stats']['hot']]

    if song['tags']:
        tags = ', '.join(tag['name'] for tag in song['tags'])
    else:
        tags = ''

    string = (
        caption['body']
        .replace('{title}', song['title'])
        .replace('{artist_name}', song['primary_artist']['name'])
        .replace('{artist}', utils.deep_link(song['primary_artist']))
        .replace('{release_date}', release_date)
        .replace('{hot}', hot)
        .replace('{tags}', tags)
        .replace('{views}', utils.human_format(song['stats'].get('pageviews', '?')))
        + features
        + album
        + producers
        + writers
        + relationships
        + external_links
    )
    string = string.strip()

    if len(string) > 1024:
        return string[:string.rfind('<b>')]
    else:
        return string
