import logging
import threading
import re
from typing import Dict, Any

from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram import Update
from telegram.ext import CallbackContext
from telegram.constants import MAX_MESSAGE_LENGTH
from bs4 import BeautifulSoup

from geniust.constants import END, TYPING_SONG
from geniust import utils, api
from geniust import get_user
from geniust.utils import log


logger = logging.getLogger('geniust')


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
        update.message.reply_text(msg)

    return TYPING_SONG


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

    if update.callback_query:
        _, song_id_str, platform = update.callback_query.data.split("_")
        update.callback_query.answer()
        update.callback_query.edit_message_reply_markup(None)
    else:
        _, song_id_str, platform = context.args[0].split("_")

    if platform == 'genius':
        song_id = int(song_id_str)
    else:
        song_id = song_id_str

    if platform == 'spotify':
        song = spotify.song(song_id)
        search = genius.search_songs(song.name, match=(song.artists[0], song.name))
        if search['match'] is not None:
            song_id = search['match']['id']
        else:
            context.bot.send_message(chat_id, text['not_found'])
            return END

    song = genius.song(song_id)["song"]
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

    bot.send_photo(chat_id, cover_art, caption, reply_markup=IBKeyboard(buttons))

    return END


@log
@get_user
def download_song(update: Update, context: CallbackContext) -> int:
    """Displays song"""
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["display_song"]
    bot = context.bot
    famusic = context.bot_data["famusic"]
    chat_id = update.effective_chat.id

    if update.callback_query:
        _, song_id_str, platform, _ = update.callback_query.data.split("_")
        update.callback_query.answer()
        update.callback_query.edit_message_reply_markup(None)
    else:
        _, song_id_str, platform, _ = context.args[0].split("_")

    song_id = int(song_id_str)
    song_url = famusic.download_url(song_id, platform)

    if song_url is None:
        bot.send_message(chat_id, text['not_found'])
    else:
        bot.send_audio(chat_id, song_url)

    return END


@log
def display_lyrics(
    update: Update, context: CallbackContext, song_id: int, text: Dict[str, str]
) -> None:
    """Retrieves and sends song lyrics to user

    Args:
        update (Update): Update object.
        context (CallbackContext): User data, texts and etc.
        song_id (int): Genius song ID.
        text (Dict[str, str]): Texts to inform user of the progress.
    """
    user_data = context.user_data
    bot = context.bot
    chat_id = update.effective_chat.id

    genius_t = api.GeniusT()

    lyrics_language = user_data["lyrics_lang"]
    include_annotations = user_data["include_annotations"]

    logger.debug(f"{lyrics_language} | {include_annotations} | {song_id}")

    message_id = bot.send_message(chat_id=chat_id, text=text)["message_id"]

    lyrics = genius_t.lyrics(
        song_id=song_id,
        song_url=genius_t.song(song_id)["song"]["url"],
        include_annotations=include_annotations,
        telegram_song=True,
    )

    # formatting lyrics language
    lyrics = BeautifulSoup(lyrics, "html.parser")
    lyrics = utils.format_language(lyrics, lyrics_language)
    lyrics = utils.remove_unsupported_tags(lyrics)
    lyrics = re.sub(r"<[/]*(br|div|p).*[/]*?>", "", str(lyrics))

    bot.delete_message(chat_id=chat_id, message_id=message_id)

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
        string = lyrics[i * max_length : (i * max_length) + max_length]
        a_start = string.count("<a")
        a_end = string.count("</a>")
        if a_start != a_end:
            a_pos = string.rfind("<a")
            string = string[:a_pos]
        bot.send_message(chat_id, string)
        sent += len(string)
        i += 1


@log
@get_user
def thread_display_lyrics(update: Update, context: CallbackContext) -> int:
    """Creates a thread to get the song"""
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["display_lyrics"]

    if update.callback_query:
        update.callback_query.answer()
        song_id = int(update.callback_query.data.split("_")[1])
    else:
        song_id = int(context.args[0].split("_")[1])

    # get and send song to user
    p = threading.Thread(
        target=display_lyrics,
        args=(
            update,
            context,
            song_id,
            text,
        ),
    )
    p.start()
    p.join()
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
        features = ", ".join([utils.deep_link(x['name'], x['id'], 'artist', 'genius') for x in song["featured_artists"]])
        features = caption["features"].replace("{}", features)

    if song.get("albums"):
        album = ", ".join(utils.deep_link(album['name'], album['id'], 'album', 'genius') for album in song["albums"])
        album = caption["albums"].replace("{}", album)

    if song.get("producer_artists"):
        producers = ", ".join([utils.deep_link(x['name'], x['id'], 'artist', 'genius') for x in song["producer_artists"]])
        producers = caption["producers"].replace("{}", producers)

    if song.get("writer_artists"):
        writers = ", ".join([utils.deep_link(x['name'], x['id'], 'artist', 'genius') for x in song["writer_artists"]])
        writers = caption["writers"].replace("{}", writers)

    if song.get("song_relationships"):
        relationships = []
        for relation in [x for x in song["song_relationships"] if x["songs"]]:
            if relation["type"] in caption:
                type_ = caption[relation["type"]]
            else:
                type_ = " ".join([x.capitalize() for x in relation["type"].split("_")])
            songs = ", ".join([utils.deep_link(x['title'], x['id'], 'song', 'genius') for x in relation["songs"]])
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
        .replace("{artist}", utils.deep_link(artist['name'], artist['id'], 'artist', 'genius'))
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
    soup = BeautifulSoup(caption, "html.parser")
    text = soup.get_text()
    length = len(text)

    while length >= limit:
        caption = caption[: caption.rfind("<b>") - 3]
        soup = BeautifulSoup(caption, "html.parser")
        length = len(soup.get_text())

    return str(soup)
