"""gets album or song lyrics from Genius"""
import logging
import re
import os
import asyncio
import queue

from bs4 import BeautifulSoup
from lyricsgenius import Genius
from concurrent.futures import ThreadPoolExecutor
from telethon import TelegramClient
from telethon.sessions import StringSession

from constants import (
    TELETHON_API_ID,
    TELETHON_API_HASH,
    TELETHON_SESSION_STRING,
    ANNOTATIONS_TELEGRAM_CHANNEL,
    GENIUS_TOKEN
)

try:
    from bot import logger
except ImportError:
    logger = logging.getLogger(__file__)


def telegram_annotation(a):
    annotation = BeautifulSoup(a, 'html.parser')

    # if the annotations has only one image in it,
    # include it using link preview
    if (images := annotation.find_all('img')) and len(images) == 1:
        img = images[0]
        # Invisible <a> tag
        image_a = annotation.new_tag('a', href=img.attrs['src'])
        image_a.string = '&#8204;'
        annotation.append(image_a)
        preview = True
    else:
        preview = False

    # remove extra tags and format the annotations to look better
    valid_tags = ('br', 'strong​', '​b​', 'em​',
                  '​i​', 'a', 'li', 'blockquote')
    for tag in annotation.find_all():
        if tag.name not in valid_tags:
            tag.unwrap()

    annotation = (
        str(annotation)
        .replace('<li>', '▪️ ')
        .replace('</li>', '\n')
        .replace('</blockquote>', '\n')
    )
    annotation = re.sub(r'<blockquote>[\n]*', '\n💬 ', annotation)

    return annotation[:4096], preview


def replace_hrefs(lyrics, posted_annotations=None, telegram_song=False):
    # annotation IDs are formatted in two ways in the lyrics:
    # the old lyrics page: somethings#note-12345
    # the new lyrics page: /12345/somethings
    get_id = re.compile(r'(?<=#note-)[0-9]+|(?<=^/)[0-9]+(?=/)')

    # remove extra tags and attributes from the lyrics
    # any tag attribute except href is redundant
    for tag in lyrics.find_all('a'):
        for attribute, value in list(tag.attrs.items()):
            if attribute != 'href':
                tag.attrs.pop(attribute)
            else:
                # there might be other links in the text except annotations
                # in that case, their href attribute is
                # set to 0 so as not to skip them later
                # in string_funcs.format_annotations()
                if tag.get('class'):
                    class_ = tag['class'][0]
                    if ('referent' not in class_
                            and 'ReferentFragment' not in class_):
                        tag[attribute] = 0
                        continue
                else:
                    tag[attribute] = 0
                    continue

                # replace the href attribute with either the link to the
                # annotation on telegram or the annotation ID
                if telegram_song:
                    url = None
                    for a in posted_annotations:
                        a_id = a[0]
                        a_url = a[1]
                        if a_id == int(get_id.search(value)[0]):
                            url = a_url
                            break
                    tag['href'] = url
                else:
                    tag['href'] = get_id.search(value)[0]


class GeniusT(Genius):

    def __init__(self, *args, **kwargs):
        super().__init__(GENIUS_TOKEN, *args, **kwargs)

        self.response_format = 'html'
        self.retries = 3
        self.timeout = 5

    def song_page_data(self, path):
        endpoint = 'page_data/song'

        params = {'page_path': '/songs/' + path}

        res = self._make_request(endpoint, params_=params, public_api=True)

        return res['page_data']

    def lyrics(self,
               song_id,
               song_url,
               include_annotations=False,
               remove_section_headers=False,
               telegram_song=False,
               ):
        """Uses BeautifulSoup to scrape song info off of a Genius song URL

        Args:
            urlthing (:obj:`str` | :obj:`int`):
                Song ID or song URL.
            remove_section_headers (:obj:`bool`, optional):
                If `True`, removes [Chorus], [Bridge], etc. headers from lyrics.

        Returns:
            :obj:`str` \\|‌ :obj:`None`:
                :obj:`str` If it can find the lyrics, otherwise `None`

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
        annotations = []

        path = song_url.replace("https://genius.com/", "")

        # Scrape the song lyrics from the HTML
        html = BeautifulSoup(
            self._make_request(path, web=True).replace('<br/>', '\n'),
            "html.parser"
        )

        # Determine the class of the div
        lyrics = html.find_all("div", class_=re.compile("^lyrics$|Lyrics__Container"))
        if lyrics is None:
            if self.verbose:
                print("Couldn't find the lyrics section. "
                      "Please report this if the song has lyrics.\n"
                      "Song URL: https://genius.com/{}".format(path))
            return None

        if 'lyrics' in lyrics[0].get('class')[0]:
            lyrics = lyrics[0]
            lyrics = lyrics.find('p') if lyrics.find('p') else lyrics
        else:
            for div in lyrics[1:]:
                lyrics[0].append(div)
            lyrics = lyrics[0]

        if include_annotations and not telegram_song:
            annotations = self.song_annotations(song_id)
        elif include_annotations and telegram_song:
            annotations = self.song_annotations(song_id)

            posted_annotations = []

            loop = asyncio.new_event_loop()
            client = TelegramClient(
                StringSession(TELETHON_SESSION_STRING),
                TELETHON_API_ID,
                TELETHON_API_HASH,
                loop=loop
            )
            client.start()
            for annotation_id, annotation_body in annotations.items():
                annotation, preview = telegram_annotation(annotation_body)

                # send the annotation to the telegram channel
                msg = client.loop.run_until_complete(
                    client.send_message(
                        entity=ANNOTATIONS_TELEGRAM_CHANNEL,
                        message=annotation,
                        link_preview=preview,
                        parse_mode='HTML')
                )
                # used to replace href attributes of <a> tags
                # in the lyrics with links to the annotations
                url = f'https://t.me/{ANNOTATIONS_TELEGRAM_CHANNEL}/{msg.id}'
                posted_annotations.append((annotation_id, url))

            client.disconnect()

        if telegram_song:
            replace_hrefs(lyrics, posted_annotations, telegram_song)
        else:
            replace_hrefs(lyrics)

        # remove redundant tags that neither Telegram
        # nor the other formats (PDF and Telegra.ph) support
        for tag in lyrics.find_all():
            if tag.name not in ('br', 'strong​', '​b​', 'em​', '​i​', 'a'):
                tag.unwrap()

        if remove_section_headers:
            assert telegram_song, False
            # Remove [Verse] and [Bridge] stuff
            lyrics = re.sub(r'(\[.*?\])*', '', lyrics)
            # Remove gaps between verses
            lyrics = re.sub('\n{2}', '\n', lyrics)

        if telegram_song:
            return lyrics
        else:
            return str(lyrics).strip('\n'), annotations

    def song_annotations(self, song_id, text_format=None):
        """Return song's annotations with associated fragment in list of tuple.

        Args:
            song_id (:obj:`int`): song ID
            text_format (:obj:`str`, optional): Text format of the results
                ('dom', 'html', 'markdown' or 'plain').

        Returns:
            :obj:`list`: list of tuples(fragment, [annotations])

        Note:
            This method uses :meth:`Genius.referents`, but provides convenient
            access to fragments (annotated text) and the corresponding
            annotations (Some fragments may have more than one annotation,
            because sometimes both artists and Genius users annotate them).

        """
        text_format = text_format or self.response_format
        assert len(text_format.split(',')), 1

        referents = self.referents(song_id=song_id,
                                   text_format=text_format,
                                   per_page=50)

        all_annotations = {}
        for r in referents['referents']:
            # r['id'] isn't always the one ued in href attributes
            api_path = r['api_path']
            annotation_id = int(api_path[api_path.rfind('/') + 1:])
            annotation = r['annotations'][0]['body'][text_format]

            if annotation_id not in all_annotations.keys():
                all_annotations[annotation_id] = annotation
        return all_annotations

    def fetch(self, track, include_annotations):
        """fetches song from Genius adds it to the artist object"""
        song = track['song']

        annotations = []

        if song['lyrics_state'] == 'complete' and not song['instrumental']:
            lyrics, annotations = self.lyrics(
                song['id'],
                song['url'],
                include_annotations=include_annotations
            )
        elif song['instrumental']:
            lyrics = "[Instrumental]"
        else:
            lyrics = ""

        song.update(
            self.song(song['id'])['song']
        )

        song['lyrics'] = lyrics
        song['annotations'] = annotations

    async def search_album(
        self,
        album_id,
        include_annotations,
        queue,
        text_format=None,
    ):
        """Searches for a specific album and gets its songs.

        You must pass either a :obj:`name` or an :obj:`album_id`.

        Args:
            album_id (:obj:`int`, optional): Album ID.
            include_annotations (:obj:`bool`): Download annotations or not.
            queue(:obj:`queue.Queue`): A :obj:`Queue` object to put the album in.
            text_format (:obj:`bool`, optional): Text format of the response.

        Returns:
            :obj:`dict`

        """
        album = self.album(album_id, text_format)['album']

        album['tracks'] = self.album_tracks(
            album_id,
            per_page=50,
            text_format=text_format
        )['tracks']

        # Get number of available cores
        try:
            threads = len(os.sched_getaffinity(0))
        except AttributeError:  # isn't available in non-Unix systems
            threads = os.cpu_count()
        with ThreadPoolExecutor(threads * 2) as executor:
            loop = asyncio.get_event_loop()
            tasks = [
                loop.run_in_executor(
                    executor,
                    self.fetch,
                    *(track, include_annotations)
                )
                for track in album['tracks']
            ]
            await asyncio.gather(*tasks)

        # return the album by putting it in the queue
        queue.put(album)

    def async_album_search(self, album_id, include_annotations=False):
        """gets the album from Genius and returns a dictionary"""
        q = queue.Queue(1)
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        future = asyncio.ensure_future(
            self.search_album(album_id, include_annotations, q)
        )
        new_loop.run_until_complete(future)
        return q.get()


def test(album_id, include_annotations=False):
    logger.setLevel(logging.DEBUG)
    genius = GeniusT(GENIUS_TOKEN)
    return genius.async_album_search(album_id, include_annotations)
