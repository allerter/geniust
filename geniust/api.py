"""gets album or song lyrics from Genius"""
import logging
import re
import requests
import string_funcs
import asyncio
import queue
from socket import timeout
from urllib.request import Request, urlopen, quote
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from bs4 import BeautifulSoup
from lyricsgenius.song import Song
from concurrent.futures import ThreadPoolExecutor
from telethon import TelegramClient
from telethon.sessions import StringSession
from constants import (TELETHON_API_ID, TELETHON_API_HASH, TELETHON_SESSION_STRING,
                       ANNOTATIONS_TELEGRAM_CHANNEL, GENIUS_TOKEN)
try:
    import ujson as json
except ImportError:
    import json

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.CRITICAL)
try:
    from bot import logger
except ImportError:
    logger = logging.getLogger(__file__)


class Artist(object):
    """An artist from the Genius.com database.

    Attributes:
        name: (str) Artist name.
        num_songs: (int) Total number of songs of the album
        songs: (list) Unordered list of Song objects of the songs of an album
        songs_urls: (list) Ordered list of song URLs of an album used to put songs in the right order
        album_description: (str) the description of the album scraped from the album page on Genius.com
        annotations: (dict) A dictionary of song annotations where the keys (song URLs) point to each song's annotations
    Methods:
        add_song()
            INPUT: newsong
            OUTPUT: None
        save_lyrics():
            INPUT:
            OUTPUT: lyrics_to_write
    """

    def __init__(self, json_dict):
        """Populate the Artist object with the data from *json_dict*"""
        self._body = json_dict['artist']
        self._url = self._body['url']
        self._api_path = self._body['api_path']
        self._id = self._body['id']
        self._songs = []
        self._num_songs = len(self._songs)
        self._album_description = ''
        self._songs_urls = []
        self._annotations = {}

    def __len__(self):
        return 1

    @property
    def name(self):
        return self._body['name']

    @property
    def songs(self):
        return self._songs

    @property
    def num_songs(self):
        return self._num_songs

    @property
    def songs_urls(self):
        return self._songs_urls

    @property
    def album_description(self):
        return self._album_description

    @property
    def annotations(self):
        return self._annotations

    def add_song(self, newsong):
        """Add a Song object to the Artist object"""

        self._songs.append(newsong)
        self._num_songs += 1
        logger.info(f"Song by {newsong.artist} was added to {self.name}.")

    def save_lyrics(self):
        """Allows user to save all lyrics within an Artist obejct to a .json or .txt file."""
        lyrics_to_write = {'songs': [{} for song in self.songs],
                           'artist': self.name,
                           'album_title': self.songs[0].album,
                           'album_art': self.songs[0]._body['album']['cover_art_url'],
                           'album_description': self.album_description}
        # put songs in lyrics_to_write in the right order
        for song in self.songs:
            i = 0
            for num, url in enumerate(self.songs_urls):
                if song.url == url:
                    i = num
                    break
            else:
                logger.critical(f'Something went wrong here\nsong.url: {song.url}\nurl: {url}')
            lyrics_to_write['songs'][i]['title'] = song.title
            lyrics_to_write['songs'][i]['album'] = song.album
            lyrics_to_write['songs'][i]['artist'] = self.name
            lyrics_to_write['songs'][i]['lyrics'] = song.lyrics
            lyrics_to_write['songs'][i]['image'] = song.song_art_image_url
            lyrics_to_write['songs'][i]['annotations'] = self.annotations[song.url]
            lyrics_to_write['songs'][i]['description'] = '' if song._body['description']['plain'] == '?' else song._body['description']['plain']

        if logger.getEffectiveLevel() == 10:  # DEBUG
            filename = string_funcs.format_title(lyrics_to_write['artist'], lyrics_to_write['album_title'])
            filename = re.sub(r'[\\/:*?\"<>|]', '', filename)
            filename = filename + '.json'
            with open(filename, 'w') as lyrics_file:
                json.dump(lyrics_to_write, lyrics_file)
            logger.debug(f'Wrote {self.num_songs} songs to {filename}.')
        return lyrics_to_write

    def __str__(self):
        """Return a string representation of the Artist object."""
        if self._num_songs >= 1:
            return f'{self.name}, {self._num_songs} song{"s" if self._num_songs != 1 else ""}'

    def __repr__(self):
        return repr((self.name, f'{self._num_songs} songs'))


class _API(object):
    """Interface with the Genius.com API
    Attributes:
        _API_URL: (str) Top-most URL to access the Genius.com API
        _API_REQUEST_TYPES: (dict) Refers each request to its own API endpoint
        _CLIENT_ACCESS_TOKEN: (str) Client access token
        _HEADER_AUTHORIZATION: (str) Authorization for API requests

    Args:
        client_access_token (str): Genius client access token used to make API requests
    """

    # Genius API constants
    _API_URL = 'https://api.genius.com/'
    _API_REQUEST_TYPES =\
        {'song': 'songs/', 'artist': 'artists/',
            'artist-songs': 'artists/songs/', 'search': 'search?q=', 'referents': 'referents?song_id='}
    _PUBLIC_API_URL = 'https://genius.com/api/'

    def __init__(self, client_access_token, client_secret='', client_id=''):
        self._CLIENT_ACCESS_TOKEN = client_access_token
        self._HEADER_AUTHORIZATION = 'Bearer ' + self._CLIENT_ACCESS_TOKEN

    def _make_api_request(self, request_term_and_type, page=1):
        """Send a request (song, artist, or search) to the Genius API, returning a json object
        INPUT:
            request_term_and_type: (tuple) (request_term, request_type, text_format='plain')
        *request term* is a string. If *request_type* is 'search', then *request_term* is just
        what you'd type into the search box on Genius.com. If you have an song ID or an artist ID,
        you'd do this: self._make_api_request('2236','song')
        Returns a json object.
        """

        # The API request URL must be formatted according to the desired
        # request type"""
        api_request = self._format_api_request(request_term_and_type, page=page)

        # Add the necessary headers to the request
        request = Request(api_request)
        request.add_header("Authorization", self._HEADER_AUTHORIZATION)
        request.add_header("User-Agent", "LyricsGenius")
        while True:
            try:
                # timeout set to 7 seconds; automatically retries if times out
                response = urlopen(request, timeout=7)
                raw = response.read().decode()
            except timeout:
                print(f'Timeout raised and caught')
                continue
            except (HTTPError, URLError) as e:
                logger.critical(f'Error raised and caught: {e}')
                continue
            break

        return json.loads(raw)['response']

    def _make_public_request(self, path, page=None):
        """Make a request to the public API
        :rtype: dict
        """
        # Since these requests don't need any credentials, ExelFabu made this method and every other method that
        # uses this public requests static to facilitate the use on the outside
        uri = f'{self._PUBLIC_API_URL}{path}{f"?page={page}" if page is not None else ""}'

        response = None
        while True:
            try:
                response = requests.get(uri)
            except requests.exceptions.Timeout:
                print(f'Timeout raised and caught')
                continue
            except requests.exceptions.RequestException as e:
                logger.critical(f'Error raised and caught: {e}')
                continue
            break

        return response.json()['response'] if response.status_code == 200 else None

    def _format_api_request(self, term_and_type, page=1):
        """Format the request URL depending on the type of request"""

        request_term, request_type = str(term_and_type[0]), term_and_type[1]
        assert request_type in self._API_REQUEST_TYPES, "Unknown API request type"

        # TODO - Clean this up (might not need separate returns)
        if request_type == 'artist-songs':
            return f'{self._API_URL}artists/{quote(request_term)}/songs?per_page=50&page={str(page)}'
        elif request_type == 'song':
            return f'{self._API_URL}{self._API_REQUEST_TYPES[request_type]}{quote(request_term)}?text_format=plain'
        elif request_type == 'referents':
            return f'{self._API_URL}{self._API_REQUEST_TYPES[request_type]}{str(term_and_type[0])}&text_format={term_and_type[2]}&per_page=50'
        else:
            return f'{self._API_URL}{self._API_REQUEST_TYPES[request_type]}{quote(request_term)}'

    def get_song_annotations(self, song_id, text_format='plain'):
        """Return song's annotations with associated fragment in list of tuple."""
        referents = self._make_api_request((song_id, 'referents', text_format))['referents']
        all_annotations = []  # list of tuples(fragment, annotations[])
        for r in referents:
            annotation_id = r['api_path']  # r['id'] isn't always the one ued in href attributes
            annotation_id = int(annotation_id[annotation_id.rfind('/') + 1:])
            annotations = []
            for a in r["annotations"]:
                if text_format == 'plain':
                    annotations.append(a["body"]["plain"])
                else:
                    annotations.append(a["body"]["html"])
            all_annotations.append((annotation_id, annotations))
        return all_annotations

    def _scrape_song_lyrics_from_url(self, URL=None, song_id=None, remove_section_headers=False,
                                     include_annotations=False, telegram_song=False, lyrics_language=None):
        """Use BeautifulSoup to scrape song info off of a Genius song URL"""

        if isinstance(URL, BeautifulSoup):
            html = URL
        else:
            page = requests.get(URL, timeout=10)
            html = BeautifulSoup(page.text, "html.parser")

        # Scrape the song lyrics from the HTML
        old_div = html.find("div", class_="lyrics")
        new_div = html.find("div", class_=re.compile("Lyrics__Root"))

        if old_div:
            lyrics = old_div
        elif new_div:
            lyrics = new_div
        else:
            return "", 0

        # Get song_id
        if song_id is None:
            meta_tag = str(html.find_all("meta"))
            m = re.search(r'{"name":"song_id","values":\["([0-9]+)', meta_tag)
            song_id = m.group(1)

        if remove_section_headers:
            # Remove [Verse] and [Bridge] stuff
            lyrics = re.sub(r'(\[.*?\])*', '', lyrics)
            # Remove gaps between verses
            lyrics = re.sub('\n{2}', '\n', lyrics)

        if include_annotations and not telegram_song:
            self.artist._annotations.update({URL: self.get_song_annotations(song_id)})
        elif include_annotations and telegram_song:
            song_annotations = self.get_song_annotations(song_id, text_format='html')

            newline_pattern = re.compile(r'(\n){2,}')  # Extra newlines
            # remove Genius HTML tags that aren't supported by Telegram HTML Markdown
            # TODO maybe I should switch to BeautifulSoup for annotations too like the lyrics
            remove_tags = re.compile(r'<[/]*p>|<hr>|<[/]*small>|<img .*?>|<[/]*su[bp]>|<[/]*h[1-3]>|<[/]*ul>|<[/]*ol>|</li>')
            search_images = re.compile(r'<img src="(.*?)"')
            posted_annotations = []

            loop = asyncio.new_event_loop()
            client = TelegramClient(StringSession(TELETHON_SESSION_STRING), TELETHON_API_ID, TELETHON_API_HASH, loop=loop)
            client.start()
            for a in reversed(song_annotations):
                annotation = newline_pattern.sub('\n', a[1][0])
                images = search_images.findall(annotation)
                # if the annotations has only one image in it, include it using link preview
                if len(images) == 1:
                    annotation += f'<a href="{images[0]}">&#8204;</a>'
                    preview = True
                else:
                    preview = False

                # remove extra tags and format the annotations to look better
                annotation = remove_tags.sub('', annotation).replace('<li>', '▪️ ').replace('</blockquote>', '\n')
                annotation = re.sub(r'<blockquote>[\n]*', '\n💬 ', annotation)

                # send the first 4096 chars of the annotation to the telegram channel
                msg = client.loop.run_until_complete(client.send_message(entity=ANNOTATIONS_TELEGRAM_CHANNEL,
                                                                         message=annotation[:4096],
                                                                         link_preview=preview, parse_mode='HTML'))
                # used to replace href attributes of <a> tags in the lyrics with links to the annotations
                posted_annotations.append((a[0], f'https://t.me/{ANNOTATIONS_TELEGRAM_CHANNEL}/{msg.id}'))

            client.disconnect()

        # annotation IDs are formatted in two ways in the lyrics:
        # the old lyrics page: somethings#note-12345
        # the new lyrics page: /12345/somethings
        get_id = re.compile(r'(?<=#note-)[0-9]+|(?<=^/)[0-9]+(?=/)')
        # remove extra tags and attributes from the lyrics
        # any tag attribute except href is redundant
        for tag in lyrics.find_all('a'):
            for attribute, value in list(tag.attrs.items()):
                if attribute != 'href':
                    tag.attrs.pop(attribute, None)
                else:
                    # there might be other links in the text except annotations
                    # in that case, their href attribute is set to 0 so as not to skip them later
                    # in string_funcs.format_annotations()
                    if tag.get('class'):
                        if tag['class'][0] not in ['referent', 'ReferentFragment__ClickTarget-oqvzi6-0']:
                            tag[attribute] = 0
                            continue
                    else:
                        tag[attribute] = 0
                        continue
                    # replace the href attribute with either the link to the annotation on telegram or the annotation ID
                    if telegram_song:
                        tag[attribute] = [x[1] for x in posted_annotations if x[0] == int(get_id.search(value)[0])][0]
                    else:
                        tag[attribute] = get_id.search(value)[0]
        # remove redundant tags that neither Telegram nor the other formats (PDF and Telegra.ph) support
        for tag in lyrics.find_all():
            if tag.name not in ['br', 'strong​', '​b​', 'em​', '​i​', 'a']:
                tag.unwrap()
        lyrics = re.sub(r'<br[/]*>', '\n', str(lyrics))
        logger.debug('finished scraping lyrics')
        return lyrics.strip('\n'), song_id


class Genius(_API):
    """User-level interface with the Genius.com API. User can search for songs (getting lyrics) and artists (getting songs)"""

    def search_genius_web(self, search_term, per_page=5):
        """Use the web-version of Genius search"""
        endpoint = "search/multi?"
        params = {'per_page': per_page, 'q': search_term}

        # This endpoint is not part of the API, requires different formatting
        url = "https://genius.com/api/" + endpoint + urlencode(params)
        response = requests.get(url, timeout=5)
        return json.loads(response.text)['response'] if response else None

    def search_song(self, song_url, artist_name="",
                    remove_section_headers=False, include_annotations=False):
        """Scrapes the song lyrics and ID from Genius and returns the Song object
         containing the lyrics, and other info provided by the API
        """
        logger.debug(f'Searching for "{song_url}" by {artist_name}...')
        lyrics, song_id = self._scrape_song_lyrics_from_url(URL=song_url,
                                                            remove_section_headers=remove_section_headers,
                                                            include_annotations=include_annotations)
        json_song = self._make_api_request((song_id, 'song'))

        # clean song description
        json_song['song']['description']['plain'] = re.sub(r'(\n){2,}', '\n', json_song['song']['description']['plain'])
        json_song['song']['description']['plain'] = re.sub(r'\nhttp[s]*.*', '', json_song['song']['description']['plain'])
        # Create the Song object
        song = Song(json_song, lyrics)

        return song

    def search_artist(self, album_link):
        """Creates the artist object by scraping the artist page on Genius"""
        artist_link = album_link[:album_link.rfind('/')].replace('albums', 'artists')
        page = requests.get(artist_link)
        html = BeautifulSoup(page.text, "html.parser")
        meta_tag = str(html.find_all("meta"))
        m = re.search(r'{"name":"artist_id","values":\["([0-9]+)', meta_tag)
        artist_id = m.group(1)
        logger.debug(f'Searching for songs by {artist_id}...')

        # Make Genius API request for the determined artist ID
        json_artist = self._make_api_request((artist_id, 'artist'))
        # Create the Artist object
        return Artist(json_artist)

    def fetch(self, track, artist, include_annotations):
        """fetches song from Genius adds it to the artist object"""
        song = self.search_song(track, artist.name, include_annotations=include_annotations)
        artist.add_song(song)

    async def search_album(self, album_link, include_annotations, q):
        """Get all lyrics from an album and return the album dict"""
        self.artist = self.search_artist(album_link)
        # create index
        index = []
        # get the album page on Genius.com
        r = requests.get(album_link)
        soup = BeautifulSoup(r.text, 'html.parser')
        # get the html section indicating if the album isn't found
        not_found = soup.find('h1', attrs={'class': 'render_404-headline'})
        if not_found is not None and "Page not found" in not_found.text:
            return "Album not found."
        # get the html section indicating if the song is missing lyrics
        missing = soup.find_all('div', attrs={
                                'class': 'chart_row-metadata_element chart_row-metadata_element--large'})
        # get album description
        album_description = soup.find("div", class_="rich_text_formatting").get_text()
        album_description = re.sub(r'(\n){2,}', '\n', album_description)
        album_description = re.sub(r'\nhttp[s]*.*', '', album_description)
        artist._album_description = album_description
        miss_nb = 0
        # count the number of songs without lyrics
        for miss in missing:
            if miss.text.find("(Missing Lyrics)") >= 0 or miss.text.find("(Unreleased)") >= 0:
                miss_nb += 1
        divi = soup.find_all('div', attrs={
                             'class': 'column_layout-column_span column_layout-column_span--primary'})
        for div in divi:
            var = 0
            # get the html section indicating the track numbers (this will be to eliminate sections similar to those of
            # songs but are actually of tracklist or credits of the album)
            mdiv = div.find_all('span', attrs={
                                'class': 'chart_row-number_container-number chart_row-number_container-number--gray'})
            for mindiv in mdiv:

                nb = mindiv.text.replace("\n", "")
                if nb != "":
                    index.append(nb)
            # create a list holding the tracks' titles
            df = []
            ndiv = div.find_all(
                'div', attrs={'class': 'chart_row-content'})
            for mindiv in ndiv:
                link = mindiv.find('a').get('href')
                df.append(link)
                var += 1
                if var == len(index):
                    break
        artist._songs_urls = df
        # loop to add song with title from the list
        with ThreadPoolExecutor(20) as executor:
            loop = asyncio.get_event_loop()
            tasks = [
                loop.run_in_executor(
                    executor,
                    self.fetch,
                    *(track, artist, include_annotations)
                )
                for track in df
            ]
            await asyncio.gather(*tasks)

        # save the lyrics
        album_file = self.artist.save_lyrics()
        q.put(album_file)


def async_album_search(api, link, include_annotations=False):
    """gets the album from Genius and returns a dictionary"""
    q = queue.Queue(1)
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    future = asyncio.ensure_future(Genius.search_album(api, link, include_annotations, q))
    new_loop.run_until_complete(future)
    return q.get()


def test(album_link, include_annotations):
    logger.setLevel(logging.DEBUG)
    genius_api = Genius(GENIUS_TOKEN)
    async_album_search(api=genius_api, link=album_link, include_annotations=include_annotations)
