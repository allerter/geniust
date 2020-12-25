import re
import logging
import asyncio
import json
from socket import timeout
from time import sleep
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Tuple, Union, List

import telegraph
from bs4 import BeautifulSoup

from geniust import utils
from geniust.constants import TELEGRAPH_TOKEN

logger = logging.getLogger('geniust')


def fetch(img: str) -> Tuple[str, str]:
    """Downloads the image and uploads it to telegraph

    Args:
        img (str): Genius image URL.

    Returns:
        Tuple[str, str]: The original image URL and the uploaded one.
    """
    req = Request(img, headers={"User-Agent": "Mozilla/5.0"})
    while True:
        try:
            webpage = urlopen(req)
            path = telegraph.upload.upload_file(webpage)[0]
            cover_art = "https://telegra.ph" + path
        except timeout:
            print("Timeout raised and caught")
            continue
        except (HTTPError, URLError) as e:
            logger.critical(f"Error raised and caught: {e}")
            cover_art = ""
        break
    return img, cover_art


async def download_cover_arts(data: Dict[str, Any], q) -> None:  # type: ignore
    """Downloads covert arts.

    Download and uploads song cover arts asynchronously
    and also avoids downloading and uploading images
    with equal URLs.

    Args:
        data (Dict[str, Any]): Album data.
        q (queue.Queue): Queue to put results in.
    """
    all_pics: List[Union[int, str]] = []
    for track in data["tracks"]:
        song = track["song"]
        img = song["song_art_image_url"]
        for i, uploaded_img in enumerate(all_pics):
            if img == uploaded_img:
                all_pics.append(i)
                break
        else:
            all_pics.append(img)
    all_pics.append(data["cover_art_url"])
    with ThreadPoolExecutor(5) as executor:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(executor, fetch, pic)
            for pic in [x for x in all_pics if type(x) is str]
        ]
        for response in await asyncio.gather(*tasks):
            all_pics = [response[1] if response[0] == x else x for x in all_pics]
    q.put(all_pics)


def create_album_songs(
    account: telegraph.Telegraph, album: Dict[str, Any], user_data: Dict[str, Any]
) -> List[List[str]]:
    """Creates Telegraph pages for songs of the album.

    Args:
        account (telegraph.Telegraph): Telegraph account to upload songs with.
        album (Dict[str, Any]): Album data.
        user_data (Dict[str, Any]): User data.

    Returns:
        List[List[str]]: List of song title and links.
    """
    # lyrics customizations
    include_annotations = user_data["include_annotations"]
    lyrics_language = user_data["lyrics_lang"]
    identifiers = ("!--!", "!__!")
    song_links = []

    artist = album["artist"]["name"]
    translation = True if "Genius" in artist else False

    # create pages
    for track in album["tracks"]:
        song = track["song"]
        lyrics = song["lyrics"]
        title = song["title"]

        # format annotations
        lyrics = utils.format_annotations(
            lyrics,
            song["annotations"],
            include_annotations,
            identifiers,
            format_type="telegraph",
        )

        # formatting language
        lyrics = utils.format_language(lyrics, lyrics_language)

        for tag in lyrics.find_all("blockquote"):
            tag.unwrap()
            tag.decompose()

        # convert annotation text style to quotes
        for tag in lyrics.find_all("annotation"):
            tag.name = "blockquote"

        # include song description
        description = ""
        if song["description"]["html"]:
            description = BeautifulSoup(song["description"]["html"], "html.parser")
            for tag in description:
                if tag.name in ("div", "script"):
                    tag.decompose()
            description = str(description) + "<br><br>"

        cover_art = song["song_art_image_url"]
        caption = f"<figcaption>{title}</figcaption>"
        cover_art = f'<figure><img src="{cover_art}">{caption}</figure><br>'

        if lyrics.find("div"):
            lyrics.find("div").unwrap()

        for a in lyrics.find_all("a"):
            if a.get("href") is None:
                a.name = "u"

        for p in lyrics.find_all("p"):
            p.unwrap()

        for div in lyrics.find_all("div"):
            div.unwrap()
            div.decompose()

        for img in lyrics.find_all("img"):
            img.decompose()

        # lyrics = re.sub(r'<br\s*[/]*>', '\n', str(lyrics))
        lyrics = str(lyrics)
        lyrics = utils.remove_extra_newlines(lyrics)
        lyrics = lyrics.replace("\n", "<br>").replace("</u>", "</u><br>")

        lyrics = f"{cover_art}" f"{description}" f"<aside>{lyrics}</aside>"

        page_title = utils.format_title(artist, title)
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
            title = re.sub(r".*[\s]* - ", "", title)
            # remove "(this_language translation) from title"
            # sometimes it's in brackets because the title itself
            # already has word(s) in parantheses
            if title.rfind(")") < title.rfind("]"):
                title = title[: title.rfind(" [")]
            else:
                title = title[: title.rfind(" (")]

        song_links.append([respone_link, title])
        logger.debug(f"Created {title} at {respone_link}")
    return song_links


def create_pages(album: Dict[str, Any], user_data: Dict[str, Any]) -> str:
    """Creates Telegraph album.

    Creates a Telegraph page for each song and a final
    album page with links to all the tracks.

    Args:
        album (Dict[str, Any]): Album data.
        user_data (Dict[str, Any]): User data.

    Returns:
        str: Telegraph album URL.
    """
    # download cover arts async
    # q = queue.Queue()
    # new_loop = asyncio.new_event_loop()
    # asyncio.set_event_loop(new_loop)
    # future = asyncio.ensure_future(download_cover_arts(album, q))
    # new_loop.run_until_complete(future)
    # cover_arts = q.get()
    # logger.debug(f'Uploaded cover arts')

    # connect to Telegraph account
    account = telegraph.api.Telegraph(access_token=TELEGRAPH_TOKEN)

    # create song pages
    song_links = create_album_songs(account, album, user_data)

    # include album description
    description = album["description_annotation"]["annotations"][0]["body"]["html"]
    if description:
        description = f"<br>{description}<br><br>"

    # put the links in an HTML list
    links = "".join(
        [
            f'<li><a href="{song_link.encode().decode()}">{song_title}</a></li>'
            for song_link, song_title in song_links
        ]
    )
    songs = f"<ol>{links}</ol>"

    # add album cover art to the album post
    album_art = album["cover_art_url"]
    caption = f'<figcaption>{album["name"]}</figcaption>'
    album_art = f'<figure><img src="{album_art}">{caption}</figure>'

    page_text = f"{album_art}" f"{description}" f"Songs:<br>{songs}"

    title = utils.format_title(album["artist"]["name"], album["name"])

    # create the album post
    response = account.create_page(title=title, html_content=page_text)
    response_link = f'https://telegra.ph/{response["path"]}'

    return response_link


def test(json_file: str, lyrics_language: str, include_annotations: bool) -> None:
    logging.getLogger('geniust').setLevel(logging.DEBUG)
    user_data: Any = {
        "lyrics_lang": lyrics_language,
        "include_annotations": include_annotations,
    }
    with open(json_file, "r") as f:
        data = json.load(f)
    print(create_pages(album=data, user_data=user_data))
