import logging
from os.path import join
from itertools import zip_longest
from typing import List, Optional, Iterable, Iterator
import tekore as tk
from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram import Update
from telegram.ext import CallbackContext

from geniust.constants import (
    SELECT_ACTION,
    SELECT_ARTISTS,
    SELECT_GENRES,
    END,
    SPOTIFY_CLIENT_ID,
    Preferences,
    SPOTIFY_CLIENT_SECRET,
)
from geniust.utils import log
from geniust import get_user, data_path, utils
from geniust.functions import account

logger = logging.getLogger("geniust")


@log
@get_user
def welcome_to_shuffle(update: Update, context: CallbackContext) -> int:
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["welcome_to_shuffle"]
    recommender = context.bot_data["recommender"]
    ud = context.user_data
    bot = context.bot
    chat_id = update.effective_chat.id
    photo = join(data_path, "shuffle.jpg")

    caption = text["body"].format(recommender.num_songs)

    buttons = [
        [IButton(text["enter_preferences"], callback_data="shuffle_manual")],
    ]

    if ud["genius_token"]:
        buttons.append(
            [IButton(text["preferences_from_genius"], callback_data="shuffle_genius")]
        )
    else:
        buttons.append(
            [
                IButton(
                    text["preferences_from_genius_login"], callback_data="login_genius"
                )
            ]
        )

    if ud["spotify_token"]:
        buttons.append(
            [IButton(text["preferences_from_spotify"], callback_data="shuffle_spotify")]
        )
    else:
        buttons.append(
            [
                IButton(
                    text["preferences_from_spotify_login"],
                    callback_data="login_spotify",
                )
            ]
        )

    bot.send_photo(
        chat_id, open(photo, "rb"), caption, reply_markup=IBKeyboard(buttons)
    )
    return SELECT_ACTION


@log
def input_preferences(update: Update, context: CallbackContext):
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["input_preferences"]
    chat_id = update.effective_chat.id

    buttons = [
        [
            IButton(text["enter_age"], callback_data="age"),
            IButton(text["choose_genres"], callback_data="genre"),
        ],
    ]

    context.user_data["genres"] = []
    context.user_data["artists"] = []

    update.callback_query.message.delete()
    context.bot.send_message(chat_id, text["body"], reply_markup=IBKeyboard(buttons))

    return SELECT_GENRES


@log
def input_age(update: Update, context: CallbackContext):
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["input_age"]
    recommender = context.bot_data["recommender"]

    if update.callback_query:
        update.callback_query.edit_message_text(text["enter_age"])
        return SELECT_GENRES

    try:
        num = int(update.message.text)
    except ValueError:
        update.message.reply_text(text["invalid_age"])
        return SELECT_GENRES

    genres = recommender.genres_by_age(num)
    if language == "fa":
        genres.append("persian")
    context.user_data["genres"] = genres

    return begin_artist(update, context)


@log
def select_genres(update: Update, context: CallbackContext):
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["select_genres"]
    recommender = context.bot_data["recommender"]
    genres_text = context.bot_data["texts"][language]["genres"]

    query = update.callback_query
    selected_genre = None
    if query.data == "genre":
        if language == "fa":
            context.user_data["genres"] = ["persian"]
        query.edit_message_text(text["choose_genres"])
    elif query.data == "done":
        return begin_artist(update, context)
    else:
        # User chose a genre between genres
        _, genre_str = query.data.split("_")
        selected_genre = recommender.genres_by_number[int(genre_str)]

    user_genres = context.user_data["genres"]

    # Remove genre if user re-selected it
    # Otherwise add it to user's genres
    if selected_genre:
        if selected_genre in user_genres:
            query.answer(text["genre_removed"])
            user_genres.remove(selected_genre)
        else:
            query.answer(text["genre_added"])
            user_genres.append(selected_genre)

    # keyboard for genres
    buttons = []
    for id, genre in recommender.genres_by_number.items():
        if genre in user_genres:
            button_text = f"✅{genres_text[genre]}✅"
        else:
            button_text = genres_text[genre]
        buttons.append(IButton(button_text, callback_data=f"genre_{id}"))

    # 3 genres in each row
    def grouper(
        n: int, iterable: Iterable, fillvalue: Optional[str] = None
    ) -> Iterator:
        """Groups iterable values by n

        Limits buttons to n button in every row
        and if there are any remaining spaces
        left in the last group, fills them with
        the value of fillvalue.

        Args:
            n ([type]): [description]
            iterable (Iterable): An iterable to be grouped.
            fillvalue ([type], optional): Value to fill
            remaining items of group. Defaults to None.

        Returns:
            Iterator: Iterator of grouped items.
        """
        # from https://stackoverflow.com/a/3415150
        args = [iter(iterable)] * n
        return zip_longest(fillvalue=IButton(fillvalue, callback_data="None"), *args)

    keyboard_buttons = []
    for button_set in grouper(3, buttons):
        keyboard_buttons.append(button_set)

    if context.user_data["genres"]:
        keyboard_buttons.append([IButton(text["done"], callback_data="done")])

    query.edit_message_reply_markup(IBKeyboard(keyboard_buttons))

    return SELECT_GENRES


@log
def begin_artist(update: Update, context: CallbackContext):
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["input_artist"]
    buttons = [
        [IButton(text["add_artist"], callback_data="input")],
        [IButton(text["done"], callback_data="done")],
    ]
    keyboard = IBKeyboard(buttons)
    if update.callback_query:
        update.callback_query.edit_message_text(text["body"], reply_markup=keyboard)
    else:
        update.message.reply_text(text["body"], reply_markup=keyboard)
    return SELECT_ARTISTS


@log
def input_artist(update: Update, context: CallbackContext):
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["input_artist"]

    update.callback_query.edit_message_text(text["enter_artist"])
    return SELECT_ARTISTS


@log
@get_user
def select_artists(update: Update, context: CallbackContext):
    ud = context.user_data
    language = ud["bot_lang"]
    text = context.bot_data["texts"][language]["select_artists"]
    db = context.bot_data["db"]
    recommender = context.bot_data["recommender"]
    chat_id = update.effective_chat.id

    if update.message:
        input_text = update.message.text
        matches = recommender.search_artist(input_text)
        if not matches:
            update.message.reply_text(text["no_match"])
            return SELECT_ARTISTS

        buttons = []
        for match in matches:
            if match.name.lower() == input_text.lower():
                index = match.id
                buttons.append([IButton(match.name, callback_data=f"artist_{index}")])

        buttons.append([IButton(text["not_in_matches"], callback_data="artist_none")])
        update.message.reply_text(
            text["choose_artist"], reply_markup=IBKeyboard(buttons)
        )
        return SELECT_ARTISTS

    query = update.callback_query

    if query.data == "done":
        ud["preferences"] = Preferences(ud.pop("genres"), ud.pop("artists"))
        db.update_preferences(chat_id, ud["preferences"])
        update.callback_query.edit_message_text(text["finished"])
        return END
    else:
        _, artist = query.data.split("_")
        if artist != "none":
            ud["artists"].append(recommender.artist(int(artist)).name)
            query.answer(text["artist_added"])
        buttons = [
            [IButton(text["add_artist"], callback_data="input")],
            [IButton(text["done"], callback_data="done")],
        ]
        query.edit_message_text(
            text["artists"].format(", ".join(ud["artists"])),
            reply_markup=IBKeyboard(buttons),
        )
        return SELECT_ARTISTS


@log
@get_user
def select_language(update: Update, context: CallbackContext):  # pragma: no cover
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["select_language"]
    bd = context.bot_data

    buttons: List[List] = [
        [
            IButton(bd["texts"][language]["en"], callback_data="en"),
            IButton(bd["texts"][language]["fa"], callback_data="fa"),
        ],
        [IButton(bd["texts"][language]["both"], callback_data="both")],
    ]

    update.callback_query.edit_message_text(text, reply_markup=IBKeyboard(buttons))


@log
@get_user
def process_preferences(update: Update, context: CallbackContext):
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["process_preferences"]
    db = context.bot_data["db"]
    recommender = context.bot_data["recommender"]
    chat_id = update.effective_chat.id
    bot = context.bot
    bd = context.bot_data

    query = update.callback_query
    _, platform = query.data.split("_")
    platform_text = bd["texts"][language][platform]

    query.message.delete()
    message = bot.send_message(chat_id, text["getting_data"].format(platform_text))

    if platform == "genius":
        token = context.user_data["genius_token"]
    else:
        cred = tk.RefreshingCredentials(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
        try:
            token = cred.refresh_user_token(context.user_data["spotify_token"])
        except tk.BadRequest:
            db.delete_token(chat_id, platform)
            update.callback_query.message = message
            update.callback_query.data = "login_spotify"
            account.login(update, context)

    preferences = recommender.preferences_from_platform(token, platform)

    if preferences is None:
        message.edit_text(text["insufficient_data"].format(platform_text))
    else:
        context.user_data["preferences"] = preferences
        context.bot_data["db"].update_preferences(
            chat_id, context.user_data["preferences"]
        )
        message.edit_text(text["done"])

    return END


@log
@get_user
def reset_shuffle(update: Update, context: CallbackContext) -> int:
    """Resets user's preferences"""
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["reset_shuffle"]
    chat_id = update.effective_chat.id
    db = context.bot_data["db"]

    db.delete_preferences(chat_id)
    context.user_data["preferences"] = None

    update.callback_query.edit_message_text(text)

    return END


@log
@get_user
def display_recommendations(update: Update, context: CallbackContext) -> int:
    """Displays song recommendations to the user"""
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["display_recommendations"]
    recommender = context.bot_data["recommender"]
    bot = context.bot
    chat_id = update.effective_chat.id
    user_preferences = context.user_data["preferences"]

    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.message.delete()

    songs = recommender.shuffle(user_preferences)

    deep_linked = []
    for song in songs:
        urls = []
        full_name = f"{song.artist} - {song.name}"
        if song.id_spotify:
            full_name = utils.deep_link(full_name, song.id_spotify, "song", "spotify")
        if song.preview_url:
            url = utils.deep_link(
                text["preview"],
                song.id,
                "song",
                "recommender_preview",
            )
            urls.append(url)
        if song.download_url:
            url = utils.deep_link(
                text["download"],
                song.id,
                "song",
                "recommender_download",
            )
            urls.append(url)
        if urls:
            urls = "|".join(urls)  # type: ignore
            item = f"{full_name} ({urls})"
        else:
            item = full_name
        deep_linked.append(item)
    caption = text["body"].format("\n".join("▪️ {}".format(x) for x in deep_linked))
    bot.send_message(chat_id, caption)

    return END
