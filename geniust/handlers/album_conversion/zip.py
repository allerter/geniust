import re
from zipfile import ZipFile, ZIP_DEFLATED
from io import BytesIO
import json
from pathlib import Path
import os
import sys

_root = Path(os.path.realpath(__file__)).parent.parent.parent
sys.path.insert(0, str(_root))

import utils


def create_zip(album, user_data):
    """creates a zip from the data applyting user_data, and returns an in-memory file"""
    bio = BytesIO()
    zip_file = ZipFile(bio, "a", compression=ZIP_DEFLATED)

    # put user_data in variables
    lyrics_language = user_data['lyrics_lang']
    include_annotations = user_data['include_annotations']
    identifiers = ('!--!', '!__!')

    # set zip file name
    name = album['name']
    artist = album['artist']['name']
    full_title = utils.format_title(artist, name)
    full_title = utils.format_filename(full_title)
    bio.name = f'{full_title}.zip'

    # Save the songs as text
    for track in album['tracks']:
        song = track['song']
        number = track['number']
        lyrics = song['lyrics']

        # format annotations
        lyrics = utils.format_annotations(
            lyrics,
            song['annotations'],
            include_annotations,
            identifiers
        )

        # formatting lyrics language
        lyrics = utils.format_language(lyrics, lyrics_language)

        # newlines in text files inside zip files need to be
        # \r\n on Windows
        lyrics = lyrics.get_text().replace('\n', '\r\n')

        # cleaning title name
        title = song['title']
        title = re.sub(r'.*[\s]*-\s*', '', title)
        title = re.sub(r'[\s][\(\[][^\x00-\x7F]+.*[\)\]]', '', title)
        title = utils.format_filename(title)

        # create lyrics file
        file_name = f'{number:02d} - {title}.txt'
        zip_file.writestr(file_name, lyrics)

    zip_file.close()
    bio.seek(0)
    return bio


# driver code
def test(json_file, lyrics_language, include_annotations):
    with open(json_file) as f:
        data = json.load(f)
    user_data = {
        'lyrics_lang': lyrics_language,
        'include_annotations': include_annotations
    }
    file = create_zip(data, user_data)
    with open('test.zip', 'wb') as f:
        f.write(file.getvalue())


# test('hotel diablo.json', 'English + Non-English', True)
