import logging
from typing import Any, Dict, List
from uuid import uuid4

import Levenshtein
from bs4 import BeautifulSoup
from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram import (
    InlineQueryResultArticle,
    InlineQueryResultPhoto,
    InputTextMessageContent,
    Update,
)
from telegram.ext import CallbackContext
from telegram.utils.helpers import create_deep_linked_url

from geniust import get_user, username, utils
from geniust.api import upload_to_imgbb
from geniust.functions.lyric_card_builder import build_lyric_card
from geniust.utils import (
    PERSIAN_CHARACTERS,
    SECTION_HEADERS,
    TRANSLATION_PARENTHESES,
    fix_section_headers,
    has_sentence,
    log,
)

logger = logging.getLogger("geniust")


@log
@get_user
def inline_menu(update: Update, context: CallbackContext) -> None:
    """Displays help for inline search"""
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["inline_menu"]

    articles = [
        InlineQueryResultArticle(
            id=str(uuid4()),
            title=text["search_albums"]["body"],
            description=text["search_albums"]["description"],
            input_message_content=InputTextMessageContent(
                text["search_albums"]["initial_caption"]
            ),
            reply_markup=IBKeyboard(
                [
                    [
                        IButton(
                            text=text["button"],
                            switch_inline_query_current_chat=".album ",
                        )
                    ]
                ]
            ),
        ),
        InlineQueryResultArticle(
            id=str(uuid4()),
            title=text["search_artists"]["body"],
            description=text["search_artists"]["description"],
            input_message_content=InputTextMessageContent(
                text["search_artists"]["initial_caption"]
            ),
            reply_markup=IBKeyboard(
                [
                    [
                        IButton(
                            text=text["button"],
                            switch_inline_query_current_chat=".artist ",
                        )
                    ]
                ]
            ),
        ),
        InlineQueryResultArticle(
            id=str(uuid4()),
            title=text["search_lyrics"]["body"],
            description=text["search_lyrics"]["description"],
            input_message_content=InputTextMessageContent(
                text["search_lyrics"]["initial_caption"]
            ),
            reply_markup=IBKeyboard(
                [
                    [
                        IButton(
                            text=text["button"],
                            switch_inline_query_current_chat=".lyrics ",
                        )
                    ]
                ]
            ),
        ),
        InlineQueryResultArticle(
            id=str(uuid4()),
            title=text["search_songs"]["body"],
            description=text["search_songs"]["description"],
            input_message_content=InputTextMessageContent(
                text["search_songs"]["initial_caption"]
            ),
            reply_markup=IBKeyboard(
                [
                    [
                        IButton(
                            text=text["button"],
                            switch_inline_query_current_chat=".song ",
                        )
                    ]
                ]
            ),
        ),
        InlineQueryResultArticle(
            id=str(uuid4()),
            title=text["search_users"]["body"],
            description=text["search_users"]["description"],
            input_message_content=InputTextMessageContent(
                text["search_users"]["initial_caption"]
            ),
            reply_markup=IBKeyboard(
                [
                    [
                        IButton(
                            text=text["button"],
                            switch_inline_query_current_chat=".user ",
                        )
                    ]
                ]
            ),
        ),
        InlineQueryResultArticle(
            id=str(uuid4()),
            title=text["lyric_card"]["body"],
            description=text["lyric_card"]["description"],
            input_message_content=InputTextMessageContent(
                text["lyric_card"]["initial_caption"]
            ),
            reply_markup=IBKeyboard(
                [
                    [
                        IButton(
                            text=text["button"],
                            switch_inline_query_current_chat=".lyric_card ",
                        )
                    ]
                ]
            ),
        ),
    ]

    update.inline_query.answer(articles)


@log
@get_user
def search_albums(update: Update, context: CallbackContext) -> None:
    """Displays a list of album names based on user input"""
    genius = context.bot_data["genius"]
    language = context.user_data["bot_lang"]
    texts = context.bot_data["texts"][language]
    text = texts["inline_menu"]["search_albums"]
    input_text = update.inline_query.query.split(".album ")
    input_text = input_text[1].strip() if len(input_text) > 1 else None
    if not input_text:
        return

    search_more = [
        IButton(
            text=f"...{text['body']}...", switch_inline_query_current_chat=".album "
        )
    ]

    res = genius.search_albums(input_text, per_page=10)
    articles = []
    for hit in res["sections"][0]["hits"][:10]:
        album = hit["result"]
        name = album["name"]
        artist = album["artist"]["name"]
        title = utils.format_title(artist, name)
        album_id = album["id"]

        if "Genius" in artist:
            description = texts["inline_menu"]["translation"]
        else:
            description = ""
        answer_text = album_caption(update, context, album, text["caption"])
        album_url = create_deep_linked_url(username, f"album_{album_id}_genius")
        cover_url = create_deep_linked_url(username, f"album_{album_id}_covers")
        songlist_url = create_deep_linked_url(username, f"album_{album_id}_tracks")
        aio_url = create_deep_linked_url(username, f"album_{album_id}_lyrics")

        buttons = [
            [IButton(texts["inline_menu"]["full_details"], url=album_url)],
            [IButton(texts["display_album"]["cover_arts"], url=cover_url)],
            [IButton(texts["display_album"]["tracks"], url=songlist_url)],
            [IButton(texts["display_album"]["lyrics"], url=aio_url)],
            search_more,
        ]
        keyboard = IBKeyboard(buttons)
        answer = InlineQueryResultArticle(
            id=str(uuid4()),
            title=title,
            thumb_url=album["cover_art_thumbnail_url"],
            input_message_content=InputTextMessageContent(
                answer_text, disable_web_page_preview=False
            ),
            reply_markup=keyboard,
            description=description,
        )
        # It's possible to provide results that are captioned photos
        # of the song cover art, but that requires using InlineQueryResultPhoto
        # and user might not be able to choose the right song this way,
        # since all they get is only the cover arts of the hits.
        # answer = InlineQueryResultPhoto(id=str(uuid4()),
        #    photo_url=search_hit['song_art_image_url'],
        #    thumb_url=search_hit['song_art_image_thumbnail_url'],
        #    reply_markup=keyboard, description=description)
        articles.append(answer)

    update.inline_query.answer(articles)


@log
@get_user
def search_artists(update: Update, context: CallbackContext) -> None:
    """Displays a list of artist names based on user input"""
    genius = context.bot_data["genius"]
    language = context.user_data["bot_lang"]
    texts = context.bot_data["texts"][language]
    text = texts["inline_menu"]["search_artists"]
    input_text = update.inline_query.query.split(".artist ")
    input_text = input_text[1].strip() if len(input_text) > 1 else None
    if not input_text:
        return

    search_more = [
        IButton(
            text=f"...{text['body']}...", switch_inline_query_current_chat=".artist "
        )
    ]

    res = genius.search_artists(input_text, per_page=10)
    articles = []
    for hit in res["sections"][0]["hits"][:10]:
        artist = hit["result"]
        title = artist["name"]
        artist_id = artist["id"]

        answer_text = artist_caption(update, context, artist, text["caption"], language)
        artist_url = create_deep_linked_url(username, f"artist_{artist_id}_genius")
        songlist_ppl = create_deep_linked_url(
            username, f"artist_{artist_id}_songs_ppt_1"
        )
        songlist_rdt = create_deep_linked_url(
            username, f"artist_{artist_id}_songs_rdt_1"
        )
        songlist_ttl = create_deep_linked_url(
            username, f"artist_{artist_id}_songs_ttl_1"
        )
        albumlist = create_deep_linked_url(username, f"artist_{artist_id}_albums")

        button_text = texts["display_artist"]
        buttons = [
            [IButton(texts["inline_menu"]["full_details"], url=artist_url)],
            [IButton(button_text["songs_by_popularity"], url=songlist_ppl)],
            [IButton(button_text["songs_by_release_data"], url=songlist_rdt)],
            [IButton(button_text["songs_by_title"], url=songlist_ttl)],
            [IButton(button_text["albums"], url=albumlist)],
            search_more,
        ]
        keyboard = IBKeyboard(buttons)
        answer = InlineQueryResultArticle(
            id=str(uuid4()),
            title=title,
            thumb_url=artist["image_url"],
            input_message_content=InputTextMessageContent(
                answer_text, disable_web_page_preview=False
            ),
            reply_markup=keyboard,
            # description=description
        )
        # It's possible to provide results that are captioned photos
        # of the song cover art, but that requires using InlineQueryResultPhoto
        # and user might not be able to choose the right song this way,
        # since all they get is only the cover arts of the hits.
        # answer = InlineQueryResultPhoto(id=str(uuid4()),
        #    photo_url=search_hit['song_art_image_url'],
        #    thumb_url=search_hit['song_art_image_thumbnail_url'],
        #    reply_markup=keyboard, description=description)
        articles.append(answer)

    update.inline_query.answer(articles)


@log
@get_user
def search_lyrics(update: Update, context: CallbackContext) -> None:
    """Displays a list of song titles based on user input"""
    genius = context.bot_data["genius"]
    language = context.user_data["bot_lang"]
    texts = context.bot_data["texts"][language]
    text = texts["inline_menu"]["search_lyrics"]
    input_text = update.inline_query.query.split(".lyrics ")
    input_text = input_text[1].strip() if len(input_text) > 1 else None
    if not input_text:
        return

    search_more = [
        IButton(
            text=f"...{text['body']}...", switch_inline_query_current_chat=".lyrics "
        )
    ]

    res = genius.search_lyrics(input_text, per_page=10)
    articles = []
    for hit in res["sections"][0]["hits"][:10]:
        song = hit["result"]
        title = song["title"]
        artist = song["primary_artist"]["name"]
        answer_title = utils.format_title(artist, title)
        song_id = song["id"]

        answer_text = song_caption(update, context, song, text["caption"], language)
        song_url = create_deep_linked_url(username, f"song_{song_id}_genius")
        lyrics_url = create_deep_linked_url(username, f"song_{song_id}_lyrics")
        buttons = [
            [IButton(texts["inline_menu"]["full_details"], url=song_url)],
            [IButton(texts["display_song"]["lyrics"], url=lyrics_url)],
            search_more,
        ]
        keyboard = IBKeyboard(buttons)
        answer = InlineQueryResultArticle(
            id=str(uuid4()),
            title=answer_title,
            thumb_url=song["song_art_image_thumbnail_url"],
            input_message_content=InputTextMessageContent(
                answer_text, disable_web_page_preview=False
            ),
            reply_markup=keyboard,
            description=hit["highlights"][0]["value"],
        )
        # It's possible to provide results that are captioned photos
        # of the song cover art, but that requires using InlineQueryResultPhoto
        # and user might not be able to choose the right song this way,
        # since all they get is only the cover arts of the hits.
        # answer = InlineQueryResultPhoto(id=str(uuid4()),
        #    photo_url=search_hit['song_art_image_url'],
        #    thumb_url=search_hit['song_art_image_thumbnail_url'],
        #    reply_markup=keyboard, description=description)
        articles.append(answer)

    update.inline_query.answer(articles)


@log
@get_user
def search_songs(update: Update, context: CallbackContext) -> None:
    """Displays a list of song titles based on user input"""
    genius = context.bot_data["genius"]
    language = context.user_data["bot_lang"]
    texts = context.bot_data["texts"][language]
    text = texts["inline_menu"]["search_songs"]
    input_text = update.inline_query.query.split(".song ")
    input_text = input_text[1].strip() if len(input_text) > 1 else None
    if not input_text:
        return

    search_more = [
        IButton(text=f"...{text['body']}...", switch_inline_query_current_chat=".song ")
    ]

    res = genius.search_songs(input_text, per_page=10)
    articles = []
    for hit in res["sections"][0]["hits"][:10]:
        song = hit["result"]
        title = song["title"]
        artist = song["primary_artist"]["name"]
        answer_title = utils.format_title(artist, title)
        song_id = song["id"]

        if "Genius" in song["full_title"]:
            description = texts["inline_menu"]["translation"]
        else:
            description = ""
        answer_text = song_caption(update, context, song, text["caption"], language)
        song_url = create_deep_linked_url(username, f"song_{song_id}_genius")
        lyrics_url = create_deep_linked_url(username, f"song_{song_id}_lyrics")
        buttons = [
            [IButton(texts["inline_menu"]["full_details"], url=song_url)],
            [IButton(texts["display_song"]["lyrics"], url=lyrics_url)],
            search_more,
        ]
        keyboard = IBKeyboard(buttons)
        answer = InlineQueryResultArticle(
            id=str(uuid4()),
            title=answer_title,
            thumb_url=song["song_art_image_thumbnail_url"],
            input_message_content=InputTextMessageContent(
                answer_text, disable_web_page_preview=False
            ),
            reply_markup=keyboard,
            description=description,
        )
        # It's possible to provide results that are captioned photos
        # of the song cover art, but that requires using InlineQueryResultPhoto
        # and user might not be able to choose the right song this way,
        # since all they get is only the cover arts of the hits.
        # answer = InlineQueryResultPhoto(id=str(uuid4()),
        #    photo_url=search_hit['song_art_image_url'],
        #    thumb_url=search_hit['song_art_image_thumbnail_url'],
        #    reply_markup=keyboard, description=description)
        articles.append(answer)

    update.inline_query.answer(articles)


@log
@get_user
def search_users(update: Update, context: CallbackContext) -> None:
    """Displays a list of usernames based on user input"""
    genius = context.bot_data["genius"]
    language = context.user_data["bot_lang"]
    texts = context.bot_data["texts"][language]
    text = texts["inline_menu"]["search_users"]
    input_text = update.inline_query.query.split(".user ")
    input_text = input_text[1].strip() if len(input_text) > 1 else None
    if not input_text:
        return

    search_more = [
        IButton(text=f"...{text['body']}...", switch_inline_query_current_chat=".user ")
    ]

    res = genius.search_users(input_text, per_page=10)
    articles = []
    for hit in res["sections"][0]["hits"][:10]:
        user = hit["result"]
        user_username = user["name"]
        user_id = user["id"]

        answer_text = user_caption(update, context, user, text["caption"], language)
        user_url = create_deep_linked_url(username, f"user_{user_id}")
        description_url = create_deep_linked_url(
            username, f"user_{user_id}_description"
        )
        header_url = create_deep_linked_url(username, f"user_{user_id}_header")
        buttons = [
            [IButton(texts["inline_menu"]["full_details"], url=user_url)],
            [
                IButton(texts["display_user"]["description"], url=description_url),
                IButton(texts["display_user"]["header"], url=header_url),
            ],
            search_more,
        ]
        keyboard = IBKeyboard(buttons)
        answer = InlineQueryResultArticle(
            id=str(uuid4()),
            title=user_username,
            thumb_url=user["avatar"]["thumb"]["url"],
            input_message_content=InputTextMessageContent(
                answer_text, disable_web_page_preview=False
            ),
            reply_markup=keyboard,
            description=user["about_me_summary"],
        )
        # It's possible to provide results that are captioned photos
        # of the song cover art, but that requires using InlineQueryResultPhoto
        # and user might not be able to choose the right song this way,
        # since all they get is only the cover arts of the hits.
        # answer = InlineQueryResultPhoto(id=str(uuid4()),
        #    photo_url=search_hit['song_art_image_url'],
        #    thumb_url=search_hit['song_art_image_thumbnail_url'],
        #    reply_markup=keyboard, description=description)
        articles.append(answer)

    update.inline_query.answer(articles)


@log
@get_user
def lyric_card(update: Update, context: CallbackContext) -> None:
    """Displays a list of lyric cards based on lyrics provided by the user"""

    def add_photo(lyrics):
        """Builds the lyric card, uploads it and adds it to the inline results"""
        lyric_card = build_lyric_card(
            cover_art=cover_art,
            lyrics=lyrics,
            song_title=title,
            primary_artists=primary_artists,
            featured_artists=featured_artists,
            rtl_lyrics=is_persian,
            rtl_metadata=False,
            format="JPEG",
        )
        uploaded_photo = upload_to_imgbb(lyric_card)["data"]
        photo = InlineQueryResultPhoto(
            id=str(uuid4()),
            photo_url=uploaded_photo["url"],
            thumb_url=uploaded_photo["thumb"]["url"],
            photo_width=lyric_card.size[0],
            photo_height=lyric_card.size[1],
            caption=f"@{username}",
            reply_markup=keyboard,
        )
        photos.append(photo)

    genius = context.bot_data["genius"]
    language = context.user_data["bot_lang"]
    texts = context.bot_data["texts"][language]
    text = texts["inline_menu"]["lyric_card"]
    input_text = update.inline_query.query.split(".lyric_card ")
    input_text = input_text[1].strip() if len(input_text) > 1 else None
    if not input_text:
        return

    search_more = [
        IButton(
            text=f"...{text['new']}...",
            switch_inline_query_current_chat=".lyric_card ",
        )
    ]
    keyboard = IBKeyboard([search_more])

    res = genius.search_lyrics(input_text, per_page=5)
    photos: List[InlineQueryResultPhoto] = []
    found_lyrics = []
    for hit in res["sections"][0]["hits"]:
        highlight = hit["highlights"][0]
        for line in highlight["value"].split("\n"):
            if Levenshtein.ratio(input_text, line) > 0.5:
                found_lyrics.append(line)
        if found_lyrics:
            break
    else:
        update.inline_query.answer(photos)
        return

    song_page_data = genius.page_data(song_id=hit["result"]["id"])["page_data"]
    song = song_page_data["song"]
    song_lyrics = (
        BeautifulSoup(song_page_data["lyrics_data"]["body"]["html"], "html.parser")
        .get_text()
        .strip()
    )
    song_lyrics = fix_section_headers(song_lyrics)
    song_lyrics = SECTION_HEADERS.sub("", song_lyrics)
    song_lyrics = song_lyrics.split("\n")

    lyrics = []
    for line in song_lyrics:
        for found_line in found_lyrics:
            if Levenshtein.ratio(found_line, line) > 0.8:
                lyrics.append(line)
                break
        if len(lyrics) == len(found_lyrics):
            break
    lyrics = "\n".join(lyrics)

    # Get song metadata
    title = song["title"]
    primary_artists = song["primary_artist"]["name"].split(" & ")
    featured_artists = [x["name"] for x in song["featured_artists"]]
    if primary_artists[0].startswith("Genius") and featured_artists == []:
        title = TRANSLATION_PARENTHESES.sub("", title).strip()
        artists, title = [x.strip() for x in title.split("-")]
        primary_artists.clear()
        primary_artists.extend(artists.split(" & "))

    cover_art_url = song["song_art_image_url"]
    cover_art = genius.download_cover_art(cover_art_url)
    is_persian = bool(PERSIAN_CHARACTERS.search(lyrics))

    add_photo(lyrics)

    update.inline_query.answer(photos, cache_time=3600)


def album_caption(
    update: Update, context: CallbackContext, album: Dict[str, Any], caption: str
) -> str:
    """Generates caption for album.

    Args:
        update (Update): Update object to make the update available
            to the error handler in case of errors.
        context (CallbackContext): Update object to make the context available
            to the error handler in case of errors.
        album (Dict[str, Any]): Album data.
        caption (str): Caption template.

    Returns:
        str: Formatted caption.
    """
    release_date = album["release_date_components"]
    if release_date is not None:
        year = release_date.get("year")
        month = release_date.get("month")
        day = release_date.get("day")
        components = [year, month, day]
        release_date = "-".join(str(x) for x in components if x is not None)
    else:
        release_date = "?"

    string = (
        caption.replace("{name}", album["name"])
        .replace("{artist_name}", album["artist"]["name"])
        .replace(
            "{artist}",
            utils.deep_link(
                album["artist"]["name"], album["artist"]["id"], "artist", "genius"
            ),
        )
        .replace("{release_date}", release_date)
        .replace("{url}", album["url"])
        .replace("{image_url}", album["cover_art_url"])
    )

    return string.strip()


@log
def artist_caption(
    update: Update,
    context: CallbackContext,
    artist: Dict[str, Any],
    caption: str,
    language: str,
) -> str:
    """Generates caption for artist.

    Args:
        update (Update): Update object to make the update available
            to the error handler in case of errors.
        context (CallbackContext): Update object to make the context available
            to the error handler in case of errors and provide language
            equivalent for True and False ('Yes' and 'No' for English).
        artist (Dict[str, Any]): Artist data.
        caption (str): Caption template.
        language (str): User's bot language.

    Returns:
        str: Formatted caption.
    """
    is_verified = context.bot_data["texts"][language][artist["is_verified"]]

    string = (
        caption.replace("{name}", artist["name"])
        .replace("{url}", artist["url"])
        .replace("{verified}", is_verified)
        .replace("{image_url}", artist["image_url"])
    )

    return string.strip()


@log
def song_caption(
    update: Update,
    context: CallbackContext,
    song: Dict[str, Any],
    caption: str,
    language,
) -> str:
    """Generates caption for artist.

    Args:
        update (Update): Update object to make the update available
            to the error handler in case of errors.
        context (CallbackContext): Update object to make the context available
            to the error handler in case of errors and provide language
            equivalent for True and False ('Yes' and 'No' for English).
        song (Dict[str, Any]): Song data.
        caption (str): Caption template.
        language (str): User's bot language.

    Returns:
        str: Formatted caption.
    """
    hot = context.bot_data["texts"][language][song["stats"]["hot"]]
    instrumental = context.bot_data["texts"][language][song["instrumental"]]
    artist = song["primary_artist"]
    views = song["stats"].get("pageviews", "?")

    string = (
        caption.replace("{title}", song["title"])
        .replace("{artist_name}", song["primary_artist"]["name"])
        .replace(
            "{artist}",
            utils.deep_link(artist["name"], artist["id"], "artist", "genius"),
        )
        .replace("{hot}", hot)
        .replace(
            "{views}", utils.human_format(views) if isinstance(views, int) else views
        )
        .replace("{instrumental}", instrumental)
        .replace("{url}", song["url"])
        .replace("{image_url}", song["song_art_image_url"])
    )

    return string.strip()


@log
def user_caption(
    update: Update,
    context: CallbackContext,
    user: Dict[str, Any],
    caption: str,
    language: str,
) -> str:
    """Generates caption for user data.

    Args:
        update (Update): Update object to make the update available
            to the error handler in case of errors.
        context (CallbackContext): Update object to make the context available
            to the error handler in case of errors.
        user (Dict[str, Any]): User data.
        caption (str): Caption template.
        language (str): User's bot language.

    Returns:
        str: Formatted caption.
    """
    if (role := user["human_readable_role_for_display"]) is None:
        role = context.bot_data["texts"][language]["none"]
    string = (
        caption.replace("{name}", user["name"])
        .replace("{iq}", utils.human_format(user["iq"]))
        .replace("{url}", user["url"])
        .replace("{role}", role)
        .replace("{image_url}", user["avatar"]["medium"]["url"])
    )
    return string
