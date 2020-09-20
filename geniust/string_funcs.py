"""
Some regular expressions, and methods used throughout the code.
Kept here in case improvements are added.
"""
import re
# (\[[^\]\n]+\]|\\n|!--![\S\s]*?!__!)|.*[^\x00-\x7F].*
remove_non_english = re.compile(r"""(\[[^\]\n]+\] # ignore headers
                            |\\n  # ignore newlines in English lines
                            |!--![\S\s]*?!__!  # ignore annotations and HTML tags which are inside !--! and !__! identifiers
                            |<.*?>) # ignore HTML tags
                            |.*  # capture the beginning of sentence
                            [^\x00-\x7F]  # but must be followed by a non-ASCII character
                            .*  # get the rest of the sentence
                            """, re.MULTILINE | re.VERBOSE)

# the two expressions below are  fairly like the ones below except they capture English lines
# the only noticeable difference is ignoring \u2005 or \u200c characters usually used in Persian
remove_english = re.compile(r"(\[[^\]\n]+\]|\\n|\\u200[5c]|!--![\S\s]*?!__!|<.*?>)|^.*[a-zA-Z]+.*", re.MULTILINE)
newline_pattern = re.compile(r'(\n){2,}(?!\[)')  # remove extra newlines except the ones before headers
# header_pattern = re.compile(r'') add newline before headers where there is only one newline before them TODO
links_pattern = re.compile(r'\nhttp[s].*')  # remove links from annotations


def format_language(lyrics, lyrics_language):
    """removes English/Non-English characters or returns the unchanged lyrics"""
    if lyrics_language == 'English':
        lyrics = remove_non_english.sub("\\1", lyrics, 0)
    elif lyrics_language == 'Non-English':
        lyrics = remove_english.sub("\\1", lyrics, 0)
    lyrics = newline_pattern.sub('\n', lyrics)
    return lyrics


def format_annotations(lyrics, annotations, include_annotations,
                       identifiers=['!--!', '!__!'], format_type='zip', lyrics_language=None):
    """Include the annotations by inspecting <a> tags and then remove the unnecessary HTML tags
     in the end.
    """
    if include_annotations and annotations:
        used = [0]
        for a in re.finditer(r'<a href="(.*?)">(.*?)</a>', lyrics, re.DOTALL):
            a_tag = a.group(0)
            annotated_text = a.group(2)
            annotation_id = int(a.group(1))
            if annotation_id in used:
                continue

            annotation = [x[1][0] for x in annotations if int(x[0]) == annotation_id]
            if annotation:
                annotation = annotation[0]
            else:
                print('annotation not found: ', annotation)
                print(annotation_id)
                print(a_tag[:10])
                continue
            annotation = newline_pattern.sub('\n', annotation)
            annotation = links_pattern.sub('', annotation)

            if format_type == 'telegraph':
                f = f'{annotated_text}\n{identifiers[0]}{annotation}{identifiers[1]}'
            elif format_type == 'pdf':
                annotation = identifiers[0].join(annotation.splitlines(True))
                f = f'{format_language(annotated_text, lyrics_language)}\n{identifiers[0]}{annotation}\n'
            elif format_type == 'zip':
                f = f'{annotated_text}\n{identifiers[0]}\n{annotation}\n{identifiers[1]}\n'

            lyrics = lyrics.replace(a_tag, f, 1)
            used.append(annotation_id)
    if format_type in ['telegraph', 'pdf']:
        # remove all tags except b, br, strong, em and i
        lyrics = re.sub(r'<(?:\/(?!(?:b|br|strong|em|i)>)[^>]*|(?!\/)(?!(?:b|br|strong|em|i)>)[^>]*)>', '', lyrics)
    elif format_type == 'zip':
        lyrics = re.sub(r'<.*?>', '', lyrics)
    return lyrics


def format_title(artist, title):
    """removes artist name if "Genius" is in the artist name"""
    if 'Genius' in artist:
        final_title = title
    else:
        final_title = f'{artist} - {title}'
    return final_title


def format_filename(string):
    """removes invalid characters in file name"""
    return re.sub(r'[\\/:*?\"<>|]', '', string)
