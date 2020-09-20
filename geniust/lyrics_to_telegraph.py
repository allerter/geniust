import re
import logging
import asyncio
import queue
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from socket import timeout
from concurrent.futures import ThreadPoolExecutor
from time import sleep

import telegraph

import string_funcs
from constants import TELEGRAPH_TOKEN

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.CRITICAL)
try:
    from bot import logger
except ImportError:
    logger = logging.getLogger(__file__)


def fetch(img):
    """downloads the image and uploads it to telegraph"""
    req = Request(img, headers={'User-Agent': 'Mozilla/5.0'})
    while True:
        try:
            webpage = urlopen(req)
            cover_art = 'https://telegra.ph' + telegraph.upload.upload_file(webpage)[0]
        except timeout:
            print('Timeout raised and caught')
            continue
        except (HTTPError, URLError) as e:
            logger.critical(f'Error raised and caught: {e}')
        break
    return (img, cover_art)


async def download_cover_arts(data, q):
    """downloads covert arts, optimizing threads.
    Avoids uploading the same pic more than once.
    """
    all_pics = []
    for song in data['songs']:
        img = song['image']
        for i, uploaded_img in enumerate(all_pics):
            if img == uploaded_img:
                all_pics.append(i)
                break
        else:
            all_pics.append(img)
    all_pics.append(data['album_art'])
    with ThreadPoolExecutor(5) as executor:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(
                executor,
                fetch,
                pic
            )
            for pic in [x for x in all_pics if type(x) is str]
        ]
        for response in await asyncio.gather(*tasks):
            all_pics = [response[1] if response[0] == x else x for x in all_pics]
    q.put(all_pics)


def create_album_songs(account, data, cover_arts, user_data):
    ''' create telegraph pages for songs of the album.'''
    # lyrics customizations
    include_annotations = user_data['include_annotations']
    lyrics_language = user_data['lyrics_lang']
    identifiers = ['!--!', '!__!']
    song_links = []
    artist = data['artist']
    translation = True if 'Genius' in artist else False

    # create pages
    for i, song in enumerate(data['songs']):
        lyrics = song['lyrics']
        title = song['title']

        # format annotations
        lyrics = string_funcs.format_annotations(lyrics, song['annotations'],
                                                 include_annotations, identifiers,
                                                 format_type='telegraph')

        # formatting language
        lyrics = string_funcs.format_language(lyrics, lyrics_language)
        # convert annotation text style to quotes
        lyrics = lyrics.replace('!--!', '<blockquote>').replace('!__!', '</blockquote>')
        # styling lyrics
        lyrics = f'<aside>{lyrics}</aside>'
        # include song description
        if song['description']:
            lyrics = f'{song["description"]}\n\n{lyrics}'
        # place covert art in page
        # TODO: compare images to avoid placing pics
        # that have a higher resolution available
        cover_art = cover_arts[i]
        cover_art = cover_art if type(cover_art) is str else cover_arts[cover_art]
        caption = f'<figcaption>{title}</figcaption>'
        lyrics = f'<figure><img src="{cover_art}">{caption}</figure><br>{lyrics}'

        # set line breaks for HTML
        lyrics = lyrics.replace('\n', '<br>')

        page_title = string_funcs.format_title(song['artist'], song['title'])

        # create telegraph page
        j = 0.2
        while True:
            try:
                response = account.create_page(title=page_title, html_content=lyrics)
                break
            except telegraph.TelegraphException:
                sleep(j)
                j += 0.2
                continue
        # store song page link
        respone_link = f'https://telegra.ph/{response["path"]}'

        if translation:
            # remove artist name from song title
            title = re.sub(r'.*[\s]* - ', '', title)
            # remove "(this_language translation) from title"
            # sometimes it's in brackets because the title itself
            # already has word(s) in parantheses
            if title.rfind(')') < title.rfind(']'):
                title = title[:title.rfind(' [')]
            else:
                title = title[:title.rfind(' (')]

        song_links.append([respone_link, title])
        logger.debug(f'Created {title} at {respone_link}')
    return song_links


def create_pages(user_data, data):
    """creates telegraph page of an album
    Returns the link to the final page.
    """
    # download cover arts async
    q = queue.Queue()
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    future = asyncio.ensure_future(download_cover_arts(data, q))
    new_loop.run_until_complete(future)
    cover_arts = q.get()
    logger.debug(f'Uploaded cover arts')
    # connect to Telegraph account
    account = telegraph.api.Telegraph(access_token=TELEGRAPH_TOKEN)

    # create song pages
    song_links = create_album_songs(account, data, cover_arts[:-1], user_data)
    page_text = ''
    # include album description
    if data['album_description']:
        page_text = f'{data["album_description"]}\n\nSongs:\n'
    # put the links in an HTML list
    links = ''.join(
        [f'<li><a href="{song_link.encode().decode()}">{song_title}</a></li>'
        for song_link, song_title in song_links]
    )

    page_text = f'{page_text}<ol>{links}</ol>'

    # add album cover art to the album post
    album_art = cover_arts[-1]
    caption = f'<figcaption>{data["album_title"]}</figcaption>'
    page_text = f'<figure><img src="{album_art}">{caption}</figure>{page_text}'

    # set line breaks for HTML
    page_text = page_text.replace('\n', '<br>')

    title = string_funcs.format_title(data['artist'], data['album_title'])

    # create the album post
    response = account.create_page(title=title, html_content=page_text)
    response_link = f'https://telegra.ph/{response["path"]}'
    # TODO shortening the link via a link-shortener service text
    return response_link


def test(json_file, lyrics_language, include_annotations):
    logging.getLogger(__name__).setLevel(logging.DEBUG)
    user_data = {
        'lyrics_lang': lyrics_language,
        'include_annotations': include_annotations
    }
    with open(json_file, 'r') as f:
        data = json.loads(f.read())
    print(create_pages(user_data=user_data, data=data))
