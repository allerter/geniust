"""
Some regular expressions, and methods used throughout the code.
Kept here in case improvements are added.
"""
import re
import logging
from functools import wraps
from typing import (Any, TypeVar, Callable, Pattern,
                    Optional, List, Union, Tuple, Dict)

from bs4 import BeautifulSoup, NavigableString, Comment
from bs4.element import Tag
from telegram.utils.helpers import create_deep_linked_url

from geniust.constants import TELEGRAM_HTML_TAGS
import geniust

# (\[[^\]\n]+\]|\\n|!--![\S\s]*?!__!)|.*[^\x00-\x7F].*
regex = (
    r'(\[[^\]\n]+\]'  # ignore headers like [Chorus]
    r'|\\n'  # ignore newlines in English lines
    r'|!--![\S\s]*?!__!'  # ignore annotations inside !--! and !__!
    r'|<.*?>)'  # ignore HTML tags
    r'|.*'  # capture the beginning of a sentence that
    r'[^\x00-\x7F]'  # is followed by a non-ASCII character
    r'.*'  # get the rest of the sentence
)
remove_non_english: Pattern[str] = re.compile(regex, re.MULTILINE)

# The two expressions are fairly like
# the one below captures lines in English.
# The only noticeable difference is
# ignoring \u2005 or \u200c characters usually used in Persian.
remove_english: Pattern[str] = re.compile(
    r"(\[[^\]\n]+\]|\\n|\\u200[5c]|!--![\S\s]*?!__!|<.*?>)|^.*[a-zA-Z]+.*",
    re.MULTILINE
)

# remove extra newlines except the ones before headers.
# Removes instances of two or more newlines (either \n or <br>)
newline_pattern: Pattern[str] = re.compile(r'(\n|<br\s*[/]*>){2,}(?!\[)')

# remove links from annotations
links_pattern: Pattern[str] = re.compile(r'\nhttp[s]*.*')


def deep_link(entity: dict) -> str:
    name = entity.get('name', entity.get('title'))
    id_ = entity['id']
    if 'album' in entity['api_path']:
        type_ = 'album'
    elif 'song' in entity['api_path']:
        type_ = 'song'
    elif 'artist' in entity['api_path']:
        type_ = 'artist'
    else:
        raise ValueError(f"Unknown entity {entity['api_path']}")

    url = create_deep_linked_url(geniust.username, f'{type_}_{id_}')

    return f"""<a href="{url}">{name}</a>"""


def remove_unsupported_tags(soup: BeautifulSoup,
                            supported: Optional[List[str]] = None) -> BeautifulSoup:
    if supported is None:
        supported = TELEGRAM_HTML_TAGS

    restart = True
    while restart:
        restart = False
        for tag in soup:
            name = tag.name
            if name is not None and name not in supported:
                if tag.text:
                    tag.unwrap()
                tag.decompose()
                restart = True
                break

    return soup


def remove_extra_newlines(s: str) -> str:
    return newline_pattern.sub('\n', s)


def remove_links(s: str) -> str:
    return links_pattern.sub('', s)


def format_language(lyrics: Union[BeautifulSoup, str],
                    lyrics_language: str
                    ) -> Union[BeautifulSoup, str]:
    """removes (non-)ASCII characters"""
    def string_formatter(s: str) -> str:
        if lyrics_language == 'English':
            s = remove_non_english.sub("\\1", s, 0)
        elif lyrics_language == 'Non-English':
            s = remove_english.sub("\\1", s, 0)
        s = remove_extra_newlines(s)
        return s

    if isinstance(lyrics, Tag):
        strings = [x for x in lyrics.descendants
                   if (isinstance(x, NavigableString)
                       and len(x.strip()) != 0
                       and not isinstance(x, Comment))
                   ]

        for string in strings:
            formatted = string_formatter(str(string))
            string.replace_with(formatted)
    else:
        lyrics = string_formatter(lyrics)

    return lyrics


def format_annotations(
        lyrics: str,
        annotations: List[Tuple[int, str]],
        include_annotations: bool,
        identifiers: Tuple[str, str] = ('!--!', '!__!'),
        format_type: str = 'zip',
        lyrics_language: Optional[str] = None) -> BeautifulSoup:
    """Formats annotations in soup.
    Include the annotations by inspecting <a> tags and
    then remove the unnecessary HTML tags
    in the end.
    """
    soup: BeautifulSoup = BeautifulSoup(lyrics, 'html.parser')
    if include_annotations and annotations:
        used = []
        for a in soup.find_all('a'):
            annotation_id = a.attrs['href']
            if annotation_id in used:
                continue

            if format_type == 'zip':
                annotation_content = (f'<annotation>'
                                      f'\n{identifiers[0]}\n'
                                      f'{annotations[annotation_id]}'
                                      f'\n{identifiers[1]}\n'
                                      f'</annotation>')
            else:
                annotation_content = (f'<annotation>'
                                      f'{annotations[annotation_id]}'
                                      f'</annotation>')
            annotation = BeautifulSoup(annotation_content, 'html.parser')
            # annotation = newline_pattern.sub('\n', annotation)
            # annotation = links_pattern.sub('', annotation)

            for tag in annotation.descendants:
                if hasattr(tag, 'attrs'):
                    for attribute, value in list(tag.attrs.items()):
                        if attribute != 'href':
                            tag.attrs.pop(attribute)
                if tag.name in ('div', 'script', 'iframe'):
                    tag.decompose()
                elif tag.name == 'blockquote':
                    tag.unwrap()

            a.attrs.clear()
            a.insert_after(annotation)
            used.append(annotation_id)

    return soup


def format_title(artist: str, title: str) -> str:
    """removes artist name if "Genius" is in the artist name"""
    if 'Genius' in artist:
        final_title = title
    else:
        final_title = f'{artist} - {title}'
    return final_title


def format_filename(string: str) -> str:
    """removes invalid characters in file name"""
    return re.sub(r'[\\/:*?\"<>|]', '', string)


def get_description(entity: Dict[str, Any]) -> str:
    if not entity.get('description_annotation'):
        return ''

    description = entity['description_annotation']['annotations'][0]['body']['plain']

    if not description:
        return ''

    description = remove_links(description)
    description = remove_extra_newlines(description)

    return description.strip()


def human_format(num: int) -> str:
    # from https://stackoverflow.com/a/579376

    if num < 10000:
        return str(num)

    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0  # type: ignore
    # add more suffixes if you need them

    if num == int(num):
        formatter = '%.1d%s'
    else:
        formatter = '%.1f%s'

    return formatter % (num, ['', 'K', 'M', 'G', 'T', 'P'][magnitude])


RT = TypeVar('RT')


def log(func: Callable[..., RT]) -> Callable[..., RT]:
    logger = logging.getLogger(func.__module__)

    @wraps(func)
    def wrapper(*args, **kwargs) -> RT:
        logger.debug('Entering: %s', func.__name__)
        result = func(*args, **kwargs)
        logger.debug('Exiting: %s (return value: %s)',
                     func.__name__,
                     repr(result))
        return result
    return wrapper
