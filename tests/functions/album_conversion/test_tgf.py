import re
from unittest.mock import MagicMock, patch

import pytest

from geniust.functions import album_conversion


users = [{'lyrics_lang': 'English',
          'include_annotations': True},
         {'lyrics_lang': 'Non-English',
          'include_annotations': False}
         ]


@pytest.mark.parametrize('user_data', users)
def test_create_album_songs(full_album, user_data):
    account = MagicMock()
    account.create_page.return_value = {'path': 'test'}

    with patch('telegraph.Telegraph', account):
        res = album_conversion.tgf.create_album_songs(account,
                                                      full_album,
                                                      user_data)

    assert account.create_page.call_count == 14
    assert isinstance(res, list)
    assert len(res) == len(full_album['tracks'])

    include_annotations = user_data['include_annotations']
    for i, song in enumerate(account.create_page.call_args_list):
        lyrics = song[1]['html_content']

        lyrics = lyrics[lyrics.find('<aside>'):]
        annotations_count = re.findall("<blockquote>", lyrics)

        if include_annotations:
            assert len(annotations_count) == len(full_album['tracks'][i]
                                                 ['song']['annotations'])
        else:
            annotations_count == 0


@pytest.mark.parametrize('user_data', users)
def test_create_pages(full_album, user_data):
    account = MagicMock()
    account().create_page.return_value = {'path': 'test'}

    with patch('telegraph.api.Telegraph', account):
        res = album_conversion.create_pages(full_album,
                                            user_data)

    assert isinstance(res, str)

    account = account()

    # create pages called for each song and finally for the album page
    assert account.create_page.call_count == len(full_album['tracks']) + 1

    album_page = account.create_page.call_args[1]['html_content']
    assert album_page.count('https://telegra.ph/test') == len(full_album['tracks'])
