import logging
from datetime import timedelta
from io import BytesIO
from typing import cast
from uuid import uuid4

import Levenshtein
from bs4 import BeautifulSoup
from lyricsgenius.utils import clean_str
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import CallbackContext

from geniust import get_user
from geniust.constants import END, TYPING_LYRIC_CARD_CUSTOM, TYPING_LYRIC_CARD_LYRICS
from geniust.functions.lyric_card_builder import build_lyric_card
from geniust.utils import (
    PERSIAN_CHARACTERS,
    SECTION_HEADERS,
    TRANSLATION_PARENTHESES,
    fix_section_headers,
    log,
)

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

    return TYPING_LYRIC_CARD_LYRICS


@log
@get_user
def search_lyrics(update: Update, context: CallbackContext) -> int:
    """Sends user a lyric card based on the lyrics the user provided"""
    genius = context.bot_data["genius"]
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["lyric_card_search_lyrics"]
    input_text = update.message.text.replace("\n", " ")
    cleaned_input = clean_str(input_text)

    # get <= 10 hits for user input from Genius API search
    json_search = genius.search_lyrics(input_text)
    found_lyrics = []
    for hit in json_search["sections"][0]["hits"][:10]:
        highlight = hit["highlights"][0]
        for line in highlight["value"].split("\n"):
            if (
                cleaned_input in clean_str(line)
                or Levenshtein.ratio(input_text, line) > 0.5
            ):
                found_lyrics.append(line)
        if found_lyrics:
            break
    else:
        update.message.reply_text(text["not_found"])
        return END

    # Get lyrics for lyric card
    song_page_data = genius.page_data(song_id=hit["result"]["id"])["page_data"]
    song = song_page_data["song"]
    song_lyrics = (
        BeautifulSoup(song_page_data["lyrics_data"]["body"]["html"], "html.parser")
        .get_text()
        .strip()
    )
    song_lyrics = fix_section_headers(song_lyrics)
    song_lyrics = SECTION_HEADERS.sub("", song_lyrics)

    lyrics = []
    for line in song_lyrics.split("\n"):
        for found_line in found_lyrics:
            # We'd expect the match between the lines in the snippet (found_lyrics)
            # and the corresponding lines in the full lyrics to be 100%, but since
            # Genius implements some methods to detect plagiarism and
            # these methods modify the lyrics, a 100% similarity ratio might not happen.
            if Levenshtein.ratio(found_line, line) > 0.75 or clean_str(
                found_line
            ) in clean_str(line):
                lyrics.append(line)
                break
        if len(lyrics) == len(found_lyrics):
            break
    if not lyrics:
        logger.error(
            "No lyrics matched despite initial highlight match. Query: %s",
            repr(input_text),
        )
        update.message.reply_text(text["not_found"])
        return END
    lyrics = "\n".join(lyrics)

    # Get song metadata
    title = song["title"]
    primary_artists = song["primary_artist"]["name"].split(" & ")
    featured_artists = [x["name"] for x in song["featured_artists"]]
    # If True, it means that this song is actually a translation.
    # So we should edit the song title and primary artist.
    # This is meant for translated songs.
    if primary_artists[0].startswith("Genius") and featured_artists == []:
        # This regex expression removes parentheses at the end of title
        # that indicates the song is a translation
        # e.g. song - title (English Translation)
        # but it only does so for Persian. It's tricky to do this for all
        # languages since the actual title itself may have parentheses and
        # it may get removed.
        title = TRANSLATION_PARENTHESES.sub("", title).strip()
        artists, title = [x.strip() for x in title.split("-")]
        primary_artists.clear()
        primary_artists.extend(artists.split(" & "))

    cover_art_url = song["song_art_image_url"]
    # When cover arts aren't 1000x1000, the builder upscales and then
    # downscales the image. Instead, we can use this hack to have
    # Genius upscale the image for us and then just have a normal
    # 1000x1000 cover art.
    # from urllib.parse import quote_plus
    # image_size = re.findall(r"[\d]{1,}x[\d]{1,}", cover_art_url)[-1]
    # if image_size != "1000x1000":
    #     encoded_url = quote_plus(cover_art_url)
    #     cover_art_url = "https://t2.genius.com/unsafe/1000x0/" + encoded_url

    cover_art = genius.download_cover_art(cover_art_url)

    is_persian = bool(PERSIAN_CHARACTERS.search(lyrics))
    lyric_card = build_lyric_card(
        cover_art=cover_art,
        lyrics=lyrics,
        song_title=title,
        primary_artists=primary_artists,
        featured_artists=featured_artists,
        rtl_lyrics=is_persian,
        rtl_metadata=False,  # Genius metadata is in English most of the time
        format="JPEG",
    )

    update.message.reply_photo(lyric_card)
    return END


@log
def remove_lyric_info(context: CallbackContext) -> None:
    """Removes the lyric_info key from user data

    To avoid using extra RAM since there is also an in-memory image
    in the lyric_card dictionary, this callback is used to delete
    the dictionary if the user has abandoned the conversation.
    """
    job_context = cast(tuple, context.job.context)
    ud: dict = job_context[0]
    id: str = job_context[1]
    # Equal ID means that the user had abandoned the conversation.
    # Otherwise it means there is an ongoing conversation.
    if "lyric_card" in ud and ud["lyric_card"]["id"] == id:
        ud.pop("lyric_card")


@log
@get_user
def custom_lyric_card(update: Update, context: CallbackContext) -> int:
    """Provides custom lyric card

    This functions implants all the different stages of sending the
    information needed for the custom lyric card.
    """
    ud = context.user_data
    language = ud["bot_lang"]
    texts = context.bot_data["texts"][language]["custom_lyric_card"]
    chat_id = update.effective_user.id

    # User started the conversation
    if "lyric_card" not in ud:
        ud["lyric_card"] = dict(
            id=str(uuid4()),
            photo=None,
            lyrics=None,
            title=None,
            primary_artists=None,
            featured_artists=None,
        )
        context.bot.send_message(chat_id, texts["send_photo"])
        return TYPING_LYRIC_CARD_CUSTOM
    lyric_card_info = ud["lyric_card"]
    text = update.message.text

    # User hasn't sent the cover art
    if lyric_card_info["photo"] is None:
        if not update.message.photo:
            update.message.reply_text(texts["send_photo"])
            return TYPING_LYRIC_CARD_CUSTOM
        lyric_card_info["photo"] = (
            update.message.photo[-1].get_file().download(out=BytesIO())
        )
        update.message.reply_text(texts["send_lyrics"])
        # Remove photo from memory if user abandons conversation
        context.job_queue.run_once(
            remove_lyric_info,
            timedelta(minutes=10),
            context=(ud, lyric_card_info["id"]),
            name=f"remove_lyric_info_{update.effective_user.id}",
        )
        return TYPING_LYRIC_CARD_CUSTOM

    # User hasn't sent the lyrics
    if lyric_card_info["lyrics"] is None:
        lyric_card_info["lyrics"] = text.strip()
        update.message.reply_text(texts["send_title"])
        return TYPING_LYRIC_CARD_CUSTOM

    # User hasn't sent the song title
    if lyric_card_info["title"] is None:
        lyric_card_info["title"] = text.strip()
        update.message.reply_text(texts["send_primary_artists"])
        return TYPING_LYRIC_CARD_CUSTOM

    # User hasn't send the primary artists
    if lyric_card_info["primary_artists"] is None:
        lyric_card_info["primary_artists"] = text.split("\n")
        update.message.reply_text(
            texts["send_featured_artists"],
            reply_markup=ReplyKeyboardMarkup(
                [[texts["no_featured_artists"]]], one_time_keyboard=True
            ),
        )
        return TYPING_LYRIC_CARD_CUSTOM

    # At this point, user has either send the featured artists or
    # has used the keyboard button to say there are none.
    # Now we can build the lyric card and send it.
    lyric_card_info["featured_artists"] = (
        text.split("\n") if text != texts["no_featured_artists"] else None
    )

    # All the metadata is put into a string to determine
    # if there are any Persian characters in the metadata and
    # so if the metadata should be RTL in the lyric card.
    metadata = []
    metadata.extend(lyric_card_info["primary_artists"])
    metadata.extend(
        lyric_card_info["featured_artists"]
        if lyric_card_info["featured_artists"]
        else []
    )
    metadata.append(lyric_card_info["title"])
    metadata = "".join(metadata)
    lyric_card = build_lyric_card(
        cover_art=lyric_card_info["photo"],
        lyrics=lyric_card_info["lyrics"],
        song_title=lyric_card_info["title"],
        primary_artists=lyric_card_info["primary_artists"],
        featured_artists=lyric_card_info["featured_artists"],
        rtl_lyrics=bool(PERSIAN_CHARACTERS.search(lyric_card_info["lyrics"])),
        rtl_metadata=bool(PERSIAN_CHARACTERS.search(metadata)),
        format="JPEG",
    )
    update.message.reply_photo(lyric_card, reply_markup=ReplyKeyboardRemove())
    ud.pop("lyric_card")
    return END
