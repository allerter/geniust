import logging
import threading

from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram import InputMediaPhoto
from telegram.error import TimedOut, NetworkError
from telegram.utils.helpers import create_deep_linked_url

from geniust.constants import (
    TYPING_ALBUM, END,
)
from geniust import (
    utils,
    database, genius, username,
)

from .album_conversion import (
    create_pdf, create_zip, create_pages
)
from geniust.api import GeniusT


def type_album(update, context):
    # user has entered the function through the main menu
    if update.callback_query:
        update.callback_query.answer()
        msg = 'Enter album name.'
        update.callback_query.edit_message_text(msg)
    else:
        chat_id = update.message.chat.id
        context.user_data['chat_id'] = chat_id

        msg = 'Enter album name.'
        update.message.reply_text(msg)

    return TYPING_ALBUM


def search_albums(update, context):
    """Checks album link or return search results, or prompt user for format"""
    text = update.message.text
    print(text)

    res = genius.search_albums(text)
    buttons = []
    for i, hit in enumerate(res['sections'][0]['hits']):
        album = hit['result']
        album_id = album['id']
        text = utils.format_title(album['artist']['name'],
                                  album['name'])
        callback = f"album_{album_id}"

        buttons.append([IButton(text, callback_data=callback)])

    update.message.reply_text(
        text='Choose an album',
        reply_markup=IBKeyboard(buttons))

    return END


def display_album(update, context):
    bot = context.bot
    chat_id = update.callback_query.message.chat.id
    album_id = int(update.callback_query.data.split('_')[1])
    print(album_id)
    language = context.user_data['menu_lang']

    update.callback_query.edit_message_reply_markup()

    album = genius.album(album_id)['album']
    cover_art = album['cover_art_url']
    caption = album_caption(album, language)

    buttons = [
        [IButton(
            "Cover Arts",
            callback_data=f"album_{album['id']}_covers")],
        [IButton(
            "List Tracks",
            callback_data=f"album_{album['id']}_tracks")],
        [IButton(
            "All-In-One Lyrics (PDF, ...)",
            callback_data=f"album_{album['id']}_aio")]
    ]

    bot.send_photo(
        chat_id,
        cover_art,
        caption,
        reply_markup=IBKeyboard(buttons))


def display_album_covers(update, context):
    if update.callback_query:
        chat_id = update.callback_query.message.chat.id
        album_id = int(update.callback_query.data.split('_')[1])
    else:
        chat_id = update.message.chat.id
        album_id = int(context.args[0].split('_')[1])

    covers = [x['image_url'] for x in genius.album_cover_arts(album_id)]

    album = genius.albums(album_id)['album']['name']

    if len(covers) == 1:
        text = f"{album} Cover Art"
        context.bot.send_photo(chat_id, covers[0], text)
    else:
        media = [InputMediaPhoto(x) for x in covers]
        media[0].caption = f"{album} Cover Arts"
        context.bot.send_media_group(chat_id, media)

    return END


def display_album_tracks(update, context):
    if update.callback_query:
        chat_id = update.callback_query.message.chat.id
        album_id = int(update.callback_query.data.split('_')[1])
    else:
        chat_id = update.message.chat.id
        album_id = int(context.args[0].split('_')[1])

        songs = []
        songs_list = genius.album_tracks(album_id, per_page=50)
        for track in songs_list['tracks']:
            num = track['number']
            song = track['song']
            song_id = song['id']
            song_name = song['name']

            url = create_deep_linked_url(username, f'song_{song_id}')
            text = f"""\n{num:02d}. <a href="{url}">{song_name}"""

            songs.append(text)

    album = genius.albums(album_id)['album']['name']

    text = f"{album} Tracks:{''.join(songs)}"

    context.bot.send_message(chat_id, text)

    return END


def display_album_formats(update, context):

    if update.callback_query:
        album_id = int(update.callback_query.data.split('_')[1])
    else:
        album_id = int(context.args[0].split('_')[1])

    buttons = [
        [IButton(
            "PDF",
            callback_data=f"album_{album_id}_aio_pdf")],
        [IButton(
            "TELEGRA.PH",
            callback_data=f"album_{album_id}_aio_tgf")],
        [IButton(
            "ZIP",
            callback_data=f"album_{album_id}_aio_zip")],
    ]

    update.callback_query.edit_message_reply_markup(IBKeyboard(buttons))

    return END


def thread_get_album(update, context):
    """Create a thread and download the album"""

    data = update.callback_query.data.split('_')

    album_id, album_format = int(data[1]), data[3]

    p = threading.Thread(
        target=get_album,
        args=(update, context, album_id, album_format,))
    p.start()
    p.join()
    return END


def get_album(update, context, album_id, album_format):
    """Download and send the album to the user in the selected format"""
    chat_id = update.callback_query.message.chat.id
    text = 'Downloading album...'

    genius = GeniusT()

    # try clause for the callback query users and
    # the except clause for inline query users
    if update.callback_query:
        progress = context.bot.edit_message_text(
            chat_id=chat_id,
            text=text,
            message_id=update.callback_query.message.message_id)
    else:
        progress = context.bot.send_message(
            chat_id=chat_id,
            text=text)

    # get album
    album = genius.async_album_search(
        album_id=album_id,
        include_annotations=context.user_data['include_annotations']
    )

    # result should be a dict if the operation was successful
    if not isinstance(album, dict):
        text = "Couldn't get the album :("
        context.bot.send_message(chat_id=chat_id, text=text)
        logging.error(
            f"Couldn't get album:\n"
            f"Album ID:{album_id}\n"
            f"Returned: {album}")
        return END

    # convert
    text = 'Converting to specified format...'
    context.bot.edit_message_text(
        chat_id=progress.chat.id,
        text=text,
        message_id=progress.message_id
    )

    if album_format == 'pdf':
        file = create_pdf(album, context.user_data)
    elif album_format == 'zip':
        file = create_zip(album, context.user_data)
    elif album_format == 'tgf':  # TELEGRA.PH
        link = create_pages(user_data=context.user_data, data=album)
        context.bot.send_message(chat_id=chat_id, text=link)

    progress.delete_message()

    # send the file
    if album_format != 'tgf':
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


def album_caption(album, length_limit=1024):
    features = ''
    labels = ''

    for x in album['song_performances']:
        if x['label'] == 'Featuring':
            features = ', '.join([x['name'] for x in x['artists']])
            features = f"\n<b>Features:</b>\n{features}"
        elif x['label'] == 'Label':
            labels = ', '.join([x['name'] for x in x['artists']])
            labels = f"\n<b>Labels:</b>\n{labels}"

    description = album['description_annotation']['annotations'][0]['body']['html']

    string = (
        f"{album['full_title']}\n"
        f"\n<b>Name:</b>\n{album['name']}"
        f"\n<b>Artist:</b>\n{album['artist']['name']}"
        f"{features}"
        f"\n<b>Release Date:</b>\n{album['release_date']}"
        f"\n<b>Total Views:</b>\n{utils.human_format(album['song_pageviews'])}"
        f"{labels}"
        f"\n\n{description}"
    )
    string = string.strip()

    if length_limit == 1024 and len(string) > 1024:
        return f'{string[:1021]}...'
    elif length_limit == 4096:
        img = f"""<a href="{album['cover_art_url']}">&#8709</a>"""
        if len(string) > 4096:
            string = img + string
            return f'{string[:4093]}...'
        else:
            return string + img
