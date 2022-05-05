import imghdr
import logging
from datetime import timedelta
from io import BytesIO
from typing import cast
from uuid import uuid4

import Levenshtein
from lyricsgenius.utils import clean_str
from telegram import ForceReply, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import CallbackContext

from geniust import DEFAULT_COVER_IMAGE, get_user, utils
from geniust.constants import END, TYPING_LYRIC_CARD_CUSTOM, TYPING_LYRIC_CARD_LYRICS
from geniust.functions.lyric_card_builder import build_lyric_card
from geniust.utils import check_callback_query_user, log

logger = logging.getLogger("geniust")


@log
@get_user
@check_callback_query_user
def type_lyrics(update: Update, context: CallbackContext) -> int:
    """Prompts user to type lyrics"""
    # user has entered the function through the main menu
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["type_lyrics"]

    if update.callback_query:
        update.callback_query.answer()
        # in groups, it's best to send a reply to the user
        reply_to_message = update.callback_query.message.reply_to_message
        if reply_to_message:
            reply_to_message.reply_text(text, reply_markup=ForceReply(selective=True))
        else:
            update.callback_query.edit_message_text(text)
    else:
        if context.args:
            if update.message is None and update.edited_message:
                update.message = update.edited_message
            update.message.text = " ".join(context.args)
            search_lyrics(update, context)
            return END
        update.message.reply_text(text, reply_markup=ForceReply(selective=True))

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
    reply_to_message_id = (
        update.message.message_id if "group" in update.message.chat.type else None
    )

    # get <= 10 hits for user input from Genius API search
    json_search = genius.search_lyrics(input_text)
    found_lyrics = []
    for hit in json_search["sections"][0]["hits"][:10]:
        # A hit with Genius as the artist means it's not a song, but a calender or etc.
        if hit["result"]["primary_artist"]["name"].lower() == "genius":
            continue
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
        update.message.reply_text(
            text["not_found"], reply_to_message_id=reply_to_message_id
        )
        return END

    # Get lyrics for lyric card
    song_page_data = genius.page_data(song_id=hit["result"]["id"])["page_data"]
    song = song_page_data["song"]
    song_lyrics = utils.extract_lyrics_for_card(
        song_page_data["lyrics_data"]["body"]["html"]
    )

    lyrics = utils.find_matching_lyrics(found_lyrics, song_lyrics)
    if lyrics is None:
        logger.error(
            "No lyrics matched despite initial highlight match. Query: %s",
            repr(input_text),
        )
        update.message.reply_text(
            text["not_found"], reply_to_message_id=reply_to_message_id
        )
        return END

    title, primary_artists, featured_artists = utils.get_song_metadata(song)
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

    if imghdr.what(cover_art) is None:
        cover_art = DEFAULT_COVER_IMAGE
    is_persian = bool(utils.PERSIAN_CHARACTERS.search(lyrics))
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

    update.message.reply_photo(lyric_card, reply_to_message_id=reply_to_message_id)
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

    if update.message and "group" in update.message.chat.type:
        chat_id = update.message.chat.id
        message_id = update.message.message_id
        msg = texts["unavailable"]
        context.bot.send_message(chat_id, msg, reply_to_message_id=message_id)
        return END

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
        rtl_lyrics=bool(utils.PERSIAN_CHARACTERS.search(lyric_card_info["lyrics"])),
        rtl_metadata=bool(utils.PERSIAN_CHARACTERS.search(metadata)),
        format="JPEG",
    )
    update.message.reply_photo(lyric_card, reply_markup=ReplyKeyboardRemove())
    ud.pop("lyric_card")
    return END
