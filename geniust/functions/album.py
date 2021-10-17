import logging
import threading
from typing import Any, Dict

from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram import InputMediaPhoto, Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import CallbackContext

from geniust import api, get_user, utils
from geniust.constants import DEVELOPERS, END, TYPING_ALBUM
from geniust.utils import log

from .album_conversion import create_pages, create_pdf, create_zip

logger = logging.getLogger("geniust")


@log
@get_user
def type_album(update: Update, context: CallbackContext) -> int:
    """Prompts user to type album name"""
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["type_album"]

    # user has entered the function through the main menu
    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.edit_message_text(text)
    else:
        # If there is context.args, it means that the user
        # typed "/album query". So we don't need to ask for a query anymore.
        if context.args:
            update.message.text = " ".join(context.args)
            search_albums(update, context)
            return END
        update.message.reply_text(text)

    return TYPING_ALBUM


@log
@get_user
def search_albums(update: Update, context: CallbackContext) -> int:
    """Displays a list of album names based on user input"""
    genius = context.bot_data["genius"]
    input_text = update.message.text
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["search_albums"]

    res = genius.search_albums(input_text)

    buttons = []

    for hit in res["sections"][0]["hits"][:10]:
        album = hit["result"]
        album_id = album["id"]
        title = utils.format_title(album["artist"]["name"], album["name"])
        callback = f"album_{album_id}_genius"

        buttons.append([IButton(title, callback_data=callback)])

    if buttons:
        update.message.reply_text(text["choose"], reply_markup=IBKeyboard(buttons))
    else:
        update.message.reply_text(text["no_albums"])

    return END


@log
@get_user
def display_album(update: Update, context: CallbackContext) -> int:
    """Displays album"""
    genius = context.bot_data["genius"]
    spotify = context.bot_data["spotify"]
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["display_album"]
    bot = context.bot
    chat_id = update.effective_chat.id

    if update.callback_query:
        _, album_id_str, platform = update.callback_query.data.split("_")
        update.callback_query.answer()
        update.callback_query.message.delete()
    else:
        _, album_id_str, platform = context.args[0].split("_")

    if platform == "genius":
        album_id = int(album_id_str)
    else:
        album = spotify.album(album_id_str)
        search = genius.search_albums(album.name)["sections"][0]
        for hit in search["hits"]:
            hit_album = hit["result"]
            if (
                hit_album["name"] == album.name
                and hit_album["artist"]["name"] == album.artists[0].name
            ):
                album_id = hit_album["id"]
                break
        else:
            context.bot.send_message(chat_id, text["not_found"])
            return END

    album = genius.album(album_id)["album"]
    cover_art = utils.fix_image_format(genius, album["cover_art_url"])
    caption = album_caption(update, context, album, text["caption"])

    buttons = [
        [IButton(text["cover_arts"], callback_data=f"album_{album['id']}_covers")],
        [IButton(text["tracks"], callback_data=f"album_{album['id']}_tracks")],
    ]
    if chat_id in DEVELOPERS:
        buttons.append(
            [IButton(text["lyrics"], callback_data=f"album_{album['id']}_lyrics")]
        )

    if album["description_annotation"]["annotations"][0]["body"]["plain"]:
        annotation_id = album["description_annotation"]["id"]
        button = IButton(
            text["description"], callback_data=f"annotation_{annotation_id}"
        )
        buttons[0].append(button)

    bot.send_photo(chat_id, cover_art, caption, reply_markup=IBKeyboard(buttons))

    return END


@log
@get_user
def display_album_covers(update: Update, context: CallbackContext) -> int:
    """Displays an album's cover arts"""
    genius = context.bot_data["genius"]
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["display_album_covers"]
    chat_id = update.effective_chat.id

    if update.callback_query:
        update.callback_query.answer()
        album_id = int(update.callback_query.data.split("_")[1])
    else:
        album_id = int(context.args[0].split("_")[1])

    covers = [x["image_url"] for x in genius.album_cover_arts(album_id)["cover_arts"]]

    album = genius.album(album_id)["album"]["name"]

    if len(covers) == 1:
        text = text[1].replace("{}", album)
        context.bot.send_photo(chat_id, covers[0], text)
    elif len(covers) > 1:
        for media in utils.grouper(10, [InputMediaPhoto(x) for x in covers]):
            # grouper fills the remaining cells with None which we remove
            media = list(filter(None, media))
            media[0].caption = text[2].replace("{}", album)
            context.bot.send_media_group(chat_id, media)
    else:
        context.bot.send_message(chat_id, text[0])

    return END


@log
@get_user
def display_album_tracks(update: Update, context: CallbackContext) -> int:
    """Displays an album's tracks"""
    genius = context.bot_data["genius"]
    language = context.user_data["bot_lang"]
    msg = context.bot_data["texts"][language]["display_album_tracks"]
    chat_id = update.effective_chat.id

    if update.callback_query:
        update.callback_query.answer()
        album_id = int(update.callback_query.data.split("_")[1])
    else:
        album_id = int(context.args[0].split("_")[1])

    songs = []
    for track in genius.album_tracks(album_id, per_page=50)["tracks"]:
        num = track["number"]
        num = f"{num:02d}" if num is not None else "--"
        song = track["song"]
        song = utils.deep_link(song["title"], song["id"], "song", "genius")
        text = f"""\n{num}. {song}"""

        songs.append(text)

    album = genius.album(album_id)["album"]["name"]

    text = f"{msg.replace('{}', album)}{''.join(songs)}"

    context.bot.send_message(chat_id, text)

    return END


@log
@get_user
def display_album_formats(update: Update, context: CallbackContext) -> int:
    """Displays available formats to get album lyrics"""
    language = context.user_data["bot_lang"]
    msg = context.bot_data["texts"][language]["display_album_formats"]
    chat_id = update.effective_chat.id

    if update.callback_query:
        update.callback_query.answer()
        album_id = int(update.callback_query.data.split("_")[1])
    else:
        album_id = int(context.args[0].split("_")[1])

    buttons = [
        [IButton("PDF", callback_data=f"album_{album_id}lyrics_pdf")],
        [IButton("TELEGRA.PH", callback_data=f"album_{album_id}_lyrics_tgf")],
        [IButton("ZIP", callback_data=f"album_{album_id}_lyrics_zip")],
    ]
    keyboard = IBKeyboard(buttons)

    if update.callback_query:
        update.callback_query.edit_message_reply_markup(keyboard)
    else:
        context.bot.send_message(chat_id, msg, reply_markup=keyboard)

    return END


@log
@get_user
def thread_get_album(update: Update, context: CallbackContext) -> int:
    """Creates a thread to get the album"""
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["get_album"]
    chat_id = update.effective_user.id

    update.callback_query.answer()
    _, album_id, _, album_format = update.callback_query.data.split("_")
    album_id = int(album_id)  # type: ignore[assignment]

    if chat_id in DEVELOPERS:
        p = threading.Thread(
            target=get_album,
            args=(
                update,
                context,
                album_id,
                album_format,
                text,
            ),
        )
        p.start()
        p.join()
    return END


@log
def get_album(
    update: Update,
    context: CallbackContext,
    album_id: int,
    album_format: str,
    text: Dict[str, str],
) -> None:
    """Gets the album and sends it to the user.

    Args:
        update (Update): Update object.
        context (CallbackContext): Contains user data.
        album_id (int): Genius album ID.
        album_format (str): Album format (pdf, tgf or zip).
        text (Dict[str, str]): Texts to inform user of the progress.

    Raises:
        ValueError: If it receives an unfamiliar format type.
    """
    ud = context.user_data
    include_annotations = ud["include_annotations"]
    msg = text["downloading"]
    genius_t = api.GeniusT()
    chat_id = update.effective_chat.id

    if album_format not in ("zip", "pdf", "tgf"):
        context.bot.send_message(chat_id, "Unknown album format.")
        return

    update.callback_query.answer()

    progress = context.bot.send_message(chat_id, msg)

    # get album
    album = genius_t.async_album_search(
        album_id=album_id, include_annotations=include_annotations
    )

    # result should be a dict if the operation was successful
    if not isinstance(album, dict):
        msg = text["failed"]
        progress.edit_text(msg)
        logging.error(
            f"Couldn't get album:\n" f"Album ID:{album_id}\n" f"Returned: {album}"
        )
        return

    # convert
    msg = text["converting"]
    progress.edit_text(msg)

    if album_format == "pdf":
        file = create_pdf(album, context.user_data)
    elif album_format == "zip":
        file = create_zip(album, context.user_data)
    else:  # TELEGRA.PH
        link = create_pages(album, context.user_data)
        context.bot.send_message(chat_id=chat_id, text=link)
        progress.delete()
        return

    msg = text["uploading"]
    update.effective_chat.send_chat_action("upload_document")
    progress.edit_text(msg)

    # send the file
    i = 1
    while True:
        if i <= 5:
            try:
                context.bot.send_document(
                    chat_id=chat_id,
                    document=file,
                    caption=file.name[:-4],
                    timeout=20,
                )
                break
            except (TimedOut, NetworkError):
                i += 1

    progress.delete()


@log
def album_caption(
    update: Update,
    context: CallbackContext,
    album: Dict[str, Any],
    caption: Dict[str, str],
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
    release_date: Any = "?"
    features = ""
    labels = ""

    if album.get("release_date_components"):
        release_date = album["release_date_components"]
        year = release_date.get("year")
        month = release_date.get("month")
        day = release_date.get("day")
        components = [year, month, day]
        release_date = "-".join(str(x) for x in components if x is not None)

    total_views = utils.human_format(album["song_pageviews"])

    for x in album.get("song_performances", []):
        if x["label"] == "Featuring":
            features = ", ".join(
                [
                    utils.deep_link(x["name"], x["id"], "artist", "genius")
                    for x in x["artists"]
                ]
            )
            features = caption["features"].replace("{}", features)
        elif x["label"] == "Label":
            labels = ", ".join(
                [
                    utils.deep_link(x["name"], x["id"], "artist", "genius")
                    for x in x["artists"]
                ]
            )
            labels = caption["labels"].replace("{}", labels)

    string = (
        caption["body"]
        .replace("{name}", album["name"])
        .replace("{artist_name}", album["artist"]["name"])
        .replace(
            "{artist}",
            utils.deep_link(
                album["artist"]["name"], album["artist"]["id"], "artist", "genius"
            ),
        )
        .replace("{release_date}", release_date)
        .replace("{url}", album["url"])
        .replace("{views}", total_views)
        + features
        + labels
    )

    return string.strip()
