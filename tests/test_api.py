import pytest
import re
from unittest.mock import MagicMock, patch, create_autospec

from bs4 import BeautifulSoup
from telethon import TelegramClient

from geniust import api


@pytest.fixture(scope='module')
def annotation():
    annotation = (
        '<p><a href="https://genius.com/artists/Mac-miller" rel="noopener"'
        'data-api_path=/artists/820>Mac Miller</a>'
        'was a rapper, songwriter, and record producer from Pittsburgh,'
        'Pennsylvania, who died of an'
        '<a href=https://www.rollingstone.com/music/music-news/mac-miller-cause-of-deat'
        'h-fentanyl-cocaine-alcohol-751974/ rel=noopener nofollow>apparent drug ov'
        'erdose</a> in September 2018. MGK told <a href=https://youtu.be/fgrbH'
        'auJYkQ?t=608 rel=noopener nofollow><em>Complex</em></a> after M'
        'iller’s death that they recorded a song together, but it never came out.</p>'
        '<p><img src=https://images.genius.com/e54e96b1e0abbaa7679094bd12583a8'
        '6.330x412x1.jpg alt= width=330 height=412 data-animated=false></p>'
    )
    return annotation


@pytest.fixture(scope='module')
def page(genius, song_url):
    path = song_url.replace("https://genius.com/", "")
    page = genius._make_request(path, web=True)
    return page


@pytest.fixture(scope='function')
def lyrics(page):
    html = BeautifulSoup(page.replace('<br/>', '\n'), 'html.parser')
    lyrics = html.find_all("div", class_=re.compile("^lyrics$|Lyrics__Container"))
    if lyrics[0].get('class')[0] == 'lyrics':
        lyrics = lyrics[0]
        lyrics = lyrics.find('p') if lyrics.find('p') else lyrics
    else:
        br = html.new_tag('br')
        try:
            for div in lyrics[1:]:
                lyrics[0].append(div).append(br)
        except Exception as e:
            msg = f'{str(e)} with {div.attrs}'
            print(msg)
        lyrics = lyrics[0]

    return lyrics


@pytest.fixture(scope='module')
def annotations(genius, song_id):
    return genius.song_annotations(song_id, 'html')


@pytest.fixture(scope='module')
def posted_annotations(genius, song_id, annotations):
    posted = []
    for id_, text in annotations.items():
        posted.append((id_, f'link_{id_}'))

    return posted


def test_telegram_annotation(annotation):
    returned_annotation, preview = api.telegram_annotation(annotation)

    assert preview is True, "Annotation preview wasn't true"
    assert '&#8204;' in returned_annotation, 'No non-width space char in annotation'


def test_replace_hrefs(lyrics, posted_annotations):
    api.replace_hrefs(lyrics)

    ids = [x[0] for x in posted_annotations]
    for a in lyrics.find_all('a'):
        if (id_ := int(a.get('href'))) != 0:
            assert id_ in ids, "annotation ID wasn't in lyrics"


def test_replace_hrefs_telegram_song(lyrics, posted_annotations):
    telegram_song = True

    api.replace_hrefs(lyrics, posted_annotations, telegram_song)

    msg = "Annotation link wasn't found in the tags"
    for text in [x[1] for x in posted_annotations]:
        assert lyrics.find('a', attrs={'href': text}) is not None, msg


def test_lyrics_no_annotations(genius, song_id, song_url, page):
    page = MagicMock(return_value=page)

    current_module = 'geniust.api'
    with patch(current_module + '.GeniusT._make_request', page):
        lyrics, annotations = genius.lyrics(song_id=song_id,
                                            song_url=song_url,
                                            include_annotations=False,
                                            telegram_song=False)
    assert isinstance(lyrics, str), "Lyrics wasn't a string"
    assert annotations == [], "Annotations weren't empty"


def test_lyrics_telegram_song(genius, song_id, song_url, page, annotations):
    page = MagicMock(return_value=page)
    telethon_client = create_autospec(TelegramClient)
    annotations = MagicMock(return_value=annotations)

    current_module = 'geniust.api'
    with patch(current_module + '.GeniusT._make_request', page), \
            patch(current_module + '.GeniusT.song_annotations', annotations), \
            patch(current_module + 'telethon.TelegramClient', telethon_client):
        lyrics = genius.lyrics(song_id=song_id,
                               song_url=song_url,
                               include_annotations=True,
                               telegram_song=True)
    assert isinstance(lyrics, str), "Lyrics wasn't a string"
