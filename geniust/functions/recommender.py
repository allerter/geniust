import logging
import difflib
from os.path import join
from itertools import zip_longest
from typing import Tuple, List, Union, Dict
from dataclasses import dataclass, asdict

import tekore as tk
import lyricsgenius as lg
import pandas as pd
import numpy as np
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
from sklearn.metrics.pairwise import linear_kernel
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
from geniust import api, get_user, data_path, utils

logger = logging.getLogger("geniust")

# based on https://www.statista.com/statistics/253915/favorite-music-genres-in-the-us/
genres_by_age_group: Dict[int, List[str]] = {
    19: ["pop", "rap", "rock"],
    24: ["pop", "rap", "rock"],
    34: ["pop", "rock", "rap", "country", "traditional"],
    44: ["pop", "rock", "rap", "country", "traditional"],
    54: ["rock", "pop", "country", "traditional"],
    64: ["rock", "country", "traditional"],
    65: ["rock", "country", "traditional"],
}


@dataclass
class Song:
    """A Song from the Recommender"""

    id: int
    artist: str
    name: str
    genres: list
    id_spotify: str = None
    isrc: str = None
    cover_art: str = None
    preview_url: str = None
    download_url: str = None

    def to_dict(self):
        return asdict(self)

    def __repr__(self):
        return f"Song(id={self.id})"


class Recommender:
    # classical - country - instrumental - persian - pop - rap - rnb - rock -traditional
    def __init__(self):
        # Read tracks
        en = pd.read_csv(join(data_path, "tracks en.csv"))
        fa = pd.read_csv(join(data_path, "tracks fa.csv"))
        self.songs: pd.DataFrame = pd.merge(
            en.drop(columns=["download_url"]), fa, how="outer"
        )
        self.songs.replace({np.NaN: None}, inplace=True)

        # Read artists
        en_artists = pd.read_csv(join(data_path, "artists en.csv"))
        fa_artists = pd.read_csv(join(data_path, "artists fa.csv"))
        self.artists: pd.DataFrame = pd.merge(en_artists, fa_artists, how="outer")
        self.artists["description"] = self.artists["description"].str.replace(r"\n", "")
        self.artists.description.fillna("", inplace=True)

        self.artists_names = self.artists.name.to_list()
        self.lowered_artists_names = {p.lower(): p for p in self.artists_names}
        # No duplicate values
        # no_duplicates = songs['id_spotify'].dropna().duplicated(
        # ).value_counts().all(False)
        # assert no_duplicates, True

        self.songs["genres"] = self.songs["genres"].str.split(",")
        songs_copy = self.songs.copy()
        # One-hot encode genres
        mlb = MultiLabelBinarizer(sparse_output=True)
        df = songs_copy.join(
            pd.DataFrame.sparse.from_spmatrix(
                mlb.fit_transform(songs_copy.pop("genres")),
                index=songs_copy.index,
                columns=mlb.classes_,
            )
        )
        self.binarizer = mlb
        # Convert df to numpy array
        numpy_df = df.drop(
            columns=[
                "id_spotify",
                "artist",
                "name",
                "download_url",
                "preview_url",
                "isrc",
                "cover_art",
            ]
        )
        self.genres = list(numpy_df.columns)
        self.genres_by_number = {}
        for i, genre in enumerate(self.genres):
            self.genres_by_number[i] = genre
        # dtype=[(genre, int) for genre in self.genres]
        self.numpy_songs = numpy_df.to_numpy()

        with open(join(data_path, "persian_stopwords.txt"), "r", encoding="utf8") as f:
            PERSIAN_STOP_WORDS = f.read().strip().split()
        stop_words = list(ENGLISH_STOP_WORDS) + PERSIAN_STOP_WORDS
        self.tfidf = TfidfVectorizer(analyzer="word", stop_words=stop_words)
        self.tfidf = self.tfidf.fit_transform(self.artists["description"])

        self.genres_by_age_group: Dict[int, List[str]] = {
            19: ["pop", "rap", "rock"],
            24: ["pop", "rap", "rock"],
            34: ["pop", "rock", "rap", "country", "traditional"],
            44: ["pop", "rock", "rap", "country", "traditional"],
            54: ["rock", "pop", "country", "traditional"],
            64: ["rock", "country", "traditional"],
            65: ["rock", "country", "traditional"],
        }

    def genres_by_age(self, age: int) -> List[str]:
        age_groups = list(self.genres_by_age_group.keys())
        for age_group in age_groups:
            if age >= age_group:
                break
        else:
            age_group = age_groups[-1]
        return self.genres_by_age_group[age_group]

    @log
    def preferences_from_platform(self, token: str, platform: str) -> Preferences:
        if platform == "genius":
            user_genius = api.GeniusT(token)
            account = user_genius.account()["user"]
            pyongs = user_genius.user_pyongs(account["id"])
            pyonged_songs = []
            for contribution in pyongs["contribution_groups"]:
                pyong = contribution["contributions"][0]
                if pyong["pyongable_type"] == "song":
                    api_path = pyong["pyongable"]["api_path"]
                    pyonged_songs.append(int(api_path[api_path.rfind("/") + 1 :]))

            public_genius = lg.PublicAPI(timeout=10)

            genres = []
            artists = []
            for song_id in pyonged_songs:
                song = public_genius.song(song_id)["song"]
                artists.append(song["primary_artist"]["name"])
                for tag in song["tags"]:
                    for genre in self.genres:
                        if genre in tag:
                            genres.append(genre)
        else:
            user_spotify = tk.Spotify(token, sender=tk.RetryingSender())
            top_tracks = user_spotify.current_user_top_tracks("short_term")
            top_artists = user_spotify.current_user_top_artists(limit=5)
            user_spotify.close()

            # Add track genres to genres list
            genres = []
            for track in top_tracks.items:
                track_genres = api.lastfm(
                    "Track.getTopTags", {"artist": track.artists[0], "track": track.name}
                )
                if "toptags" in track_genres:
                    for tag in track_genres["toptags"]["tag"]:
                        for genre in self.genres:
                            if genre in tag:
                                genres.append(genre)

            artists = [artist.name for artist in top_artists.items]

        # get count of genres and only keep genres with a >=30% occurance
        unique_elements, counts_elements = np.unique(genres, return_counts=True)
        counts_elements = counts_elements.astype(float)
        counts_elements /= counts_elements.sum()
        genres = np.asarray((unique_elements, counts_elements))
        genres = genres[0][genres[1] >= 0.30]

        # find user artists in recommender artists
        found_artists = []
        for artist in artists:
            found_artist = self.artists[
                self.artists.name == artist
            ].name.values
            if found_artist.size > 0:
                found_artists.append(found_artist[0])

        return Preferences(genres, artists) if genres else None

    def search_artist(self, artist: str) -> List[str]:
        artist = artist.lower()
        matches = difflib.get_close_matches(artist, self.lowered_artists_names.keys())
        return [self.lowered_artists_names[m] for m in matches]

    def binarize(self, genres: List[str]) -> np.ndarray:
        return self.binarizer.transform([genres]).toarray()[0]

    def shuffle(
        self,
        user_preferences: Preferences,
        # language: str = 'any',
        song_type="any",
    ) -> List[Song]:
        user_genres = self.binarize(user_preferences.genres)
        persian_index = np.where(self.binarize(["persian"]) == 1)[0][0]
        persian_user = True if user_genres[persian_index] == 1 else False
        similar = []
        for index, song in enumerate(self.numpy_songs):
            # skip song if it doesn't match user language
            if bool(song[persian_index]) != persian_user:
                continue
            for i, genre in enumerate(song):
                if i != persian_index and genre == 1 and user_genres[i] == 1:
                    similar.append(index)
                    break
            # no need for language parameter since
            # the first if statement enforeces the value of "persian" genre
            #        if ((language == 'any')
            #            or (language == 'en' and song[persian_index] == 0)
            #                or (language == 'fa' and song[persian_index] == 1)):

        # Randomly choose 20 songs from similar songs
        # This is to avoid sending the same set of songs each time
        if similar:
            selected = np.random.choice(
                similar,
                20,
            )  # TODO: set probability array
        else:
            return []

        # sort songs by most similar song artists to user artists
        user_artists = [
            self.artists[self.artists.name == artist]
            for artist in user_preferences.artists
        ]
        if user_artists:
            song_artists = [
                self.artists[self.artists.name == self.songs.loc[song].artist]
                for song in selected
            ]
            cosine_similarities = []
            user_tfifd = self.tfidf[[artist.index[0] for artist in user_artists], :]
            for index, artist in enumerate(song_artists):
                cosine_similarity = (
                    linear_kernel(self.tfidf[artist.index[0]], user_tfifd)
                    .flatten()
                    .sum()
                )
                if artist.name.values[0] in [x.name.values[0] for x in user_artists]:
                    cosine_similarity += 1
                cosine_similarities.append((index, cosine_similarity))
            cosine_similarities.sort(key=lambda x: x[1], reverse=True)
            hits = []
            for row in cosine_similarities:
                song = self.song(selected[row[0]])
                if song_type == "any":
                    hits.append(song)
                elif song_type == "any_file":
                    if song.preview_url or song.download_url:
                        hits.append(song)
                elif song_type == "preview":
                    if song.preview_url:
                        hits.append(song)
                elif song_type == "full":
                    if song.download_url:
                        hits.append(song)
                elif song_type == "preview,full":
                    if song.preview_url and song.download_url:
                        hits.append(song)
                if len(hits) == 5:
                    break
        else:
            hits = []
            for index in selected:
                song = self.song(index)
                if song_type == "any":
                    hits.append(song)
                elif song_type == "any_file":
                    if song.preview_url or song.download_url:
                        hits.append(song)
                elif song_type == "preview":
                    if song.preview_url:
                        hits.append(song)
                elif song_type == "full":
                    if song.download_url:
                        hits.append(song)
                elif song_type == "preview,full":
                    if song.preview_url and song.download_url:
                        hits.append(song)
                if len(hits) == 5:
                    break

        return hits

    def song(self, id: int = None, id_spotify: str = None) -> Song:
        if not any([id is not None, id_spotify]):
            raise AssertionError("Must supply either id or id_spotify.")
        if id:
            row = self.songs.iloc[id]
        else:
            rows = self.songs[self.songs.id_spotify == id_spotify]
            id = rows.index[0]
            row = rows.iloc[0]
        return Song(id=int(id), **row.to_dict())


@log
def welcome_to_shuffle(update: Update, context: CallbackContext) -> int:
    language = context.user_data["bot_lang"]
    text = context.bot_data["texts"][language]["welcome_to_shuffle"]
    recommender = context.bot_data["recommender"]
    ud = context.user_data
    bot = context.bot
    chat_id = update.effective_chat.id
    photo = join(data_path, "shuffle.jpg")

    caption = text["body"].format(len(recommender.songs))

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
    def grouper(n, iterable, fillvalue=None):
        # from https://stackoverflow.com/a/3415150
        args = [iter(iterable)] * n
        return zip_longest(fillvalue=IButton("⬛️", callback_data="None"), *args)

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
        matches = difflib.get_close_matches(
            input_text,
            recommender.artists.name.to_list(),
            n=5,
        )
        if not matches:
            update.message.reply_text(text["no_match"])
            return SELECT_ARTISTS

        buttons = []
        for match in matches:
            index = recommender.artists[recommender.artists["name"] == match].index[0]
            buttons.append([IButton(match, callback_data=f"artist_{index}")])

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
            ud["artists"].append(recommender.artists.name.loc[int(artist)])
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
def select_language(update: Update, context: CallbackContext):  # pragam: no cover
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
        genius_token = context.user_data["genius_token"]
        user_genius = api.GeniusT(genius_token)
        account = user_genius.account()["user"]
        pyongs = user_genius.user_pyongs(account["id"])
        pyonged_songs = []
        for contribution in pyongs["contribution_groups"]:
            pyong = contribution["contributions"][0]
            if pyong["pyongable_type"] == "song":
                api_path = pyong["pyongable"]["api_path"]
                pyonged_songs.append(int(api_path[api_path.rfind("/") + 1 :]))

        public_genius = lg.PublicAPI(timeout=10)

        genres = []
        artists = []
        for song_id in pyonged_songs:
            song = public_genius.song(song_id)["song"]
            artists.append(song["primary_artist"]["name"])
            for tag in song["tags"]:
                for genre in recommender.genres:
                    if genre in tag:
                        genres.append(genre)
    else:
        spotify_token = context.user_data["spotify_token"]
        token = spotify_token
        cred = tk.RefreshingCredentials(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
        token = cred.refresh_user_token(spotify_token)
        user_spotify = tk.Spotify(token, sender=tk.RetryingSender())
        top_tracks = user_spotify.current_user_top_tracks("short_term")
        top_artists = user_spotify.current_user_top_artists(limit=5)
        user_spotify.close()

        # Add track genres to genres list
        genres = []
        for track in top_tracks.items:
            track_genres = api.lastfm(
                "Track.getTopTags", {"artist": track.artists[0], "track": track.name}
            )
            if "toptags" in track_genres:
                for tag in track_genres["toptags"]["tag"]:
                    for genre in recommender.genres:
                        if genre in tag:
                            genres.append(genre)

        artists = [artist.name for artist in top_artists.items]

    # get count of genres and only keep genres with a >=30% occurance
    unique_elements, counts_elements = np.unique(genres, return_counts=True)
    counts_elements = counts_elements.astype(float)
    counts_elements /= counts_elements.sum()
    genres = np.asarray((unique_elements, counts_elements))
    genres = genres[0][genres[1] >= 0.30]

    # find user artists in recommender artists
    found_artists = []
    for artist in artists:
        found_artist = recommender.artists[
            recommender.artists.name == artist
        ].name.values
        if found_artist.size > 0:
            found_artists.append(found_artist[0])

    if not genres:
        message.edit_text(text["insufficient_data"].format(platform_text))
    else:
        context.user_data["preferences"] = Preferences(genres, found_artists)
        context.bot_data["db"].update_preferences(context.user_data["preferences"])
        message.edit_text(text["done"])

    return END


@log
@get_user
def reset_shuffle(update: Update, context: CallbackContext) -> int:
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
