"""gets album or song lyrics from Genius"""
import logging
import re
import os
import asyncio
import queue
import time
from typing import Any, Tuple, Optional, Union, List, Dict
from collections import namedtuple

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
    TELETHON_API_ID,
    TELETHON_API_HASH,
    TELETHON_SESSION_STRING,
    ANNOTATIONS_CHANNEL_HANDLE,
    GENIUS_TOKEN,
)

logger = logging.getLogger("geniust")


def lastfm(method: str, parameters_input: dict) -> dict:
    raise NotImplementedError("LASTFM_API_KEY not defined.")
    # Variabls: Set local
    api_key_lastfm = LASTFM_API_KEY
    user_agent_lastfm = "GeniusT"
    api_url_lastfm = "http://ws.audioscrobbler.com/2.0/"
    # Last.fm API header and default parameters
    headers = {"user-agent": user_agent_lastfm}
    parameters = {"method": method, "api_key": api_key_lastfm, "format": "json"}
    parameters.update(parameters_input)
    # Responses and error codes
    state = False
    while state is False:
        try:
            response = requests.get(
                api_url_lastfm, headers=headers, params=parameters, timeout=10
            )
            if response.status_code == 200:
                logger.debug(
                    ("Last.fm API: 200" " - Response was successfully received.")
                )
                state = True
            elif response.status_code == 401:
                logger.debug(
                    ("Last.fm API: 401" " - Unauthorized. Please check your API key.")
                )
            elif response.status_code == 429:
                logger.debug(
                    ("Last.fm API: 429" " - Too many requests. Waiting 60 seconds.")
                )
                time.sleep(5)
                state = False
            else:
                logger.debug(
                    (
                        "Last.fm API: Unspecified error %s."
                        " No response was received."
                        " Trying again after 60 seconds..."
                    ),
                    response.status_code,
                )
                time.sleep(1)
                state = False
        except OSError as err:
            logger.debug("Error: %s. Trying again...", str(err))
            time.sleep(3)
            state = False
    return response.json()


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

    Args:
        Genius (lyricsgenius.Genius): The original Genius class.
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

        if telegram_song:
            replace_hrefs(lyrics, posted_annotations, telegram_song)
        else:
            replace_hrefs(lyrics)

        # remove redundant tags that neither Telegram
        # nor the other formats (PDF and Telegra.ph) support
        for tag in lyrics.find_all():
            if tag.name not in ("br", "strong​", "​b​", "em​", "​i​", "a"):
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

    def fetch(self, track: Dict[str, Any], include_annotations: bool) -> None:
        """fetches song from Genius adds it to the artist object"""
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
        """gets the album from Genius and returns a dictionary"""
        q: queue.Queue = queue.Queue(1)
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        future = asyncio.ensure_future(
            self.search_album(album_id, include_annotations, q)
        )
        new_loop.run_until_complete(future)
        new_loop.close()
        return q.get()


class Sender:  # pragma: no cover
    """Sends HTTP requests."""

    # Create a persistent requests connection

    def __init__(self, timeout=5, sleep_time=0.2, retries=0):
        self._session = requests.Session()
        self._session.headers = {
            "application": "GeniusT",
            "User-Agent": "https://github.com/Allerter/geniust",
        }
        self.timeout = timeout
        self.sleep_time = sleep_time
        self.retries = retries

    def _make_request(self, path, params=None, method="GET", web=False, **kwargs):
        """Makes a request to Genius."""
        uri = path

        params = params if params else {}

        # Make the request
        response = None
        tries = 0
        while response is None and tries <= self.retries:
            tries += 1
            try:
                if method == "GET":
                    response = self._session.request(
                        method, uri, timeout=self.timeout, params=params, **kwargs
                    )
                else:
                    response = self._session.request(
                        method, uri, timeout=self.timeout, data=params, **kwargs
                    )
                logger.debug("%s status code for %s", response.status_code, uri)
                response.raise_for_status()
            except Timeout as e:
                error = "Request timed out:\n{e}".format(e=e)
                logger.error(error)
                if tries > self.retries:
                    response = None
            except HTTPError as e:
                error = str(e)
                logger.error(error)
                if response.status_code < 500 or tries > self.retries:
                    response = None

            # Enforce rate limiting
            time.sleep(self.sleep_time)

        if response is None:
            return None
        elif web:
            return response.text
        else:
            return response.json()


def songs_match(first_artist, first_song, second_artist, second_song):
    if clean_str(first_artist) == clean_str(second_artist) and clean_str(
        first_song
    ) == clean_str(second_song):
        return True
    else:
        return False


MusicSource = namedtuple(
    "MusicSource",
    "name, download_url, search_url, method, parameters",
    defaults=["GET", None],
)


class FaMusic:  # pragma: no cover
    """Interface to APIs of Persian music websites"""

    sources = [
        MusicSource(
            name="nex1music",
            download_url="https://apin1mservice.com/WebService/music-more.php",
            search_url="https://apin1mservice.com/WebService/search.php",
            method="POST",
            parameters={"download": "post_id", "search": "text"},
        ),
        MusicSource(
            name="radiojavan",
            download_url="https://api-rjvn.app/api2/mp3",
            search_url="https://api-rjvn.app/api2/search",
            parameters={"download": "id", "search": "query"},
        ),
        MusicSource(
            name="navahang",
            download_url="https://navahang.co/navaapi2/GetSingleMediaInfo",
            search_url="https://navahang.com/main-search.php",
            parameters={"download": "media_id", "search": "q"},
        ),
    ]

    def __init__(self):
        timeout = 5
        retries = 3
        sleep_time = 0.2
        self.sender = Sender(sleep_time=sleep_time, timeout=timeout, retries=retries)

    def search(self, artist: str, song: str, type: Optional[str] = "song"):
        for source in self.sources:
            params = {source.parameters["search"]: song}
            res = self.sender._make_request(source.search_url, params, source.method)
            logger.info("%s API Search", source.name)
            if res:
                if source.name == "radiojavan":
                    for hit in res["mp3s"]:
                        if songs_match(artist, song, hit["artist"], hit["song"]):
                            return hit["id"], source.name
                elif source.name == "navahang":
                    for hit in res["MP3"]:
                        if songs_match(
                            artist, song, hit["artist_name"], hit["song_name"]
                        ):
                            return hit["id"], source.name
                else:
                    for hit in res[1:]:
                        if songs_match(
                            artist, song, hit["artisten"], hit["tracken"]
                        ) or songs_match(artist, song, hit["artistfa"], hit["trackfa"]):
                            return hit["id"], source.name
        return None, None

    def download_url(self, song_id, song_source):
        for source in self.sources:
            if source.name == song_source:
                break
        else:
            return None
        params = {source.parameters["download"]: song_id}
        res = self.sender._make_request(source.download_url, params, source.method)

        logger.info("%s API Download", source.name)

        if res is None:
            return None
        elif source.name == "radiojavan":
            return res["link"]
        elif source.name == "navahang":
            return res[0]["download"]
        else:
            return res["Music128"]
