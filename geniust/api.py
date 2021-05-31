"""gets album or song lyrics from Genius"""
import logging
import re
import os
import asyncio
import queue
from json.decoder import JSONDecodeError
from typing import Any, Tuple, Optional, Union, List, Dict
from dataclasses import dataclass
from io import BytesIO

import requests
import telethon
from requests.exceptions import HTTPError, Timeout
from bs4 import BeautifulSoup
from lyricsgenius import Genius, PublicAPI
from lyricsgenius.utils import clean_str
from concurrent.futures import ThreadPoolExecutor
from telethon.sessions import StringSession
from telethon import types

from geniust.constants import (
    RECOMMENDER_TOKEN,
    TELETHON_API_ID,
    Preferences,
    TELETHON_API_HASH,
    TELETHON_SESSION_STRING,
    ANNOTATIONS_CHANNEL_HANDLE,
    GENIUS_TOKEN,
    IMGBB_TOKEN,
)

logger = logging.getLogger("geniust")
IMGBB_API_URL = "https://api.imgbb.com/1/upload"


def get_channel() -> types.TypeInputPeer:
    """Returns telethon Input Peer for the annotations channel

    Returns:
        types.TypeInputPeer
    """

    with telethon.TelegramClient(
        StringSession(TELETHON_SESSION_STRING),
        TELETHON_API_ID,
        TELETHON_API_HASH,
        loop=asyncio.new_event_loop(),
    ) as client:
        return client.loop.run_until_complete(
            client.get_input_entity(ANNOTATIONS_CHANNEL_HANDLE)
        )


def telegram_annotation(a: str) -> Tuple[str, bool]:
    """Formats the annotation for Telegram

    If the annotations has only one image,
    the image is added in an invisible
    space character to the beginning. Then
    all tags not supported by Telegram are
    removed.

    Args:
        a (str): an annotation

    Returns:
        Tuple[str, bool]: formatted annotation and
            preview if link preview should be activated.
    """
    a = a.replace("<p>", "").replace("</p>", "")
    annotation = BeautifulSoup(a, "html.parser")

    # if the annotations has only one image in it,
    # include it using link preview
    if (images := annotation.find_all("img")) and len(images) == 1:
        img = images[0]
        # Invisible <a> tag
        image_a = annotation.new_tag("a", href=img.attrs["src"])
        image_a.string = "&#8204;"
        annotation.insert(0, image_a)
        preview = True
    else:
        preview = False

    # remove extra tags and format the annotations to look better
    valid_tags = ("br", "strong​", "​b​", "em​", "​i​", "a", "li", "blockquote")
    restart = True
    while restart:
        restart = False
        for tag in annotation.find_all():
            if tag.name == "div":
                tag.replace_with("")
                restart = True
                break
            elif tag.name not in valid_tags:
                tag.unwrap()
                restart = True
                break

    # remove unnecessary attributes (all except href)
    for tag in annotation:
        if hasattr(tag, "attrs"):
            for attr in list(tag.attrs.keys()):
                if attr != "href":
                    tag.attrs.pop(attr)

    annotation = (
        str(annotation)
        .replace("&amp;", "&")  # bs4 escapes the '&' in '&#8204;'
        .replace("<li>", "▪️ ")
        .replace("</li>", "\n")
        .replace("</blockquote>", "\n")
    )
    annotation = re.sub(r"<blockquote>[\n]*", "\n💬 ", annotation)
    annotation = re.sub(r"^(?!💬)\n{2,}", "\n\n", annotation)

    return annotation[:4096], preview


def replace_hrefs(
    lyrics: BeautifulSoup,
    posted_annotations: Optional[List[Tuple[int, str]]] = None,
    telegram_song: bool = False,
) -> None:
    """Replaced the href of <a> tags with annotation IDs or links

    This function replaces the href attributes with the annotation
    ID inside the href or with a link to a Telegram post (uploaded
    annotation) so the annotated fragment can be linked to the
    annotation.

    Args:
        lyrics (BeautifulSoup): song lyrics as a BeautifulSoup object
        posted_annotations (List[Tuple[int, str]], optional):
            List of uploaded annotations to Telegram with tuples of
            annotation IDs and their corresponding Telegram post. Defaults to [].
        telegram_song (bool, optional): Indicates if it's the lyrics is meant
            for Telegram. Defaults to False.
    """
    if posted_annotations is None:
        posted_annotations = []
    # annotation IDs are formatted in two ways in the lyrics:
    # the old lyrics page: somethings#note-12345
    # the new lyrics page: /12345/somethings
    get_id = re.compile(r"(?<=#note-)[0-9]+|(?<=^/)[0-9]+(?=/)")

    # remove extra tags and attributes from the lyrics
    # any tag attribute except href is redundant
    for tag in lyrics.find_all("a"):
        for attribute, value in list(tag.attrs.items()):
            if attribute != "href":
                tag.attrs.pop(attribute)
            else:
                # there might be other links in the text except annotations
                # in that case, their href attribute is
                # set to 0 so as not to skip them later
                # in string_funcs.format_annotations()
                if tag.get("class"):
                    class_ = tag["class"][0]
                    if "referent" not in class_ and "ReferentFragment" not in class_:
                        tag[attribute] = 0
                        continue
                else:
                    tag[attribute] = 0
                    continue

                # replace the href attribute with either the link to the
                # annotation on telegram or the annotation ID
                if telegram_song:
                    url = "0"
                    for a in posted_annotations:
                        a_id = a[0]
                        a_url = a[1]
                        match = get_id.search(value)
                        if match and int(a_id) == int(match[0]):
                            url = a_url
                            break
                    tag["href"] = url
                else:
                    match = get_id.search(value)
                    tag["href"] = match[0] if match else "0"


class GeniusT(Genius):
    """Interface to Genius

    This class inherits lyricsgenius.Genius and overrides some
    methods to provide the functionality needed for the bot.
    """

    def __init__(self, *args, **kwargs):
        token = GENIUS_TOKEN if not args else args[0]
        super().__init__(token, *args, **kwargs)

        self.response_format = "html,plain"
        self.retries = 3
        self.timeout = 5
        self.public_api = True
        self.annotations_channel = None

    def artist(
        self,
        artist_id: int,
        text_format: Optional[str] = None,
        public_api: bool = False,
    ) -> Dict[str, dict]:
        """Gets data for a specific artist.

        Args:
            artist_id (int): Genius artist ID
            text_format (str, optional): Text format of the results
                ('dom', 'html', 'markdown' or 'plain').
            public_api (bool, optional): If `True`, performs the search
                using the public API endpoint.
        Returns:
            dict
        Note:
            Using the public API will return the same artist but with more fields:
            - API: Result will have 19 fields.
            - Public API: Result will have 24 fields.
        """
        if public_api or self.public_api:
            return super(PublicAPI, self).artist(artist_id, text_format)
        else:
            if self.access_token is None:
                raise ValueError("You need an access token for the developers API.")
            return super().artist(artist_id, text_format)

    def song(
        self, song_id: int, text_format: Optional[str] = None, public_api: bool = False
    ) -> Dict[str, dict]:
        """Gets data for a specific song.

        Args:
            song_id (int): Genius song ID
            text_format (str, optional): Text format of the results
                ('dom', 'html', 'markdown' or 'plain').
            public_api (bool, optional): If `True`, performs the search
                using the public API endpoint.
        Returns:
            dict
        Note:
            Using the public API will return the same song but with more fields:
            - API: Song will have 39 fields.
            - Public API: Song will have 68 fields.
        """
        if public_api or self.public_api:
            return super(PublicAPI, self).song(song_id, text_format)
        else:
            if self.access_token is None:
                raise ValueError("You need an access token for the developers API.")
            return super().song(song_id, text_format)

    def search_songs(
        self,
        search_term: str,
        per_page: Optional[int] = None,
        page: Optional[int] = None,
        public_api: bool = False,
        match: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        """Searches songs hosted on Genius.

        Args:
            search_term (str): A term to search on Genius.
            per_page (int, optional): Number of results to
                return per page. It can't be more than 5 for this method.
            page (int, optional): Number of the page.
            public_api (bool, optional): If `True`, performs the search
                using the public API endpoint.
            match (tuple, optional): If it's not None, matches the hits
                with the tuple(artist, title) and returns the song if it
                matches. Otherwise returns {'match': None}.

        Returns:
            dict

        Note:
            Using the API or the public API returns the same results. The only
            difference is in the number of values each API returns.
            - API: Each song has 17 fields and songs are
              accessable through ``response['hits']``
            - Public API: Each song has 21 fields and songs are accessible
              through ``response['sections'][0]['hits']``
        """
        if public_api or self.public_api:
            res = super(PublicAPI, self).search_songs(search_term, per_page, page)
            if match:
                res = res["sections"][0]
        else:
            if self.access_token is None:
                raise ValueError("You need an access token for the developers API.")
            res = super().search_songs(search_term, per_page, page)

        if match is None:
            return res
        else:
            for hit in res["hits"]:
                song = hit["result"]
                if clean_str(song["primary_artist"]["name"]) == clean_str(
                    match[0]
                ) and clean_str(song["title"]) == clean_str(match[1]):
                    return {"match": song}
            return {"match": None}

    def lyrics(
        self,
        song_id: int,
        song_url: str,
        include_annotations: bool = False,
        remove_section_headers: bool = False,
        telegram_song: bool = False,
    ) -> Union[Tuple[str, Dict[int, str]], str]:
        """Uses BeautifulSoup to scrape song info off of a Genius song URL

        Args:
            urlthing (str | int):
                Song ID or song URL.
            remove_section_headers (bool, optional):
                If `True`, removes [Chorus], [Bridge], etc. headers from lyrics.

        Returns:
            str \\|‌ None:
                str If it can find the lyrics, otherwise `None`

        Note:
            If you pass a song ID, the method will have to make an extra request
            to obtain the song's URL and scrape the lyrics off of it. So it's best
            to pass the method the song's URL if it's available.

            If you want to get a song's lyrics by searching for it,
            use :meth:`Genius.search_song` instead.

        Note:
            This method removes the song headers based on the value of the
            :attr:`Genius.remove_section_headers` attribute.

        """
        annotations: Dict[int, str] = {}
        posted_annotations: List[Tuple[int, str]] = []

        path = song_url.replace("https://genius.com/", "")

        # Scrape the song lyrics from the HTML
        page = self._make_request(path, web=True)
        html = BeautifulSoup(page.replace("<br/>", "\n"), "html.parser")

        # Determine the class of the div
        lyrics = html.find_all("div", class_=re.compile("^lyrics$|Lyrics__Container"))
        if not lyrics:
            logger.error(
                "Couldn't find the lyrics section. "
                "Please report this if the song has lyrics.\n"
                "Song URL: https://genius.com/{}".format(path)
            )
            if telegram_song:
                return "None"
            else:
                return "None", annotations

        if lyrics[0].get("class")[0] == "lyrics":
            lyrics = lyrics[0]
            lyrics = lyrics.find("p") if lyrics.find("p") else lyrics
        else:
            br = html.new_tag("br")
            for div in lyrics[1:]:
                if div.get_text().strip():
                    div.append(br)
                    lyrics[0].append(div)
            lyrics = lyrics[0]

        if include_annotations and not telegram_song:
            annotations = self.song_annotations(song_id, "html")
        elif include_annotations and telegram_song:
            annotations = self.song_annotations(song_id, "html")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            client = telethon.TelegramClient(
                StringSession(TELETHON_SESSION_STRING),
                TELETHON_API_ID,
                TELETHON_API_HASH,
                loop=loop,
            )

            client.start()
            if self.annotations_channel is None:
                self.annotations_channel = get_channel()
            annotations_channel = self.annotations_channel

            for annotation_id, annotation_body in annotations.items():
                annotation, preview = telegram_annotation(annotation_body)

                # send the annotation to the telegram channel
                try:
                    msg = client.loop.run_until_complete(
                        client.send_message(
                            entity=annotations_channel,
                            message=annotation,
                            link_preview=preview,
                            parse_mode="HTML",
                        )
                    )

                    # used to replace href attributes of <a> tags
                    # in the lyrics with links to the annotations
                    url = f"https://t.me/{ANNOTATIONS_CHANNEL_HANDLE}/{msg.id}"
                except telethon.errors.FloodWaitError as e:
                    logger.error(str(e))
                    url = ""
                    break
                posted_annotations.append((annotation_id, url))

            client.disconnect()

        if include_annotations:
            if telegram_song:
                replace_hrefs(lyrics, posted_annotations, telegram_song)
            else:
                replace_hrefs(lyrics)

        # remove redundant tags that neither Telegram
        # nor the other formats (PDF and Telegra.ph) support
        useful_tags = ["br", "strong", "b", "em", "i"]
        if include_annotations:
            useful_tags.append("a")
        for tag in lyrics.find_all():
            if tag.name not in useful_tags:
                tag.unwrap()

        if remove_section_headers:
            assert telegram_song, False
            # Remove [Verse] and [Bridge] stuff
            lyrics = re.sub(r"(\[.*?\])*", "", lyrics)
            # Remove gaps between verses
            lyrics = re.sub("\n{2}", "\n", lyrics)

        if telegram_song:
            return lyrics
        else:
            return str(lyrics).strip("\n"), annotations

    def song_annotations(
        self, song_id: int, text_format: Optional[str] = None
    ) -> Dict[int, str]:
        """Return song's annotations with associated fragment in list of tuple.

        Args:
            song_id (int): song ID
            text_format (str, optional): Text format of the results
                ('dom', 'html', 'markdown' or 'plain').

        Returns:
            list: list of tuples(fragment, [annotations])

        Note:
            This method uses :meth:`Genius.referents`, but provides convenient
            access to fragments (annotated text) and the corresponding
            annotations (Some fragments may have more than one annotation,
            because sometimes both artists and Genius users annotate them).

        """
        text_format = text_format or self.response_format
        assert len(text_format.split(",")) == 1

        referents = self.referents(
            song_id=song_id, text_format=text_format, per_page=50
        )

        all_annotations: Dict[int, str] = {}
        for r in referents["referents"]:
            # r['id'] isn't always the one ued in href attributes
            api_path = r["api_path"]
            annotation_id = int(api_path[api_path.rfind("/") + 1 :])
            annotation = r["annotations"][0]["body"][text_format]

            if annotation_id not in all_annotations.keys():
                all_annotations[annotation_id] = annotation
        return all_annotations

    def download_cover_art(self, url: str) -> BytesIO:
        data = self._session.get(url).content
        return BytesIO(data)

    def fetch(self, track: Dict[str, Any], include_annotations: bool) -> None:
        """fetches song from Genius adds it to the artist objecty

        Args:
            track (Dict[str, Any]): Track dict including track information.
            include_annotations (bool): True or False.
        """
        song = track["song"]

        annotations: Dict[int, str] = {}

        if song["lyrics_state"] == "complete" and not song["instrumental"]:
            lyrics, annotations = self.lyrics(  # type: ignore
                song["id"], song["url"], include_annotations=include_annotations
            )
        elif song["instrumental"]:
            lyrics = "[Instrumental]"
        else:
            lyrics = ""

        song.update(self.song(song["id"])["song"])

        song["lyrics"] = lyrics
        song["annotations"] = annotations

    async def search_album(
        self,
        album_id: int,
        include_annotations: bool,
        queue: queue.Queue,
        text_format: Optional[str] = None,
    ) -> None:
        """Searches for a specific album and gets its songs.

        Overrides the orignal genius.search_album method to
        get the songs asynchronously.

        You must pass either a name or an album_id.

        Args:
            album_id (int, optional): Album ID.
            include_annotations (bool): Retrieve annotations for each song.
            queue(queue.Queue): A Queue object to put the album in.
            text_format (bool, optional): Text format of the response.


        """
        album = self.album(album_id, text_format)["album"]

        album["tracks"] = self.album_tracks(
            album_id, per_page=50, text_format=text_format
        )["tracks"]

        # Get number of available cores
        try:
            threads = len(os.sched_getaffinity(0))  # type: ignore
        except AttributeError:  # pragma: no cover - isn't available in non-Unix systems
            cpu_count = os.cpu_count()
            threads = cpu_count if cpu_count is not None else 4
        with ThreadPoolExecutor(threads * 2) as executor:
            loop = asyncio.get_event_loop()
            tasks = [
                loop.run_in_executor(
                    executor, self.fetch, *(track, include_annotations)
                )
                for track in album["tracks"]
            ]
            await asyncio.gather(*tasks)

        # return the album by putting it in the queue
        queue.put(album)

    def async_album_search(
        self, album_id: int, include_annotations: bool = False
    ) -> Dict[str, Any]:
        """gets the album from Genius and returns a dictionary

        Args:
            album_id (int): Album ID.
            include_annotations (bool, optional): Include annotations
                in album. Defaults to False.

        Returns:
            Dict[str, Any]: Album data and lyrics.
        """
        q: queue.Queue = queue.Queue(1)
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        future = asyncio.ensure_future(
            self.search_album(album_id, include_annotations, q)
        )
        new_loop.run_until_complete(future)
        new_loop.close()
        return q.get()


@dataclass
class SimpleArtist:
    """An artist without full info"""

    id: int
    name: str

    def __repr__(self):
        return f"SimpleArtist(id={self.id})"


@dataclass
class Artist(SimpleArtist):
    """A Artist from the Recommender"""

    description: str

    def __repr__(self):
        return f"Artist(id={self.id})"


@dataclass
class Song:
    """A Song from the Recommender"""

    id: int
    artist: str
    name: str
    genres: List[str]
    id_spotify: Optional[str]
    isrc: Optional[str]
    cover_art: Optional[str]
    preview_url: Optional[str]
    download_url: Optional[str]

    def __repr__(self):
        return f"Song(id={self.id})"


class Recommender:
    API_ROOT = "https://geniust-recommender.herokuapp.com/"

    def __init__(
        self, genres: Optional[List[str]] = None, num_songs: Optional[int] = None
    ):
        self._sender = Sender(self.API_ROOT, access_token=RECOMMENDER_TOKEN, retries=3)
        if num_songs is None:
            try:
                num_songs = self._sender.request("songs/len")["len"]
            except Exception as e:
                logger.warn(e)
                num_songs = 20000

        if genres is None:
            try:
                genres = self._sender.request("genres")["genres"]
            except Exception as e:
                logger.warn(e)
                genres = [
                    "classical",
                    "country",
                    "instrumental",
                    "persian",
                    "pop",
                    "rap",
                    "rnb",
                    "rock",
                    "traditional",
                ]

        self.num_songs: int = num_songs
        self.genres: List[str] = genres
        self.genres_by_number = {}
        for i, genre in enumerate(self.genres):
            self.genres_by_number[i] = genre

    def artist(self, id: int) -> Artist:
        res = self._sender.request(f"artists/{id}")["artist"]
        return Artist(**res)

    def genres_by_age(self, age: int) -> List[str]:
        return self._sender.request("genres", params={"age": age})["genres"]

    def preferences_from_platform(
        self, token: str, platform: str
    ) -> Optional[Preferences]:
        res = self._sender.request(
            "preferences", params={"token": token, "platform": platform}
        )["preferences"]
        return Preferences(**res) if res["genres"] else None

    def search_artist(self, q: str) -> List[SimpleArtist]:
        res = self._sender.request("search/artists", params={"q": q})["hits"]
        return [SimpleArtist(**x) for x in res]

    def shuffle(self, pref: Preferences) -> List[Song]:
        params = {"genres": ",".join(pref.genres)}
        artists = ",".join(pref.artists)
        if artists:
            params["artists"] = artists
        res = self._sender.request(
            "recommendations",
            params=params,
        )["recommendations"]
        return [Song(**x) for x in res]

    def song(self, id: int) -> Song:
        res = self._sender.request(f"songs/{id}")["song"]
        return Song(**res)


class Sender:
    """Sends requests to the GeniusT Recommender."""

    def __init__(
        self,
        api_root: str,
        access_token: str = None,
        timeout: int = 5,
        retries: int = 0,
    ):
        self.api_root = api_root
        self._session = requests.Session()
        self._session.headers = {
            "application": "GeniusT TelegramBot",
            "User-Agent": "https://github.com/allerter/geniust",
        }  # type: ignore
        if access_token:
            self._session.headers["Authorization"] = f"Bearer {access_token}"
        self.timeout: int = timeout
        self.retries: int = retries

    def request(
        self, path: str, method: str = "GET", params: dict = None, **kwargs
    ) -> dict:
        """Makes a request to Genius."""
        uri = self.api_root
        uri += path
        params = params if params else {}

        # Make the request
        response = None
        tries = 0
        while response is None and tries <= self.retries:
            tries += 1
            try:
                response = self._session.request(
                    method, uri, timeout=self.timeout, params=params, **kwargs
                )
                response.raise_for_status()
            except Timeout as e:  # pragma: no cover
                error = "Request timed out:\n{e}".format(e=e)
                logger.warn(error)
                if tries > self.retries:
                    raise Timeout(error)
            except HTTPError as e:  # pragma: no cover
                error = get_description(e)
                if response.status_code < 500 or tries > self.retries:
                    raise HTTPError(response.status_code, error)
        return response.json()


def get_description(e: HTTPError) -> str:  # pragma: no cover
    error = str(e)
    try:
        res = e.response.json()
    except JSONDecodeError:
        res = {}
    description = res["detail"] if res.get("detail") else res.get("error_description")
    error += "\n{}".format(description) if description else ""
    return error


def upload_to_imgbb(image: BytesIO, expiration_date: int = 60) -> dict:
    req = requests.post(
        IMGBB_API_URL,
        data=dict(key=IMGBB_TOKEN, expiration_date=expiration_date),
        files=dict(image=image),
    )
    req.raise_for_status()
    return req.json()
