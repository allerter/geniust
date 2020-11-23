from uuid import uuid4
from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram import (
    InlineQueryResultArticle,
    InputTextMessageContent
)
from telegram.utils.helpers import create_deep_linked_url

from .album import album_caption
from .artist import artist_caption
from .song import song_caption
from geniust import genius, username, utils


def menu(update, context):
    articles = [
        InlineQueryResultArticle(
            id=uuid4(),
            title='Search Albums',
            description='Album info and lyrics.',
            input_message_content=InputTextMessageContent(
                'Click on the button below to search albums.'),
            reply_markup=IBKeyboard([[IButton(
                text='Click Here', switch_inline_query_current_chat='.album ')]])
        ),

        InlineQueryResultArticle(
            id=uuid4(),
            title='Search Artists',
            description='Artist info, songs and albums.',
            input_message_content=InputTextMessageContent(
                'Click on the button below to search artists.'),
            reply_markup=IBKeyboard([[IButton(
                text='Click Here', switch_inline_query_current_chat='.artist ')]])
        ),

        InlineQueryResultArticle(
            id=uuid4(),
            title='Search Songs',
            description='Song info and lyrics.',
            input_message_content=InputTextMessageContent(
                'Click on the button below to search songs.'),
            reply_markup=IBKeyboard([[IButton(
                text='Click Here', switch_inline_query_current_chat='.song ')]])
        ),
    ]

    update.inline_query.answer(articles)


def search_albums(update, context):
    text = update.inline_query.query

    search_more = [IButton(
        text='Search Albums...',
        switch_inline_query_current_chat='.album ')
    ]

    res = genius.search_albums(text, per_page=10)
    articles = []
    for i, hit in enumerate(res['sections'][0]['hits']):
        album = hit['result']
        name = album['name']
        artist = album['primary_artist']['name']
        text = utils.format_title(artist, name)
        album_id = album['id']

        description = 'Translation' if 'Genius' in artist else ''
        answer_text = album_caption(album, 4096)
        coverlist_url = create_deep_linked_url(username, f"album_{album_id}_covers")
        songlist_url = create_deep_linked_url(username, f"album_{album_id}_songs")
        aio_url = create_deep_linked_url(username, f"album_{album_id}_aio")

        buttons = [
            [IButton("Cover Arts", url=coverlist_url)],
            [IButton("List Songs", url=songlist_url)],
            [IButton("All-In-One Lyrics (PDF, ...)", url=aio_url)],
            search_more
        ]
        keyboard = IBKeyboard(buttons)
        answer = InlineQueryResultArticle(
            id=uuid4(),
            title=text,
            thumb_url=album['cover_art_thumbnail_url'],
            input_message_content=InputTextMessageContent(answer_text),
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


def search_artists(update, context):
    text = update.inline_query.query

    search_more = [IButton(
        text='Search artists...',
        switch_inline_query_current_chat='.artist ')
    ]

    res = genius.search_artists(text, per_page=10)
    articles = []
    for i, hit in enumerate(res['sections'][0]['hits']):
        artist = hit['result']
        text = artist['name']
        artist_id = artist['id']

        description = f"AKA {', '.join(artist['alternate_names'])}"
        answer_text = artist_caption(artist, 4096)
        songlist_ppl = create_deep_linked_url(
            username,
            f"artist_{artist_id}_songs_ppl")
        songlist_rdt = create_deep_linked_url(
            username,
            f"artist_{artist_id}_songs_rdt")
        songlist_ttl = create_deep_linked_url(
            username,
            f"artist_{artist_id}_songs_ttl")
        albumlist = create_deep_linked_url(
            username,
            f"artist_{artist_id}_albums")

        buttons = [
            [IButton("List Songs (By Popularity)", url=songlist_ppl)],
            [IButton("List Songs (By Release Date)", url=songlist_rdt)],
            [IButton("List Songs (By Title)", url=songlist_ttl)],
            [IButton("List Albums", url=albumlist)],
            search_more
        ]
        keyboard = IBKeyboard(buttons)
        answer = InlineQueryResultArticle(
            id=uuid4(),
            title=text,
            thumb_url=artist['image_url'],
            input_message_content=InputTextMessageContent(answer_text),
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


def search_songs(update, context):
    text = update.inline_query.query

    search_more = [IButton(
        text='Search Songs...',
        switch_inline_query_current_chat='.song ')
    ]

    res = genius.search_songs(text, per_page=10)
    articles = []
    for i, hit in enumerate(res['hits']):
        song = hit['result']
        title = song['title']
        artist = song['primary_artist']['name']
        text = utils.format_title(artist, title)
        song_id = song['id']

        description = 'Translation' if 'Genius' in artist else ''
        answer_text = song_caption(song, 4096)
        button_url = create_deep_linked_url(username, f'song_{song_id}')
        lyrics = [IButton(text='Lyrics', url=button_url)]
        keyboard = IBKeyboard([lyrics, search_more])
        answer = InlineQueryResultArticle(
            id=uuid4(),
            title=text,
            thumb_url=song['song_art_image_thumbnail_url'],
            input_message_content=InputTextMessageContent(answer_text),
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
