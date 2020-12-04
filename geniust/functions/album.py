import logging
import threading

from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram import InputMediaPhoto
from telegram.error import TimedOut, NetworkError

from geniust.constants import (TYPING_ALBUM, END,)
from geniust import (api, utils, get_user)
from geniust.utils import log

from .album_conversion import (
    create_pdf, create_zip, create_pages
)


logger = logging.getLogger()


@log
@get_user
def type_album(update, context):
    language = context.user_data['bot_lang']
    text = context.bot_data['texts'][language]['type_album']

    # user has entered the function through the main menu
    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.edit_message_text(text)
    else:
        update.message.reply_text(text)

    return TYPING_ALBUM


@log
@get_user
def search_albums(update, context):
    """Checks album link or return search results, or prompt user for format"""
    genius = context.bot_data['genius']
    input_text = update.message.text
    language = context.user_data['bot_lang']
    text = context.bot_data['texts'][language]['search_albums']

    res = genius.search_albums(input_text)

    buttons = []

    for hit in res['sections'][0]['hits'][:10]:
        album = hit['result']
        album_id = album['id']
        title = utils.format_title(album['artist']['name'],
                                  album['name'])
        callback = f"album_{album_id}"

        buttons.append([IButton(title, callback_data=callback)])

    if buttons:
        update.message.reply_text(text['choose'], reply_markup=IBKeyboard(buttons))
    else:
        update.message.reply_text(text['no_albums'])

    return END


@log
@get_user
def display_album(update, context):
    genius = context.bot_data['genius']
    language = context.user_data['bot_lang']
    text = context.bot_data['texts'][language]['display_album']
    bot = context.bot
    chat_id = update.effective_chat.id

    if update.callback_query:
        album_id = int(update.callback_query.data.split('_')[1])
        update.callback_query.answer()
        update.callback_query.edit_message_reply_markup(None)
    else:
        album_id = int(context.args[0].split('_')[1])

    logger.debug('album %s', album_id)

    album = genius.album(album_id)['album']
    cover_art = album['cover_art_url']
    caption = album_caption(update, context, album, text['caption'])

    buttons = [
        [IButton(
            text['cover_arts'],
            callback_data=f"album_{album['id']}_covers")],
        [IButton(
            text['tracks'],
            callback_data=f"album_{album['id']}_tracks")],
        [IButton(
            text['lyrics'],
            callback_data=f"album_{album['id']}_lyrics")]
    ]

    if album['description_annotation']['annotations'][0]['body']['plain']:
        annotation_id = album['description_annotation']['id']
        button = IButton(text['description'],
                         callback_data=f"annotation_{annotation_id}")
        buttons[0].append(button)

    bot.send_photo(
        chat_id,
        cover_art,
        caption,
        reply_markup=IBKeyboard(buttons))

    return END


@log
@get_user
def display_album_covers(update, context):
    genius = context.bot_data['genius']
    language = context.user_data['bot_lang']
    text = context.bot_data['texts'][language]['display_album_covers']
    chat_id = update.effective_chat.id

    if update.callback_query:
        update.callback_query.answer()
        album_id = int(update.callback_query.data.split('_')[1])
    else:
        album_id = int(context.args[0].split('_')[1])

    covers = [x['image_url']
              for x in genius.album_cover_arts(album_id)['cover_arts']
              ]

    album = genius.album(album_id)['album']['name']

    if len(covers) == 1:
        text = text[1].replace('{}', album)
        context.bot.send_photo(chat_id, covers[0], text)
    else:
        media = [InputMediaPhoto(x) for x in covers]
        media[0].caption = text[2].replace('{}', album)
        context.bot.send_media_group(chat_id, media)

    return END


@log
@get_user
def display_album_tracks(update, context):
    genius = context.bot_data['genius']
    language = context.user_data['bot_lang']
    msg = context.bot_data['texts'][language]['display_album_tracks']
    chat_id = update.effective_chat.id

    if update.callback_query:
        update.callback_query.answer()
        album_id = int(update.callback_query.data.split('_')[1])
    else:
        album_id = int(context.args[0].split('_')[1])

    songs = []
    for track in genius.album_tracks(album_id, per_page=50)['tracks']:
        num = track['number']
        song = track['song']
        song = utils.deep_link(song)
        text = f"""\n{num:02d}. {song}"""

        songs.append(text)

    album = genius.album(album_id)['album']['name']

    text = f"{msg.replace('{}', album)}{''.join(songs)}"

    context.bot.send_message(chat_id, text)

    return END


@log
def display_album_formats(update, context):
    language = context.user_data['bot_lang']
    msg = context.bot_data['texts'][language]['display_album_formats']
    chat_id = update.effective_chat.id

    if update.callback_query:
        update.callback_query.answer()
        album_id = int(update.callback_query.data.split('_')[1])
    else:
        album_id = int(context.args[0].split('_')[1])

    buttons = [
        [IButton(
            "PDF",
            callback_data=f"album_{album_id}lyrics_pdf")],
        [IButton(
            "TELEGRA.PH",
            callback_data=f"album_{album_id}_lyrics_tgf")],
        [IButton(
            "ZIP",
            callback_data=f"album_{album_id}_lyrics_zip")],
    ]
    keyboard = IBKeyboard(buttons)

    if update.callback_query:
        update.callback_query.edit_message_reply_markup(keyboard)
    else:
        context.bot.send_message(chat_id, msg, reply_markup=keyboard)

    return END


@log
@get_user
def thread_get_album(update, context):
    """Create a thread and download the album"""
    language = context.user_data['bot_lang']
    text = context.bot_data['texts'][language]['get_album']

    update.callback_query.answer()
    _, album_id, _, album_format = update.callback_query.data.split('_')
    album_id = int(album_id)

    p = threading.Thread(
        target=get_album,
        args=(update, context, album_id, album_format, text,))
    p.start()
    p.join()
    return END


@log
def get_album(update, context, album_id, album_format, text):
    """Download and send the album to the user in the selected format"""
    ud = context.user_data
    include_annotations = ud['include_annotations']
    msg = text['downloading']
    genius_t = api.GeniusT()
    chat_id = update.effective_chat.id

    progress = update.callback_query.edit_message_text(msg)

    # get album
    album = genius_t.async_album_search(
        album_id=album_id,
        include_annotations=include_annotations
    )

    # result should be a dict if the operation was successful
    if not isinstance(album, dict):
        text = text['failed']
        progress.edit_message_text(text)
        logging.error(
            f"Couldn't get album:\n"
            f"Album ID:{album_id}\n"
            f"Returned: {album}")
        return

    # convert
    msg = text['converting']
    progress.edit_message_text(msg)

    if album_format == 'pdf':
        file = create_pdf(album, context.user_data)
    elif album_format == 'zip':
        file = create_zip(album, context.user_data)
    elif album_format == 'tgf':  # TELEGRA.PH
        link = create_pages(album, context.user_data)
        context.bot.send_message(chat_id=chat_id, text=link)
        progress.delete_message()
        return
    else:
        raise ValueError(f'Unknown album format: {album_format}')

    msg = text['uploading']
    progress.edit_message_text(msg)

    # send the file
    i = 1
    while True:
        if i != 0 and i < 6:
            try:
                context.bot.send_document(
                    chat_id=chat_id,
                    document=file,
                    caption=file.name[:-4],
                    timeout=20,)
                break
            except (TimedOut, NetworkError):
                i += 1

    progress.delete_message()


@log
def album_caption(update, context, album, caption):

    release_date = ''
    features = ''
    labels = ''

    if album.get('release_date'):
        release_date = album['release_date']
    elif album.get('release_date_components'):
        release_date = album['release_date_components']
        year = release_date.get('year')
        month = release_date.get('month')
        day = release_date.get('day')
        components = [year, month, day]
        release_date = '-'.join(str(x) for x in components if x is not None)

    total_views = utils.human_format(album['song_pageviews'])

    for x in album.get('song_performances', []):
        if x['label'] == 'Featuring':
            features = ', '.join([utils.deep_link(x) for x in x['artists']])
            features = caption['features'].replace('{}', features)
        elif x['label'] == 'Label':
            labels = ', '.join([utils.deep_link(x) for x in x['artists']])
            labels = caption['labels'].replace('{}', labels)

    string = (
        caption['body']
        .replace('{name}', album['name'])
        .replace('{artist_name}', album['artist']['name'])
        .replace('{artist}', utils.deep_link(album['artist']))
        .replace('{release_date}', release_date)
        .replace('{url}', album['url'])
        .replace('{views}', total_views)
        + features
        + labels
    )

    return string.strip()
