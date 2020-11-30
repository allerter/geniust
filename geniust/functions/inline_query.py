import logging
from uuid import uuid4
from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram import (
    InlineQueryResultArticle,
    InputTextMessageContent
)
from telegram.utils.helpers import create_deep_linked_url

from geniust.constants import END
from geniust import genius, username, utils, get_user
from geniust.utils import log


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


@log
@get_user
def inline_menu(update, context):
    language = context.user_data['bot_lang']
    text = context.bot_data['texts'][language]['inline_menu']

    articles = [
        InlineQueryResultArticle(
            id=uuid4(),
            title=text['search_albums']['body'],
            description=text['search_albums']['description'],
            input_message_content=InputTextMessageContent(
                text['search_albums']['initial_caption']),
            reply_markup=IBKeyboard([[IButton(
                text=text['button'], switch_inline_query_current_chat='.album ')]])
        ),

        InlineQueryResultArticle(
            id=uuid4(),
            title=text['search_artists']['body'],
            description=text['search_artists']['description'],
            input_message_content=InputTextMessageContent(
                text['search_artists']['initial_caption']),
            reply_markup=IBKeyboard([[IButton(
                text=text['button'], switch_inline_query_current_chat='.artist ')]])
        ),

        InlineQueryResultArticle(
            id=uuid4(),
            title=text['search_songs']['body'],
            description=text['search_songs']['description'],
            input_message_content=InputTextMessageContent(
                text['search_songs']['initial_caption']),
            reply_markup=IBKeyboard([[IButton(
                text=text['button'], switch_inline_query_current_chat='.song ')]])
        ),
    ]

    update.inline_query.answer(articles)


@log
@get_user
def search_albums(update, context):
    language = context.user_data['bot_lang']
    texts = context.bot_data['texts'][language]
    text = texts['inline_menu']['search_albums']
    input_text = update.inline_query.query.split('.album ')[1].strip()
    if not input_text:
        return

    search_more = [IButton(
        text=f"...{text['body']}...",
        switch_inline_query_current_chat='.album ')
    ]

    res = genius.search_albums(input_text, per_page=10)
    articles = []
    for i, hit in enumerate(res['sections'][0]['hits']):
        album = hit['result']
        name = album['name']
        artist = album['artist']['name']
        title = utils.format_title(artist, name)
        album_id = album['id']

        if 'Genius' in artist:
            description = texts['inline_menu']['translation']
        else:
            description = ''
        answer_text = album_caption(update, context, album, text['caption'])
        album_url = create_deep_linked_url(username, f"album_{album_id}")
        cover_url = create_deep_linked_url(username, f"album_{album_id}_covers")
        songlist_url = create_deep_linked_url(username, f"album_{album_id}_tracks")
        aio_url = create_deep_linked_url(username, f"album_{album_id}_lyrics")

        buttons = [
            [IButton(texts['inline_menu']['full_details'],
                     url=album_url)],
            [IButton(texts['display_album']['cover_arts'],
                     url=cover_url)],
            [IButton(texts['display_album']['tracks'],
                     url=songlist_url)],
            [IButton(texts['display_album']['lyrics'],
                     url=aio_url)],
            search_more
        ]
        keyboard = IBKeyboard(buttons)
        answer = InlineQueryResultArticle(
            id=uuid4(),
            title=title,
            thumb_url=album['cover_art_thumbnail_url'],
            input_message_content=InputTextMessageContent(
                answer_text,
                disable_web_page_preview=False),
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
        articles.append(answer)

        if i == 9:
            break

    update.inline_query.answer(articles)


@log
@get_user
def search_artists(update, context):
    language = context.user_data['bot_lang']
    texts = context.bot_data['texts'][language]
    text = texts['inline_menu']['search_artists'],
    input_text = update.inline_query.query.split('.artist ')[1].strip()
    if not input_text:
        return END

    search_more = [IButton(
        text=f"...{text['body']}...",
        switch_inline_query_current_chat='.artist ')
    ]

    res = genius.search_artists(input_text, per_page=10)
    articles = []
    for i, hit in enumerate(res['sections'][0]['hits']):
        artist = hit['result']
        title = artist['name']
        artist_id = artist['id']

        # description = f"AKA {', '.join(artist['alternate_names'])}"
        answer_text = artist_caption(update, context, artist, text['caption'], language)
        artist_url = create_deep_linked_url(
            username,
            f"artist_{artist_id}")
        songlist_ppl = create_deep_linked_url(
            username,
            f"artist_{artist_id}_songs_ppt_1")
        songlist_rdt = create_deep_linked_url(
            username,
            f"artist_{artist_id}_songs_rdt_1")
        songlist_ttl = create_deep_linked_url(
            username,
            f"artist_{artist_id}_songs_ttl_1")
        albumlist = create_deep_linked_url(
            username,
            f"artist_{artist_id}_albums")

        button_text = texts['display_artist']
        buttons = [
            [IButton(texts['inline_menu']['full_details'], url=artist_url)],
            [IButton(button_text['songs_by_popularity'], url=songlist_ppl)],
            [IButton(button_text['songs_by_release_data'], url=songlist_rdt)],
            [IButton(button_text['songs_by_title'], url=songlist_ttl)],
            [IButton(button_text['albums'], url=albumlist)],
            search_more
        ]
        keyboard = IBKeyboard(buttons)
        answer = InlineQueryResultArticle(
            id=uuid4(),
            title=title,
            thumb_url=artist['image_url'],
            input_message_content=InputTextMessageContent(
                answer_text,
                disable_web_page_preview=False),
            reply_markup=keyboard,
            # description=description
        )
        # It's possible to provide results that are captioned photos
        # of the song cover art, but that requires using InlineQueryResultPhoto
        # and user might not be able to choose the right song this way,
        # since all they get is only the cover arts of the hits.
        # answer = InlineQueryResultPhoto(id=uuid4(),
        #    photo_url=search_hit['song_art_image_url'],
        #    thumb_url=search_hit['song_art_image_thumbnail_url'],
        #    reply_markup=keyboard, description=description)
        articles.append(answer)

        if i == 9:
            break

    update.inline_query.answer(articles)

    return END


@log
@get_user
def search_songs(update, context):
    language = context.user_data['bot_lang']
    texts = context.bot_data['texts'][language]
    text = texts['inline_menu']['search_songs']
    input_text = update.inline_query.query.split('.song ')[1].strip()
    if not input_text:
        return

    search_more = [IButton(
        text=f"...{text['body']}...",
        switch_inline_query_current_chat='.song ')
    ]

    res = genius.search_songs(input_text, per_page=10)
    articles = []
    for i, hit in enumerate(res['hits']):
        song = hit['result']
        title = song['title']
        artist = song['primary_artist']['name']
        answer_title = utils.format_title(artist, title)
        song_id = song['id']

        description = 'Translation' if 'Genius' in artist else ''
        answer_text = song_caption(update, context, song, text['caption'], language)
        song_url = create_deep_linked_url(username, f'song_{song_id}')
        lyrics_url = create_deep_linked_url(username, f'song_{song_id}_lyrics')
        buttons = [
            [IButton(texts['inline_menu']['full_details'], url=song_url)],
            [IButton(texts['display_song']['lyrics'], url=lyrics_url)],
            search_more
        ]
        keyboard = IBKeyboard(buttons)
        answer = InlineQueryResultArticle(
            id=uuid4(),
            title=answer_title,
            thumb_url=song['song_art_image_thumbnail_url'],
            input_message_content=InputTextMessageContent(
                answer_text,
                disable_web_page_preview=False),
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
        articles.append(answer)

        if i == 9:
            break

    update.inline_query.answer(articles)


@log
def album_caption(update, context, album, caption):

    release_date = album['release_date_components']
    year = release_date.get('year')
    month = release_date.get('month')
    day = release_date.get('day')
    components = [year, month, day]
    release_date = '-'.join(str(x) for x in components if x is not None)

    string = (
        caption
        .replace('{name}', album['name'])
        .replace('{artist_name}', album['artist']['name'])
        .replace('{artist}', utils.deep_link(album['artist']))
        .replace('{release_date}', release_date)
        .replace('{url}', album['url'])
        .replace('{url}', album['cover_art_url'])
    )

    return string.strip()


@log
def artist_caption(update, context, artist, caption, language):

    is_verified = context.bot_data['texts'][language][artist['is_verified']]

    string = (
        caption
        .replace('{name}', artist['name'])
        .replace('{url}', artist['url'])
        .replace('{verified}', is_verified)
        .replace('{image_url}', artist['image_url'])
    )

    return string.strip()


@log
def song_caption(update, context, song, caption, language):

    hot = context.bot_data['texts'][language][song['stats']['hot']]

    string = (
        caption
        .replace('{title}', song['title'])
        .replace('{artist_name}', song['primary_artist']['name'])
        .replace('{artist}', utils.deep_link(song['primary_artist']))
        .replace('{hot}', hot)
        .replace('{views}', utils.human_format(song['stats']['pageviews']))
        .replace('{url}', song['url'])
        .replace('{image_url}', song['song_art_image_url'])
    )

    return string.strip()
