import logging
import re
from functools import partial
from typing import Any

from bs4 import BeautifulSoup
from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram import Update
from telegram.ext import CallbackContext
from telethon.extensions import html
from telethon.utils import split_text

from geniust import get_user, username, utils
from geniust.constants import DEVELOPERS, END, TYPING_LYRICS, TYPING_SONG
from geniust.utils import log

logger = logging.getLogger("geniust")


@log
@get_user
def type_lyrics(update: Update, context: CallbackContext) -> int:
    """Prompts user to type lyrics"""
    # user has entered the function through the main menu
    language = context.user_data["bot_lang"]
    msg = context.bot_data["texts"][language]["type_lyrics"]

    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.edit_message_text(msg)
    else:
        if context.args:
            update.message.text = " ".join(context.args)
            search_lyrics(update, context)
            return END
        update.message.reply_text(msg)

    return TYPING_LYRICS


@log
@get_user
def type_song(update: Update, context: CallbackContext) -> int:
    """Prompts user to type song title"""
    # user has entered the function through the main menu
    language = context.user_data["bot_lang"]
    msg = context.bot_data["texts"][language]["type_song"]

    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.edit_message_text(msg)
    else:
        if context.args:
            update.message.text = " ".join(context.args)
            search_songs(update, context)
            return END
        update.message.reply_text(msg)

    return TYPING_SONG


@log
@get_user
def search_lyrics(update: Update, context: CallbackContext) -> int:
    """Displays a list of song titles based on user input"""
    genius = context.bot_data["genius"]
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["search_lyrics"]
    input_text = update.message.text

    # get <= 10 hits for user input from Genius API search
    json_search = genius.search_lyrics(input_text)
    caption = ""
    for i, hit in enumerate(json_search["sections"][0]["hits"][:10]):
        song = hit["result"]
        title = song["title"]
        artist = song["primary_artist"]["name"]
        full_title = utils.format_title(artist, title)
        full_title = utils.deep_link(full_title, song["id"], "song", "genius")
        highlight = hit["highlights"][0]["value"]

        caption += f'''\n\n◽️{i + 1}. {full_title}\n"{highlight}"'''

    if caption:
        update.message.reply_text(caption)
    else:
        update.message.reply_text(text["no_lyrics"])
    return END


@log
@get_user
def search_songs(update: Update, context: CallbackContext) -> int:
    """Displays a list of song titles based on user input"""
    genius = context.bot_data["genius"]
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["search_songs"]
    input_text = update.message.text

    # get <= 10 hits for user input from Genius API search
    json_search = genius.search_songs(input_text)
    buttons = []
    for hit in json_search["sections"][0]["hits"][:10]:
        song = hit["result"]
        title = song["title"]
        artist = song["primary_artist"]["name"]
        title = utils.format_title(artist, title)
        callback = f"song_{song['id']}_genius"

        buttons.append([IButton(text=title, callback_data=callback)])

    if buttons:
        update.message.reply_text(text["choose"], reply_markup=IBKeyboard(buttons))
    else:
        update.message.reply_text(text["no_songs"])
    return END


@log
@get_user
def display_song(update: Update, context: CallbackContext) -> int:
    """Displays song"""
    language = context.user_data["bot_lang"]
    spotify = context.bot_data["spotify"]
    text = context.bot_data["texts"][language]["display_song"]
    bot = context.bot
    genius = context.bot_data["genius"]
    chat_id = update.effective_chat.id
    recommender = context.bot_data["recommender"]

    if update.callback_query:
        _, song_id_str, platform = update.callback_query.data.split("_")
        update.callback_query.answer()
        update.callback_query.message.delete()
    else:
        _, song_id_str, platform = context.args[0].split("_")

    preview_url = None
    download_url = None
    if platform == "genius":
        genius_id = int(song_id_str)
        spotify_id = None
    else:
        if platform == "spotify":
            spotify_id = song_id_str
            song = spotify.track(spotify_id)
            preview_url = song.preview_url
            download_url = None
            song_name = song.name
            song_artist = song.artists[0].name
            song_id = song.id
        else:
            song = recommender.song(int(song_id_str))
            preview_url = song.preview_url
            download_url = song.download_url
            song_name = song.name
            song_artist = song.artist
            song_id = song.id
            spotify_id = None
        search = genius.search_songs(song_name, match=(song_artist, song.name))
        if search["match"] is not None:
            genius_id = search["match"]["id"]
        else:
            song_url = download_url if download_url else preview_url
            logger.debug("Song %s not found. Sending audio %s", song_id, song_url)
            context.bot.send_audio(
                chat_id,
                song_url,
                performer=song_artist,
                title=song_name,
                caption=f"@{username}",
            )
            return END

    song = genius.song(genius_id)["song"]
    cover_art = song["song_art_image_url"]
    caption = song_caption(update, context, song, text["caption"], language)

    callback_data = f"song_{song['id']}_lyrics"
    buttons = [[IButton(text["lyrics"], callback_data=callback_data)]]

    if song["description_annotation"]["annotations"][0]["body"]["plain"]:
        annotation_id = song["description_annotation"]["id"]
        button = IButton(
            text["description"], callback_data=f"annotation_{annotation_id}"
        )
        buttons[0].append(button)

    if preview_url:
        callback = "song_{song_id}_{platform}_preview".format(
            song_id=song_id,
            platform="spotify" if spotify_id else "recommender",
        )
        buttons.append(
            [
                IButton(
                    text["preview"],
                    callback_data=callback,
                )
            ]
        )

    if download_url:
        buttons.append(
            [
                IButton(
                    text["download"],
                    callback_data=f"song_{song_id}_recommender_download",
                )
            ]
        )
    else:
        if spotify_id is None:
            artist = song["primary_artist"]["name"]
            title = song["title"].replace("\u200b", "")
            query = f"{title} artist:{artist}"
            spotify_search = spotify.search(query, types=("track",), limit=5)[0]
            for track in spotify_search.items:
                if title in track.name and artist == track.artists[0].name:
                    spotify_id = track.id
        if spotify_id:
            buttons.append(
                [
                    IButton(
                        text["download"],
                        url=f"http://t.me/acutebot?start=music_{spotify_id}",
                    )
                ]
            )

    bot.send_photo(chat_id, cover_art, caption, reply_markup=IBKeyboard(buttons))

    return END


@log
@get_user
def download_song(update: Update, context: CallbackContext) -> int:
    """Displays song"""
    bot = context.bot
    chat_id = update.effective_chat.id
    recommender = context.bot_data["recommender"]
    spotify = context.bot_data["spotify"]

    if update.callback_query:
        _, song_id_str, platform, type = update.callback_query.data.split("_")
        update.callback_query.answer()
    else:
        _, song_id_str, platform, type = context.args[0].split("_")

    if platform == "recommender":
        song = recommender.song(int(song_id_str))
        song_url = song.download_url if type == "download" else song.preview_url
        artist = song.artist
        name = song.name
    else:
        song = spotify.track(song_id_str)
        song_url = song.preview_url
        artist = " & ".join([artist.name for artist in song.artists])
        name = song.name

    bot.send_audio(
        chat_id, song_url, performer=artist, title=name, caption=f"@{username}"
    )

    return END


@log
@get_user
def display_lyrics(update: Update, context: CallbackContext) -> int:
    """Retrieves and sends song lyrics to user"""

    if update.callback_query:
        update.callback_query.answer()
        song_id = int(update.callback_query.data.split("_")[1])
    else:
        song_id = int(context.args[0].split("_")[1])

    user_data = context.user_data
    bot = context.bot
    chat_id = update.effective_user.id
    genius_t = context.bot_data["genius"]
    genius = context.bot_data["lyricsgenius"]
    language = context.user_data["bot_lang"]
    texts = context.bot_data["texts"][language]["display_lyrics"]

    lyrics_language = user_data["lyrics_lang"]
    include_annotations = user_data["include_annotations"] and chat_id in DEVELOPERS
    logger.debug(f"{lyrics_language} | {include_annotations} | {song_id}")

    song = genius_t.song(song_id)["song"]
    song_url = song["url"]

    if song["lyrics_placeholder_reason"]:
        reason = song["lyrics_placeholder_reason"]
        text = texts.get(reason)
        if text is None:
            logger.error(
                "Couldn't find placeholder text for incomplete lyrics. "
                "Song ID: %d - Reason: %s",
                song["id"],
                reason,
            )
            text = reason
        bot.send_message(chat_id, text)
        return END

    try:
        lyrics = genius_t.lyrics(
            song_id=song_id,
            song_url=song_url,
            include_annotations=include_annotations,
            telegram_song=True,
        )
    except Exception:
        logger.exception("Error when retrieving lyrics for %d", song_id)
        lyrics = genius.lyrics(song_url=song_url)

    # formatting lyrics language
    # lyrics = BeautifulSoup(lyrics, "html.parser")
    lyrics = utils.format_language(lyrics, lyrics_language)
    lyrics = utils.remove_unsupported_tags(lyrics)
    lyrics = re.sub(r"<[/]*(br|div|p).*[/]*?>", "", str(lyrics))
    # This adds a newline wherever the next section is separated from
    # the previous section with only one newline.
    lyrics = utils.fix_section_headers(lyrics)

    def to_dict(entity):
        """Converts entity to a dict that is compatible with PTB"""
        dic = entity.dict
        dic["type"] = entity.type
        dic.pop("_", None)
        return dic

    for text, entities in split_text(
        *html.parse(lyrics), limit=4096, split_at=(r"\n\n", r"\n")
    ):
        for entity in entities:
            entity.dict = entity.to_dict()
            entity.type = utils.MESSAGE_ENTITY_TYPES[entity.dict["_"]]
            entity.to_dict = partial(to_dict, entity=entity)
        bot.send_message(
            chat_id,
            text,
            entities=entities,
            parse_mode=None,  # If it's set, Telegram will ignore the entities.
            # And since we've set a default for it in bot.py,
            # here we have to override and set to None.
        )
    return END


@log
def song_caption(
    Update: Update,
    context: CallbackContext,
    song,
    caption,
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
    release_date = ""
    features = ""
    album = ""
    producers = ""
    writers = ""
    relationships: Any = ""
    tags = ""

    if song.get("release_date"):
        release_date = song["release_date_for_display"]

    if song.get("featured_artists"):
        features = ", ".join(
            [
                utils.deep_link(x["name"], x["id"], "artist", "genius")
                for x in song["featured_artists"]
            ]
        )
        features = caption["features"].replace("{}", features)

    if song.get("albums"):
        album = ", ".join(
            utils.deep_link(album["name"], album["id"], "album", "genius")
            for album in song["albums"]
        )
        album = caption["albums"].replace("{}", album)

    if song.get("producer_artists"):
        producers = ", ".join(
            [
                utils.deep_link(x["name"], x["id"], "artist", "genius")
                for x in song["producer_artists"]
            ]
        )
        producers = caption["producers"].replace("{}", producers)

    if song.get("writer_artists"):
        writers = ", ".join(
            [
                utils.deep_link(x["name"], x["id"], "artist", "genius")
                for x in song["writer_artists"]
            ]
        )
        writers = caption["writers"].replace("{}", writers)

    if song.get("song_relationships"):
        relationships = []
        for relation in [x for x in song["song_relationships"] if x["songs"]]:
            if relation["type"] in caption:
                type_ = caption[relation["type"]]
            else:
                type_ = " ".join([x.capitalize() for x in relation["type"].split("_")])
            songs = ", ".join(
                [
                    utils.deep_link(x["title"], x["id"], "song", "genius")
                    for x in relation["songs"]
                ]
            )
            string = f"\n<b>{type_}</b>:\n{songs}"

            relationships.append(string)
        relationships = "".join(relationships)

    genius_url = f"""<a href="{song['url']}">Genius</a>"""
    external_links = caption["external_links"].replace("{}", genius_url)
    if song.get("media"):
        media = []
        for m in [x for x in song["media"]]:
            provider = m["provider"].capitalize()
            url = m["url"]
            string = f"""<a href="{url}">{provider}</a>"""

            media.append(string)
        external_links += " | " + " | ".join(media)

    hot = context.bot_data["texts"][language][song["stats"]["hot"]]

    tags = (
        ", ".join(caption.get(tag["name"].lower(), tag["name"]) for tag in song["tags"])
        if song["tags"]
        else ""
    )

    views = song["stats"].get("pageviews", "?")
    if isinstance(views, int):
        views = utils.human_format(views)
    artist = song["primary_artist"]

    string = (
        caption["body"]
        .replace("{title}", song["title"])
        .replace("{artist_name}", song["primary_artist"]["name"])
        .replace(
            "{artist}",
            utils.deep_link(artist["name"], artist["id"], "artist", "genius"),
        )
        .replace("{release_date}", release_date)
        .replace("{hot}", hot)
        .replace("{tags}", tags)
        .replace("{views}", views)
        + features
        + album
        + producers
        + writers
        + external_links
        + relationships
    )
    string = string.strip()

    return check_length(string)


def check_length(caption: str, limit: int = 1024) -> str:
    """checks length of message against Telegram limits

    Args:
        caption (str): Message string.
        limit (int, optional): Message length limit. Defaults to 1024.

    Returns:
        str: If caption length minus entities if more than the limit,
            removes info till message length is within limits. Each <b> denotes
            one piece of info (e.g. contributing artists).
    """
    soup = BeautifulSoup(caption, "html.parser")
    text = soup.get_text()
    length = len(text)

    while length >= limit:
        caption = caption[: caption.rfind("<b>") - 3]
        soup = BeautifulSoup(caption, "html.parser")
        length = len(soup.get_text())

    return str(soup)
