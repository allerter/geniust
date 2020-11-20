import threading

from telegram.constants import MAX_MESSAGE_LENGTH

from .. import (utils, genius, database, END, TYPING_SONG)
from ..text.keyboards import IButton, IBKeyboard
from ..api import GeniusT


def display_song(update, context):
    bot = context.bot
    chat_id = update.callback_query.message.chat.id
    song_id = int(update.callback_query.data.split()[1])
    language = context.user_data['menu_lang']

    update.callback_query.edit_message_reply_markup()

    song = genius.song(song_id)['song']
    cover_art = song['song_art_image_url']
    caption = song_caption(song, language)
    callback_data = f"song_{song['id']}_lyrics"

    button = IButton("Lyrics", callback_data)

    bot.send_photo(
        chat_id,
        cover_art,
        caption,
        reply_markup=IBKeyboard([[button]]))

    return END


def display_lyrics(bot, user_data, song_id):
    """retrieve and send song lyrics to user"""

    genius = GeniusT()

    if user_data.get('lyrics_lang'):
        lyrics_language = user_data['lyrics_lang']
        include_annotations = user_data['include_annotations']
    else:
        # default settings for new users (probably unnecessary)
        lyrics_language = 'English + Non-English'
        include_annotations = False

    message_id = bot.send_message(
        chat_id=user_data['chat_id'],
        text='getting lyrics...')['message_id']

    lyrics = genius.lyrics(
        song_id=song_id,
        song_url=genius.song(song_id)['song']['url'],
        include_annotations=include_annotations,
        lyrics_language=lyrics_language,
        telegram_song=True,
    )

    # formatting lyrics language
    strings = []

    lyrics = utils.format_language(lyrics, lyrics_language)

    # edit the message for callback query users
    bot.delete_message(chat_id=user_data['chat_id'],
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
        bot.send_message(
            chat_id=user_data['chat_id'],
            text=text,
            parse_mode='HTML',
            disable_web_page_preview=True)
        sent += len(text)
        i += 1


def thread_display_lyrics(update, context):
    song_id = int(update.callback_query.data.split('_')[1])

    # get and send song to user
    p = threading.Thread(
        target=display_lyrics,
        args=(context.bot, context.user_data, song_id,)
    )
    p.start()
    p.join()
    return END


def type_song(update, context):
    # user has entered the function through the main menu
    if update.callback_query:
        update.callback_query.answer()
        msg = 'Send me either a Genius song link, or a title to search'
        update.callback_query.edit_message_text(msg)
    else:
        chat_id = update.message.chat.id
        context.user_data['chat_id'] = chat_id

        if not context.user_data.get('lyrics_lang'):
            database.user(chat_id, context.user_data)
        msg = 'Send a title to search'
        update.message.reply_text(msg)

    return TYPING_SONG


def search_songs(update, context):
    """Handle incoming song request"""
    text = update.message.text
    # get <= 10 hits for user input from Genius API search
    json_search = genius.search_songs(text)
    n_hits = min(10, len(json_search['hits']))
    buttons = []
    for i in range(n_hits):
        search_hit = json_search['hits'][i]['result']
        found_song = search_hit['title']
        found_artist = search_hit['primary_artist']['name']
        text = utils.format_title(found_artist, found_song)
        callback = f"song_{search_hit['id']}"

        buttons.append([IButton(text=text, callback_data=callback)])

    update.message.reply_text(
        text='Choose a song',
        reply_markup=IBKeyboard(buttons)
    )
    return END


def song_caption(song, length_limit=1024):
    if song['featured_artists']:
        features = ', '.join([x['name'] for x in song['featured_artists']])
        features = f"\n<b>Features:</b>\n{features}"
    else:
        features = ''

    album = f"\n<b>Album:</b>\n{song['album']['name']}" if song['album'] else ''

    if song['producer_artists']:
        producers = ', '.join([x['name'] for x in song['producer_artists']])
        producers = f"\n<b>Producers:</b>\n{producers}"
    else:
        producers = ''

    if song['writer_artists']:
        writers = ', '.join([x['name'] for x in song['writer_artists']])
        writers = f"\n<b>Writers:</b>\n{writers}"
    else:
        writers = ''

    if song['song_relationships']:
        relationships = []
        for relation in [x for x in song['song_relationships'] if x['songs']]:
            type_ = ' '.join([x.capitalize() for x in relation['type'].split('_')])
            songs = ', '.join([x['title'] for x in relation['songs']])
            string = f"\n<b>{type_}:\n{songs}</b>"

            relationships.append(string)
        relationships = ''.join(relationships)
    else:
        relationships = ''

    if song['media']:
        media = []
        for m in [x for x in song['media']]:
            provider = m['provider'].capitalize()
            url = m['url']
            string = f"""<a href="{url}">{provider}</a>"""

            media.append(string)
        media = ' | '.join(media)
        media = f"\n<b>External Links:</b>\n{media}"
    else:
        media = ''

    description = song['description_annotation']['annotations'][0]['body']['html']
    if description:
        description = '. '.join(description.split('. ')[:2])

    string = (
        f"{song['full_title']}\n"
        f"\n<b>Title:</b>\n{song['title']}"
        f"\n<b>Artist:</b>\n{song['primary_artist']['name']}"
        f"\n<b>Release Date:</b>\n{song['release_date_for_display']}"
        f"\n<b>Hot:</b>\n{song['stats']['hot']}"
        f"\n<b>Views:</b>\n{utils.human_format(song['stats']['pageviews'])}"
        f"{features}"
        f"{album}"
        f"{producers}"
        f"{writers}"
        f"{relationships}"
        f"{media}"
        f"\n\n{description}"
    )
    string = string.strip()

    if length_limit == 1024 and len(string) > 1024:
        return f'{string[:1021]}...'
    elif length_limit == 4096:
        img = f"""<a href="{song['song_art_image_url']}">&#8709</a>"""
        if len(string) > 4096:
            string = img + string
            return f'{string[:4093]}...'
        else:
            return string + img
