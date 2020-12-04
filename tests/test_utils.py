import re
from unittest.mock import patch, MagicMock

import pytest
from telegram.utils.helpers import create_deep_linked_url
from bs4 import BeautifulSoup

from geniust import utils, api


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

    api.replace_hrefs(lyrics)

    # remove redundant tags that neither Telegram
    # nor the other formats (PDF and Telegra.ph) support
    for tag in lyrics.find_all():
        if tag.name not in ('br', 'strong​', '​b​', 'em​', '​i​', 'a'):
            tag.unwrap()

    return str(lyrics).strip()


def test_deep_link():
    username = 'test_bot'
    entity = {'name': 'test_name',
              'api_path': 'artist',
              'id': 1,
              }
    url = create_deep_linked_url(username, f"artist_{entity['id']}")
    final_link = f"""<a href="{url}">{entity['name']}</a>"""

    with patch('geniust.username', username):
        res = utils.deep_link(entity)

    assert res == final_link


def test_remove_unsupported_tags():
    html = ('<a>t</a>'
            '<b>t</b>'
            '<img>'
            '<u>t</u>'
            '<invalid>t</invalid>'
            )
    soup = BeautifulSoup(html, 'html.parser')

    utils.remove_unsupported_tags(soup)

    assert soup.find('img') is None
    assert soup.find('invalid') is None
    assert soup.get_text().count('t') == 4


def test_remove_unsupported_tags_my_tags():
    html = ('<a>t</a>'
            '<b>t</b>'
            '<img>'
            '<u>t</u>'
            '<invalid>t</invalid>'
            )
    soup = BeautifulSoup(html, 'html.parser')
    supported = ['a', 'b', 'invalid']

    utils.remove_unsupported_tags(soup, supported)

    assert soup.find('img') is None
    assert soup.find('u') is None
    assert soup.find('invalid') is not None
    assert soup.get_text().count('t') == 4


def test_remove_extra_newlines():
    string = "text\n\nsome_text\n\n[verse]\n<br>\nmore_text"

    res = utils.remove_extra_newlines(string)

    assert res.find('\n\n[verse]') != -1
    assert res.find('text\nsome_text') != -1
    assert res.find('<br>') == -1


def test_remove_links():
    string = "text\nhttps://example.com\ntext\nhttp://example.com\ntext"

    res = utils.remove_links(string)

    assert res == 'text\ntext\ntext'


@pytest.mark.parametrize('language', ['English',
                                      'Non-English',
                                      'English + Non-English'])
def test_format_language_str(language):
    string = 'line with ütf8 chars.\nline with only ascii chars\nخط فقط با غیر اسمی۲'

    res = utils.format_language(string, language)

    if language == 'English':
        assert res == '\nline with only ascii chars\n'
    elif language == 'Non-English':
        assert res == '\nخط فقط با غیر اسمی۲'
    else:
        assert res == string


@pytest.mark.parametrize('language', ['English',
                                      'Non-English',
                                      'English + Non-English'])
def test_format_language_soup(lyrics, language):
    soup = BeautifulSoup(lyrics, 'html.parser')

    utils.format_language(soup, language)

    if language == 'English':
        lyrics = str(soup.get_text())
        assert re.match(r'[^\x00-\x7F]', lyrics) is None
    elif language == 'Non-English':
        lyrics = re.sub(r'(\[.*?\]|\n)', '', str(soup.get_text()))
        assert re.match(r'[\x00-\x7F]', lyrics) is None
    else:
        assert str(soup) == lyrics


@pytest.mark.parametrize('format_type', ['zip',
                                         'else'])
def test_format_annotations(lyrics, annotations, format_type):

    num_annotations = len(annotations.keys())

    res = utils.format_annotations(lyrics,
                                   annotations,
                                   include_annotations=True,
                                   format_type=format_type)

    assert len(res.find_all('annotation')) == num_annotations

    if format_type == 'zip':
        assert res.get_text().count('!--!') == num_annotations


@pytest.mark.parametrize('artist, title', [('Genius Translation', 'test_name'),
                                           ('test_artist', 'test_name')])
def test_format_title(artist, title):

    res = utils.format_title(artist, title)

    if 'Genius' in artist:
        assert res == 'test_name'
    else:
        assert res == 'test_artist - test_name'


@pytest.mark.parametrize('entity', [pytest.lazy_fixture('album_dict'),
                                    pytest.lazy_fixture('artist_dict'),
                                    pytest.lazy_fixture('song_dict'),
                                    {'entity': {}}])
def test_get_description(entity):
    entity = entity[list(entity)[0]]

    res = utils.get_description(entity)

    assert isinstance(res, str)


@pytest.mark.parametrize('number, result', [(2000, '2000'),
                                            (10000, '10K'),
                                            (154000, '154K'),
                                            (2400000, '2.4M'),
                                            ])
def test_human_format(number, result):

    res = utils.human_format(number)

    assert res == result


def test_log():
    func = MagicMock()
    func.__name__ = 'test_log'
    logger = MagicMock()

    with patch('logging.getLogger', logger):
        res = utils.log(func)
        res(1, 2, a='a')

    func.assert_called_once_with(1, 2, a='a')
    assert logger().debug.call_count == 2
