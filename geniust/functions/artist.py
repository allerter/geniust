import logging
from typing import Any, Dict

from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram import Update
from telegram.ext import CallbackContext

from geniust import get_user, utils
from geniust.constants import END, TYPING_ARTIST
from geniust.utils import log

logger = logging.getLogger("geniust")


@log
@get_user
def type_artist(update: Update, context: CallbackContext) -> int:
    """Prompts user to type artist name"""
    # user has entered the function through the main menu
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["type_artist"]

    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.edit_message_text(text)
    else:
        if context.args:
            update.message.text = " ".join(context.args)
            search_artists(update, context)
            return END
        update.message.reply_text(text)

    return TYPING_ARTIST


@log
@get_user
def search_artists(update: Update, context: CallbackContext) -> int:
    """Displays a list of artist names based on user input"""
    genius = context.bot_data["genius"]
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["search_artists"]
    input_text = update.message.text

    res = genius.search_artists(input_text)
    buttons = []
    for hit in res["sections"][0]["hits"][:10]:
        artist = hit["result"]
        artist_id = artist["id"]
        title = artist["name"]
        callback_data = f"artist_{artist_id}_genius"

        buttons.append([IButton(title, callback_data=callback_data)])

    if buttons:
        update.message.reply_text(text["choose"], reply_markup=IBKeyboard(buttons))
    else:
        update.message.reply_text(text["no_artists"])

    return END


@log
@get_user
def display_artist(update: Update, context: CallbackContext) -> int:
    """Displays artist"""
    genius = context.bot_data["genius"]
    spotify = context.bot_data["spotify"]
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["display_artist"]
    bot = context.bot
    chat_id = update.effective_chat.id

    if update.callback_query:
        _, artist_id_str, platform = update.callback_query.data.split("_")
        update.callback_query.answer()
        update.callback_query.message.delete()
    else:
        _, artist_id_str, platform = context.args[0].split("_")

    if platform == "genius":
        artist_id = int(artist_id_str)
    else:
        artist = spotify.artist(artist_id_str)
        search = genius.search_artists(artist.name)["sections"][0]
        for hit in search["hits"]:
            hit_artist = hit["result"]
            if hit_artist["name"] == artist.name:
                artist_id = hit_artist
                break
        else:
            context.bot.send_message(chat_id, text["not_found"])
            return END

    artist = genius.artist(artist_id)["artist"]
    cover_art = utils.fix_image_format(genius, artist["image_url"])
    caption = artist_caption(update, context, artist, text["caption"], language)

    buttons = [
        [IButton(text["albums"], callback_data=f"artist_{artist['id']}_albums")],
        [
            IButton(
                text["songs_by_popularity"],
                callback_data=f"artist_{artist['id']}_songs_ppt_1",
            )
        ],
        [
            IButton(
                text["songs_by_release_data"],
                callback_data=f"artist_{artist['id']}_songs_rdt_1",
            )
        ],
        [
            IButton(
                text["songs_by_title"],
                callback_data=f"artist_{artist['id']}_songs_ttl_1",
            )
        ],
    ]

    if artist["description_annotation"]["annotations"][0]["body"]["plain"]:
        annotation_id = artist["description_annotation"]["id"]
        button = IButton(
            text["description"], callback_data=f"annotation_{annotation_id}"
        )
        buttons[0].append(button)

    bot.send_photo(chat_id, cover_art, caption, reply_markup=IBKeyboard(buttons))

    return END


@log
@get_user
def display_artist_albums(update: Update, context: CallbackContext) -> int:
    """Displays artist's albums"""
    genius = context.bot_data["genius"]
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["display_artist_albums"]
    chat_id = update.effective_chat.id

    if update.callback_query:
        update.callback_query.answer()
        artist_id = int(update.callback_query.data.split("_")[1])
    else:
        artist_id = int(context.args[0].split("_")[1])

    albums = []

    albums_list = genius.artist_albums(artist_id, per_page=50)
    for album in albums_list["albums"]:
        name = text["album"].replace(
            "{}", utils.deep_link(album["name"], album["id"], "album", "genius")
        )
        albums.append(name)

    if albums:
        artist = albums_list["albums"][0]["artist"]["name"]
        string = f"{text['albums'].replace('{}', artist)}\n{''.join(albums)}"
    else:
        artist = genius.artist(artist_id)["artist"]["name"]
        text = text["no_albums"].replace("{}", artist)
        context.bot.send_message(chat_id, text)
        return END

    context.bot.send_message(chat_id, string)

    return END


@log
@get_user
def display_artist_songs(update: Update, context: CallbackContext) -> int:
    """Displays artist's songs"""
    genius = context.bot_data["genius"]
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["display_artist_songs"]
    chat_id = update.effective_chat.id

    if update.callback_query:
        update.callback_query.answer()
        message = update.callback_query.message
        # A message with a photo means the user came from display_artist
        # and so we send the songs as a new message
        message = message if message.photo is None else None
        _, artist_id_str, _, sort, page_str = update.callback_query.data.split("_")
    else:
        message = None
        _, artist_id_str, _, sort, page_str = context.args[0].split("_")

    page = int(page_str)
    artist_id = int(artist_id_str)

    if sort == "ppt":
        sort = "popularity"
    elif sort == "rdt":
        sort = "release_date"
    else:
        sort = "title"

    songs = []
    per_page = 50
    songs_list = genius.artist_songs(artist_id, per_page=per_page, page=page, sort=sort)
    next_page = songs_list["next_page"]
    previous_page = page - 1 if page != 1 else None

    for i, song in enumerate(songs_list["songs"]):
        num = per_page * (page - 1) + i + 1
        title = f"\n{num:02} - {utils.deep_link(song['title'], song['id'], 'song', 'genius')}"

        views = song["stats"].get("pageviews")
        if sort == "popularity" and views:
            views = utils.human_format(views)
            title += f" ({views})"

        songs.append(title)

    if songs:
        artist = songs_list["songs"][0]["primary_artist"]["name"]
        msg = text["songs"].replace("{artist}", artist).replace("{sort}", text[sort])
        string = f"{msg}\n{''.join(songs)}"
    else:
        artist = genius.artist(artist_id)["artist"]["name"]
        text = text["no_songs"].replace("{}", artist)
        context.bot.send_message(chat_id, text)
        return END

    logger.debug("%s - %s - %s", previous_page, page, next_page)

    if sort == "popularity":
        sort = "ppt"
    elif sort == "release_date":
        sort = "rdt"
    else:
        sort = "ttl"

    if previous_page:
        msg = text["previous_page"].replace("{}", str(previous_page))
        previous_button = IButton(
            msg, callback_data=f"artist_{artist_id}_songs_{sort}_{previous_page}"
        )
    else:
        previous_button = IButton("⬛️", callback_data="None")

    current_button = IButton(str(page), callback_data="None")

    if next_page:
        msg = text["next_page"].replace("{}", str(next_page))
        next_button = IButton(
            msg, callback_data=f"artist_{artist_id}_songs_{sort}_{next_page}"
        )
    else:
        next_button = IButton("⬛️", callback_data="None")

    buttons = [[previous_button, current_button, next_button]]
    keyboard = IBKeyboard(buttons)

    if message:
        update.callback_query.edit_message_caption(string, reply_markup=keyboard)
    else:
        context.bot.send_message(chat_id, string, reply_markup=keyboard)

    return END


@log
def artist_caption(
    update: Update,
    context: CallbackContext,
    artist: Dict[str, Any],
    caption: Dict[str, str],
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
    alternate_names = ""
    social_media = ""
    social_media_links = []

    if artist.get("alternate_names"):
        names = ", ".join(artist["alternate_names"])
        alternate_names = caption["alternate_names"].replace("{}", names)

    if artist.get("facebook_name"):
        url = f"https://www.facebook.com/{artist['facebook_name']}"
        social_media_links.append(f"""<a href="{url}">Facebook</a>""")
    if artist.get("instagram_name"):
        url = f"https://www.instagram.com/{artist['instagram_name']}"
        social_media_links.append(f"""<a href="{url}">Instagram</a>""")
    if artist.get("twitter_name"):
        url = f"https://www.twitter.com/{artist['twitter_name']}"
        social_media_links.append(f"""<a href="{url}">Twitter</a>""")
    if social_media_links:
        links = " | ".join(social_media_links)
        social_media = caption["social_media"].replace("{}", links)

    followers_count = utils.human_format(artist["followers_count"])

    is_verified = context.bot_data["texts"][language][artist["is_verified"]]

    string = (
        caption["body"]
        .replace("{name}", artist["name"])
        .replace("{url}", artist["url"])
        .replace("{verified}", is_verified)
        .replace("{followers}", followers_count)
        + social_media
        + alternate_names
    )

    return string.strip()
